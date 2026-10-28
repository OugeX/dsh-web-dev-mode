---
name: deployment-ops
description: 本地开发环境与生产环境的部署运维规范。本地：Mac/Linux 用 Docker 并复用已有 MySQL/Redis 容器（一实例多库），Windows 不用 WSL 改原生安装（含 Windows 无官方 Redis 的替代方案：Garnet/Memurai/社区移植版）。生产：Linux + Docker 编排、多阶段构建、健康检查与回滚，以及系统性性能调优（sysctl 内核参数、BBR、文件句柄、MySQL innodb_buffer_pool 与 flush 策略、Redis 内存策略、Go GOMAXPROCS/GOMEMLIMIT、Docker 资源限制与日志切割）。当搭本地开发环境、写 Dockerfile/compose、部署上线、或做服务器性能压榨时使用。
---

# 定位：本地求稳，生产求榨

**两个环境目标不同**：
- **本地**：环境一致、切换快、不污染宿主。性能不重要。
- **生产**：榨干硬件、可回滚、出问题能定位。一致性靠镜像保证。

---

## 一、本地开发 · Mac / Linux

### 1.1 基础策略：Docker + 复用已有容器

**不要每个项目起一套 MySQL/Redis**。一个实例跑多个库即可：

```sql
CREATE DATABASE proj_a CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE proj_b CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Redis 用 **database 编号**隔离（`SELECT 0/1/2`，共 16 个），或直接用 **key 前缀**（更推荐，因为 Redis Cluster 不支持多 DB）。

### 1.2 复用容器的两种接法

**接法 A：宿主机端口映射（推荐）**

```yaml
# ~/docker/infra/docker-compose.yml  —— 全局基础设施，一次起好长期复用
services:
  mysql:
    image: mysql:8.0
    ports: ["127.0.0.1:3306:3306"]
    environment:
      MYSQL_ROOT_PASSWORD: root
      TZ: Asia/Shanghai
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --default-time-zone=+08:00
    volumes:
      - mysql_data:/var/lib/mysql        # ← named volume，必须
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports: ["127.0.0.1:6379:6379"]
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  mysql_data:
  redis_data:
```

项目连 `127.0.0.1:3306` / `127.0.0.1:6379`。**最简单，项目本身不需要进容器**（Go 直接 `go run` 跑在宿主机，热重载最快）。

**接法 B：Docker 网络**

项目容器加入 infra 的网络，用服务名访问（`mysql:3306`）。只在"项目整体容器化"时用。

### 1.3 三条硬规则

**① 数据卷必须用 named volume，不要 bind mount**

```yaml
volumes:
  - mysql_data:/var/lib/mysql      # ✅
  # - ./data/mysql:/var/lib/mysql  # ❌ Mac 上极慢
