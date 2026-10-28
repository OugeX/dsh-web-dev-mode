---
name: go-backend-architecture
description: Go 后端目录架构与分层规范。包含 cmd/internal/pkg 布局、handler/service/repository 五层职责边界、DTO 与 model 分离防批量赋值、按分层与按业务域两种组织方式、API+Worker 双入口、jobs 队列表与 SKIP LOCKED、worker 七项必备（优雅退出/并发上限/超时/重试/死信/幂等/日志）。当新建 Go 项目、设计后端目录结构、加后台任务队列或评审分层是否串层时使用。
---

# Go 后端架构与分层

> **本 skill 是预制标准体系的一部分。** 新项目的完整产物清单与验收清单在 `web-project-bootstrap`；本文负责说清「每个文件为什么这么分、层与层的边界在哪、Worker 怎么组织」。


---

> **表结构设计先看 skill `mysql-schema-design`**：拆表判断树、1:1 与 1:N 的区分、字段类型与索引规范都在那里。model 结构体必须与表结构一一对应。

> **文件体量硬限见 `web-project-bootstrap` 第五节**：service 300 行、handler/repository 150-200 行、单函数 60 行。service 按「操作」拆成同包多文件。

## 一、前后端分离后，MVC 变成什么

| ThinkPHP MVC | 前后端分离 |
|---|---|
| Controller | **Handler**（只管 HTTP） |
| Model（表 + 查询 + 业务混在一起） | 拆成 **Model + Repository + Service** |
| View / 模板 | **前端**，后端不再有 V |
| validate 验证器 | **DTO + binding tag** |
| common.php | `internal/pkg/` |
| route/app.php | `internal/router/` |
| middleware.php | `internal/middleware/` |

---

## 二、标准目录树

```
project/
├── cmd/
│   ├── api/main.go              HTTP 入口，只做装配
│   └── worker/main.go           任务入口（有 worker 时）
├── internal/                    Go 强制外部不可 import
│   ├── router/                  路由注册，接口清单唯一来源
│   ├── middleware/              Recover / CORS / Logger / JWT
│   ├── handler/                 接口层
│   ├── service/                 业务层
│   ├── repository/              数据层
│   ├── model/                   表结构
│   ├── dto/                     请求/响应结构
│   ├── job/                     任务处理器（有 worker 时）
│   ├── queue/                   队列抽象（有 worker 时）
│   ├── scheduler/               定时任务（有 worker 时）
│   ├── config/
│   └── pkg/                     response / jwt / errcode
├── migrations/
├── docs/                        swagger 产物
└── .env
```

`pkg/` 只放真正要跨项目复用的东西。**大部分项目不需要。**

---

## 三、五层职责边界（不许串层）

| 层 | 该做 | 不许做 |
|---|---|---|
| handler | 绑参、校验、调 service、组装响应 | 不写业务、不碰 SQL、不返回 model |
| service | 业务规则、事务、跨 repo 编排 | 不碰 `gin.Context`、不写 SQL |
| repository | 只取数，返回 model | 不写业务判断 |
| model | 只映射表结构 | 不暴露给前端 |
| dto | 请求/响应结构 | 不带 GORM tag |

**`service` 不碰 `gin.Context`** 这条最关键——一旦拿到 Context，这段业务就无法脱离 HTTP 复用，也无法单测。

---

## 四、dto 与 model 必须分离

**问题一：批量赋值漏洞** —— 前端传 `role=admin`，直接提权
**问题二：字段泄漏** —— `password` 忘了 `json:"-"`，直接吐给前端

```go
// dto：只有前端允许传的字段
type CreateUserReq struct {
    Username string `json:"username" binding:"required,min=3,max=32"`
    Password string `json:"password" binding:"required,min=6"`
    Nickname string `json:"nickname"`
}

// model：数据库全部字段，永不直接返回
```

---

## 五、组织方式：分层 vs 按域

**A. 按分层（默认）**
```
internal/handler/{order,user,auth}.go
internal/service/{order,user,auth}.go
internal/repository/{order,user,auth}.go
```

**B. 按业务域**（复杂后换）
```
internal/modules/
├── order/{handler,service,repository,model,dto}.go
├── user/{...}
└── product/{...}
```

**切换信号**：单域代码超 **800 行**，或有 3 个以上互不相关的业务域。没到就先用 A。**两种不要混用一半。**

---

## 六、依赖注入

在 `main.go` 手工构造器注入，清晰、无魔法：

```go
db, _ := database.Connect(cfg)

userRepo  := repository.NewUserRepo(db)
orderRepo := repository.NewOrderRepo(db)
authSvc   := service.NewAuthService(userRepo, cfg)
orderSvc  := service.NewOrderService(orderRepo)
h         := handler.New(authSvc, orderSvc)

r := gin.New()
router.Register(r, h, cfg)
r.Run(":" + cfg.AppPort)
```

**不要引入 wire / dig 等 DI 容器；不要用全局 `db` 变量。**

---

## 七、错误处理与防御性编程的边界

### 7.1 一句话原则

