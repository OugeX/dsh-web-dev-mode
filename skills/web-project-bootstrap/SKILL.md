---
name: web-project-bootstrap
description: 新 Web 项目从 0 到 1 的预制脚手架标准。给定项目类型，直接产出：技术栈选型结果、完整目录树、依赖清单、配置与 .env 模板、五层骨架代码、统一响应与错误码、Makefile、迁移脚本、验收清单。当要新建 Web 项目、起新仓库、复制一套标准架构、或检查现有项目是否合规时使用。
---

# 定位：预制件，不是参考资料

新项目按本文执行。**不要重新讨论选型、不要发明目录名、不要跳过产物、不要把"建议"当"可选"。**

配套细则：
- 各栈怎么写 → skill `web-tech-stack`
- 后端分层与 Worker → skill `go-backend-architecture`
- 登录与鉴权 → skill `jwt-session-auth`
- **前端目录、统一登录态、列表页、权限、样式** → skill `react-frontend-architecture`
- **数据表设计、该不该拆表、字段类型、索引、迁移** → skill `mysql-schema-design`
- **图片/文件上传、头像、附件、媒体鉴权、多端共享资源** → skill `media-file-management`

---

## 零、技能路由表（先看这里）

| 你在做什么 | 加载哪个 skill |
|---|---|
| **新建项目 / 起仓库 / 要标准目录骨架 / 检查项目合规** | 本文（bootstrap） |
| 选技术栈 / 判断某栈怎么写 / 做 H5、小程序、App | `web-tech-stack` |
| 设计数据表 / 判断该不该拆表 / 字段类型 / 索引 / 迁移 / 审计 | `mysql-schema-design` |
| 后端目录与分层 / Worker / 防御性编程边界 | `go-backend-architecture` |
| 登录 / 鉴权中间件 / 权限 / 会话失效 / 踢人 | `jwt-session-auth` |
| 前端目录 / 统一登录态 / 列表页 / 组件规范 / 文件体量 | `react-frontend-architecture` |
| 图片与文件上传 / 头像 / 附件 / 媒体鉴权 / 本地存储 | `media-file-management` |
| **写测试 / 被要求提高覆盖率 / agent 乱起服务或连库** | `testing-strategy` |
| **搭本地环境 / 写 Dockerfile 与 compose / 部署上线 / 服务器性能调优** | `deployment-ops` |
| **设计 CRUD 接口 / 定返回字段 / 脱敏 / 公共与私有配置 / 批量操作** | `api-contract-design` |
| **弹窗还是抽屉 / 提示用哪种 / 要不要搜索分页 / 按钮放哪 / 页面骨架** | `ui-ux-decision-guide` |
| **手机端页面 / 响应式 / iOS 与安卓兼容 / 键盘遮挡 / 刘海屏 / 滚动异常** | `mobile-responsive-layout` |
| **表单细节 / 输入框状态与动画 / 提示文案 / 必填标记 / 校验时机** | `form-design-spec` |
| **登录页 / 注册页 / 找回密码 / 验证码流程 / 记住我** | `auth-pages-spec` |
| **骨架屏 / 加载跳动 / 表格列宽抖动 / 图片撑开 / CLS 优化** | `async-loading-stability` |
| **页面切换过渡 / 弹窗与抽屉动画 / toast 进出 / 列表增删动画** | `motion-animation-spec` |
| **列宽策略 / 固定列 / 行内编辑 / 树形表格 / 虚拟滚动 / 跨页选择** | `table-advanced` |
| **图表选型 / 色板 / 双 Y 轴 / 空数据 / 仪表盘** | `data-visualization` |
| **富文本编辑器 / 文件上传 / 拖拽粘贴 / 分片断点续传** | `rich-media-input` |
| **消息中心 / 未读角标 / 标记已读 / WebSocket 推送** | `notification-center` |
| **多语言 / RTL / 文案膨胀 / 日期货币格式化** | `i18n-spec` |

**规则**：
- 命中即加载，**读完再写代码**，不要凭记忆。
- 可同时加载多个（如新建项目时需 bootstrap + 后端 + 前端 + 表设计）。
- 这二十一个 skill 是全局的，其他模式（不废话、红队）下也能单独调用。

