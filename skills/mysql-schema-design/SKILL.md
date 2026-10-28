---
name: mysql-schema-design
description: MySQL 数据表设计与结构规范。包含拆表判断决策树、1:1 与 1:N 的关键区分、30-50 字段宽表为何不该拆（InnoDB 行格式事实）、拆表的真实代价、必须拆表的五个硬指标、字段类型与命名规范、金额/时间/状态/软删的固定写法、索引设计与联合索引顺序、迁移规范。当设计用户表/订单表等业务表、判断该不该拆表、加索引、写迁移脚本、或评审现有表结构时使用。
---

# 定位：预制规范，不是教科书

**表设计的目标不是「符合 3NF」，而是「一次查询能拿到页面需要的全部数据」。**

业务系统（OLTP）的查询频率远高于更新频率，所以适度反范式是对的。3NF 是为了避免更新异常，代价是查询变复杂——这个代价在业务系统里由每个页面每天支付。

---

## 一、拆表判断决策树（照这个走，不要凭感觉）

拿到一份字段清单，依次问：

```
1. 这组字段里，有没有「一个用户对应多条」的？
   → 有：拆成 1:N 子表（地址、银行卡、流水、日志）  ✅ 必须拆，不用犹豫
   → 没有：继续

2. 有没有 TEXT / BLOB / 超长 VARCHAR(2000+) 的字段，且不是每次都读？
   → 有：算行大小，单行 > 8KB 才拆出去
   → 没有：继续

3. 字段总数 > 150？
   → 是：按「访问频率」拆（高频轻字段一表，低频重字段一表）
   → 否：继续

4. 有没有合规/权限隔离要求？（身份证号独立加密、资金独立审计）
   → 有：只把那部分拆出去，其余留主表
   → 没有：继续

5. 不同字段的访问频率差 10 倍以上？（头像 base64 每次查用户都带出）
   → 是：拆那一个大字段
   → 否：**单表，不要拆**
```

**结论：30 个字段全部落在第 5 步的「否」，就是单表。**

---

## 二、1:1 拆表 vs 1:N 拆表（最关键的区分）

| 关系 | 含义 | 处理 |
|---|---|---|
| **1:N** | 一个用户有多条地址 / 多张银行卡 / 多条流水 | **必须拆**，这是关系型数据库的本职 |
| **1:1** | 一个用户有一个余额 / 一份资料 / 一个身份信息 | **默认不拆**，是有害的过早优化 |

agent 的典型错误：把「资金」当成一个独立实体拆出去，但实际上它只是用户的几个属性（余额、冻结额、累计充值、累计消费）。

**判断口诀：这个字段会有「第二行」吗？**
- 会有第二行（第二条地址、第二笔流水）→ 1:N，拆
- 永远只有一行（一个余额）→ 1:1，留在主表

---

## 三、30 个字段单表为什么完全没问题

### InnoDB 的真实约束

| 事实 | 数值 |
|---|---|
| 页大小 | 16 KB |
| 行格式 | DYNAMIC（MySQL 5.7+ 默认） |
| 单行建议上限 | **约 8 KB**（页的一半），超过触发行溢出 |
| 30 个常规字段的实际行大小 | INT 4B + BIGINT 8B + VARCHAR(64) 约 66B + DECIMAL(12,2) 6B |
| **30 字段估算** | **约 1–2 KB，占页 6%–12%** |

**结论：30 个常规字段的宽表，InnoDB 毫无压力。** 「字段多影响性能」在 MySQL 里是过时的担忧，除非你的字段全是 TEXT。

### 真正的性能影响在别处

- 索引数量与选择性
- 是否有大字段被无谓地 SELECT
- JOIN 的表数（超过 3 张就明显了）
- 慢查询、缺索引、N+1

**字段数量本身，在 50 个以内，几乎不影响性能。**

---

## 四、拆表的真实代价（agent 从来不算这笔账）

以用户表拆成 4 张为例：

