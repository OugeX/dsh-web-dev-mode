---
name: jwt-session-auth
description: JWT 鉴权与会话管理的完整方案。包含纯 JWT / Redis 白名单 / MySQL 审计双写的取舍、sessions 与 login_logs 建表、登录登出改密立刻失效的实现顺序、Redis miss 回查 MySQL 防重启掉线、refresh token 轮换、以及 alg=none、X-Forwarded-For 伪造、token 落库只存哈希等安全红线。当实现登录接口、鉴权中间件、权限控制、会话失效或踢人时使用。
---

# JWT 鉴权与会话

> **本 skill 是预制标准体系的一部分。** 起项目时鉴权要生成哪些文件见 `web-project-bootstrap` 第二节；本文负责方案取舍与实现细节。


---

## 一、前提：JWT 本身不需要存任何地方

JWT 是自包含签名令牌，验证只需密钥。要存的不是 token，是**会话状态**（撤销、踢人、设备列表）。

**决策表**：

| 需求 | 方案 | 代码量 |
|---|---|---|
| 无踢人需求、用户 < 1000 | 纯 JWT，什么都不存 | 30 行 |
| 要记录 IP/UA/时间 + 登出 + 改密失效 | **Redis + MySQL 双写** | 300 行 |
| 要做"登录设备管理"列表 | 上面 + sessions 表查询接口 | +80 行 |

**从第一档开始，需求出现再升级。**

---

## 二、为什么是双写，不是二选一

| 需求 | 存储特性 | 归谁 |
|---|---|---|
| 记录 IP/UA/时间、可查询审计 | 长期保存、要分页查、不能过期 | **MySQL** |
| 登出/改密后立刻失效 | 每请求一次、毫秒级 | **Redis** |

Redis 存不了历史（会过期、不能分页），MySQL 扛不了热路径（登录校验是每请求一次）。

**结论：两边都要写，职责不重叠。**

---

## 三、MySQL 两张表

**`sessions`** —— 有效会话，一条 = 一次登录

