---
name: api-contract-design
description: 前后端职责划分与接口契约设计规范。包含增删改查各自归属（前端校验是体验、后端校验是安全）、列表/详情/表单三套 DTO 视图模型、字段脱敏与字段级权限分级（禁止前端做脱敏）、公共配置与登录后配置与私有配置的三层划分与缓存策略、批量操作单接口、前端不该做的六件事、后端不该做的三件事、接口清单模板。当设计 CRUD 接口、决定哪些字段返回给前端、处理手机号身份证等敏感字段脱敏、或发现前端拉全量数据自己计算时使用。
---

# 定位：接口返回视图，不是表

**核心判断**：
> 前端组件的 props 来自哪个接口，那个接口就**只**返回这个组件需要的字段。
> 两个页面要的字段差很多 → 就该是两个接口（或一个接口带 `view` 参数），不是返回整条记录让前端自己挑。

---

## 一、增删改查各管什么

| 操作 | 前端做 | 后端做 |
|---|---|---|
| **列表** | 传分页/筛选/排序参数；渲染；**三态**（加载/空/错误）；URL 同步 | 查询、排序、分页、**字段裁剪**、按权限过滤行 |
| **详情** | 传 id；渲染；按权限隐藏按钮 | 查单条、**脱敏**、校验"能不能看这一条" |
| **新建** | 表单**格式**校验（必填/长度/格式）；提交；防重复点击 | **业务**校验（唯一性/状态/额度）、权限、写库、审计 |
| **编辑** | 回填；格式校验；只提交**可写字段** | 同新建 + 版本号/乐观锁 + 检查字段是否允许改 |
| **删除** | 二次确认；调接口；刷新列表 | 权限、软删、**级联检查**、审计 |

### 最重要的一条

> **前端校验是体验，后端校验是安全。**
> 前端校验永远可以被绕过（改请求、直接 curl）。

所以分工是：

| 校验类型 | 谁做 | 例 |
|---|---|---|
| 格式校验 | **前端**（为了即时反馈）+ 后端 binding tag | 必填、长度、邮箱格式、数字范围 |
| **业务校验** | **只能后端** | 用户名唯一、状态机合法性、库存足够、余额不足、不能删有子记录的父对象 |
| 权限校验 | **只能后端** | 能不能看、能不能改、能改哪些字段 |

**agent 常犯的错**：前端 `if (form.status === 3) return` 就以为不能删了，后端不校验。这是漏洞。

---

## 二、三套 DTO（这是本节的核心）

以 `users` 表 30 个字段为例：

```
数据库 30 字段
├─ 列表视图   6 字段    id username nickname phone(脱敏) status createdAt
├─ 详情视图  15 字段    + email role avatarUrl lastLoginAt idCardNo(脱敏) ...
└─ 编辑表单   5 字段    nickname email role status（可写）
```

### 2.1 列表项（精简）

```go
type UserListItem struct {
    ID        uint   `json:"id"`
    Username  string `json:"username"`
    Nickname  string `json:"nickname"`
    Phone     string `json:"phone"`       // 已脱敏
    Status    int8   `json:"status"`
    CreatedAt string `json:"createdAt"`   // RFC3339
}
```

**列表页永远不带**：大字段（头像 base64、富文本）、敏感字段（密码、身份证完整值）、关联对象全量。

### 2.2 详情（完整但按权限脱敏）

```go
type UserDetail struct {
    UserListItem
    Email       string `json:"email"`
    Role        string `json:"role"`
    AvatarURL   string `json:"avatarUrl"`
    LastLoginAt string `json:"lastLoginAt"`
    IDCardNo    string `json:"idCardNo"`   // 按角色决定完整或脱敏
}
```

### 2.3 编辑请求（可写字段，与可读字段严格分离）