---

## 一、选型决策表（一次定死，不再问）

| 项目类型 | 后端 | 前端 | 队列 | 鉴权 |
|---|---|---|---|---|
| **PC 后台管理**（主力） | Go + Gin + GORM | React 19 + Vite + AntD 5 + TanStack Query | 无 | 纯 JWT |
| **带后台任务** | 同上 + `cmd/worker` | 同上 | Redis List 或 jobs 表 | 纯 JWT |
| **要记录登录设备 / 踢人** | 同上 | 同上 | — | JWT + Redis 白名单 + MySQL 审计 |
| **仅手机 H5** | Go + Gin（纯 API） | Vue3 + Vant | 无 | 纯 JWT |
| **小程序 / App** | Go + Gin（纯 API） | uni-app + Wot Design Uni | 无 | 纯 JWT |
| **老项目维护** | **沿用原栈，不要迁移** | 沿用原栈 | 沿用 | 沿用 |

数据库一律 **MySQL 8**，字符集 `utf8mb4`，引擎 `InnoDB`。

---

## 二、后端产物清单（Go 主力栈，26 项）

```
backend/
├── go.mod                              module <project>; go 1.25
├── .env.example                        全部环境变量 + 注释
├── Makefile                            run / build / test / lint / migrate
├── cmd/
│   ├── api/main.go                     只做装配：config → db → repo → service → handler → router
│   └── worker/main.go                  仅"带后台任务"时生成
├── internal/
│   ├── config/config.go                环境变量加载，带默认值
│   ├── database/mysql.go               DSN + 连接池三参数 + AutoMigrate + seed
│   ├── router/router.go                路由注册，接口清单唯一来源
│   ├── middleware/
│   │   ├── recover.go                  兜 panic，返回 500 统一体
│   │   ├── logger.go                   请求日志 + request_id
│   │   ├── cors.go                     只允许 .env 里配置的来源
│   │   └── auth.go                     JWT 校验 → 塞 uid/jti/role 进 context
│   ├── handler/
│   │   ├── health.go                   GET /api/health，返回 {code:0,data:"ok"}
│   │   ├── auth.go                     login / logout / me / change-password
│   │   └── <domain>.go                 每个业务域一个
│   ├── service/
│   │   ├── auth.go
│   │   └── <domain>.go
│   ├── repository/
│   │   ├── user.go
│   │   └── <domain>.go
│   ├── model/
│   │   ├── user.go                     含 Password 且 json:"-"
│   │   └── <domain>.go
│   ├── dto/
│   │   ├── auth.go                     LoginReq / TokenPair / MeResp
│   │   └── <domain>.go                 入参带 binding tag，出参不带 GORM tag
│   ├── pkg/
│   │   ├── response/response.go        OK / Page / Fail / BadRequest / Unauthorized ...
│   │   ├── errcode/errcode.go          错误码常量（分段见第四节）
│   │   └── jwt/jwt.go                  签发 + 解析（WithValidMethods + exp 必填）
│   ├── job/                            仅"带后台任务"时生成
│   ├── queue/                          同上
│   └── scheduler/                      同上
├── migrations/0001_init.sql            建表 SQL（与 AutoMigrate 一致）**设计前先过 mysql-schema-design 的判断树**
└── docs/                               swag init 产物
```

**必须存在的三个文件**：`internal/pkg/response/response.go`、`internal/pkg/errcode/errcode.go`、`internal/pkg/jwt/jwt.go`。没有这三个，后面每个 handler 都会各写一套，必然分裂。

---

## 三、前端产物清单（React 主力栈，16 项）

> 目录分层、各层职责边界、统一登录态、列表页三态、权限、样式规范**全部在 skill `react-frontend-architecture`**。本节只列"必须有哪些文件"，不重复细则。生成前端前先加载那个 skill。