> **在边界防御，在内部信任。**
> 错误处理的目标是「让失败可见且可定位」，不是「让代码看起来健壮」。

到处判 nil、吞错兜底、多层 wrap —— 效果恰好相反：失败被藏起来了。

### 7.2 该防御的三个边界（只有这三处）

| 边界 | 必须做 |
|---|---|
| **外部输入** | HTTP body/query/header、上传文件、第三方 API 响应、MQ 消息 → 全量校验 |
| **系统边界** | MySQL、Redis、外部 HTTP → 错误必须处理 + 必须带超时 |
| **不可信数据** | DB 里可能为 NULL 的字段、JSON 反序列化结果 → 判空 |

**数据穿过边界的那一刻校验一次。之后在内部一律假设它合法。**

### 7.3 不该防御的地方

- 自己刚 `new` 出来的对象 —— 不需要判 nil
- binding tag 已校验过的参数 —— service 里不要再 required/min/max
- 构造函数已返回 error 的情况 —— 调用方不需要再判内部字段
- `http.Response.Body`（成功返回时永远非 nil）
- 内部函数的返回值 —— 契约就是"成功则有值"

### 7.4 九种典型画蛇添足（对照表）

| 画蛇添足 | 正确做法 |
|---|---|
| 每层都 `log.Printf(err)` + `return fmt.Errorf("...: %w", err)` | 中间层只 wrap 不 log；只在顶层（handler/中间件）记一次日志 |
| 三层校验同一参数（binding → service → repo） | **只在边界校验一次**：binding tag 管格式，service 只做业务规则 |
| repo 里 `if user == nil { return errors.New("not found") }` | repo 返回 `gorm.ErrRecordNotFound`，service 用 `errors.Is` 判断业务分支 |
| 为每个 repository 定义 interface（只有一个实现） | 直接用 struct。Go 的接口在**消费方**定义，等真要 mock 时再抽 |
| 单条 SELECT 也开 `db.Transaction(...)` | 只读不需要事务。多写操作、或先查后改才需要 |
| 每个 handler 都 `defer recover()` | `Recover()` 中间件一个就够，全局兜底 |
| 为「将来可能」的字段加配置项和参数 | YAGNI。需要时再加，加的成本远低于维护猜想的成本 |
| `if ctx.Err() != nil { return ctx.Err() }` 满文件写 | DB/HTTP 调用天然感知 ctx，不需要手写检查 |
| service 里 `if x == nil { return 0, nil }` 吞错 | 直接返回 err。吞错比崩溃更难排查 |

### 7.5 Go 特有的七条

1. **error 只处理一次**：要么 wrap 返回，要么 log 后返回，**不要既 log 又 wrap**
2. **wrap 不超过两层**：`fmt.Errorf("create order: %w", err)` 一次够；调用栈本身已经有信息了
3. **禁止吞错**：`if err != nil { return nil }` 是灾难级写法
4. **panic 只用于启动期**：配置缺失、依赖初始化失败可以 panic；业务错误绝不
5. **nil 是有意义的值**：nil slice 可以 range，nil map 不能写。不要见 nil 就判
6. **接口在消费方定义**：不要在 provider 侧预先抽接口
7. **错误要能分类**：用 sentinel error（`var ErrNotFound = errors.New(...)`）+ `errors.Is`，不要靠字符串匹配

### 7.6 量化标准（agent 需要数字）

| 指标 | 红线 |
|---|---|
| 单个函数里 `if err != nil` 的数量 | ≤ 函数里涉及 IO 的调用数，多出来的就是冗余 |
| error wrap 层数 | ≤ 2 |
| 同一参数校验次数 | 1（边界那次） |
| 防御/校验代码占函数体比例 | > 30% 说明过度 |
| `return nil, nil` 出现 | 0（用 `golangci-lint` 的 `nilnil` 拦） |

### 7.7 lint 能拦的和拦不住的

能拦：
```yaml
linters:
  enable: [nilnil, errcheck, errorlint, bodyclose, sqlclosecheck]
```
- `nilnil` —— 禁止 `return nil, nil`
- `errcheck` —— 未处理的 error
- `errorlint` —— error 比较方式错误（用 `==` 而不是 `errors.Is`）

**拦不住**：重复校验、过度 wrap、为不存在的场景写分支。这些只能靠本节规范 + 代码评审。

### 7.8 标准三件套（照这个写，不要自行扩展）

**handler** —— 只做四件事：绑参、校验、调 service、回响应。**不重复校验。**

```go
func (h *OrderHandler) Create(c *gin.Context) {
    var req dto.CreateOrderReq
    if err := c.ShouldBindJSON(&req); err != nil {   // ① 边界校验，只此一次
        response.BadRequest(c, "参数错误: "+err.Error())
        return
    }
    id, err := h.svc.Create(c.Request.Context(), req) // ② 业务
    if err != nil {
        response.FailByErr(c, err)                    // ③ 统一错误映射
        return
    }
    response.OK(c, gin.H{"id": id})                   // ④ 响应
}
```

**service** —— 业务规则 + 事务，错误直接返回，不吞不兜底。