```go
type UserUpdateReq struct {
    Nickname string `json:"nickname" binding:"max=32"`
    Email    string `json:"email"    binding:"omitempty,email"`
    Role     string `json:"role"     binding:"omitempty,oneof=admin user"`
    Status   *int8  `json:"status"   binding:"omitempty,oneof=0 1"`
}
```

**为什么不能直接用 model 接请求**：
1. 前端可以传 `role: admin` 提权（**批量赋值漏洞**）
2. 前端可以传 `balance: 999999`
3. 前端可以传 `id` 覆盖别的记录

**可写字段清单必须显式枚举**，没在 DTO 里的字段前端传了也会被忽略。

### 2.4 三个 DTO 的实际收益

| 维度 | 返回整条 model | 三套 DTO |
|---|---|---|
| 列表传输量 | 30 字段 | 6 字段，**少 80%** |
| 敏感字段泄漏 | 密码哈希、身份证全在 | 只有脱敏值 |
| 前端演化 | 拿到一堆没用的字段，慢慢有人在组件里用上了 → 隐形耦合 | 加字段不破坏前端 |
| 权限控制 | 做不到字段级 | 按视图分发 |

---

## 三、脱敏：这是权限问题，不是技术问题

### 3.1 绝对禁止前端做脱敏

```tsx
// ❌ 掩耳盗铃：数据已经在浏览器里了
const masked = phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
```

打开 Network 面板，原始手机号一览无余。**脱敏必须后端做。**

### 3.2 标准脱敏规则

| 字段 | 规则 | 示例 |
|---|---|---|
| 手机号 | 前 3 + 后 4 | `138****8888` |
| 身份证 | 前 6 + 后 4 | `330102********1234` |
| 银行卡 | 后 4 | `**** **** **** 1234` |
| 姓名 | 保留姓 | `张**` |
| 邮箱 | @ 前首字符 | `z***@example.com` |
| 地址 | 到区级 | `浙江省杭州市西湖区****` |
| 密码 | **永不返回**（`json:"-"`） | — |
| 金额 | **不脱敏**（业务需要精确值） | — |

### 3.3 按角色分级（关键）

脱敏不是"永远脱敏"，而是**按当前用户对该字段的权限**决定：

| 角色 | 手机号 | 身份证 | 银行卡 |
|---|---|---|---|
| 超管 | 完整 | 完整 | 完整 |
| 运营 | 脱敏 | 脱敏 | 脱敏 |
| 用户本人 | 完整 | 脱敏 | 脱敏 |
| 用户看他人 | 脱敏/隐藏 | 隐藏 | 隐藏 |

```go
func MaskPhone(phone string, full bool) string {
    if full || len(phone) < 7 {
        return phone
    }
    return phone[:3] + "****" + phone[len(phone)-4:]
}

// 在 service 组装 DTO 时按角色决定
detail.Phone = MaskPhone(u.Phone, viewer.CanSeeFull("user.phone"))
```

**权限判定放在 service，不在 handler**——因为它是业务规则。

---

## 四、配置分三层，接口也要分三档

| 类型 | 内容 | 谁需要 | 接口 | 缓存 |
|---|---|---|---|---|
| **公共配置** | 站点名、logo、备案号、协议文本、城市列表、支付方式 | **所有人，含未登录** | `GET /api/config/public` | 长缓存 / CDN |
| **登录后配置** | 用户菜单、权限列表、个人偏好、主题 | 已登录用户 | `GET /api/config/me` | 短缓存，按用户 |
| **私有配置** | 敏感开关、内部参数、灰度策略 | 特定角色 | `GET /api/config/admin` | 不缓存 |

### 4.1 公共配置不要带 token

```go
// 路由分组：公开组不挂 JWT 中间件
public := r.Group("/api")
{
    public.GET("/config/public", h.Config.Public)   // 未登录也能取
    public.POST("/auth/login", h.Auth.Login)
}

authed := r.Group("/api", middleware.JWT())
{
    authed.GET("/config/me", h.Config.Me)          // 需要登录
    authed.GET("/users", h.User.List)
}
```