```
frontend/
├── package.json
├── vite.config.ts                      必须配 server.proxy['/api'] → 后端
├── tsconfig.json
├── index.html
├── .env.development                    VITE_API_BASE=/api
├── src/
│   ├── main.tsx                        AntD ConfigProvider + QueryClientProvider
│   ├── App.tsx
│   ├── router.tsx                      React Router 7，含路由守卫
│   ├── api/
│   │   ├── client.ts                   axios 实例 + 请求拦截器（带 token）+ 响应拦截器（401 跳登录）
│   │   ├── auth.ts
│   │   └── <domain>.ts
│   ├── types/api.d.ts                  openapi-typescript 生成，不手写
│   ├── stores/auth.ts                  Zustand：token / user / roles
│   ├── hooks/useAuth.ts
│   ├── layouts/AdminLayout.tsx         antd Layout：Sider 菜单 + Header + Content + 面包屑
│   ├── pages/
│   │   ├── Login.tsx
│   │   └── <Domain>/List.tsx           列表页必须三态齐全
│   └── components/
│       ├── index.ts                    **唯一组件出口**
│       ├── Btn/ AuthButton/ ProTable/ PageContainer/ SearchForm/
│       ├── StatusTag/ Total/ Hint/ EmptyState/
│       └── Confirm/ Toast/
├── scripts/check-conventions.sh        **构建前检查，防造轮子**
└── COMPONENTS.md                       **组件清单，agent 必读**
```

**列表页三态是硬要求**：`Spin`（加载中）/ `Empty`（0 条）/ `Result`（请求失败）。缺一个都不算完成。

---

## 四、硬性规范（违反即打回重写）

### 响应体

```json
{ "code": 0, "msg": "ok", "data": {} }
```

- `code = 0` 成功；非 0 失败
- HTTP 状态码同步设置（401 就返回 401，不要一律 200）
- **失败时 `data` 为 `null`，不要塞空对象**

### 分页

```json
{ "code": 0, "msg": "ok", "data": { "page": 1, "pageSize": 20, "total": 128, "list": [] } }
```

参数名固定 `page` / `pageSize`，**不要用 `size`、`limit`、`offset`**。

### 错误码分段

| 段 | 含义 | 例 |
|---|---|---|
| 0 | 成功 | 0 |
| 1xxx | 参数错误 | 1001 参数缺失、1002 格式错误 |
| 2xxx | 认证失败 | 2001 未登录、2002 token 过期、2003 登录失效 |
| 3xxx | 权限不足 | 3001 无权限 |
| 4xxx | 业务规则 | 4001 库存不足、4002 状态不允许 |
| 5xxx | 系统错误 | 5001 内部错误、5002 依赖不可用 |

**5xxx 的 msg 一律是「服务器繁忙」，真实错误只写日志。** 不把 SQL 语句、文件路径返回给前端。

### 命名

| 项 | 规则 | 例 |
|---|---|---|
| JSON 字段 | camelCase，**显式写 json tag** | `orderNo` `createdAt` |
| 数据库字段 | snake_case | `order_no` `created_at` |
| Go 结构体 | PascalCase | `OrderNo` |
| 接口路径 | 小写 + 复数 + 连字符 | `/api/orders` `/api/login-logs` |
| 时间 | RFC3339 字符串 | `2026-10-28T19:50:00+08:00` |

### 日志

- 统一 `log/slog`
- 每个请求带 `request_id`（中间件生成 UUID，写进 context 和日志）
- 级别：`Info` 正常请求、`Warn` 可恢复异常、`Error` 需要人工介入
- **禁止打印密码、token、完整请求体**

### 分层铁律

- handler 不写业务、不碰 SQL、不返回 model
- service 不碰 `gin.Context`
- repository 只取数，返回 model
- dto 与 model 严格分离

---

## 五、文件体量规范（强制，防 agent 写大文件）

### 5.1 为什么必须量化

agent 倾向把相关内容塞进一个文件，因为"跨文件容易出错"。结果是 3000 行单文件：bundle 变大、agent 后续读代码要反复切片、耦合扩散。

**光写"保持文件精简"无效。必须给数字 + lint 拦截。**

### 5.2 硬性上限

