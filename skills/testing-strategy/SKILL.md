---
name: testing-strategy
description: Go 与 React 项目的测试策略与执行纪律。包含 agent 乱调用的防护（Makefile 单一入口、APP_ENV 环境检查、测试库隔离、禁止裸跑破坏性命令）、测试优先级与分层比例（单元 30%/集成 60%/E2E 10%）、禁止的测试反模式（测实现不测行为、mock 自己写的 repo、断言错误字符串、time.Sleep 同步）、Go 表驱动模板与集成测试库方案、前端只写纯函数单测与 E2E 冒烟、覆盖率 40-60% 目标、禁止伪造测试通过。当写测试、被要求提高覆盖率、或发现 agent 随意起服务/连库/跑迁移时使用。
---

# 定位：测试防回归，执行有边界

两条主线：
1. **执行纪律** —— 什么能跑、在哪跑、怎么跑（防「乱调用」）
2. **测试设计** —— 测什么、不测什么（防「乱测试」）

---

## 一、执行纪律（比测试本身更重要）

### 1.1 agent 乱调用的典型行为

| 行为 | 后果 |
|---|---|
| 写完代码直接 `go run main.go` + curl | 端口冲突、脏数据进入开发库 |
| 连 `.env` 里配的库（可能是生产） | **直接操作生产数据** |
| 执行 `TRUNCATE` / `DROP` / 迁移脚本不看环境 | 数据不可恢复 |
| `rm -rf` / `git reset --hard` 清场 | 工作丢失 |
| 同一个失败命令疯狂重试 | 掩盖真实错误 |
| 改 `.env` 做临时测试，忘了改回来 | 后续行为全错 |

**根因**：agent 没有"环境"概念，只有"把任务做完"。

### 1.2 唯一解：Makefile 作为唯一入口

**禁止 agent 直接执行底层命令**，所有操作走 Makefile target：

```makefile
APP_ENV ?= dev

.PHONY: dev test test-cover migrate-dev db-reset

dev:                    ## 起开发服务（占用 8080 前会检查）
	@lsof -i :8080 >/dev/null 2>&1 && (echo "端口 8080 被占用，请先停止或改用 make dev PORT=8081"; exit 1) || true
	APP_ENV=dev go run ./cmd/api

test:                   ## 跑测试（强制 test 库）
	@test "$(APP_ENV)" = "test" || (echo "❌ 测试必须在 APP_ENV=test 下运行"; exit 1)
	go test ./... -count=1 -race

test-cover:
	APP_ENV=test go test ./... -coverprofile=cover.out -count=1
	go tool cover -func=cover.out | tail -1

migrate-dev:            ## 迁移（只允许 dev/test）
	@echo "$(APP_ENV)" | grep -qE '^(dev|test)$$' || (echo "❌ 只能在 dev/test 环境执行迁移，当前 APP_ENV=$(APP_ENV)"; exit 1)
	APP_ENV=$(APP_ENV) go run ./cmd/migrate

db-reset:               ## 重建测试库（只允许 test）
	@test "$(APP_ENV)" = "test" || (echo "❌ 只能在 test 环境重置数据库"; exit 1)
	mysql -e "DROP DATABASE IF EXISTS go_admin_test; CREATE DATABASE go_admin_test CHARACTER SET utf8mb4"
```

**`migrate-dev` 里的环境检查是关键的一道闸**：agent 想在生产库上跑迁移，`APP_ENV` 不是 dev/test 就直接退出。

### 1.3 测试库必须物理隔离

```
.env              DB_NAME=go_admin          APP_ENV=dev
.env.test         DB_NAME=go_admin_test     APP_ENV=test
```

```go
// 启动时硬校验：测试环境绝不连非 test 库
func mustTestDB(name string) {
    if !strings.HasSuffix(name, "_test") {
        log.Fatalf("拒绝启动：测试环境必须使用 *_test 库，当前为 %s", name)
    }
}
```

**这条硬校验能救命**：没有它，一次误配就把开发库洗了。

### 1.4 破坏性操作清单（每一条都要环境检查）

| 操作 | 必须检查 |
|---|---|
| `DROP` / `TRUNCATE` / `DELETE` 无 `WHERE` | `APP_ENV ∈ {dev,test}` |
| 迁移脚本 | 同上 |
| `rm -rf` | 目标路径白名单，且不在项目外 |
| 批量改文件（sed -i） | 先 `--dry-run` 或输出 diff |
| `git reset --hard` / `git clean -fd` | 先 `git status` 并说明影响 |

### 1.5 端口与进程

- 起服务前检查端口占用；被占用就换端口并**告知老大**
- 测试起服务用随机端口（`httptest.NewServer` 自动分配）
- 禁止 kill 不认识的进程

---

## 二、测试设计：测行为，不测实现

### 2.1 一条判断标准

> **把实现整个重写一遍，测试还能通过吗？**
> 能通过 → 测的是行为，好测试。
> 全红 → 测的是实现，脆测试。

