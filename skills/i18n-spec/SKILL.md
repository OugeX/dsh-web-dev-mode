---
name: i18n-spec
description: 国际化与多语言的界面规范。包含文案长度膨胀（德语 +30%、俄语 +20%）与布局余量、RTL 阿拉伯语与希伯来语的镜像规则（margin/padding/图标/滚动条/图表）、日期时间数字货币的格式化与不要硬编码、复数规则与变量插值、翻译文件组织与命名空间、语言切换与持久化、CJK 与拉丁字体栈、图片中文字与不可翻译内容、localStorage 与正则的地区差异。当做多语言、上 RTL 语言、或发现界面在英文下被撑破时使用。
---

# 定位：先留余量，再谈翻译

**80% 的国际化 bug 不是翻译错，是布局被撑破。**

---

## 一、文案长度膨胀

### 1.1 各语言的膨胀率（以中文为基准）

| 语言 | 相对中文长度 |
|---|---|
| 英文 | **+30% ~ +60%** |
| 德文 | **+60% ~ +100%**（最长的常见语言） |
| 俄文 | **+50% ~ +80%** |
| 日文 | +10% ~ +20% |
| 韩文 | +5% ~ +15% |

**一条中文 6 个字的按钮，德语可能要 14 个字符。**

### 1.2 布局余量规则

| 元素 | 规则 |
|---|---|
| **按钮** | 宽度**不写死**，用 `min-width` + padding；文字不换行 |
| **Tab / 菜单项** | 允许换行或加省略号，不要写死宽度 |
| **表格列头** | 用 `ellipsis` + Tooltip |
| **表单 label** | 宽度按最长语言算，或改成上下布局 |
| **弹窗标题** | 单行 + ellipsis |
| **Tooltip / 提示** | 不要写死宽度，用 `max-width` |

```css
/* ✅ */
.btn { min-width: 88px; padding: 0 16px; white-space: nowrap; }

/* ❌ */
.btn { width: 88px; }
```

### 1.3 允许换行的地方

- 段落、描述、说明文字 → 允许换行
- 按钮、Tab、菜单、标签 → **不允许换行**（用省略或缩短文案）

**不要用 `text-overflow: ellipsis` 处理所有文案**——该换行的地方省略了反而看不懂。

### 1.4 文案要短

写中文文案时就按"会被翻成德语"的标准控制长度：

- 「确定」而不是「确认并继续」
- 「删除」而不是「删除所选记录」
- 长说明放 help text 或 Tooltip，不要塞进按钮

---

## 二、RTL（阿拉伯语 / 希伯来语）

### 2.1 用逻辑属性，不要用物理属性

```css
/* ❌ 物理属性，RTL 下会错 */
.card { margin-left: 16px; padding-right: 8px; text-align: left; }

/* ✅ 逻辑属性，自动镜像 */
.card { margin-inline-start: 16px; padding-inline-end: 8px; text-align: start; }
```

| 物理 | 逻辑 |
|---|---|
| `margin-left/right` | `margin-inline-start/end` |
| `padding-left/right` | `padding-inline-start/end` |
| `border-left` | `border-inline-start` |
| `left` / `right` | `inset-inline-start/end` |
| `text-align: left` | `text-align: start` |

### 2.2 整体方向

```html
<html dir="rtl" lang="ar">
```

```css
[dir="rtl"] { direction: rtl; }
```

**只改 `dir` 不会自动镜像所有东西**，还要处理：

| 元素 | 处理 |
|---|---|
| **图标**（箭头、返回） | 用 `transform: scaleX(-1)` 镜像，或用 RTL 专用图标 |
| **滚动条** | 在 RTL 下会跑到左侧（浏览器自动处理） |
| **图表坐标轴** | Y 轴移到右侧（ECharts 有 `reverse` / `rtl` 选项） |
| **进度条** | 从右往左填充 |
| **轮播** | 方向反转 |
| **数字和电话号码** | **保持 LTR**（`dir="ltr"` 包裹） |
| **代码块、URL、邮箱** | **保持 LTR** |
| **图标+文字的间距** | 用 `margin-inline-start` |

**不要镜像的**：播放按钮、时钟图标、品牌 logo、勾选标记。

### 2.3 第三方组件库