| 文件类型 | 行数上限 | 用什么拦 |
|---|---|---|
| React 组件 `.tsx` | **200** | eslint `max-lines` |
| 前端 hooks / utils / api 单文件 | **150** | eslint `max-lines` |
| Go handler 单文件 | **150** | `golangci-lint` funlen |
| Go service 单文件 | **300** | 同上 |
| Go repository 单文件 | **200** | 同上 |
| 单函数（任何语言） | **60 行 / 40 语句** | funlen |
| 圈复杂度 | **15** | gocyclo |
| 常量 / 枚举字典 | 300（例外） | — |

### 5.3 三条行为铁律

1. **触线即拆，不许"再忍一下"**。到 200 行就该问"这是几件事"，不是等到 3000。
2. **修改已超限的文件时，先拆再改** —— 严禁继续往里追加。这是 agent 让文件失控的主要路径。
3. **一个文件一个主导出**，文件名 = 内容。`order.ts` 里有 12 个函数说明它该叫 `order-query.ts` / `order-export.ts`。

### 5.4 前端 ESLint 配置（加进产物）

```js
// eslint.config.js
{
  rules: {
    'max-lines': ['error', { max: 200, skipBlankLines: true, skipComments: true }],
    'max-lines-per-function': ['error', { max: 80, skipBlankLines: true, skipComments: true }],
    'complexity': ['error', 15],
  },
  ignores: ['**/*.d.ts', '**/constants/**', '**/route*/**'],
}
```

### 5.5 后端 golangci-lint 配置

```yaml
# .golangci.yml
linters:
  enable: [funlen, gocyclo, gocognit, maintidx]
linters-settings:
  funlen:   { lines: 60, statements: 40 }
  gocyclo:  { min-complexity: 15 }
  gocognit: { min-complexity: 20 }
```

### 5.6 体量巡检脚本

```bash
#!/usr/bin/env bash
# scripts/check-size.sh —— 输出超限文件，按行数降序
echo "=== 前端（上限 200 / hooks&utils 150）==="
find src -type f \( -name '*.tsx' -o -name '*.ts' \) \
  ! -name '*.d.ts' ! -path '*/constants/*' \
  -exec sh -c 'n=$(wc -l < "$1"); lim=200; case "$1" in *.d.ts|*/hooks/*|*/utils/*|*/api/*) lim=150;; esac; [ "$n" -gt "$lim" ] && echo "$n (限 $lim) $1"' _ {} \; | sort -rn

echo "=== 后端（上限 300 / handler 150）==="
find . -name '*.go' ! -name '*_test.go' \
  -exec sh -c 'n=$(wc -l < "$1"); lim=300; case "$1" in */handler/*) lim=150;; esac; [ "$n" -gt "$lim" ] && echo "$n (限 $lim) $1"' _ {} \; | sort -rn
```

接进 `"prebuild"`，与 `check-conventions.sh` 串联。

### 5.7 拆分模板（照这个拆，不要自创结构）

**前端：一个 1500 行的订单列表页**

```
pages/order/
├── index.tsx            80 行    只组装：PageContainer + SearchForm + ProTable + Modal
├── columns.tsx         120 行    表格列定义（单独文件，常被复用）
├── constants.ts         50 行    状态枚举、筛选项
├── hooks/
│   ├── useOrderList.ts  60 行    取数 + 分页 + 筛选（useTable 封装）
│   └── useOrderForm.ts  90 行    新增/编辑表单逻辑
└── components/
    ├── OrderForm.tsx   150 行    表单
    └── OrderDetail.tsx 100 行    详情抽屉
```

**后端：一个 1200 行的 order service**

```
internal/service/order/
├── order.go        30 行   装配、接口定义、共享依赖
├── create.go      120 行   创建
├── update.go      150 行   状态变更
├── query.go       120 行   查询与分页
├── export.go      100 行   导出
└── sync.go        180 行   ERP 同步
```

按**操作**拆，不按"技术细节"拆。Go 里同一包内多文件共享私有函数，拆开无额外成本。

### 5.8 拆分后的验证

拆完必须立刻验证，否则 agent 会怕拆：

- 前端：`npm run lint && npm run build`
- 后端：`go build ./... && go vet ./... && go test ./...`

**split 后编译不过 = 拆错了，比不拆更糟。**