```go
func (s *OrderService) Create(ctx context.Context, req dto.CreateOrderReq) (uint, error) {
    order := &model.Order{ /* 业务构造 */ }
    if err := s.repo.Create(ctx, order); err != nil {
        return 0, fmt.Errorf("create order: %w", err)  // wrap 一次，不 log
    }
    return order.ID, nil
}
```

**repository** —— 只取数，原样返回驱动层错误。

```go
func (r *OrderRepo) GetByID(ctx context.Context, id uint) (*model.Order, error) {
    var o model.Order
    if err := r.db.WithContext(ctx).First(&o, id).Error; err != nil {
        return nil, err      // 原样返回 gorm.ErrRecordNotFound，由 service 判断
    }
    return &o, nil
}
```

### 7.9 错误统一出口

内部 error **不得原样返回前端**（会泄漏 SQL 语句、文件路径）。统一转成 `pkg/response` 的错误码 + 中文提示，原始错误只写日志：

```go
func FailByErr(c *gin.Context, err error) {
    var be *BizError
    switch {
    case errors.Is(err, gorm.ErrRecordNotFound):
        Fail(c, 404, 4004, "记录不存在")
    case errors.As(err, &be):
        Fail(c, 400, be.Code, be.Msg)
    default:
        slog.Error("internal error", "err", err, "request_id", GetReqID(c))
        Fail(c, 500, 5001, "服务器繁忙")   // 真实错误只进日志
    }
}
```

---

## 八、API + Worker 双入口（同一后端两个进程，不算拆服务）

**核心原则：一份业务代码，两个入口。**

```
cmd/api/main.go        HTTP
cmd/worker/main.go     后台任务
internal/{service,repository,model,dto}   ← 共享
```

**job 层边界（最重要）**：`internal/job/` 的任务处理器只做「解析参数 → 调 service → 返回 error」，**业务规则一律在 service**。

```go
// internal/job/order_sync.go —— 只做四件事
func OrderSync(ctx context.Context, payload []byte) error {
    var req dto.OrderSyncReq
    if err := json.Unmarshal(payload, &req); err != nil {
        return err
    }
    return orderSvc.SyncFromERP(ctx, req.ID)
}
```

**为什么**：一旦在 job 里写业务，API 和 worker 会各有一份"订单状态变更"逻辑。改需求时改一处漏一处，两个月后数据对不上。

### 队列选型

| 方式 | 用途 |
|---|---|
| **Redis List / Stream** | 首选 |
| **DB jobs 表** | 没 Redis 时用，几万任务/天无压力 |
| ❌ Kafka / RabbitMQ | 不要。一人项目运维成本过高 |

### jobs 表结构

```sql
CREATE TABLE jobs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  type VARCHAR(64) NOT NULL,
  payload JSON NOT NULL,
  status TINYINT NOT NULL DEFAULT 0,      -- 0待处理 1执行中 2成功 3失败 4死信
  attempts INT NOT NULL DEFAULT 0,
  max_attempts INT NOT NULL DEFAULT 3,
  run_at DATETIME NOT NULL,
  locked_at DATETIME NULL,
  locked_by VARCHAR(64) NULL,
  last_error TEXT NULL,
  created_at DATETIME NOT NULL,
  KEY idx_status_runat (status, run_at)
);
```

多 worker 安全抢任务（MySQL 8.0+）：

```sql
SELECT * FROM jobs
 WHERE status = 0 AND run_at <= NOW()
 ORDER BY id LIMIT 20
 FOR UPDATE SKIP LOCKED;      -- SKIP LOCKED 关键，没有会重复领取
```

### worker 七项必备

| # | 要素 | 漏了会怎样 |
|---|---|---|
| 1 | 优雅退出（SIGTERM 等任务跑完） | 部署时任务做一半 |
| 2 | 并发上限（worker pool） | 内存打爆 |
| 3 | context 超时 | 一个卡死占住 worker |
| 4 | 重试 + 最大次数 | 偶发失败丢任务 |
| 5 | 死信记录 | 失败任务消失无人知 |
| 6 | **幂等** | 重复扣款、重复发货 |
| 7 | 执行日志/耗时 | 出问题只能猜 |

**第 6 条最容易忽略**：队列语义是「至少一次」，不是「恰好一次」。幂等靠唯一键或状态机：

```sql
UPDATE orders SET status=3 WHERE id=? AND status=2   -- 看影响行数
-- 而不是 UPDATE orders SET status=3 WHERE id=?
```

### 什么时候才真的拆两个服务

只有两种情况：
1. 扩容需求不对称（API 3 台，worker 20 台）
2. 发布节奏不同

否则就是**同仓库两个 cmd 入口**。

---

## 九、七条反面清单

1. ❌ 用 model 直接接收请求体
2. ❌ 把 model 直接返回前端
3. ❌ handler 里写 SQL 或业务判断
4. ❌ service 里用 `gin.Context`
5. ❌ 所有代码塞进 `main.go`
6. ❌ 用全局 `db` 变量代替注入
7. ❌ 把 `err.Error()` 原样返回前端