### 2.2 最典型的错误：mock 自己写的 repository

```go
// ❌ 测的是「有没有调用 mock」，不是「创建订单对不对」
func TestCreateOrder(t *testing.T) {
    ctrl := gomock.NewController(t)
    mockRepo := mocks.NewMockOrderRepo(ctrl)
    mockRepo.EXPECT().Create(gomock.Any()).Return(nil)
    svc := NewOrderService(mockRepo)

    _, err := svc.Create(ctx, req)
    require.NoError(t, err)
    mockRepo.AssertExpectations(t)   // ← 断言的是调用次数
}
```

这个测试永远绿——即使 SQL 写错、字段拼错、事务没提交。

**正确做法**：用真数据库跑集成测试，断言**结果**。

```go
// ✅ 连测试库，断言最终状态
func TestCreateOrder_Integration(t *testing.T) {
    db := testdb.Open(t)             // 连 go_admin_test，事务内跑完回滚
    svc := NewOrderService(repo.NewOrderRepo(db))

    id, err := svc.Create(ctx, dto.CreateOrderReq{Customer: "张三", Amount: 100})
    require.NoError(t, err)

    var got model.Order
    require.NoError(t, db.First(&got, id).Error)
    assert.Equal(t, "张三", got.Customer)
    assert.Equal(t, 100.0, got.Amount)
    assert.Equal(t, int8(1), got.Status)     // 断言业务规则：初始状态必须是待付款
}
```

### 2.3 测试分层比例（Go 里跟经典金字塔不同）

| 层 | 经典金字塔 | **Go 实际推荐** | 理由 |
|---|---|---|---|
| 单元测试 | 70% | **30%** | 只测纯逻辑（计算、状态机、校验） |
| 集成测试 | 20% | **60%** | 真连库跑 repo+service，性价比最高 |
| E2E | 10% | **10%** | 关键链路 1-2 条 |

**Go 的集成测试成本很低**：编译快、起测试库简单、事务回滚清理干净。mock 一堆 repository 反而更累且价值低。

### 2.4 优先级（决定先写哪个）

| 优先级 | 测什么 | 占比 |
|---|---|---|
| **P0** | 核心业务规则（金额计算、状态流转、权限判断、库存扣减） | 60% |
| **P1** | 边界与错误路径（空值、超长、越权、重复提交、并发） | 25% |
| **P2** | 接口契约（HTTP 状态码、响应体结构、错误码） | 10% |
| **P3** | 工具函数 | 5% |

**P0 写不好，P3 写再多也没用。**

### 2.5 每个 service 方法的测试三件套

```go
// 1. 正常路径
func TestXxx_正常(t *testing.T)
// 2. 参数非法
func TestXxx_参数非法(t *testing.T)
// 3. 依赖失败（repo 返回 error / 外部服务超时）
func TestXxx_依赖失败(t *testing.T)
```

**这条比"覆盖率 80%"具体得多，也可执行。** 一个 service 方法没有这三个，就算没测。

---

## 三、禁止的测试反模式

| # | 禁止 | 为什么 | 改成 |
|---|---|---|---|
| 1 | `mockRepo.AssertExpectations(t)` 测调用次数 | 测实现不测行为 | 断言数据库最终状态 |
| 2 | `time.Sleep` 等异步 | 慢且不稳 | `require.Eventually` 或 channel 同步 |
| 3 | 断言 `err.Error()` 字符串 | 改文案就红 | `errors.Is(err, ErrXxx)` |
| 4 | 测私有函数 | 锁死实现细节 | 通过公开 API 测 |
| 5 | 一个测试断言 20 件事 | 失败时不知哪条挂 | 拆成多个 `t.Run` |
| 6 | 测试依赖执行顺序 | 单独跑就挂 | 每个测试自备数据、自清理 |
| 7 | 为 getter/setter/纯转发写测试 | 零价值 | 删掉 |
| 8 | 断言日志内容 | 日志格式会变 | 断言业务结果 |
| 9 | 测试里用 `context.Background()` 无超时 | 挂住不返回 | `context.WithTimeout` |
| 10 | 全局共享测试数据 | 互相污染 | 每个测试自己造 |

---

## 四、Go 测试模板

### 4.1 表驱动（默认写法）

```go
func TestCalcAmount(t *testing.T) {
    tests := []struct {
        name string
        in   int
        want int
    }{
        {"正常", 100, 110},
        {"零值", 0, 0},
        {"负数", -1, 0},
        {"上限", math.MaxInt32, 0},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel()
            assert.Equal(t, tt.want, CalcAmount(tt.in))
        })
    }
}
```

### 4.2 集成测试的库与清理

```go
// internal/testutil/db.go
func Open(t *testing.T) *gorm.DB {
    t.Helper()
    dsn := os.Getenv("TEST_DSN")   // .../go_admin_test
    db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
    require.NoError(t, err)

    // 每个测试在事务里跑，结束回滚 —— 不需要手工清表
    tx := db.Begin()
    t.Cleanup(func() { tx.Rollback() })
    return tx
}
```

