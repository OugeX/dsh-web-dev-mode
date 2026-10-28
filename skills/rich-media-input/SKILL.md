---
name: rich-media-input
description: 富文本编辑器与文件上传的交互规范。包含富文本该不该用的判断、工具栏只给必要按钮、从 Word/网页粘贴的清洗、编辑器内图片上传与回显、文件上传的三种触发（点击/拖拽/粘贴）、上传队列与并发数、进度与失败重试与取消、大文件分片与断点续传、类型大小数量限制的提示时机、文件列表与预览、删除与替换。当要加富文本编辑、评论区、商品描述、或实现文件上传（附件、图片批量、大文件）时使用。
---

# 定位：富文本越少越好，上传越透明越好

---

## 一、富文本：先问该不该用

### 1.1 决策

| 场景 | 方案 |
|---|---|
| 商品描述、文章正文、协议条款 | **富文本** |
| 评论、反馈、备注 | **纯文本 textarea**（最多支持换行） |
| 结构化内容（标题/段落/图片分开存） | **分字段的表单**，不用富文本 |

**判断标准**：用户需要**控制排版**吗？

- 需要（加粗、列表、插图、链接）→ 富文本
- 不需要（就是一段话）→ textarea

**默认给 textarea。** 富文本的复杂度（工具栏、粘贴清洗、HTML 安全）是纯文本的十倍。

### 1.2 工具栏：只给必要的按钮

```
最小集（推荐）：加粗 / 斜体 / 有序列表 / 无序列表 / 链接 / 图片 / 清除格式
中等集：+ 标题（H2/H3）/ 引用 / 分割线
```

**不要全开**：字号、字体、颜色、对齐、缩进这些按钮 90% 的用户不会用，只会把内容排乱。

**不要给**：
- 字体选择（后台系统里应统一字体）
- 字号（用标题层级代替）
- 文字颜色（会破坏主题一致性）
- HTML 源码视图（除非给高级用户）

### 1.3 从 Word / 网页粘贴（最大的坑）

用户从 Word 粘贴，会带进一堆 `<span style="font-family:宋体;font-size:10.5pt">` 以及 `mso-*` 属性。

**必须清洗**：

```ts
// 方案 A：编辑器自带（推荐）
// TinyMCE 的 paste_as_text / powerpaste 插件
// wangEditor 的 pasteFilter
// TipTap 的 paste handler

// 方案 B：手写白名单
const ALLOWED_TAGS = ['p','br','strong','em','ul','ol','li','a','h2','h3','blockquote','img']
const ALLOWED_ATTR = { a: ['href','target'], img: ['src','alt','width','height'] }
// 用 DOMPurify 白名单清洗
import DOMPurify from 'dompurify'
const clean = DOMPurify.sanitize(dirty, { ALLOWED_TAGS, ALLOWED_ATTR })
```

**白名单，不要黑名单**——黑名单永远漏。

### 1.4 编辑器内的图片

- 插入图片 = **走统一上传接口**（见 `media-file-management`），拿到 `file_id` 和 URL
- 编辑器里存 `<img src="url" data-file-id="123">`
- **不要把 base64 塞进 HTML**（内容会膨胀几十倍，且无法走 CDN）
- 粘贴截图也要走上传（监听 `paste` 事件，提取 `clipboardData.files`）

### 1.5 内容安全（XSS）

**渲染用户富文本时必须清洗**，编辑时干净不代表存储时干净（有人直接调接口）。

```tsx
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(content) }} />
```

**不要信任前端清洗**——后端也要清一遍。

---

## 二、文件上传

### 2.1 三种触发方式，都要支持

| 方式 | 实现 | 注意 |
|---|---|---|
| **点击** | `<input type="file">`（隐藏） | 必须支持 `multiple` |
| **拖拽** | `dragover` / `drop` 事件 | 要 `preventDefault()`，否则浏览器会打开文件 |
| **粘贴** | `paste` 事件，取 `clipboardData.files` | 截图粘贴是最常用的 |

```tsx
// 拖拽要有视觉反馈
<div
  onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
  onDragLeave={() => setDragging(false)}
  onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
  className={dragging ? 'dropzone dropzone-active' : 'dropzone'}
/>
```

**拖拽时的视觉反馈必须有**（边框变主色 + 背景变色），否则用户不知道能不能放。

### 2.2 上传队列

**不要一次并发全部上传**——20 个文件同时发会把浏览器连接数占满，页面卡住。

```ts
const CONCURRENCY = 3
// 用法：p-limit
import pLimit from 'p-limit'
const limit = pLimit(CONCURRENCY)
const results = await Promise.all(
  files.map(f => limit(() => uploadOne(f)))
)
```

**并发数 3**（浏览器同域通常允许 6 个连接，留一半给其他请求）。

### 2.3 进度与状态

每个文件都有独立状态：

```ts
type UploadItem = {
  uid: string
  file: File
  status: 'pending' | 'uploading' | 'success' | 'error' | 'canceled'
  progress: number      // 0-100
  fileId?: number       // 成功后的服务端 id
  error?: string
}
```

**展示规则**：