## 六、生成顺序（严格按序，每步可验证）

| # | 步骤 | 验证方式 |
|---|---|---|
| 1 | `go mod init` + 装依赖 | `go mod tidy` 无报错 |
| 2 | `pkg/`（response / errcode / jwt） | `go build ./...` 通过 |
| 3 | `config` + `database` | 启动能连上 MySQL，AutoMigrate 成功 |
| 4 | `model` + `migrations/0001_init.sql` | 表建出来，字段与 model 一致 |
| 5 | `repository` | `go build` 通过 |
| 6 | `service` | `go build` 通过 |
| 7 | `dto` | `go build` 通过 |
| 8 | `handler` | `go build` 通过 |
| 9 | `middleware` | `go build` 通过 |
| 10 | `router` + `main.go` | 启动后 `GET /api/health` 返回 `{code:0}` |
| 11 | 登录接口 | `POST /api/auth/login` 能拿到 token |
| 12 | 前端脚手架（Vite + AntD + Router + Query） | `npm run dev` 起得来 |
| 13 | axios + proxy | 前端能调到 `/api/health` |
| 14 | 登录页 + 一个列表页 | 登录 → 跳转 → 列表有数据 |
| 15 | ESLint / golangci 体量与规则校验 | **故意写一个裸 `<button>` 和一个 250 行组件，确认 `npm run lint` 报错**；后端 `golangci-lint run` 能拦住超长函数 |
| 16 | 联调验收 | 见第七节 |

**第 1-10 步没跑通，不要开始写任何业务代码。** 骨架不通的情况下写的业务全是返工。

---

## 七、验收清单（全过才算交付）

### 后端

- [ ] `go build ./...` 通过
- [ ] `go vet ./...` 无告警
- [ ] `go test ./...` 通过（至少有 health 的测试）
- [ ] 启动能连 MySQL，`AutoMigrate` 成功，无 panic
- [ ] `GET /api/health` → `{code:0,msg:"ok",data:"ok"}`
- [ ] 错误请求返回非 0 code + 对应 HTTP 状态码
- [ ] 5xx 响应里看不到 SQL 或路径
- [ ] `.env.example` 里没有真实密码

### 鉴权（有登录时）

- [ ] 登录成功返回 token
- [ ] 不带 token 访问受保护接口 → 401 + code 2001
- [ ] 带 token 访问 → 200
- [ ] 登出后同一 token 再访问 → 401
- [ ] 改密后旧 token 立刻失效

### 前端

- [ ] `npm run dev` 无报错
- [ ] `/api` 代理到后端，无 CORS 错误
- [ ] 未登录访问受保护路由 → 跳登录页
- [ ] 列表页三态齐全（加载中 / 空 / 失败）
- [ ] 401 时自动清 token 并跳登录

### 体量（防大文件）

- [ ] 没有任何 React 组件超过 200 行
- [ ] 没有 hooks / utils / api 单文件超过 150 行
- [ ] 没有 Go service 超过 300 行、handler 超过 150 行
- [ ] 没有单函数超过 60 行 / 40 语句
- [ ] `eslint.config.js` 里 `max-lines` / `max-lines-per-function` 已配置
- [ ] `.golangci.yml` 里 `funlen` / `gocyclo` 已启用
- [ ] `scripts/check-size.sh` 已存在并接入 `prebuild`
- [ ] **故意写超限文件能被 lint 拦住**（已验证）

### 规范

- [ ] 所有接口返回 `{code,msg,data}`
- [ ] 分页统一 `{page,pageSize,total,list}`
- [ ] JSON 全 camelCase
- [ ] 没有 model 直接返回前端
- [ ] 没有 model 直接接收请求体

---

## 八、新业务域的加法

新增一个域（如 `product`），按固定六件套加，**不要动已有文件**：

```
internal/model/product.go
internal/dto/product.go
internal/repository/product.go
internal/service/product.go
internal/handler/product.go
internal/router/router.go   ← 只在 Register 里加一行分组
```

链路：`model → dto → repository → service → handler → router`。
service 依赖 repository，handler 依赖 service，**方向单一，不许反向 import**。
