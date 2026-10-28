# 提交到 DSH 市场

## 已提交（2026-10-28）

| 市场 | PR | 状态 |
|---|---|---|
| [awesome-dsh-plugin](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin)（21k stars） | [#10150](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin/pull/10150) | open |
| [awesome-dsh-presets](https://github.com/hackerFish/awesome-dsh-presets)（preset 专收） | [#1](https://github.com/hackerFish/awesome-dsh-presets/pull/1) | open |

提交形式：
- 大市场：`data/plugins/OugeX__dsh-web-dev-mode.yml`，`category: workflow`
- preset 库：`presets/web-dev/{agent.cordis.yml,preset.yml}` + 两个 README 清单各加一行

**校验结果**：`validate-presets.mjs --harness <node_modules>` → `✅ web-dev（含包存在性校验）`，0 错误。

---


> **DSH 没有官方内置市场。** 源码 `packages/preset/agent-presets/` 里只有本地 preset 的扫描与创作能力（`discovery.ts` / `authoring.ts`），没有 registry、publish 或 marketplace 模块；`dsh` CLI 也只有 `web` 和 `plugin` 两个子命令。
>
> 所以「提交到市场」= 提交到**社区维护**的收录仓库或本地市场插件。

---

## 三个渠道

| 渠道 | 形态 | 适合 | 提交方式 |
|---|---|---|---|
| **[awesome-dsh-plugin](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin)** | 精选收录，最大 | plugins 为主 | Fork → 加 yml → PR（**当前是 yml-only workflow**） |
| **[awesome-dsh-presets](https://github.com/hackerFish/awesome-dsh-presets)** | 预设合集，中文优先 | **agent preset（最匹配）** | PR，需过结构与包存在性校验 |
| **[dsh-plugin-marketplace](https://github.com/AwesomeHou/dsh-plugin-marketplace)** · **[DSH-Marketplace](https://github.com/QT7-C23/DSH-Marketplace)** | 本地市场插件 | 想做一键安装入口 | 装插件后它 live-sync GitHub 的 `dsh-plugin` topic |

> 注意：第三个是**同步 topic**，不是接受 PR。给仓库打上对应 topic 就可能被扫到。

---

## 推荐路径：awesome-dsh-presets

因为它专门收 preset、中文优先、且有结构校验（说明维护质量高）。

### 提交前自检

这个仓库要求「结构与包存在性校验」，我们的包已经过一遍：

```bash
# 1. 结构
ls presets/web-dev/agent.cordis.yml presets/web-dev/preset.yml

# 2. 包存在性（用 DSH 自己的扫描器验证，应输出 OK 而非 BROKEN）
#    参考本仓库 docs/DESIGN.md 里的验证方式
```

**本仓库的 preset 已被 DSH 原生扫描器验证为 `OK`**（不是 broken），满足包存在性要求。

### PR 需要的材料

- 仓库地址：`https://github.com/OugeX/dsh-web-dev-mode`
- preset id：`web-dev`
- 显示名：`Web开发模式`
- 一句话说明：预制件形态的 Web 开发规范，12 个技能覆盖选型到部署
- 目标安装位置：`~/.dsh/.agent-presets/web-dev/` + `~/.dsh/skills/*`

具体目录结构与 yml 字段以对方 `contributing.md` 为准（本机 DNS 无法读取，需在浏览器打开确认）。

---

## 备选：先打 topic

如果暂时不想提 PR，可以给仓库加 topic，让 live-sync 类市场（渠道三）能扫到：

```bash
# 用 GitHub CLI（需先安装 gh 并登录）
gh repo edit OugeX/dsh-web-dev-mode \
  --add-topic dsh \
  --add-topic dsh-preset \
  --add-topic dsh-skill \
  --add-topic deepseek-harness
```

或用 API：

```bash
curl -X PUT \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/OugeX/dsh-web-dev-mode/topics \
  -d '{"names":["dsh","dsh-preset","dsh-skill","deepseek-harness","web-development"]}'
```

**是否生效取决于对方插件扫描的 topic 名**，需在插件设置里确认。

---

## 自动化工具

社区有一个一键发布工具：[7gzgn/dsh-slipway](https://github.com/7gzgn/dsh-slipway)

> Ship a local DSH plugin project to GitHub and the plugin market in one call: preflight, per-file upload with byte verification, the market registry PR, then pull every published file back and compare bytes.

它做的是：预检 → 逐文件上传校验 → **提交 market registry PR** → 回读比对。

⚠️ 它是为 **plugin（npm 包）** 设计的，本仓库是 **preset + skills（纯文件）**，不一定适用。用之前先确认它的 preflight 接受目录型项目。

---

## 我没有代做 PR 的原因

1. **需要你的 GitHub 身份** —— PR 会记在你名下，署名与责任应该是你的
2. **格式未确认** —— 本机 DNS 拦掉了 `raw.githubusercontent.com` 和镜像站，读不到对方的 `contributing.md`；按猜的格式提交会被退回
3. **提交前应该先看一遍对方的收录标准** —— 有的仓库明确不收"中文重度定制"或"非插件类"

---

## 建议顺序

1. 浏览器打开 [awesome-dsh-presets](https://github.com/hackerFish/awesome-dsh-presets)，看 README 和 contributing
2. 如果没有 contributing，直接开一个 issue 问「收不收 preset + skills 组合」
3. 格式确认后，按它的结构提 PR
4. 同时给仓库打 topic，覆盖 live-sync 类市场

**先问再加，比按猜的格式提 PR 快。**
