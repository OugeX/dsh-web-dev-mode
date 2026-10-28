---
name: media-file-management
description: 前后端分离下的图片与文件资源管理规范。包含统一上传接口与文件表设计（SHA-256 秒传去重）、数据库只存 file_id 不存 URL、三种鉴权模式（公开读/登录可读/私有签名）及选择标准、头像这类多端共享资源为何应公开读、取图接口与 CDN、前端禁止本地留存的规范、上传安全红线（magic number 校验/UUID 命名/禁用 SVG）、图片压缩与缩略图、孤儿文件清理、本地到 OSS 的演进。当实现头像上传、附件管理、图片展示、文件鉴权、或发现同一文件存在多份副本时使用。
---

# 定位：单一真相，多端消费

**一个文件只有一份物理存储、一条数据库记录、一个 file_id。**
用户端、后台端、小程序端拿到的都是同一个 `file_id`，因此**不存在"更新后不同步"的可能**。

---

## 一、agent 的典型错误（先认出病症）

| 错误做法 | 后果 |
|---|---|
| 前端上传后存 localStorage / IndexedDB / 前端 static 目录 | 多份副本，改动不同步，无法鉴权 |
| 用户端和后台端各有一个 upload 接口，落到不同目录 | 同一张头像两个物理文件 |
| 数据库存完整 URL（`avatar_url VARCHAR(512)`） | 换 CDN / 换域名要全表 UPDATE |
| 后台管理端直接引用用户端服务器的静态路径 | 跨端耦合，一端下线全挂 |
| 上传后不记录归属，只把文件丢进目录 | 无法清理、无法鉴权、无法追踪 |

**根因**：没把文件当"后端资源"，而是当前端的附属物。

---

## 二、核心架构

```
用户端 ─┐
后台端 ─┼─→ POST /api/files（唯一上传接口）─→ 对象存储（唯一物理存储）
小程序 ─┘                │
                        ↓
                   files 表（唯一记录，返回 file_id）
                        │
        ┌───────────────┼───────────────┐
        ↓               ↓               ↓
   用户端展示       后台端展示       小程序展示
   （同一个 id、同一个 URL）
```

**四条铁律**：
1. **只有一个上传接口**，所有端都调用它
2. **只有一处物理存储**（本地目录或 OSS，通过抽象切换）
3. **数据库只存 `file_id`**，不存 URL、不存路径
4. **各端只存 `file_id`**，不缓存文件本体

---

## 三、文件表设计（含秒传与去重）

```sql
CREATE TABLE files (
  id            BIGINT       PRIMARY KEY AUTO_INCREMENT,
  hash          CHAR(64)     NOT NULL COMMENT '文件内容 SHA-256',
  size          BIGINT       NOT NULL COMMENT '字节数',
  storage       VARCHAR(16)  NOT NULL DEFAULT 'local' COMMENT 'local/oss/s3',
  bucket        VARCHAR(64)  NOT NULL DEFAULT '',
  object_key    VARCHAR(512) NOT NULL COMMENT '存储键，如 avatar/2026/10/{uuid}.jpg',
  original_name VARCHAR(255) NOT NULL,
  mime          VARCHAR(128) NOT NULL,
  ext           VARCHAR(16)  NOT NULL,
  width         INT          NULL COMMENT '图片宽',
  height        INT          NULL COMMENT '图片高',
  biz_type      VARCHAR(32)  NOT NULL COMMENT 'avatar/order_attachment/id_card',
  uploader_id   BIGINT       NOT NULL,
  is_public     TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '1=公开读',
  status        TINYINT      NOT NULL DEFAULT 1 COMMENT '1正常 0已删除',
  ref_count     INT          NOT NULL DEFAULT 0 COMMENT '被业务表引用次数（可选）',
  created_at    DATETIME     NOT NULL,
  UNIQUE KEY uk_hash_size (hash, size),      -- 秒传与去重的核心
  KEY idx_uploader (uploader_id, created_at),
  KEY idx_biz (biz_type, created_at),
  KEY idx_orphan (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文件资源';
```