```

Mac 的 Docker Desktop 对 bind mount 有文件系统转换层（gRPC-FUSE / VirtioFS），MySQL 的随机 IO 会被拖慢 3–10 倍，还容易损坏 InnoDB 文件。**Linux 上 bind mount 性能尚可，但为了配置一致，也建议 named volume。**

**② 端口只映射到 `127.0.0.1`**

```yaml
ports: ["127.0.0.1:3306:3306"]   # ✅ 仅本机
# ports: ["3306:3306"]           # ❌ 局域网可访问
```

后者在咖啡厅/公司网络里等于把 MySQL 裸奔出去。

**③ 一个 infra compose 长期跑，不随项目启停**

放 `~/docker/infra/`，`docker compose up -d` 一次，之后所有项目共用。

### 1.4 性能预期（要心里有数）

| 环境 | MySQL 相对原生性能 |
|---|---|
| Linux 原生 | 100% |
| Linux Docker | 95–98% |
| Mac Docker（VirtioFS） | 60–75% |
| Mac Docker（bind mount） | **30–50%，不推荐** |

本地开发够用。**如果觉得慢，先检查是不是 bind mount 了数据目录。**

---

## 二、本地开发 · Windows

### 2.1 不用 WSL（你的判断是对的）

WSL2 的坑：
- `/mnt/c` 跨文件系统 IO 慢 10–20 倍
- WSL 的 IP 每次重启会变，端口转发要动态配置
- Go 在 WSL 编译的是 Linux 二进制，调试链路多一层
- 文件监听（air / fsnotify）在跨文件系统时不触发

**Windows 上直接原生跑**，Go 用 Windows 版，MySQL/Redis 用原生服务。

### 2.2 MySQL：原生安装

```powershell
# 用官方 MSI Installer，或 winget
winget install Oracle.MySQL
```

安装时选 **Server only**，字符集设 `utf8mb4`，时区 `+08:00`。之后：

```powershell
mysql -u root -p -e "SELECT VERSION();"
```

**注意**：Windows 的 MySQL 默认 `lower_case_table_names=1`（表名小写），Linux 默认 `0`。**这个差异会导致开发能跑、上线报表不存在**。在 `my.ini` 里显式设为 `1` 或 `0`，两边保持一致（建议都设 `1` 或都不依赖大小写）。

### 2.3 Redis：Windows 上没有官方版本（关键事实）

**redis.io 官方不提供 Windows 版本。** 网上搜到的"Windows 版 Redis"多半是 2016 年的 3.0.504，没有 Stream、没有 ACL、没有 Redis 6/7 的特性，**用了会在生产环境踩坑**。

三个可用方案：

| 方案 | 说明 | 推荐度 |
|---|---|---|
| **Garnet** | 微软研究院开源（2024），**原生支持 Windows**，Redis 协议兼容，性能极好 | ⭐⭐⭐ 首选 |
| **Memurai** | 商业产品，Redis 兼容，有免费 Developer Edition | ⭐⭐ 省事 |
| **tporadowski/redis** | 社区维护的 Windows 移植版（5.0.x） | ⭐ 能用但版本旧 |

**推荐 Garnet**：

```powershell
# 从 GitHub 下载 release 的 zip，解压后直接跑
.\GarnetServer.exe --port 6379 --memory 256m
```

**注意兼容边界**：Garnet 兼容 Redis 协议，但少数命令和模块（如部分 Lua 行为、RedisJSON、RediSearch）不支持。**如果你的代码只用到 String/Hash/List/Set/ZSet/过期/事务，完全没问题。**

### 2.4 Windows 开发的三条注意

1. **路径分隔符**：代码里一律用 `filepath.Join`，不要手拼 `/`
2. **换行符**：Git 配 `core.autocrlf=input`，避免整仓 diff
3. **文件锁**：Windows 不允许删除被打开的文件，日志轮转、热重载会因此失败 —— 用 `air` 时注意 exclude `tmp/`

---

## 三、生产环境 · Docker 部署

### 3.1 多阶段构建（Go）

```dockerfile
FROM golang:1.25-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/app ./cmd/api

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata && \
    adduser -D -H -u 10001 app
ENV TZ=Asia/Shanghai
WORKDIR /app
COPY --from=builder /out/app /app/app
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/api/health || exit 1
ENTRYPOINT ["/app/app"]
```

**要点**：
- `CGO_ENABLED=0` → 静态二进制，不依赖 glibc
- `-s -w` 去符号表，体积小 30%
- **非 root 用户运行**
- `HEALTHCHECK` 必须有，编排靠它判断存活
- 最终镜像 **< 30MB**

### 3.2 生产 compose

```yaml
services:
  app:
    image: registry.example.com/myapp:${TAG}
    restart: unless-stopped
    env_file: .env.prod
    expose: ["8080"]                       # 不映射到宿主机，只给 nginx 访问
    deploy:
      resources:
        limits:   { cpus: "2", memory: 1G }
        reservations: { cpus: "0.5", memory: 256M }
    logging:
      driver: json-file
      options: { max-size: "50m", max-file: "5" }   # ← 不配会撑爆磁盘
    depends_on: [mysql, redis]

  nginx:
    image: nginx:1.27-alpine
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
      - ./storage:/data/app/storage:ro     # 本地存储时
    logging:
      driver: json-file
      options: { max-size: "50m", max-file: "5" }

  mysql:
    image: mysql:8.0
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
      - ./my.cnf:/etc/mysql/conf.d/my.cnf:ro
    # 不要映射 3306 到宿主机
    logging:
      driver: json-file
      options: { max-size: "50m", max-file: "5" }

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "/usr/local/etc/redis/redis.conf"]
    volumes:
      - redis_data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf:ro
    logging:
      driver: json-file
      options: { max-size: "20m", max-file: "3" }

