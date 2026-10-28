# 自定义指南

---

## 一、改哪里

| 想改什么 | 改哪个文件 |
|---|---|
| 称呼、风格、五问铁律、交付节奏 | `presets/web-dev/agent.cordis.yml` 的 `persona.prefix` |
| 技能分工与触发场景 | `skills/web-project-bootstrap/SKILL.md` 的「零、技能路由表」 |
| 主力技术栈（探测不到时的默认） | `agent.cordis.yml` 的「铁律一」第 3 条 |
| 文件行数上限 | `web-project-bootstrap` 第五节「文件体量规范」 |
| 覆盖率目标 | `testing-strategy` 第六节 |
| 弹窗/抽屉尺寸 | `ui-ux-decision-guide` 第一节 |
| 脱敏规则 | `api-contract-design` 第三节 |
| 部署方式 | `deployment-ops` 第四节（SSH）或第三节（Docker） |

**改 skill 与 preset 都不用重启：刷新页面即可。** 下拉里看不到时再重启。

---

## 二、加一个新技能

### 1. 建目录

```bash
mkdir -p ~/.dsh/skills/my-new-skill
```

### 2. 写 SKILL.md

```markdown
---
name: my-new-skill
description: 一两句话说清「什么时候用」。要包含触发词，模型靠这段匹配。
---

# 定位

一句话说清这个技能解决什么。

## 一、决策表
（什么情况选什么，要给判据）

## 二、数字与阈值
（200 行、40%、15 分钟这种，模型需要数字）

## 三、模板
（可直接抄的正例代码）

## 四、验收清单
- [ ] 具体、可勾选

## 五、反面清单
❌ 不要这样做
```

**description 是关键**：模型靠它判断该不该加载。写清"当……时使用"，把用户可能说的词都带上。

### 3. 在路由表登记

编辑 `skills/web-project-bootstrap/SKILL.md` 的「零、技能路由表」，加一行：

```markdown
| 你在做什么 | 加载哪个 skill |
|---|---|
| ... | ... |
| **你的场景关键词** | `my-new-skill` |
```

**这一步不能省** —— persona 只指向 bootstrap，bootstrap 才是真正的路由。

### 4. 不用重启

skill 是热加载的，存盘即生效。

---

## 三、调整五问铁律

默认是必须问 5 个。想改成 3 个或换维度：

`agent.cordis.yml` → `铁律二：写代码前先问` → 改第 1 条和第 3 条。

**建议保留「一次问完」和「问完停下」两条**，那是它生效的关键。分散提问或边问边写都会退化。

---

## 四、换主力技术栈

当前默认：`Go + Gin + GORM + MySQL + React 19 + Vite + AntD 5 + TanStack Query`

改成 Vue 或 PHP：

1. `agent.cordis.yml` → 「铁律一」第 3 条 → 改栈描述
2. `agent.cordis.yml` → 「三条红线」→ 改主力栈那一行
3. `skills/web-tech-stack/SKILL.md` → 确认新栈有对应章节（没有就加）
4. `skills/web-project-bootstrap/SKILL.md` → 「一、选型决策表」→ 改对应行

---

## 五、调整严格程度

觉得太严（比如五问太啰嗦）：

| 调整 | 位置 |
|---|---|
| 减少提问维度 | 铁律二的五维列表 |
| 扩大「例外」范围 | 铁律二的例外条款 |
| 放宽行数上限 | web-project-bootstrap 第五节表格 |
| 降低覆盖率要求 | testing-strategy 第六节 |
| 允许直接上 OSS | media-file-management 第十一节判断表 |

觉得太松：

| 调整 | 位置 |
|---|---|
| 五问改成必须等回答 | 铁律二第 4 条加"未经回答不得写任何代码" |
| lint 规则加严 | react-frontend-architecture 第十一节 |
| 测试禁止 mock | testing-strategy 第三节 |

---

## 六、只想要部分技能

不需要的可以直接删 `~/.dsh/skills/<name>/`，然后从 bootstrap 路由表删对应行。

**但注意**：如果删了 bootstrap，会破坏两级路由。要么保留 bootstrap，要么把路由表内容搬回 persona。

---

## 七、调试「技能没被加载」

按顺序查：

1. **文件在不在**
   ```bash
   ls ~/.dsh/skills/<name>/SKILL.md
   ```

2. **frontmatter 格式对不对**
   ```bash
   head -3 ~/.dsh/skills/<name>/SKILL.md
   # 必须是 --- / name: xxx / description: xxx
   ```

3. **有没有出现在技能列表**
   DSH 的会话技能 catalog 里应该能看到。看不到 = 没被识别，检查文件名是不是 `SKILL.md`（大写）。

4. **description 能不能匹配**
   如果 catalog 里有但它不加载，通常是 description 写得太抽象。加上用户实际会说的话（"弹窗""抽屉""分页"这种）。

5. **preset 改了吗**
   改 preset 之后**刷新页面**即可；看不到再重启 DSH。

---

## 八、贡献回来

如果你改出了更好的判据，欢迎 PR。

判断标准只有一条：**这条规则是不是来自一个真实踩过的坑？**

来自想象的规则不要加。