**agent 常犯的错**：把公共配置也挂在鉴权组里，导致登录页拿不到站点名和 logo。

### 4.2 什么该打包进前端，什么该走接口

| 内容 | 方式 | 理由 |
|---|---|---|
| 枚举字典（订单状态 → 文案/颜色） | **打包进前端** `constants/options.ts` | 与代码逻辑强绑定，改枚举必然要改代码 |
| 站点名 / logo / 备案号 | **接口** | 运营会改，不能每次都发版 |
| 功能开关 | **接口 + 短缓存（60s）** | 要能紧急关停 |
| 城市 / 行业等基础数据 | **接口 + 长缓存** | 数据量大且会增补 |
| 校验规则（正则、长度） | 两边各写一份（后端是权威） | 前端要即时反馈 |

### 4.3 私有配置的边界

```go
// ❌ 错：把内部参数返回给前端
type AdminConfig struct {
    DBHost     string `json:"dbHost"`      // 绝对不行
    SMTPPass   string `json:"smtpPass"`    // 绝对不行
    FeatureFlag bool  `json:"featureFlag"` // 可以
}
```

**私有配置里只返回"前端需要用来做 UI 决策"的开关**，不返回任何基础设施信息。

---

## 五、批量操作：一个接口，不是循环调用

```ts
// ❌ agent 常这么写：20 条删 20 次
for (const id of selectedIds) {
  await api.deleteUser(id)
}
```

问题：20 次网络往返、20 个事务、20 条审计、部分成功时状态不一致。

**正确**：

```
DELETE /api/users       body: { "ids": [1,2,3] }
→ { code:0, data: { success: [1,2], failed: [{id:3, reason:"有未完成订单"}] } }
```

```go
func (s *UserService) BatchDelete(ctx context.Context, ids []uint) (dto.BatchResult, error) {
    var res dto.BatchResult
    return res, s.tx.Transaction(ctx, func(tx *gorm.DB) error {
        for _, id := range ids {
            if err := s.deleteOne(tx, id); err != nil {
                res.Failed = append(res.Failed, dto.BatchFail{ID: id, Reason: err.Error()})
                continue                     // 单条失败不影响其他
            }
            res.Success = append(res.Success, id)
        }
        return nil                            // 全部失败也返回 200，明细在 data 里
    })
}
```

**设计要点**：
- 一次事务
- 返回成功/失败明细，让前端能精确提示
- 部分失败不回滚全部（除非业务要求原子性）
- 单次批量上限（如 200 条），超了拒绝

---

## 六、前端不该做的六件事

| # | 不该做 | 为什么 | 该怎么做 |
|---|---|---|---|
| 1 | **拉全量数据到前端算** | 1000 条订单在 JS 里 sum/filter，传输量和内存都爆 | 后端加统计接口 / 聚合字段 |
| 2 | **做脱敏** | 数据已到浏览器，Network 能看到 | 后端脱敏 |
| 3 | **做数据聚合（统计、分组）** | 同上 | 后端 SQL 聚合 |
| 4 | **自己拼状态文案和颜色** | 加一个状态要改十几处 | 后端返回 code，前端用 `constants/options` 映射 |
| 5 | **信任前端权限判断** | 隐藏按钮 ≠ 不能调接口 | 后端每个接口都校验权限 |
| 6 | **自己算金额/折扣/税费** | 浮点精度、规则变更 | 后端算，返回最终值 |

### 关于第 1 条（最高频）

```tsx
// ❌ 拉 1000 条到前端算
const { data } = useQuery(['orders'], () => api.listOrders({ pageSize: 1000 }))
const total = data.list.reduce((s, o) => s + o.amount, 0)

// ✅ 后端返回聚合
const { data } = useQuery(['order-stats'], () => api.orderStats(params))
// { totalAmount: 128900.00, count: 1000 }
```