volumes:
  mysql_data:
  redis_data:
```

**四条必须**：
1. **`logging` 必须设 `max-size`** —— 不配的话单个容器日志能涨到几十 GB，磁盘满 = 全站挂
2. **`restart: unless-stopped`** —— 服务器重启后自动起
3. **DB 端口不映射到宿主机** —— 只让 app 通过内部网络访问
4. **资源 limits** —— 防止一个容器吃光内存触发 OOM killer 杀掉别的

### 3.3 网络模式选择

| 模式 | 开销 | 何时用 |
|---|---|---|
| `bridge`（默认） | 有 NAT，多一次 netfilter | 一般场景，够用 |
| `host`（Linux） | 无 NAT，性能最好 | 单机、追求极致吞吐、不想配端口映射 |
| `macvlan` | 接近物理网卡 | 需要独立 IP 时 |

**追求性能就用 `network_mode: host`**，代价是容器网络与宿主共享（端口冲突要自己管）。对单机部署的一人项目是划算的。

### 3.4 部署与回滚

```bash
#!/usr/bin/env bash
# deploy.sh  —— 失败自动回滚
set -euo pipefail
TAG="$1"
PREV=$(docker compose ps -q app | xargs -r docker inspect -f '{{.Config.Image}}' 2>/dev/null || echo "")

TAG=$TAG docker compose pull app
TAG=$TAG docker compose up -d --no-deps app

# 等健康检查通过（最多 60 秒）
for i in $(seq 1 30); do
  s=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q app)")
  [ "$s" = "healthy" ] && { echo "✅ 部署成功 $TAG"; exit 0; }
  sleep 2
done

echo "❌ 健康检查失败，回滚到 $PREV"
[ -n "$PREV" ] && docker tag "$PREV" registry.example.com/myapp:rollback && \
  docker compose up -d --no-deps --force-recreate app
exit 1
```

**没有自动回滚的部署脚本等于没有部署方案。**

---

## 四、SSH 直连部署与文件传输

### 4.1 为什么 SSH 是最通用的通道

| 方式 | 依赖 | 适用 |
|---|---|---|
| **SSH** | 只要服务器开了 sshd | 任何 Linux 服务器，**首选** |
| 云厂商 API / CLI | 厂商 SDK + AK/SK | 只能在你绑定的云上 |
| Registry + pull | 自建/云 registry | 要额外维护 registry |
| CI/CD 平台 | 平台账号 | 重，一人项目没必要 |

SSH 是唯一"什么服务器都能用"的方式。**部署、上传、执行远程命令、看日志，一条通道全包。**

---

### 4.2 认证：密码能用，但应该升级成密钥

老大给的是 IP / 用户名 / 密码 / 端口——**能用，但每次都要交互输密码，无法自动化**。

| 方式 | 自动化 | 安全 | 配置成本 |
|---|---|---|---|
| 密码 | 需要 `sshpass` / `plink -pw`（密码会出现在进程列表） | 低（可被爆破） | 0 |
| **SSH 密钥** | **原生免密** | 高 | **一次性 5 分钟** |

**强烈建议一次性配好密钥**，之后永久免密，比每次输密码省事得多，也更安全。

#### 一次性配置（Windows PowerShell）

```powershell
# ① 生成密钥（ed25519 比 RSA 更短更安全）
ssh-keygen -t ed25519 -C "deploy@myapp" -f $env:USERPROFILE\.ssh\id_deploy