### `uk_hash_size` 是「存量好几份」的直接解药

```
上传 → 算 SHA-256 → 查 uk_hash_size
  ├ 命中：直接返回已有 file_id，**不落盘、不建新记录**
  └ 未命中：落盘 + 插入记录 + 返回新 id
```

同一张头像被用户端传一次、后台端再传一次，**数据库里始终只有一条记录、磁盘上只有一个文件**。

### 业务表只存 id

```sql
-- ❌ 错
users.avatar_url VARCHAR(512)

-- ✅ 对
users.avatar_file_id BIGINT NULL COMMENT '引用 files.id'
orders.attachment_ids JSON NULL COMMENT '[1,5,9]'  -- 多个附件
```

**为什么不能存 URL**：换 CDN、换域名、加签名参数、冷热分层迁移，每一种都会让全表 URL 失效。`file_id` 永不变。

---

## 四、鉴权：三种模式，必须明确选一个

| 模式 | 适用资源 | 实现 | 性能 |
|---|---|---|---|
| **公开读** | 头像、商品图、banner、文章配图 | 直接给 CDN/静态 URL，不校验 | 最好，可缓存 |
| **登录可读** | 后台附件、订单凭证、报表导出 | 校验 token 后 302 到实际地址，或发短时签名 URL | 中 |
| **私有** | 身份证、合同、病历 | 签名 URL，有效期 5–15 分钟 | 最重，不可缓存 |

### 头像是哪一种？——**公开读**

判断依据：**这张图要给"多个不同身份的人"看吗？**

- 头像要给**后台管理员**看、给**其他用户**看 → 必须公开读
- 如果头像是私有的，列表页 20 条记录 = 20 次鉴权请求 → 性能灾难

**安全替代方案**：`object_key` 用不可猜的 UUID。

```
avatar/2026/10/7f3a9c21-4e8b-4d2f-9a11-8c5e6b2d1f03.jpg
```

URL 不可枚举，比"每张图都鉴权"实用得多。**可猜的路径 + 鉴权**不如**不可猜的路径 + 公开**。

### 私有资源的签名 URL

```
GET /api/files/{id}/url
  ① 校验当前用户对该文件有权限
  ② 生成带过期的签名地址
  → { url: "https://cdn/xxx.jpg?Expires=...&Signature=...", expiresIn: 900 }
```

**不要用后端代理文件流**（`c.File(path)` / `io.Copy`）——图片流量会全压在应用服务器上，一个下载就把你的 Go 进程打满。

---

## 五、接口规范

```
POST   /api/files              上传，multipart/form-data，返回 { id, url, width, height }
GET    /api/files/{id}         取文件：302 到存储地址（或直接返回签名 URL）
GET    /api/files/{id}/detail  取元信息（不返回二进制）
DELETE /api/files/{id}         软删（status=0），不物理删除
```

**上传响应统一**：

```json
{ "code": 0, "msg": "ok",
  "data": { "id": 1024, "url": "https://cdn/avatar/2026/10/xxx.jpg",
            "width": 400, "height": 400, "size": 38210 } }
```

前端拿到 `id` 存业务表，拿到 `url` 用于即时预览。**`url` 是快照，下次刷新应该重新从 `id` 取。**

### 秒传预检（可选，大文件时）

```
POST /api/files/check   { hash, size }
→ { exists: true, id: 1024 }   // 已存在，直接复用
→ { exists: false }            // 继续上传
```

---

## 六、前端规范（这里是 agent 最爱犯错的地方）

### 禁止

- ❌ 把文件内容存 localStorage / IndexedDB / sessionStorage
- ❌ 上传后把文件拷到前端 `public/` 或 `assets/` 目录
- ❌ 在前端维护一份"文件列表"，与后端不同步
- ❌ 用户端和后台端各写一个上传函数、各调一个接口

### 正确