| 维度 | 单表 | 拆 4 张 |
|---|---|---|
| 读用户详情 | 1 次 SELECT | 4 次查询 或 1 次 4 表 JOIN |
| 延迟（实测量级） | ~0.3 ms | ~1.2 ms |
| 注册（写） | 1 条 INSERT | **必须事务 + 4 条 INSERT** |
| 缓存 | 1 个 key | 4 个 key，失效要同步 |
| 代码量 | 1 model + 1 repo + 1 dto | 4 model + 4 repo + 4 dto |
| 迁移/备份 | 简单 | 4 张表要保证一致 |
| 审计 | 一张表看全 | 要跨表拼 |
| 出错概率 | 低 | 高（跨表一致性） |

**1:1 拆表在 JOIN 时没有任何性能收益**，只有成本。

---

## 五、必须拆的五个硬指标

只有命中这里才拆，且要在代码注释里写清命中了哪条：

1. **1:N 关系**（地址、银行卡、流水、日志、附件）
2. **行大小 > 8 KB**（大 TEXT/BLOB、base64 图片）
3. **字段数 > 150**
4. **合规/权限隔离**（身份证、支付信息需要独立加密与访问审计）
5. **访问频率差 10 倍以上**（某字段 95% 的请求都不需要）

---

## 六、案例：用户 30 个字段怎么落

### 正确设计

```
users                       单表，30 字段
  ├─ 基础：id, username, password, phone, email, status, role
  ├─ 资料：nickname, avatar_url, gender, birthday, province, city, bio
  ├─ 资金：balance, frozen_balance, total_recharge, total_consume
  ├─ 身份：real_name, id_card_no, verify_status, verify_at
  └─ 其他：last_login_at, last_login_ip, created_at, updated_at, deleted_at

user_addresses              1:N —— 地址可以多个
user_bank_cards             1:N —— 银行卡可以多张
wallet_transactions         1:N —— 资金流水，append-only
user_verify_logs            1:N —— 认证审核记录
```

**要点**：
- 余额、累计充值这类「只有一个值」的字段，**留在 users**
- 「有多条记录」的才独立成表
- `avatar_url` 存 URL 而不是 base64（这是最容易犯的错，动了就别放主表）

### 错误设计（agent 常给）

```
users            10 字段
user_profiles     8 字段   ← 1:1，错
user_wallets      5 字段   ← 1:1，错
user_identities   5 字段   ← 1:1，错
user_settings     5 字段   ← 1:1，错
```

**问题**：注册要开事务写 5 张表；查一次用户详情要 5 次查询；每个新字段都要先想"放哪张表"。

---

## 七、字段类型固定写法

| 类型 | 用什么 | 禁止 |
|---|---|---|
| 主键 | `BIGINT UNSIGNED AUTO_INCREMENT` | 不用 INT（几年就满）、不用 UUID 做主键（随机写放大） |
| 金额 | **`DECIMAL(12,2)`** | **禁止 FLOAT / DOUBLE**（精度丢失，0.1+0.2≠0.3） |
| 状态 | **`TINYINT`** + 代码里定义常量 | **禁止 ENUM**（加值要 DDL，迁移麻烦） |
| 布尔 | `TINYINT(1)` | — |
| 时间 | **`DATETIME`**（业务时间）/ `TIMESTAMP`（跨时区） | 不用字符串存时间 |
| 字符串 | `VARCHAR(长度)`，按实际需要给 | 不用 `VARCHAR(255)` 一刀切 |
| 手机号 | `VARCHAR(20)` | 不用数字（会丢前导 0、国际号段） |
| 身份证 | `VARCHAR(32)` + 加密存储 | — |
| JSON | `JSON` 类型（MySQL 5.7+） | 不用 TEXT 存 JSON |
| 大文本 | `TEXT` / `MEDIUMTEXT` | — |

### 必备字段（每张表都要）

```sql
id          BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
deleted_at  DATETIME NULL COMMENT '软删时间，NULL 为未删除',
```

**软删规则**：业务表默认软删。唯一索引要带 `deleted_at`，否则删除后无法用同一个用户名/手机号重新注册。