Ant Design、Element Plus 大多支持 `ConfigProvider direction="rtl"`，但**自定义组件要自己测**。

---

## 三、格式化：日期、时间、数字、货币

### 3.1 绝对不要硬编码

```ts
// ❌ 全是坑
`${y}-${m}-${d}`
`${price.toFixed(2)} 元`
`${n.toLocaleString()}`
'sunday'

// ✅ 用 Intl
new Intl.DateTimeFormat(locale).format(date)          // 2026/10/28 vs 10/28/2026
new Intl.NumberFormat(locale, { style: 'currency', currency }).format(price)
new Intl.NumberFormat(locale).format(n)
new Intl.RelativeTimeFormat(locale).format(-3, 'day') // "3 天前" / "3 days ago"
```

### 3.2 各地区的差异

| 项 | 差异 |
|---|---|
| **日期顺序** | 中文/欧洲：年月日；美国：月日年 |
| **时间制** | 美国 12 小时（AM/PM），欧洲/中国 24 小时 |
| **周起始** | 中国/美国周日起；欧洲周一起 |
| **数字分隔** | 英文 `1,234.56`；德文 `1.234,56` |
| **货币符号位置** | `¥100` vs `100 €` |
| **千分位/万** | 中文用「万/亿」，英文用「K/M/B」 |

**「万」不是通用的**：英文里没有 `10万`，要说 `100K`。用 `Intl.NumberFormat` 的 `notation: 'compact'`。

### 3.3 时区

- **存储用 UTC**，展示时按用户时区转换
- 后端返回 ISO 8601 带时区：`2026-10-28T21:05:33+08:00`
- 前端用 `dayjs` / `date-fns` 带 timezone 插件
- **不要在数据库存本地时间字符串**

---

## 四、复数与变量插值

### 4.1 复数规则（中文没有，但英文有）

```ts
// ❌ 英文下永远是 "1 items"
`${count} items`

// ✅
new Intl.PluralRules(locale).select(count)   // 'one' | 'other'
// 或 i18next 的 _one / _other 后缀
```

不同语言的复数形式：

| 语言 | 形式数 |
|---|---|
| 中文、日文、韩文 | 1 种 |
| 英文、德文 | 2 种（单/复） |
| 俄文、波兰文 | 3–4 种 |
| 阿拉伯文 | 6 种 |

**用框架的复数能力，不要自己拼。**

### 4.2 变量插值不要拼接

```ts
// ❌ 语序会错
`打开 ${name} 的 ${file}`
// 英文："Open ${file} of ${name}" —— 语序完全不同

// ✅ 用带占位符的完整句子
t('openFile', { name, file })
// zh: '打开 {{name}} 的 {{file}}'
// en: 'Open {{file}} of {{name}}'
```

**一句话一个 key**，不要在代码里拼句子。

### 4.3 不要用文案做逻辑判断

```ts
// ❌ 翻译一改就断
if (msg === '保存成功') { ... }

// ✅ 用 code
if (res.code === 0) { ... }
```

---

## 五、翻译文件组织

### 5.1 目录结构

```
locales/
├── zh-CN/
│   ├── common.json      # 通用（确定/取消/保存/删除）
│   ├── auth.json        # 登录注册
│   ├── order.json       # 订单模块
│   └── validation.json  # 校验提示
├── en-US/
│   └── ...
└── index.ts
```

**按模块分文件**，不要一个大文件（几千个 key 无法维护）。

### 5.2 key 命名

```json
{
  "order.list.title": "订单列表",
  "order.list.empty": "还没有订单",
  "order.action.delete.confirm": "确定删除这条订单？",
  "common.action.save": "保存",
  "common.action.cancel": "取消"
}
```

**用语义 key，不要用中文做 key**（改中文会破坏所有引用）。

### 5.3 缺失翻译的处理

```ts
t('some.key')   // 缺失时返回 'some.key'
```

**开发环境要报错**，生产环境回退到默认语言：

```ts
i18n.on('missingKey', (lng, ns, key) => {
  if (import.meta.env.DEV) console.error(`[i18n] 缺失翻译: ${lng}/${ns}/${key}`)
})
```

---

## 六、语言切换