- ✅ 所有端共用同一个 `uploadFile()` 封装（在 `api/file.ts`）
- ✅ 业务对象只持 `fileId`，展示时用后端返回的 `url`
- ✅ 头像更新后只需 `invalidateQueries(['user', userId])`，各端自然拿到新图
- ✅ 上传中显示进度，成功后立刻用返回的 `url` 预览（避免等下一次请求）

```ts
// api/file.ts —— 唯一上传入口
export async function uploadFile(file: File, bizType: string) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('bizType', bizType)
  return client.post('/files', fd).then(r => r.data)  // { id, url, ... }
}
```

**为什么前端不留存**：文件本体在前端留存后，无法鉴权、无法压缩、无法追溯、无法保证一致性。**前端缓存 URL 可以，缓存文件不行。**

---

## 七、上传安全红线

| # | 必须做 | 为什么 |
|---|---|---|
| 1 | **读文件头 magic number 校验类型** | `Content-Type` 和扩展名都能伪造 |
| 2 | **文件名用 UUID，绝不用用户提供的名字** | 原名可含 `../` 路径穿越、可含 XSS |
| 3 | **类型白名单**：jpg/png/webp/gif | 不白名单就等于允许上传任意文件 |
| 4 | **大小限制**（头像 2MB，附件 10MB） | 防存储打满 |
| 5 | **落盘目录不可执行** | 上传目录配 `php_admin_value engine off` / Nginx 禁 `*.php` |
| 6 | **禁用或净化 SVG** | SVG 内含 `<script>`，是完整的 XSS 载体 |
| 7 | **剥离 EXIF** | 手机照片带 GPS 坐标，泄漏位置 |
| 8 | **图片重新编码而非原样保存** | 能洗掉藏在图片里的恶意负载 |

```go
// magic number 校验（不要信 Content-Type）
func detectImageType(f io.Reader) (string, error) {
    buf := make([]byte, 512)
    n, _ := io.ReadFull(f, buf)
    return http.DetectContentType(buf[:n]), nil   // 返回 image/jpeg 等
}
```

**「重新编码」是最强的一招**：`image.Decode` 再 `jpeg.Encode`，恶意负载在解码时就被丢弃了。

---

## 八、图片处理流程

```
上传 → 校验 magic number → 限大小 → 解码 → 剥离 EXIF
     → 原图（可选） + 缩略图（列表用） + 水印（可选）
     → 计算 hash → 去重 → 落盘 → 入库
```

| 产物 | 用途 | 尺寸 |
|---|---|---|
| 原图 | 详情页、下载 | 保留 |
| 缩略图 | 列表、头像 | 200×200（头像）、400×400（列表） |
| 中图 | 卡片、预览 | 800×800 |

**列表页永远用缩略图**。用原图渲染 20 个头像 = 拉 20 张 3MB 的图。

库：`github.com/disintegration/imaging`（简单够用）、`github.com/bimg`（依赖 libvips，快但装起来麻烦）。

---

## 九、孤儿文件清理

文件软删后不会自动消失，业务表改引用也留下旧文件。定时任务每天跑：

```sql
-- 找出 30 天前创建、status=1、且没有被任何业务表引用的文件
SELECT f.id, f.object_key FROM files f
 WHERE f.created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
   AND f.status = 1
   AND NOT EXISTS (SELECT 1 FROM users   u WHERE u.avatar_file_id = f.id)
   AND NOT EXISTS (SELECT 1 FROM orders  o WHERE JSON_CONTAINS(o.attachment_ids, CAST(f.id AS JSON)))
   -- ... 其他引用表
```

**判定为孤儿的处理**：先 `status=0`，再过 30 天物理删除（留一个反悔窗口）。

**不要在上传时就删旧文件**。用户可能刚改完又改回来，旧文件可能还被缓存引用。

---

## 十、存储演进（设计成可切换）

```go
type Storage interface {
    Put(ctx context.Context, key string, r io.Reader, size int64, mime string) error
    Get(ctx context.Context, key string) (io.ReadCloser, error)
    Delete(ctx context.Context, key string) error
    URL(key string, expire time.Duration) string   // 公开资源返回永久 URL，私有返回签名 URL
}
```