```sql
UNIQUE KEY uk_username (username, deleted_at)
```

---

## 八、命名规范

| 项 | 规则 | 例 |
|---|---|---|
| 表名 | 小写 + 下划线 + **复数** | `users` `order_items` |
| 字段名 | 小写 + 下划线 | `created_at` `order_no` |
| 索引 | `idx_字段` / `uk_字段` | `idx_status_created` `uk_phone` |
| 外键字段 | `关联表单数_id` | `user_id` `order_id` |
| 布尔字段 | `is_` / `has_` 前缀 | `is_vip` `has_paid` |
| 禁止 | 拼音、缩写、保留字 | ~~`yh_id`~~ ~~`desc`~~ |

**不使用物理外键约束**（`FOREIGN KEY`）：影响写入性能、迁移困难、分库分表时是障碍。**用应用层保证 + 索引加速**。

---

## 九、索引规范

### 必须建索引的场景

1. 所有 `WHERE` 高频条件字段
2. 所有 `JOIN` 的关联字段
3. 所有 `ORDER BY` 字段（配合 WHERE 做联合索引）
4. 唯一约束字段

### 联合索引顺序（最左前缀）

```sql
-- 查询：WHERE status = 1 AND created_at > '2026-01-01' ORDER BY created_at DESC
KEY idx_status_created (status, created_at)
```

**原则**：等值条件在前，范围/排序在后。**顺序错了索引就废了。**

### 索引的代价

- 每个索引都增加写入成本
- 单表索引 **不超过 5 个**，超过要审视查询
- 低选择性字段（如 `status` 只有 3 个值）单独建索引意义不大，要做联合索引

### 禁止

- 在 `SELECT *` 上加索引指望覆盖
- 给每个字段都建索引（写入会崩）
- 用函数包裹索引字段：`WHERE DATE(created_at) = '2026-01-01'` 索引失效，改成范围查询

---

## 十、审计设计（先问查询，再定表数）

### 10.1 第一步不是建表，是列查询

审计表建几张，由**要回答什么问题**决定。先列出来：

| 要回答的问题 | 需要的字段 |
|---|---|
| Q1 这条记录谁改过？ | `record_id` + `operator_id` + 时间索引 |
| Q2 每次改了哪些字段、从什么变成什么？ | 字段级 diff（JSON） |
| Q3 某人某段时间改了哪些记录？ | `operator_id` + `created_at` 索引 |
| Q4 某时间点这条记录完整长什么样？ | **完整快照** |
| Q5 审计记录不能被篡改（等保/财务） | 哈希链 + 只读账号 |

**Q1+Q2+Q3 → 1 张表就够。** 只有需要 Q4 才加第二张。

### 10.2 需求分档（对号入座，不要越档）

| 真实需求 | 方案 | 额外表数 |
|---|---|---|
| 只想显示"最后修改人/时间" | **主表加 `updated_by` 字段**，用已有 `updated_at` | **0** |
| 要查变更历史列表（谁改过） | `audit_logs` | 1 |
| 要看字段级 diff | `audit_logs` + `changes JSON` | 1 |
| 要还原某时间点完整记录 | `+ audit_snapshots` | 2 |
| 等保/财务合规（防篡改） | 上面 + 哈希链 + 独立只读账号 | 2~3 |

**最常见的情况是第一行。** agent 一上来就建审计表，但需求只是"页面上显示最后修改人"——加一个 `updated_by` 就够，零额外表。

### 10.3 关键：JSON 让「明细表」消失

MySQL 5.7 之前，存字段级变更必须建明细表：

```sql
-- 老方案（3 张表）
audit_logs(id, table_name, record_id, action, operator_id, created_at)
audit_details(id, audit_id, field_name, old_value, new_value)   ← 现在不需要了
audit_snapshots(...)
```

有了 `JSON` 类型，`details` 直接内嵌：