**原则：能一次 SQL 算出来的，不要拉全量到前端算。**

---

## 七、后端不该做的三件事

| # | 不该做 | 为什么 |
|---|---|---|
| 1 | 返回 HTML 片段（除非明确要 SSR） | 前后端分离后，后端只管数据 |
| 2 | 关心"按钮放哪、什么颜色" | 这是 UI 决策 |
| 3 | 把分页结果格式化成展示字符串 | 返回原始数据 + total，渲染交前端 |

**但有一条例外**：状态文案建议后端返回 `code`，前端映射；如果文案涉及业务规则（如"已超时"依赖当前时间），那就后端算好返回 `statusText`。**判断标准：这个文案需要业务知识才能算出来吗？**

---

## 八、接口清单模板（写代码前先填）

```
# 用户模块

| 方法 | 路径 | 鉴权 | 请求 | 响应 data | 备注 |
|---|---|---|---|---|---|
| GET | /api/config/public | 无 | — | {siteName, logo, icp} | 未登录可访问 |
| POST | /api/auth/login | 无 | {username,password} | {accessToken, user, permissions} | 限流 5次/分 |
| GET | /api/users | JWT | ?page&pageSize&keyword&status | {page,pageSize,total,list:UserListItem[]} | 列表视图，6 字段 |
| GET | /api/users/:id | JWT | — | UserDetail | 按角色脱敏 |
| POST | /api/users | JWT+perm | UserCreateReq | {id} | 可写字段白名单 |
| PUT | /api/users/:id | JWT+perm | UserUpdateReq | null | 只允许改 5 个字段 |
| DELETE | /api/users/:id | JWT+perm | — | null | 软删 + 级联检查 |
| DELETE | /api/users | JWT+perm | {ids:[]} | {success[],failed[]} | 批量，上限 200 |
```

**填不出这一张表，就说明职责还没想清楚，不要开始写代码。**

---

## 九、验收清单

### DTO 分离

- [ ] 列表接口返回的是精简 DTO，不是 model
- [ ] 详情接口返回的是脱敏 DTO
- [ ] 创建/更新用的是独立 `*Req` 结构，字段白名单显式枚举
- [ ] 没有任何接口直接序列化 model
- [ ] 可写字段 ≠ 可读字段（`role`、`balance`、`status` 等不能随便写）

### 脱敏

- [ ] 手机号/身份证/银行卡在后端脱敏
- [ ] 前端代码里没有脱敏正则
- [ ] 脱敏按角色分级，不是一刀切
- [ ] 密码字段是 `json:"-"`
- [ ] 详情接口校验了"能不能看这一条"，不只是"能不能登录"

### 配置

- [ ] 公共配置接口不需要 token
- [ ] 登录后配置按用户返回
- [ ] 私有配置不包含任何基础设施信息（host/password/key）
- [ ] 枚举字典打包在前端，站点配置走接口

### 批量与计算

- [ ] 批量操作是单接口 + 明细返回，不是前端循环
- [ ] 没有把全量数据拉到前端做统计/聚合
- [ ] 金额、折扣、税费由后端计算返回

### 校验

- [ ] 前端校验之后，后端仍然做了业务校验
- [ ] 唯一性、状态合法性、额度、库存都在后端校验

---

## 十、反面清单

1. ❌ 列表接口 `SELECT *` 后直接返回 model
2. ❌ 用 model 接收请求体（批量赋值漏洞）
3. ❌ 前端 `phone.replace(...)` 做脱敏
4. ❌ 所有字段永远脱敏，不按角色分级
5. ❌ 公共配置接口要求登录
6. ❌ 把 DB 地址、SMTP 密码放进"配置接口"
7. ❌ 批量删除在前端循环调单个接口
8. ❌ 拉 1000 条订单在前端 `reduce` 算总额
9. ❌ 前端校验了就不在后端校验
10. ❌ 隐藏了按钮就不校验接口权限