| 阶段 | 实现 | 时机 |
|---|---|---|
| **1. 本地磁盘** | `LocalStorage`，`./storage/uploads/`，Nginx 静态托管 | 起步就用这个，一人项目足够 |
| **2. 对象存储** | `OSSStorage`（阿里云 OSS / 腾讯 COS） | 多机部署、需要 CDN 时 |
| **3. 直传** | 后端只发签名，前端直传 OSS + 回调确认 | 大文件多、并发高时 |

**用 interface 抽象，换存储只加一个实现，业务代码不动。**

### 上传方式对比

| 方式 | 说明 | 适用 |
|---|---|---|
| **中转**（前端 → 后端 → 存储） | 简单，可做校验/压缩 | 一人项目首选，≤10MB |
| **直传**（前端 → OSS，后端发签名） | 不占应用带宽，需回调确认 | 大文件、高并发 |

---

## 十一、纯本地存储方案（不用 OSS）

### 11.1 先判断：你到底需不需要 OSS

| 场景 | 结论 |
|---|---|
| 单机部署、日活 < 5000 | **本地完全够，不要上 OSS** |
| 要多机负载均衡 / 水平扩容 | 必须 OSS 或共享存储（见 11.9） |
| 需要 CDN 加速、跨地域访问 | 上 OSS + CDN |
| 有异地容灾的合规要求 | OSS，或自建双机备份 |

**不要为了"以后可能扩容"提前上 OSS。** 只要 `files` 表和 `Storage` interface 设计对了，以后迁移是一次脚本的事。

### 11.2 目录布局（按年月分，公开私有分离）

```
/data/app/storage/
├── public/                          ← 公开资源，Nginx 直接托管
│   ├── avatar/2026/10/{uuid}.jpg
│   ├── avatar/2026/10/{uuid}_200.jpg    缩略图
│   ├── avatar/2026/10/{uuid}_400.jpg
│   └── product/2026/10/{uuid}.jpg
└── private/                         ← 私有资源，走 X-Accel-Redirect
    ├── idcard/2026/10/{uuid}.jpg
    └── contract/2026/10/{uuid}.pdf
```

**两个必须**：

1. **按 `年/月` 分目录**。单目录文件数超过 1 万，`ls`、备份、ext4 目录查找都会明显变慢。这是硬要求。
2. **公开与私有物理隔离**。私有目录在 Nginx 侧配 `internal`，外部根本访问不到。混在一起迟早出事。

### 11.3 文件位置：不要放在项目目录里

```
❌ /var/www/myapp/uploads/         部署打包会覆盖、git 可能误提交、权限混乱
✅ /data/app/storage/              项目外，独立备份，独立磁盘配额
```

配置里用 `STORAGE_ROOT=/data/app/storage`，代码只认这个变量。

### 11.4 公开资源：Nginx 直接托管

```nginx
# 公开文件：直接静态托管，不经过 Go
location /uploads/ {
    alias /data/app/storage/public/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    access_log off;                 # 图片访问日志很吵，关掉
    try_files $uri =404;
}
```

**要点**：
- `expires 30d` + `immutable`：URL 带 UUID，内容永不变，可长期缓存
- `try_files $uri =404`：防止目录遍历
- 关闭 access_log：图片请求量是页面的 10–20 倍，日志会撑爆磁盘

数据库里存的 `object_key` 就是 `avatar/2026/10/xxx.jpg`，拼成 `/uploads/` + key 即为访问地址。

### 11.5 私有资源：X-Accel-Redirect（本地鉴权的正确姿势）

**不要用 Go 直接读文件返回**（`c.File()` / `io.Copy`）——每个下载占一个 goroutine 和一份内存缓冲，10 个人同时下 20MB 文件就把进程拖死。

正确做法：**鉴权在 Go，传输交给 Nginx**。