```json
{
  "amount":   { "old": 100.00, "new": 120.00 },
  "status":   { "old": 1,      "new": 2 },
  "remark":   { "old": "",     "new": "客户要求改价" }
}
```

**表数从 3 降到 1。** 查询也简单：`WHERE JSON_EXTRACT(changes, '$.amount') IS NOT NULL`，或直接在应用层解析。

### 10.4 标准表结构（默认方案）

```sql
CREATE TABLE audit_logs (
  id            BIGINT       PRIMARY KEY AUTO_INCREMENT,
  table_name    VARCHAR(64)  NOT NULL COMMENT '被审计的表',
  record_id     BIGINT       NOT NULL COMMENT '被审计记录的主键',
  action        VARCHAR(16)  NOT NULL COMMENT 'create/update/delete/restore',
  changes       JSON         NOT NULL COMMENT '字段级 diff，见上',
  operator_id   BIGINT       NOT NULL,
  operator_name VARCHAR(64)  NOT NULL COMMENT '**冗余姓名，不许省**',
  ip            VARCHAR(45)  NULL,
  request_id    VARCHAR(64)  NULL COMMENT '串起同一请求的多个变更',
  created_at    DATETIME(3)  NOT NULL COMMENT '毫秒精度，同秒多次变更也能排序',
  KEY idx_table_record (table_name, record_id, created_at),
  KEY idx_operator (operator_id, created_at),
  KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审计日志（append-only）';
```

**三个容易做错的点**：

1. **`operator_name` 必须冗余存**。只存 `operator_id` 的话，用户改名后历史记录就查不出"当时是谁"。审计日志是不可变的，必须自包含。
2. **`DATETIME(3)` 带毫秒**。秒级精度在同秒多次变更时无法确定顺序。
3. **`request_id`**。一次业务操作可能改多张表，靠 request_id 能把它们串成一组。

### 10.5 需要历史回看时才加快照表

```sql
CREATE TABLE audit_snapshots (
  id           BIGINT      PRIMARY KEY AUTO_INCREMENT,
  table_name   VARCHAR(64) NOT NULL,
  record_id    BIGINT      NOT NULL,
  audit_log_id BIGINT      NOT NULL COMMENT '对应哪次变更',
  data         JSON        NOT NULL COMMENT '变更后的完整记录',
  created_at   DATETIME(3) NOT NULL,
  KEY idx_table_record (table_name, record_id, created_at),
  KEY idx_audit (audit_log_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

查询"3 月 5 日这单什么样"：

```sql
SELECT data FROM audit_snapshots
 WHERE table_name='orders' AND record_id=? AND created_at <= '2026-03-05 23:59:59'
 ORDER BY created_at DESC LIMIT 1;
```

**不要用「版本链表」改造主表**（加 `version` / `valid_from` / `valid_to`）——它会让所有查询都要带 `valid_to IS NULL`，忘一次就查出错数据，而主表也会膨胀。审计放附属表更安全。

### 10.6 合规场景：哈希链 + 只读账号

```sql
ALTER TABLE audit_logs
  ADD COLUMN prev_hash   CHAR(64) NOT NULL DEFAULT '',
  ADD COLUMN record_hash CHAR(64) NOT NULL DEFAULT '';