# ② 上传公钥（这一步还要输一次密码）
type $env:USERPROFILE\.ssh\id_deploy.pub |
  ssh -p 22 user@1.2.3.4 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

# ③ 之后免密
ssh -i $env:USERPROFILE\.ssh\id_deploy -p 22 user@1.2.3.4 "echo ok"
```

#### 一次性配置（Linux / Mac）

```bash
ssh-keygen -t ed25519 -C "deploy@myapp" -f ~/.ssh/id_deploy
ssh-copy-id -i ~/.ssh/id_deploy.pub -p 22 user@1.2.3.4
ssh -i ~/.ssh/id_deploy -p 22 user@1.2.3.4 "echo ok"
```

#### 如果只能用密码（临时服务器）

Linux / Mac：
```bash
sshpass -p "$DEPLOY_PASS" ssh -p 22 user@host "命令"
```

Windows（装 PuTTY，用 plink）：
```powershell
plink -ssh -P 22 -pw $env:DEPLOY_PASS user@host "命令"
```

**注意**：`sshpass -p` 和 `plink -pw` 会让密码出现在 `ps aux` 进程列表里。**只在个人开发机上用，不要在共享机器上用。**

---

### 4.3 `~/.ssh/config` 别名 + 连接复用（必配）

```sshconfig
Host prod
    HostName 1.2.3.4
    User deploy
    Port 22
    IdentityFile ~/.ssh/id_deploy
    ServerAliveInterval 30
    # 连接复用：多条命令共用一个 TCP+SSH 连接，握手开销几乎归零
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h-%p
    ControlPersist 10m
```

之后所有命令简化为：

```bash
ssh prod "docker compose ps"
scp ./app prod:/opt/app/
```

**`ControlMaster` 的价值**：部署脚本里通常会连续执行 5–10 条 SSH 命令，没有复用时每次都要完整握手（100–300ms），有了复用是毫秒级。**这是最容易被忽略的提速项。**

Windows 的 OpenSSH 也支持这套配置（`%USERPROFILE%\.ssh\config`）。

---

### 4.4 上传方案：tar over SSH 最可靠

| 方案 | 增量 | 跨平台 | 依赖 | 评价 |
|---|---|---|---|---|
| `scp -r` | ❌ 全量 | ✅ | 无 | 简单可靠，文件多时慢 |
| `rsync -avz` | ✅ 增量 | ⚠️ **Windows 无内置** | 要装 cwRsync | Linux/Mac 最佳 |
| **`tar czf - \| ssh`** | ❌ 全量但**单流高效** | ✅ **两端都自带** | 无 | **跨平台首选** |
| `docker save \| ssh docker load` | — | ✅ | 无 | 镜像传输专用 |

#### 推荐：tar over SSH

```bash
# Linux / Mac
tar czf - -C ./dist . | ssh prod "mkdir -p /opt/app/public && tar xzf - -C /opt/app/public"

# Windows PowerShell（同样能用，走内置 tar + ssh）
tar -czf - -C .\dist . | ssh prod "mkdir -p /opt/app/public && tar -xzf - -C /opt/app/public"
```

**为什么它最好**：
- 一条命令完成打包→传输→解压，中间不落临时文件
- 两端都不需要额外工具（tar、ssh 都是系统自带）
- 单流传输，比 `scp -r` 传上千个小文件快得多（scp 每个文件都要往返）

#### Linux/Mac 上 rsync 更好（要增量时）

```bash
rsync -avz --delete --progress ./dist/ prod:/opt/app/public/
```

**`--delete` 慎用**：它会删除目标端多余文件。第一次用先 `--dry-run`。

#### 传输 Docker 镜像（没有 registry 时）

```bash
# 本地构建
docker build -t myapp:$TAG .

# 直接流式传到服务器加载，不落中间文件
docker save myapp:$TAG | gzip | ssh prod "gunzip | docker load"