```go
// GET /api/files/:id —— 私有文件
func (h *FileHandler) Serve(c *gin.Context) {
    id := parseID(c)

    f, err := h.svc.Get(c.Request.Context(), id)
    if err != nil { response.NotFound(c, "文件不存在"); return }

    // ① 鉴权在这里做（可查归属、查角色、查共享关系）
    if !h.svc.CanAccess(c.Request.Context(), currentUser(c), f) {
        response.Forbidden(c, "无权访问"); return
    }

    // ② 交给 Nginx 传输 —— 零拷贝，不占 Go 进程
    c.Header("X-Accel-Redirect", "/__protected/"+f.ObjectKey)
    c.Header("Content-Type", f.Mime)
    c.Header("Content-Disposition", "inline")
    c.Status(http.StatusOK)                     // 空 body，Nginx 接手
}
```

```nginx
# 私有文件：internal 表示只能被内部重定向访问，外部直连 404
location /__protected/ {
    internal;
    alias /data/app/storage/private/;
}
```

| 维度 | Go 直出 | X-Accel-Redirect |
|---|---|---|
| 鉴权灵活性 | 高 | 高（一样在 Go 里） |
| 传输开销 | 占 goroutine + 内存 | Nginx sendfile，零拷贝 |
| Range 请求（断点续传/视频拖动） | 要自己实现 | Nginx 原生支持 |
| 大文件 | 容易 OOM | 无压力 |

**这是本地存储做私有资源的唯一正确方案。** 没有 OSS 的签名 URL，就用它。

### 11.6 LocalStorage 实现

```go
type LocalStorage struct {
    root   string // /data/app/storage
    domain string // https://example.com
}

func (s *LocalStorage) Put(ctx context.Context, key string, r io.Reader, size int64, mime string) error {
    full := filepath.Join(s.root, key)
    if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
        return err
    }
    // 先写临时文件再 rename，避免半截文件被读到
    tmp := full + ".tmp"
    f, err := os.Create(tmp)
    if err != nil { return err }
    defer os.Remove(tmp)

    if _, err := io.Copy(f, r); err != nil { f.Close(); return err }
    if err := f.Close(); err != nil { return err }
    return os.Rename(tmp, full)          // 原子替换
}

// URL 只对公开资源有意义；私有资源返回空，由 handler 做 X-Accel-Redirect
func (s *LocalStorage) URL(key string, public bool) string {
    if public { return s.domain + "/uploads/" + key }
    return ""
}
```

**`先写 .tmp 再 rename` 很重要**：直接写目标文件时，进程中途崩溃会留下半截文件，而数据库记录可能已经写入 —— 用户看到损坏的图。

### 11.7 备份（本地存储必须自己做）

```bash
#!/usr/bin/env bash
# 每天 03:30
set -e
D=$(date +%F)

rsync -a /data/app/storage/ /backup/storage/          # 文件
mysqldump --single-transaction --routines --triggers mydb | gzip > /backup/db-$D.sql.gz
find /backup -name 'db-*.sql.gz' -mtime +14 -delete    # 保留 14 天
```

**文件和数据库必须一起备份，且用同一时间点。** 只有文件 → 不知道文件属于谁；只有数据库 → 全是断链；时间点不一致 → "数据库有记录但文件已被删"的错配。

**备份到另一块物理盘**，同一块盘坏了两个一起没。

### 11.8 从本地迁移到 OSS（设计对了就很简单）

因为 `files.storage` 字段已预留 `local/oss`，可以**逐步切换**：

```go
func (s *FileService) URL(f *model.File) string {
    switch f.Storage {
    case "oss": return s.oss.URL(f.ObjectKey, f.IsPublic == 1)
    default:    return s.local.URL(f.ObjectKey, f.IsPublic == 1)
    }
}
```

迁移步骤：
1. 写 `OSSStorage` 实现
2. 跑脚本：遍历 `files` 表，上传本地文件到 OSS，更新 `storage='oss'` 与 `object_key`
3. 新上传直接走 OSS
4. 旧文件按 `storage` 字段继续从本地读，直到全部迁完
5. 迁完后本地目录留作冷备

**前提**：从第一天起 `files.storage` 就必须存在且默认 `'local'`。加这个字段成本是 0，省掉的是未来一次"全站改 URL"的灾难。