```

```go
// 写入时计算：任何一条被改，后续整链断裂
h := sha256.Sum256([]byte(prevHash + tableName + recordID + action + string(changes) + createdAt))
```

配套：
- 创建一个**只能 INSERT / SELECT** 的数据库账号，应用写审计用这个账号
- 审计表**禁止 UPDATE / DELETE**（业务账号无此权限）
- 定期归档到只读存储（对象存储 + 对象锁）

### 10.7 性能与运维

| 问题 | 做法 |
|---|---|
| 表快速增长 | 按月分区（`PARTITION BY RANGE (TO_DAYS(created_at))`）或定期归档到归档表 |
| 写入阻塞业务 | 低频场景：与业务同事务（强一致）；高频场景：写队列 + worker 异步落库 |
| 大字段变更 | `changes` 里不存大字段的值，存 `{"avatar_url": {"changed": true}}` |
| 索引过多 | 只保留上面三个索引，别再给 `action` 单独建（选择性太低） |
| 查询慢 | 查审计一定是按 `table_name + record_id` 或 `operator_id + 时间`，这两个索引覆盖 99% 场景 |

**同步还是异步的判断**：审计量 < 每秒几十条 → 同事务；更高 → 异步 + 失败补偿。**不要为了"不丢审计"把所有业务都变慢。**

### 10.8 反面清单

1. ❌ 需求只是"显示最后修改人"，却建了审计表 → 主表加 `updated_by` 即可
2. ❌ 建 `audit_details` 明细表 → 用 `changes JSON`
3. ❌ 审计表只存 `operator_id` 不存姓名
4. ❌ `created_at` 用秒级精度
5. ❌ 用触发器做审计 → 逻辑藏在数据库里，调试痛苦、性能损耗、迁移困难
6. ❌ 把主表改造成版本链表（`valid_from/valid_to`）
7. ❌ 应用账号对审计表有 UPDATE/DELETE 权限
8. ❌ 用 binlog/CDC 做审计（一人项目运维成本过高）
9. ❌ 审计表不建 `(table_name, record_id)` 联合索引

## 十一、迁移规范

```
migrations/
├── 0001_init.sql
├── 0002_add_user_verify.sql
└── 0003_add_order_index.sql
```

**规则**：
1. 文件名 `序号_动作.sql`，序号四位递增
2. **一个迁移只做一件事**（加表 / 加字段 / 加索引分开）
3. **禁止修改已执行的迁移文件**，改动一律新建
4. 加字段必须给默认值或允许 NULL，否则大表会锁表
5. 大表加索引用 `ALTER TABLE ... ADD INDEX ..., ALGORITHM=INPLACE, LOCK=NONE`
6. 开发期用 GORM `AutoMigrate`，**生产环境必须走迁移文件**，不能靠 AutoMigrate

---

## 十二、评审清单

- [ ] 每个拆出去的表都能说出命中了第五节哪条硬指标
- [ ] 没有 1:1 拆表（除了合规/大字段）
- [ ] 金额是 `DECIMAL` 不是 `FLOAT`
- [ ] 状态是 `TINYINT` 不是 `ENUM`
- [ ] 每张表有 `id / created_at / updated_at / deleted_at`
- [ ] 软删表的唯一索引含 `deleted_at`
- [ ] 没有物理外键约束
- [ ] 所有 WHERE / JOIN / ORDER BY 字段有索引
- [ ] 联合索引顺序符合最左前缀
- [ ] 单表索引 ≤ 5 个
- [ ] 没有 `VARCHAR(255)` 一刀切
- [ ] 没有拼音/缩写字段名
- [ ] 生产环境不用 AutoMigrate

---

### 审计（有审计需求时）

- [ ] 审计表数符合需求档位（没有为「只显示最后修改人」建审计表）
- [ ] 没有 `audit_details` 明细表（字段级 diff 用 `changes JSON`）
- [ ] `audit_logs` 有 `operator_name` 冗余字段
- [ ] `created_at` 是 `DATETIME(3)`（毫秒精度）
- [ ] 有 `(table_name, record_id, created_at)` 联合索引
- [ ] 有 `request_id` 串联同一请求的多表变更
- [ ] 应用账号对审计表**无** UPDATE / DELETE 权限
- [ ] 没有用触发器做审计

---

## 十三、七条反面清单

1. ❌ 按「主题」机械拆 1:1 表（资料/资金/身份/设置）
2. ❌ 用 `FLOAT` 存金额
3. ❌ 用 `ENUM` 存状态
4. ❌ 用 UUID 做主键（随机写放大，页分裂）
5. ❌ 软删表的唯一索引不带 `deleted_at`
6. ❌ `WHERE DATE(created_at) = ?` 这种函数包裹导致索引失效
7. ❌ 用 `SELECT *` 把大字段一起查出来