# 服务器上重启
ssh prod "cd /opt/app && TAG=$TAG docker compose up -d --no-deps app"
```

**这一招解决了一人项目"没有私有 registry"的问题**，比搭 Harbor 省事得多。

---

### 4.5 完整部署脚本

#### Linux / Mac（`deploy.sh`）

```bash
#!/usr/bin/env bash
set -euo pipefail
TAG="${1:?用法: ./deploy.sh <tag>}"
HOST=prod

echo "▶ 1/6 本地构建"
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o ./build/app ./cmd/api

echo "▶ 2/6 连通性检查"
ssh -o ConnectTimeout=5 "$HOST" "echo ok" >/dev/null || { echo "❌ SSH 不通"; exit 1; }

echo "▶ 3/6 备份当前版本"
ssh "$HOST" "cp -r /opt/app/bin /opt/app/bin.bak.\$(date +%s) 2>/dev/null || true"

echo "▶ 4/6 上传二进制"
tar czf - -C ./build . | ssh "$HOST" "tar xzf - -C /opt/app/bin"

echo "▶ 5/6 重启服务"
ssh "$HOST" "sudo systemctl restart myapp"

echo "▶ 6/6 健康检查"
for i in $(seq 1 15); do
  if ssh "$HOST" "curl -sf http://127.0.0.1:8080/api/health >/dev/null"; then
    echo "✅ 部署成功 $TAG"; exit 0
  fi
  sleep 2
done

echo "❌ 健康检查失败，回滚"
ssh "$HOST" "cp -f /opt/app/bin.bak.* /opt/app/bin/app 2>/dev/null; sudo systemctl restart myapp"
exit 1
```

#### Windows PowerShell（`deploy.ps1`）

```powershell
param([Parameter(Mandatory)][string]$Tag)
$ErrorActionPreference = "Stop"
$Host = "prod"

Write-Host "▶ 1/6 本地构建"
$env:CGO_ENABLED="0"; $env:GOOS="linux"; $env:GOARCH="amd64"
go build -trimpath -ldflags="-s -w" -o .\build\app.exe .\cmd\api
if ($LASTEXITCODE -ne 0) { throw "构建失败" }

Write-Host "▶ 2/6 连通性检查"
ssh -o ConnectTimeout=5 $Host "echo ok"
if ($LASTEXITCODE -ne 0) { throw "SSH 不通" }

Write-Host "▶ 3/6 备份"
ssh $Host "cp -r /opt/app/bin /opt/app/bin.bak.`$(date +%s) 2>/dev/null || true"

Write-Host "▶ 4/6 上传"
tar -czf - -C .\build . | ssh $Host "tar xzf - -C /opt/app/bin"
if ($LASTEXITCODE -ne 0) { throw "上传失败" }

Write-Host "▶ 5/6 重启"
ssh $Host "sudo systemctl restart myapp"

Write-Host "▶ 6/6 健康检查"
for ($i=0; $i -lt 15; $i++) {
  ssh $Host "curl -sf http://127.0.0.1:8080/api/health"
  if ($LASTEXITCODE -eq 0) { Write-Host "✅ 部署成功 $Tag"; exit 0 }
  Start-Sleep -Seconds 2
}
throw "健康检查失败，请手动回滚"
```

---

### 4.6 交叉编译（在 Windows 上出 Linux 二进制）

**不要在服务器上装 Go。** 本地交叉编译：

```powershell
$env:CGO_ENABLED="0"; $env:GOOS="linux"; $env:GOARCH="amd64"
go build -trimpath -ldflags="-s -w" -o .\build\app .\cmd\api
```

`CGO_ENABLED=0` 是关键——静态链接，不依赖服务器上的 glibc 版本。

**ARM 服务器**（部分云厂商）：`GOARCH=arm64`。

---

### 4.7 sudo 的处理

部署用户通常不是 root，重启服务要 sudo，会卡在密码提示。

两个方案：

**方案 A：NOPASSWD（推荐，限定命令）**
```bash
# 服务器上
echo "deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart myapp, /bin/systemctl status myapp" \
  | sudo tee /etc/sudoers.d/deploy-myapp