**事务回滚清理**是最干净的方案：测试并行也无冲突，跑完自动恢复。

### 4.3 handler 测试用 httptest

```go
func TestLoginHandler(t *testing.T) {
    r := gin.New()
    r.POST("/api/auth/login", h.Login)

    w := httptest.NewRecorder()
    req := httptest.NewRequest("POST", "/api/auth/login",
        strings.NewReader(`{"username":"admin","password":"admin123"}`))
    req.Header.Set("Content-Type", "application/json")
    r.ServeHTTP(w, req)

    assert.Equal(t, http.StatusOK, w.Code)
    var body map[string]any
    require.NoError(t, json.Unmarshal(w.Body.Bytes(), &body))
    assert.Equal(t, float64(0), body["code"])       // 统一响应体
}
```

---

## 五、前端测试策略

**不写组件单测。** 理由：
- 断言脆弱，改样式就红
- 真正的 bug 在交互流程，不在组件内部
- 维护成本高于收益

只做两件事：

### 5.1 关键纯函数单测

```ts
// utils/format.test.ts
describe('formatAmount', () => {
  it('两位小数千分位', () => expect(formatAmount(1234.5)).toBe('1,234.50'))
  it('零值', () => expect(formatAmount(0)).toBe('0.00'))
  it('负数', () => expect(formatAmount(-1)).toBe('-1.00'))
})
```

### 5.2 E2E 冒烟 1-2 条

Playwright，只跑主流程：

```
登录 → 进列表 → 新建 → 查看到 → 删除 → 列表消失
```

**一条 E2E 覆盖的价值 > 50 个组件单测。**

---

## 六、覆盖率

| 层 | 目标 |
|---|---|
| **整体** | **40–60%**（追求 90% 一定在写垃圾测试） |
| service 核心业务逻辑 | ≥ 70% |
| repository | 靠集成测试，不看行覆盖率 |
| handler | 只测关键接口，不看覆盖率 |
| 前端 | 不统计 |

**覆盖率是体检指标，不是 KPI。** 数字高但测试都在测 getter，毫无意义。

---

## 七、绝对禁止：伪造测试通过

这是最恶劣的行为，比不写测试更糟——它让人失去对测试的信任。

| 行为 | 性质 |
|---|---|
| `t.Skip("TODO")` 跳过失败测试 | 掩盖问题 |
| 注释掉断言 | 同上 |
| `t.Log(err)` 代替 `t.Fatal(err)` | 失败也不报 |
| **修改测试来适配错误的实现** | **最严重：测试变绿但代码是错的** |
| 把集成测试改成 mock 让它跑通 | 测不出真问题 |
| `-short` 模式跳过关键测试并当成功 | 同上 |

### 唯一正确的处理

> **测试红了 → 改代码。不要改测试。**
> 除非测试本身写错了，此时必须**明确说明为什么测试错了**，再改。

---

## 八、验收清单

### 执行纪律

- [ ] 所有操作走 Makefile target，没有裸跑 `go run` / `mysql` CLI
- [ ] `migrate-dev` 等破坏性 target 里有 `APP_ENV` 校验
- [ ] 测试库名是 `*_test`，且有硬校验拒绝非 test 库
- [ ] `.env.test` 与 `.env` 分离
- [ ] 起服务前检查端口占用
- [ ] 行为里没有"改 .env 做临时测试后忘了改回"

### 测试设计

- [ ] service 每个方法有：正常 / 参数非法 / 依赖失败 三个测试
- [ ] 没有 mock 自己写的 repository 来测 service
- [ ] 集成测试真连库，断言最终数据状态
- [ ] 错误断言用 `errors.Is`，不用字符串
- [ ] 没有 `time.Sleep` 做同步
- [ ] 表驱动是默认写法
- [ ] 测试可单独运行、可并行（`-race` 通过）
- [ ] 前端只测关键纯函数 + 1-2 条 E2E
- [ ] 覆盖率达到 40–60%，没有为凑数写的垃圾测试

### 诚实性

- [ ] 没有未说明理由的 `t.Skip`
- [ ] 没有注释掉的断言
- [ ] 没有为让测试变绿而修改测试（或已明确说明测试本身写错）
- [ ] `go test ./... -race -count=1` 全绿

---

## 九、反面清单

1. ❌ 写完代码直接 `go run` + curl 手工验证就当测过了
2. ❌ 直接连 `.env` 里的库跑测试
3. ❌ 没有环境校验的迁移脚本
4. ❌ 用 mock 测 service，断言 mock 被调用
5. ❌ 追求 90% 覆盖率
6. ❌ 给 getter/setter 写测试
7. ❌ 用 `time.Sleep` 等异步
8. ❌ 断言错误信息字符串
9. ❌ 修改测试让错误的实现通过
10. ❌ 为前端组件写大量单测