- 切换后**立即生效**，不要刷新页面
- **持久化**：`localStorage` + 用户设置（登录用户以服务端为准）
- **同步 `<html lang>`**：影响字体渲染、断词、读屏
- **同步日期/数字格式**：切换语言时这些要跟着变
- 首次访问时按 `navigator.language` 猜，但**给用户明确的切换入口**

```ts
document.documentElement.lang = locale
```

---

## 七、字体

### 7.1 字体栈要覆盖多脚本

```css
font-family:
  -apple-system, BlinkMacSystemFont,
  "Segoe UI", "PingFang SC", "Hiragino Sans GB",
  "Microsoft YaHei", "Noto Sans CJK SC",
  "Noto Sans Arabic", "Noto Sans Hebrew",
  sans-serif;
```

**中日韩 vs 拉丁的字重不同**：同一个 `font-weight: 500`，中文可能显示为常规，英文是半粗。设计稿要分别确认。

### 7.2 行高要按语言调

| 语言 | 建议行高 |
|---|---|
| 中文 | 1.6–1.75 |
| 英文 | 1.4–1.5 |
| 阿拉伯文 | **1.8–2.0**（有上下延伸的笔画） |
| 泰文 | **2.0+**（有上下标） |

---

## 八、图片与不可翻译内容

| 问题 | 处理 |
|---|---|
| 图片里有文字 | **改成图层文字**，或按语言出多套图 |
| 品牌名、产品名 | 不翻译，加 `translatable="false"` 标记 |
| 代码、命令、URL | 不翻译，用 `<code>` 包裹并设 `dir="ltr"` |
| 用户名、文件名 | 不翻译，但要防溢出 |
| 表情、图标里的文字 | 用无文字的图标 |

---

## 九、容易被忽略的细节

| 项 | 问题 |
|---|---|
| **正则里的中文** | `[\u4e00-\u9fa5]` 只匹配中文，国际化后失效 |
| **字符串排序** | `'a'.localeCompare('b', locale)`，不要用 `<` |
| **姓名顺序** | 中文「姓+名」，欧美「名+姓」 |
| **地址格式** | 各国顺序不同，用多行字段而不是一行拼接 |
| **电话号码** | 国际格式带区号，长度各国不同 |
| **输入法** | 日文/中文输入法有组合态，`compositionstart/end` 要处理 |
| **首字母大写** | 土耳其语的 `i` 大写是 `İ` 不是 `I` |
| **`localStorage` 里的中文** | 没问题，但 URL 参数要 `encodeURIComponent` |

---

## 十、验收清单

- [ ] 按钮用 `min-width` + padding，宽度不写死
- [ ] 没有 `width: 88px` 这种固定宽度（除图标按钮）
- [ ] 表单 label 宽度能容纳最长语言
- [ ] CSS 用逻辑属性（`margin-inline-start` 等）
- [ ] `dir="rtl"` 下测过：图标镜像、数字保持 LTR、图表翻转
- [ ] 日期/时间/数字/货币全部用 `Intl`
- [ ] 时区按用户时区转换，存储用 UTC
- [ ] 文案带占位符而不是拼接
- [ ] 复数用 `Intl.PluralRules` 或框架能力
- [ ] 翻译文件按模块分，key 是语义化英文
- [ ] 缺失翻译在开发环境报错
- [ ] 切换语言立即生效 + 持久化 + 同步 `<html lang>`
- [ ] 字体栈覆盖 CJK / 阿拉伯 / 希伯来
- [ ] 图片里没有硬编码文字
- [ ] 正则里没有硬编码中文范围
- [ ] 字符串比较用 `localeCompare`

---

## 十一、反面清单

1. ❌ 按钮写死 `width: 88px`
2. ❌ 用 `margin-left` 而不是 `margin-inline-start`
3. ❌ RTL 下电话号码被镜像
4. ❌ 硬编码 `YYYY-MM-DD` 格式
5. ❌ 硬编码「元」「万」
6. ❌ 拼接句子 `打开 ${name} 的文件`
7. ❌ 用中文做翻译 key
8. ❌ 用文案做逻辑判断
9. ❌ 切换语言要刷新页面
10. ❌ 正则里写死 `[\u4e00-\u9fa5]`
11. ❌ 图片里烧进文字
12. ❌ 只支持一个语言却按多语言设计（过早抽象）