sudo chmod 440 /etc/sudoers.d/deploy-myapp
```
**只授权特定命令**，不要 `NOPASSWD: ALL`。

**方案 B：user-level systemd**（服务以部署用户身份跑）
```bash
ssh prod "systemctl --user restart myapp"
```
需要 `loginctl enable-linger deploy`，否则用户登出服务就停。

---

### 4.8 安全红线（这几条必须守住）

| # | 红线 | 后果 |
|---|---|---|
| 1 | **密码不写进代码、不写进 `.env` 提交、不打印到日志** | 泄漏后服务器任人进 |
| 2 | **密码不长期留在对话/文档里** | 同上。**配好密钥后应立刻作废或更换那个密码** |
| 3 | `.ssh/`、`.env.deploy`、`*.pem` 必须在 `.gitignore` | 一次误提交 = 永久泄漏 |
| 4 | 部署日志里不输出完整命令（可能含密码参数） | `set -x` 要慎用 |
| 5 | 生产服务器建议**禁用密码登录**（只留密钥） | 减少暴力破解面 |

**关于第 2 条特别提醒老大**：如果打算把服务器密码发给我用，建议改成——**你先在服务器上执行一次密钥配置，然后把密钥路径告诉我**；或者配好后把密码改掉。密码一旦进了对话记录，就按"已泄漏"处理。

禁用密码登录的正确姿势（避免把自己锁死）：

```bash
# ① 先确认密钥登录已经能用（另开一个终端测试成功）
# ② 再改配置
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sshd -t                      # 语法检查，必做
# ③ 重载（不要 restart，reload 不断开现有连接）
sudo systemctl reload sshd
# ④ 当前连接不要断，另开新终端验证能登
```

---

### 4.9 SSH + Docker 的组合

SSH 是**通道**，Docker 是**运行时**，两者不冲突：

```bash
# 方式 1：本地构建镜像 → 流式传到服务器加载（无 registry 时最实用）
docker save myapp:$TAG | gzip | ssh prod "gunzip | docker load"
ssh prod "cd /opt/app && TAG=$TAG docker compose up -d --no-deps app"

# 方式 2：源码传上去，服务器上构建（服务器性能好、或要复用层缓存时）
tar czf - --exclude=.git . | ssh prod "tar xzf - -C /opt/app/src"
ssh prod "cd /opt/app/src && docker compose build && docker compose up -d"

# 方式 3：推到 registry，服务器 pull（有多台服务器时）
docker push registry.example.com/myapp:$TAG
ssh prod "cd /opt/app && TAG=$TAG docker compose pull && docker compose up -d"
```

**一人项目推荐方式 1**：不需要搭 registry，不需要在服务器装 Go/Node，一条命令完成。

---

## 五、生产环境 · Linux 性能调优

### 4.1 内核参数（`/etc/sysctl.d/99-tuning.conf`）

```ini
# ── 网络：吞吐与连接数 ──
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 10000 65000
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_slow_start_after_idle = 0

# ── BBR 拥塞控制：吞吐提升最明显的一招 ──
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# ── 文件句柄 ──
fs.file-max = 1000000
fs.nr_open = 1000000

# ── 内存 ──
vm.swappiness = 10
vm.overcommit_memory = 1          # Redis fork 需要，否则可能 OOM
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
```

```bash
sysctl --system     # 生效
sysctl net.ipv4.tcp_congestion_control    # 确认 bbr
```

**`vm.overcommit_memory=1` 是 Redis 的硬要求**，否则 `bgsave` 时内存不够会失败。

### 4.2 文件句柄

```bash
# /etc/security/limits.d/99-nofile.conf
*  soft nofile 65535
*  hard nofile 65535
```

**systemd 服务要单独配**（limits.conf 对 systemd 不生效）：

```ini
# /etc/systemd/system/myapp.service
[Service]
LimitNOFILE=65535
```

### 4.3 MySQL 调优（`my.cnf`）

按 **16GB 内存 / 4 核 / SSD** 的机器举例：

```ini
[mysqld]
# ── 内存：buffer pool 是最大头 ──
innodb_buffer_pool_size = 10G            # 物理内存的 60-70%
innodb_buffer_pool_instances = 4         # 每 GB 一个，最多 8
innodb_log_file_size = 2G                # buffer pool 的 1/4
innodb_log_buffer_size = 64M