| 状态 | 展示 |
|---|---|
| pending | 文件名 + 「等待中」 |
| uploading | 文件名 + **进度条** + 百分比 + 取消按钮 |
| success | 文件名 + 绿色对勾 + 预览/下载 |
| error | 文件名 + 红色 + **错误原因** + 「重试」 |
| canceled | 灰色 + 「已取消」 |

**进度用 `onUploadProgress`**（axios 支持），不要用假进度条。

### 2.4 失败与重试

- **失败要说清原因**：「文件超过 10MB」「不支持 .exe 类型」「网络中断」
- **单条重试**，不要"全部重试"（已成功的会重复上传）
- **自动重试 1 次**（网络抖动），之后手动
- 失败的项**不删除**，留在列表里让用户重试或移除

### 2.5 取消上传

```ts
const controller = new AbortController()
axios.post('/api/files', formData, {
  signal: controller.signal,
  onUploadProgress: (e) => setProgress(Math.round(e.loaded / e.total! * 100)),
})
// 取消
controller.abort()
```

取消后状态置为 `canceled`，**不占队列**。

### 2.6 限制与提示时机

| 限制 | 提示时机 |
|---|---|
| 类型 | **选择时立即拦**（不发请求） |
| 大小 | **选择时立即拦** |
| 数量 | 选择时拦，提示「最多 9 个」 |

```ts
// 在 handleFiles 入口统一校验，不要等到上传失败才知道
const invalid = files.filter(f => f.size > MAX_SIZE)
if (invalid.length) {
  message.error(`${invalid[0].name} 超过 ${MAX_SIZE / 1024 / 1024}MB`)
  return
}
```

**提示要具体**：「不支持 .exe 类型」比「文件类型错误」有用。

### 2.7 大文件分片与断点续传

| 文件大小 | 方案 |
|---|---|
| < 10MB | 直接上传 |
| 10–100MB | 分片（2MB/片）+ 并发 3 |
| > 100MB | 分片 + 断点续传 + 秒传预检 |

**分片流程**：

```
① POST /api/files/init   { hash, size, name }  → 返回 uploadId、已上传分片索引
② PUT  /api/files/{uploadId}/chunk/{index}      → 并发上传缺失分片
③ POST /api/files/{uploadId}/complete           → 服务端合并、校验 hash
```

**`hash` 用 SHA-256 或 md5**，用于秒传（服务端已有同 hash 文件直接返回）和完整性校验。

**断点续传**：初始化时返回已上传的分片索引，只传缺的。刷新页面后凭 `uploadId` 继续。

### 2.8 文件列表

| 场景 | 展示 |
|---|---|
| 图片 | **缩略图网格**（120×120，圆角），悬停显示删除与预览 |
| 文档（PDF/Word） | 图标 + 文件名 + 大小 + 下载/删除 |
| 混合 | 统一列表，图片行内给小缩略图 |

**必须有**：预览（图片灯箱 / PDF 内嵌）、删除（二次确认）、下载。

**文件名过长**：中间省略 `very-long-fil...name.pdf`，hover 显示全名。

### 2.9 替换 vs 删除重传

单个文件位（如头像、封面）应该是**替换语义**：

```tsx
// 点击已上传的图片 → 重新选择 → 替换，不是"删除再加一个"
<Uploader value={avatarId} onChange={setAvatarId} max={1} />
```

**替换后旧文件由后端软删**（见 `media-file-management` 的孤儿清理），前端不管。

---

## 三、验收清单

### 富文本

- [ ] 确认真的需要富文本（不是能改用 textarea）
- [ ] 工具栏只保留必要按钮，无字体/字号/颜色
- [ ] Word/网页粘贴经过白名单清洗
- [ ] 编辑器内图片走统一上传接口，不存 base64
- [ ] 渲染时用 DOMPurify 清洗
- [ ] 后端也做了清洗

### 文件上传

- [ ] 支持点击、拖拽、粘贴三种方式
- [ ] 拖拽时有视觉反馈
- [ ] 并发数限制为 3
- [ ] 每个文件有独立进度与状态
- [ ] 进度是真实 `onUploadProgress`，不是假进度
- [ ] 失败显示具体原因 + 单条重试
- [ ] 可取消上传
- [ ] 类型/大小/数量在选择时即校验，不是上传后
- [ ] > 10MB 有分片方案
- [ ] > 100MB 有断点续传与秒传
- [ ] 图片显示缩略图，文档显示图标
- [ ] 文件名过长中间省略 + hover 全名
- [ ] 单文件位是替换语义

---

## 四、反面清单

1. ❌ 评论框用富文本
2. ❌ 工具栏全开（字体/字号/颜色）
3. ❌ 粘贴不清洗，脏 HTML 入库
4. ❌ 图片以 base64 塞进富文本
5. ❌ 渲染时不 sanitize（XSS）
6. ❌ 20 个文件同时上传
7. ❌ 用定时器造假进度条
8. ❌ 只提供一个「全部重试」按钮
9. ❌ 选完文件上传到一半才提示"超过大小"
10. ❌ 大文件不分片（10 分钟内必超时）
11. ❌ 文件名不做省略，撑破布局
12. ❌ 头像上传做成"删除 + 新增"而不是替换