### 11.9 什么时候本地存储一定会崩

**只有一个场景：多台应用服务器。**

```
用户上传 → 打到 A 机器 → 文件存在 A 的本地盘
用户刷新 → 负载均衡打到 B 机器 → 404
```

| 方案 | 代价 | 说明 |
|---|---|---|
| **单机部署** | 0 | 一人项目首选，没有这个问题 |
| NFS / 共享块存储 | 中 | 有单点故障，性能受网络影响 |
| rsync 定时同步 | 中低 | 有延迟和冲突，只适合只读场景 |
| **上 OSS** | 低（迁移后） | 真正的解法 |

**判断信号**：只要出现"两台以上的应用服务器"，就必须换。在这之前，本地存储没有任何问题。

### 11.10 反面清单

1. ❌ 上传目录放在项目代码目录里（部署即丢）
2. ❌ 所有文件放同一个目录（文件数上万后 io 变慢）
3. ❌ 公开和私有文件混在一个目录
4. ❌ 用 Go `c.File()` 直出大文件
5. ❌ 直接写目标文件不做 tmp+rename
6. ❌ Nginx 的 `internal` 没配，私有文件能被直连
7. ❌ 图片访问日志没关，磁盘被日志撑爆
8. ❌ 只备份数据库不备份文件（或反之）
9. ❌ 备份放在同一块物理盘
10. ❌ 一开始不给 `files.storage` 字段，迁移时全站改 URL

---

## 十二、验收清单

- [ ] 全站只有一个上传接口 `POST /api/files`
- [ ] 用户端与后台端调用的是同一个接口
- [ ] 数据库存 `file_id` 而不是 URL
- [ ] `files` 表有 `uk_hash_size`，重复上传返回同一个 id
- [ ] 头像 / 商品图是 `is_public=1`，走公开 URL
- [ ] 私有资源走签名 URL，有效期 ≤ 15 分钟
- [ ] `object_key` 是 UUID，不可枚举
- [ ] 上传校验的是 magic number 而非 `Content-Type`
- [ ] 落盘文件名与用户提供的名字无关
- [ ] 上传目录不可执行
- [ ] SVG 已禁用或净化
- [ ] 图片已剥离 EXIF
- [ ] 列表页用缩略图而非原图
- [ ] 前端没有任何一处缓存文件本体
- [ ] 同一张图在用户端和后台端显示的是同一个 URL
- [ ] 更新头像后，后台端刷新即看到新图（不需要任何同步逻辑）
- [ ] 有孤儿文件清理任务

---

### 本地存储（不用 OSS 时）

- [ ] 存储根目录在项目代码目录之外（如 `/data/app/storage`）
- [ ] 按 `年/月` 分目录
- [ ] `public/` 与 `private/` 物理隔离
- [ ] 公开文件由 Nginx `alias` 直接托管，带 `expires` + `immutable`
- [ ] 私有文件走 `X-Accel-Redirect`，Nginx 对应 location 配了 `internal`
- [ ] 没有用 Go `c.File()` 直出大文件
- [ ] `Put` 先写 `.tmp` 再 `rename`
- [ ] 图片目录的 `access_log` 已关闭
- [ ] 备份脚本同时包含文件与数据库，且在同一时间点
- [ ] 备份存放在另一块物理盘
- [ ] `files.storage` 字段存在，默认 `'local'`

---

## 十三、反面清单

1. ❌ 前端本地存一份文件副本
2. ❌ 用户端和后台端各有一个上传接口
3. ❌ 数据库存完整 URL
4. ❌ 头像走鉴权读（列表页 20 张图 = 20 次鉴权）
5. ❌ `object_key` 用自增 id 或原始文件名（可枚举/可穿越）
6. ❌ 相信 `Content-Type`
7. ❌ 后端代理文件流（图片流量压垮应用服务器）
8. ❌ 上传时立即删除旧文件
9. ❌ 允许 SVG 上传且不净化
10. ❌ 列表页直接用原图