```sql
CREATE TABLE sessions (
  id             BIGINT       PRIMARY KEY AUTO_INCREMENT,
  user_id        BIGINT       NOT NULL,
  jti            CHAR(36)     NOT NULL COMMENT 'JWT ID',
  refresh_hash   CHAR(64)     NULL     COMMENT 'refresh token 的 SHA-256，绝不存原文',
  ip             VARCHAR(45)  NOT NULL COMMENT '支持 IPv6',
  ua             VARCHAR(512) NOT NULL,
  device         VARCHAR(64)  NULL     COMMENT '解析后设备名',
  login_at       DATETIME     NOT NULL,
  last_active_at DATETIME     NULL,
  logout_at      DATETIME     NULL,
  revoke_at      DATETIME     NULL,
  revoke_reason  VARCHAR(32)  NULL     COMMENT 'logout/password_change/force_kick/expired',
  expires_at     DATETIME     NOT NULL,
  UNIQUE KEY uk_jti (jti),
  KEY idx_user_valid (user_id, expires_at),
  KEY idx_login_at (login_at),
  KEY idx_cleanup (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**`login_logs`** —— 所有登录尝试，**含失败**，append-only

```sql
CREATE TABLE login_logs (
  id          BIGINT       PRIMARY KEY AUTO_INCREMENT,
  user_id     BIGINT       NULL,
  username    VARCHAR(64)  NOT NULL,
  ip          VARCHAR(45)  NOT NULL,
  ua          VARCHAR(512) NOT NULL,
  success     TINYINT      NOT NULL DEFAULT 0,
  fail_reason VARCHAR(64)  NULL,
  created_at  DATETIME     NOT NULL,
  KEY idx_user_time (user_id, created_at),
  KEY idx_username_time (username, created_at),
  KEY idx_ip_time (ip, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**为什么两张**：失败登录没有 session，必须单独记。不记失败就无法发现爆破。

---

## 四、Redis 键结构

```
sess:{jti}         string  "1"                TTL = expires_at - now
user:sess:{uid}    set     { jti1, jti2, ...} 用于批量踢人
login:fail:{name}  string  失败次数            TTL 15min，用于锁定
```

---

## 五、四个流程

### 登录

1. 校验密码（失败也写 `login_logs`）
2. 生成 `jti`
3. `INSERT INTO sessions (... ip, ua, login_at, expires_at)`
4. `SET sess:{jti}` TTL
5. `SADD user:sess:{uid} jti` + `EXPIRE`
6. 签发 JWT `{sub, jti, role, exp}`

### 请求校验（中间件）—— 最关键的一步

```
验签 → 取 jti → GET sess:{jti}
        │
        ├ hit  → 放行
        └ miss → 回查 MySQL sessions（jti 存在 且 revoke_at/logout_at 为空 且未过期）
                   ├ 命中 → 重建 Redis → 放行
                   └ 未命中 → 401
```

```go
ok, _ := rdb.Exists(ctx, "sess:"+claims.ID).Result()
if ok == 0 {
    sess, err := sessRepo.FindValidByJti(ctx, claims.ID)
    if err != nil { response.Unauthorized(c, "登录已失效"); return }
    ttl := time.Until(sess.ExpiresAt)
    if ttl <= 0 { response.Unauthorized(c, "登录已失效"); return }
    rdb.Set(ctx, "sess:"+claims.ID, "1", ttl)
}
```

**这一步不能省**：不做的话 Redis 一重启，所有用户当场掉线。做了之后 Redis 只是加速层，撤销仍然立刻生效——因为 MySQL 的 `revoke_at` 才是真相。

### 登出

```go
sessRepo.Revoke(ctx, jti, time.Now(), "logout")   // MySQL
rdb.Del(ctx, "sess:"+jti)                          // Redis
rdb.SRem(ctx, "user:sess:"+uid, jti)
```

### 改密后立刻失效

```go
tx.Transaction(func(tx *gorm.DB) error {
    tx.Model(u).Update("password", string(newHash))
    return tx.Model(&model.Session{}).
        Where("user_id = ? AND revoke_at IS NULL AND logout_at IS NULL", uid).
        Updates(map[string]any{
            "revoke_at":     time.Now(),
            "revoke_reason": "password_change",
        }).Error
})
// ⚠ 事务提交成功之后，才清 Redis
// SMEMBERS user:sess:{uid} → 逐个 DEL sess:{jti} → DEL user:sess:{uid}
```

**顺序不能颠倒**：先删 Redis 再提交事务，事务回滚就会出现"用户被踢了但密码没改"。测试环境几乎发现不了，上线才炸。

---

## 六、不做本地缓存

| 做本地缓存 | 不做 |
|---|---|
| 踢人延迟 = 缓存 TTL | 立刻就是立刻 |
| 多实例内存不一致 | 状态单一 |
| 多一层 | 简单 |

后台系统 QPS 不高，Redis 单次 0.5ms，**每次请求都打完全够**。需求写了"立刻失效"，就不要加缓存。

---

## 七、两个安全硬性要求

**1. `SetTrustedProxies` 必须配**

```go
r.SetTrustedProxies([]string{"127.0.0.1", "10.0.0.0/8"})
```

不配的话，任何人发 `X-Forwarded-For: 1.2.3.4` 就能伪造来源 IP，**审计功能形同虚设**。

**2. token 落库只存哈希**

```go
h := sha256.Sum256([]byte(refreshToken))
```

库泄露时，存原文 = 所有会话可被直接劫持。

---

## 八、JWT 安全清单

| # | 必须做 | 为什么 |
|---|---|---|
| 1 | `jwt.WithValidMethods([]string{"HS256"})` | 防 `alg=none` 伪造 |
| 2 | 显式要求 exp（`WithExpirationRequired`） | 否则永不过期 |
| 3 | 密钥 ≥ 32 字节随机 | HS256 密钥短了可暴力破解 |
| 4 | token 只走 `Authorization` 头 | 放 URL 会进日志和 Referer |
| 5 | 登出必须服务端撤销 | 只前端删 token 照样能用 |
| 6 | 改密作废该用户全部会话 | 用户的安全预期 |
| 7 | 登录接口限流 + 失败锁定 | 防撞库 |
| 8 | 敏感操作要求二次验证 | 不能只信 token |

---

## 九、Refresh Token

- access token：15–30 分钟
- refresh token：7–30 天

**必须一次性使用 + 轮换**：用一次就作废旧签发新。不轮换的话，refresh 被盗后攻击者能永久续期，你永远发现不了。轮换后攻击者用一次，真实用户下一次就失败——这就是泄露信号。

存放：access 放内存或 `Authorization` 头；refresh 放 **httpOnly cookie**（Web）或系统安全存储（App）。

---

## 十、last_active_at 不要每请求更新

热点行，每请求 UPDATE 会让 MySQL 写入翻倍、还有锁竞争。

- 需要就记 Redis `active:{jti}`（TTL 10 分钟），定时任务每 5 分钟批量回写
- 不需要就只记 `login_at`，大多数场景够用

---

## 十一、定时清理

```sql
-- 每天 03:00
DELETE FROM sessions   WHERE expires_at < NOW() - INTERVAL 30 DAY;
DELETE FROM login_logs WHERE created_at < NOW() - INTERVAL 180 DAY;
```

---

## 十二、依赖

```
github.com/golang-jwt/jwt/v5
github.com/redis/go-redis/v9
github.com/google/uuid
github.com/mileusna/useragent
golang.org/x/crypto/bcrypt
gorm.io/gorm
```