# ── 刷盘策略（性能 vs 安全的取舍，见下方警告）──
innodb_flush_log_at_trx_commit = 2       # 1=最安全 2=快（丢最近 1 秒）
innodb_flush_method = O_DIRECT
innodb_io_capacity = 2000                # SSD；HDD 用 200
innodb_io_capacity_max = 4000

# ── 连接 ──
max_connections = 300
wait_timeout = 600
interactive_timeout = 600

# ── 其他 ──
skip_name_resolve = ON                   # 避免反解 DNS 的开销
slow_query_log = ON
long_query_time = 1
```

**`innodb_flush_log_at_trx_commit` 的取舍必须说清**：

| 值 | 含义 | 丢数据风险 | 适用 |
|---|---|---|---|
| `1` | 每次提交都刷盘 | 不丢 | **账务、订单、任何不能丢的** |
| `2` | 每秒刷一次 | 掉电丢最近 1 秒 | 日志、统计、可重放的数据 |
| `0` | 交给 OS | 丢更多 | 不推荐 |

**默认给 `1`。** 除非确认数据可重放，才设 `2`。

### 4.4 Redis 调优（`redis.conf`）

```conf
maxmemory 8gb                    # 物理内存的 50-70%，留余量给 fork
maxmemory-policy allkeys-lru     # 纯缓存；持久数据用 noeviction
appendonly yes
appendfsync everysec             # 每秒刷，最多丢 1 秒
save ""                          # 只用 AOF 时关闭 RDB（省 fork 开销）
tcp-backlog 511
timeout 0
tcp-keepalive 300

# 大 key 保护
hash-max-listpack-entries 128
zset-max-listpack-entries 128
```

**注意**：`maxmemory-policy allkeys-lru` 会**随机淘汰**，包括你存的白名单 session。如果 Redis 同时存缓存和会话，要分开实例，或用 `volatile-lru`（只淘汰设了 TTL 的 key）。

### 4.5 Go 应用调优

```yaml
environment:
  GOMAXPROCS: "2"          # 与容器 CPU limit 一致
  GOMEMLIMIT: "800MiB"     # 容器 memory limit 的 80%
  GOGC: "100"              # 默认；内存充裕可调高到 200 减少 GC 频率
```

**`GOMEMLIMIT` 必须设**（Go 1.19+）：不设的话，Go 会一直申请内存直到被 cgroup OOM kill，表现为容器莫名其妙重启。

```go
// 也可以代码里设，避免依赖环境变量
debug.SetMemoryLimit(800 << 20)
```

**Go 1.25 已自动识别 cgroup 的 CPU limit**，但 `GOMEMLIMIT` 仍然是软限制，建议显式设。

### 4.6 磁盘与文件系统

```bash
# SSD 用 none，HDD 用 mq-deadline
echo none > /sys/block/sda/queue/scheduler

# 挂载参数
# /etc/fstab: noatime,nodiratime,discard
```

**`noatime`** 能减少每次读文件时的元数据写入，对小文件多的场景提升明显。

### 4.7 关闭不需要的东西

```bash
swapoff -a                    # 或 vm.swappiness=1
systemctl disable --now firewalld   # 如果前面有云防火墙
systemctl disable --now postfix
```

**swap 关闭的风险**：内存打满时进程直接被 OOM killer 杀。所以必须先设好 `GOMEMLIMIT` 和容器 limits，再关 swap。

### 4.8 压测验证（调优必须有基线）

```bash
# 接口压测
wrk -t4 -c400 -d30s http://127.0.0.1:8080/api/health

