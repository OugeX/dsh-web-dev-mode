# DSH Web Dev Mode · Web 开发模式

> **AI 不该直接甩你 3000 行代码。它该先问你 5 个问题。**

一个给 [DSH](https://github.com/deepseek-ai) 用的 agent 模式 + 12 个配套技能。
不是 prompt 合集，是一套带**决策表**和**验收清单**的工程预制件。

<sub>An agent preset + 12 skills for production Web development in DSH. Chinese-first.</sub>

---

## 你可能遇到过这些

| 现象 | 后果 |
|---|---|
| 列表接口 `SELECT *` 后直接序列化 model | 密码哈希、身份证号一起吐到浏览器 |
| 30 个字段的用户表被拆成 4 张 | 注册要开事务写 4 次，查一次详情 4 次往返 |
| 按钮、提示、弹窗每个页面各写各的 | 改一次样式，改 8 个文件 |
| agent 写完代码直接 `go run` + curl | 连的是开发库，一个 `TRUNCATE` 一下午白干 |
| 你说"加个订单列表"，它给 React + Tailwind | 而你项目是 layui，两套心智打架 |
| 一个文件写到 3000 行 | 之后每次改动它都要重新切片读一遍 |
| 前端 `phone.replace(...)` 做脱敏 | 打开 Network 面板，原始手机号一览无余 |
| 每层都 `if err != nil { log; return wrap }` | 日志里 8 层前缀，看不出真错在哪 |

这些都不是"AI 不够聪明"，是**没人给它判据**。它只能凭通用印象猜，猜错了你看不见。

---

## 它是什么

**12 个可加载技能 + 1 套行为约束。**

和「往对话里贴一段规范」的区别：

| | 贴一段 prompt | 这个模式 |
|---|---|---|
| 生效方式 | 你贴了才生效，贴了就占满上下文 | 命中主题才加载，用完即走 |
| 有判据吗 | 通常是"建议""注意" | 决策树 + 数字阈值 + 尺寸表 |
| 有验收吗 | 没有 | 每个技能带验收清单，过不了算没做完 |
| 会膨胀吗 | 会，越补越长 | 不会，persona 恒定 4.7K，知识在技能里 |
| 能复用吗 | 复制粘贴 | 全局技能，其他模式也能单独调用 |

---

## 30 秒开始

```bash
git clone https://github.com/<you>/dsh-web-dev-mode.git
cd dsh-web-dev-mode

# Linux / macOS
bash install.sh

# Windows PowerShell
.\install.ps1
```

重启 DSH → 模式下拉里选「Web开发模式」。

> 技能是热加载的，放进去立即生效；**只有 preset 需要重启**。

想设为默认：`~/.dsh/settings.yaml`

```yaml
agent-presets:
  default: web-dev
```

---

## 它实际长什么样

### 每收到一个新任务，先亮判断

```
你：帮我做一个订单管理页面

它：技能计划：web-project-bootstrap + api-contract-design +
    react-frontend-architecture + ui-ux-decision-guide
    （新建 CRUD 页面，需要目录规范、接口契约、前端骨架与控件选型）
```

**这一行的意义**：判断错了你能第一句就纠正，不用等代码写完才发现漏了规范。

### 然后问 5 个问题，不是直接写

```
需求澄清清单：

1. 布局几何：筛选栏放表格上方一行，还是收进「高级筛选」抽屉？
2. 数据来源：orders 表的分页参数用 page/pageSize，默认 20 条对吗？
3. 交互状态：删除成功后是留在当前页还是跳回第 1 页？
4. 参照物：项目里 src/pages/user/index.tsx 结构可以照抄吗？
5. 边界例外：订单号超长时截断显示还是换行？0 条数据显示哪个空态？
```

**问完停下等回答。** 不许"顺便先写个初版给你看看"。

答完后先复述 3 行理解，再动手。

### 大页面分三轮，每轮可验证

```
第 1 轮：骨架     只要 HTML 结构 + 布局 class，文字全用「XXX」占位，不写样式不写 JS
第 2 轮：样式     补齐组件库原生组件与间距
第 3 轮：接数据   改成模板语法或 API 层 + 三态
```

每轮结束停下等确认。**第 1 轮改 20 行，第 3 轮改 300 行。**

---

## 12 个技能

| 技能 | 解决什么 |
|---|---|
| **web-project-bootstrap** | 总纲。选型决策表、26 项后端产物、16 项前端产物、15 步生成顺序、22 条验收清单 |
| **web-tech-stack** | 各栈实现细则：ThinkPHP+layui / Vue3+Element / Nuxt / Next / Go+Gin / Go+React / Rust / 跨端 |
| **mysql-schema-design** | 拆表判断树（**1:1 不拆，1:N 必拆**）、30 字段宽表为何不该拆、审计设计、索引、迁移 |
| **go-backend-architecture** | 五层职责边界、DTO 与 model 分离、API+Worker 双入口、**防御性编程的边界** |
| **jwt-session-auth** | 纯 JWT / Redis 白名单 / MySQL 审计双写、四个流程、refresh 轮换、8 条安全红线 |
| **react-frontend-architecture** | 目录分层、统一登录态（**并发 401 去重**）、TanStack Query 与 Zustand 边界、组件防造轮子 |
| **media-file-management** | 文件表与 SHA-256 秒传去重、三种鉴权模式、**纯本地存储方案**、上传安全红线 |
| **testing-strategy** | 执行纪律（Makefile + `APP_ENV` 校验）、测试分层反金字塔、**禁止伪造测试通过** |
| **deployment-ops** | Docker 复用容器、Windows 无官方 Redis 的替代、**SSH 直连部署**、Linux 性能调优 |
| **api-contract-design** | 三套 DTO 视图模型、脱敏是权限问题、公共/私有配置分层、批量操作单接口 |
| **ui-ux-decision-guide** | 弹窗还是抽屉（**判据 + 尺寸表**）、六种提示形态、要不要搜索分页、页面骨架 |
| **mobile-responsive-layout** | `100dvh` 替代 `100vh`、iOS 微信 `innerHeight` 不变、安全区域、滚动穿透、1px |

---

## 三条设计原则

### 一、预制件，不是参考资料

参考资料写：

> 建议使用统一的响应体。

预制件写：

> 响应体必须是 `{code,msg,data}`。错误码分五段（1xxx 参数 / 2xxx 认证 / 3xxx 权限 / 4xxx 业务 / 5xxx 系统）。5xx 的 msg 一律是「服务器繁忙」，真实错误只进日志。违反即打回重写。

**差别在于能不能直接执行。**

### 二、机制 > 规范

写「请使用 Ant Design 组件」——没用，它照样 `<button>`。

真正有效的是：

```js
'no-restricted-imports': ['error', {
  paths: [{ name: 'antd', importNames: ['message', 'notification', 'Modal', 'Button'],
            message: '请从 @/components 导入封装版：Btn/toast/useConfirm。' }],
}],
'no-restricted-syntax': ['error',
  { selector: "JSXOpeningElement[name.name='button']",
    message: '禁止裸 <button>，请用 <Btn> 或 <AuthButton perm="...">。' }],
```

**lint 一跑就红，它必须改。** 这是唯一真正生效的约束。

配合第三条：**让正确用法比造轮子更短**。`await confirm('确定删除？')` 比 `Modal.confirm({...8 个参数})` 短一半，它才会用。

### 三、在边界防御，在内部信任

到处判 nil 不是健壮，是**没有边界概念**。

- **该防御的只有三处**：外部输入、系统边界（DB/Redis/HTTP）、不可信数据
- **不该防御**：自己刚 new 的对象、binding 已校验的参数、构造函数已返回 error 的情况

> 错误处理的目标是「让失败可见且可定位」，不是「让代码看起来健壮」。
> 到处判 nil、吞错兜底、多层 wrap，效果恰好相反——失败被藏起来了。

其中**吞错**最恶劣：`if err != nil { return 0, nil }` 把失败变成了"看起来成功的错误数据"，比崩溃难查十倍。

---

## 它不做什么

- **不替你写业务逻辑**。它管规范、结构和判据，业务规则你来定。
- **不替你做技术决策**。选型表是给判据，最终换不换栈是你的决定。
- **不含任何项目数据、密钥、服务器信息**。导出包已验证：零绝对路径、零凭据。
- **不绑定某个技术栈**。会先探测项目实际用的是什么，探测不到才用主力栈。

---

## 目录结构

```
.
├── README.md
├── LICENSE                     MIT
├── CONTRIBUTING.md             贡献标准（唯一标准：来自真实踩过的坑）
├── install.sh                  Linux/macOS 安装（含安装后校验）
├── install.ps1                 Windows 安装（含安装后校验）
├── presets/web-dev/
│   ├── preset.yml              模式名与描述
│   └── agent.cordis.yml        persona + 15 个插件条目
├── skills/                     12 个技能
│   ├── web-project-bootstrap/SKILL.md
│   ├── mysql-schema-design/SKILL.md
│   └── ...
├── docs/
│   ├── DESIGN.md               设计取舍：为什么这么拆
│   └── CUSTOMIZE.md            改哪里、加技能、调阈值
└── .github/workflows/
    └── validate.yml            CI：frontmatter、绝对路径、密钥泄漏
```

---

## 兼容性

| 项 | 说明 |
|---|---|
| **跨平台** | preset 里用 `!!js process.platform` 判断，Windows 自动用 pwsh、Linux 自动用 bash，同一份配置两边跑 |
| **插件依赖** | 17 个 `@deepseek-ai/dsh-*` 包，标准 DSH 安装自带 |
| **skill 复用** | 12 个技能装在 `~/.dsh/skills/`，**全局可用**，不装 preset 也能在别的模式下单独调用 |
| **热加载** | 改 skill 不用重启；改 preset 要重启 |

---

## 为什么值得一试

如果你也用 AI 写 Web 项目，并且遇到过上面那张表里的任意两行——

这个仓库的价值不是"再多一份规范"，而是**把规范变成了可执行的判据和拦截**。

12 个技能，约 12.6 万字符，每一条都是踩过坑之后写下的。

**Star ⭐ 一个，下次建新项目时省下的返工就不止这点时间。**

---

## License

MIT