# 数据库压测
sysbench oltp_read_write --mysql-host=127.0.0.1 --tables=10 --table-size=1000000 run
```

**调优前先测一次，调优后再测一次。** 没有对比数据的"调优"都是猜测。

---

## 六、agent 接管边界（重要）

### 可以自己做

- 写 Dockerfile / compose / nginx.conf / my.cnf
- 构建镜像、启动容器、查看日志、重启服务
- 读取 `docker stats`、`docker inspect` 排查
- 写部署脚本、回滚脚本
- 生成调优配置**文件**

### 必须先问老大

| 操作 | 为什么 |
|---|---|
| **改内核参数并 `sysctl --system`** | 改错可能断网，无法远程恢复 |
| 改防火墙（`iptables` / `ufw`） | 可能把自己锁在外面 |
| 改 SSH 配置 | 同上 |
| 删除数据卷（`docker volume rm`） | 数据不可恢复 |
| `docker system prune -a` | 会删掉不在用的镜像和卷 |
| 调整 `innodb_flush_log_at_trx_commit` | 影响数据安全等级 |
| 关闭 swap | 影响 OOM 行为 |
| 重启数据库容器 | 有停机时间 |

### 绝对不能做

- 直接对生产库执行 `DROP` / `TRUNCATE` / 大批量 `UPDATE` / `DELETE`
- 在没有备份的情况下做结构变更
- 把 `.env.prod` 提交到仓库或打印到日志

---

## 七、验收清单

### 本地

- [ ] Mac/Linux 用 Docker，MySQL/Redis 数据卷是 **named volume**（不是 bind mount）
- [ ] 端口只映射 `127.0.0.1`
- [ ] 一个 infra compose 复用，不随项目启停
- [ ] 项目库用独立 database 名，Redis 用 key 前缀隔离
- [ ] Windows 没有用 WSL；MySQL 原生安装
- [ ] Windows 的 Redis 用 Garnet / Memurai / 5.0.x 移植版之一，**没有用 3.0.504**
- [ ] Windows 与 Linux 的 `lower_case_table_names` 一致

### 生产部署

- [ ] 多阶段构建，最终镜像 < 30MB
- [ ] 容器以非 root 运行
- [ ] 有 `HEALTHCHECK`
- [ ] 所有容器配了 `logging.max-size`
- [ ] `restart: unless-stopped`
- [ ] DB / Redis 端口未映射到宿主机
- [ ] 配了资源 limits
- [ ] 部署脚本含健康检查 + 自动回滚

### 性能调优

- [ ] `net.ipv4.tcp_congestion_control = bbr` 已生效
- [ ] `vm.overcommit_memory = 1`（有 Redis 时）
- [ ] 文件句柄 65535，systemd 服务单独配 `LimitNOFILE`
- [ ] `innodb_buffer_pool_size` 为内存的 60-70%
- [ ] `innodb_flush_log_at_trx_commit` 按数据重要性明确选择并记录理由
- [ ] Redis `maxmemory` 与淘汰策略明确
- [ ] Go 容器设了 `GOMEMLIMIT` 与 `GOMAXPROCS`
- [ ] 磁盘挂载含 `noatime`
- [ ] **有调优前后的压测对比数据**

---

## 八、反面清单

1. ❌ 每个项目起一套 MySQL/Redis 容器
2. ❌ Mac 上把 MySQL 数据目录 bind mount（性能腰斩 + 易损坏）
3. ❌ 端口映射到 `0.0.0.0:3306`
4. ❌ Windows 用 WSL 跑 Go 项目（IO 慢、端口转发坑）
5. ❌ Windows 装 3.0.504 版 Redis 当生产等价环境
6. ❌ 开发用 Windows、生产用 Linux 但没统一 `lower_case_table_names`
7. ❌ Docker 容器不配日志大小限制
8. ❌ DB 端口暴露到宿主机
9. ❌ Go 容器不设 `GOMEMLIMIT`（会被 OOM kill）
10. ❌ 盲目 `innodb_flush_log_at_trx_commit=2` 用在账务系统
11. ❌ 调优没有压测基线，凭感觉改参数
12. ❌ swap 和 `GOMEMLIMIT` 都不管，内存一满就被杀
