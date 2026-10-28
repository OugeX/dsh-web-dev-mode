---
name: mobile-responsive-layout
description: 移动端 H5 与响应式布局的约束规范与兼容性修复。包含 viewport 配置与 vw/rem 适配方案、安全区域 env() 处理、100vh 与 100dvh 的区别、iOS 软键盘与 position:fixed 错位、input 字体小于 16px 自动放大、Android 各厂商 WebView 差异、滚动穿透、1px 边框、点击区域 44px、touch 事件 passive、visualViewport 键盘监听、真机调试方法（Windows 下如何调 iOS）。当写手机端页面、做响应式、遇到 iOS/Android 浏览器样式错乱、弹窗遮挡、键盘顶起布局、滚动异常或需要适配刘海屏时使用。
---

# 定位：移动端先守约束，再谈效果

移动端 80% 的 bug 来自 5 个原因：**viewport 没配全、用了 100vh、没处理安全区域、没处理软键盘、滚动手势冲突**。

---

## 一、viewport 必须写全（第一件事）

```html
<meta name="viewport"
      content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
```

| 参数 | 作用 | 漏了的后果 |
|---|---|---|
| `width=device-width` | 视口宽度 = 设备宽 | 页面被缩小成大屏布局 |
| `initial-scale=1.0` | 初始不缩放 | 部分安卓机默认缩 |
| `maximum-scale=1.0, user-scalable=no` | 禁止双指缩放 | 表单聚焦时页面被放大后卡住 |
| **`viewport-fit=cover`** | **允许内容延伸到刘海/圆角** | **`env(safe-area-inset-*)` 全部失效** |

**`viewport-fit=cover` 是安全区域方案的前提**，漏了它下面所有 `env()` 都不生效。

---

## 二、适配方案：选一种，不要混

| 方案 | 写法 | 适用 |
|---|---|---|
| **vw**（推荐） | `width: 100vw` / `font-size: 4vw` | 设计稿 750，用 `postcss-px-to-viewport` 自动转 |
| rem | `font-size: 0.32rem` | 需要动态改 `html` 字号时 |
| px + media query | 手写断点 | 简单页面、断点少 |

**配置示例（Vite + postcss-px-to-viewport）**：

```js
// postcss.config.js
export default {
  plugins: {
    'postcss-px-to-viewport-8-plugin': {
      viewportWidth: 750,       // 设计稿宽度
      unitPrecision: 5,
      viewportUnit: 'vw',
      selectorBlackList: ['.ignore-'],   // 不想转换的类名前缀
      minPixelValue: 1,
      mediaQuery: false,
    },
  },
}
```

**注意**：Ant Design Mobile / Vant 这类组件库内部已处理，不要再转它们。

---

## 三、安全区域（刘海屏 / 底部指示条）

```css
/* 顶部固定栏 */
.header {
  padding-top: env(safe-area-inset-top);
}
/* 底部固定操作栏 */
.footer-bar {
  padding-bottom: env(safe-area-inset-bottom);
}
/* 全屏容器 */
.page {
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}
```

**用 `padding` 不用 `margin`** —— `margin` 会让背景色留白。

**固定定位的底部栏必须处理**，否则在 iPhone 上会被底部横条压住：

```css
.fixed-bottom {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}
```

---

## 四、100vh 是最大的坑

**问题**：iOS Safari 的地址栏收起/展开会改变可视高度，但 `100vh` 始终等于**地址栏展开时**的高度。结果：

- 地址栏收起时，页面底部被裁掉一截
- 全屏弹层高度不足，底部露出背景
- 微信内置浏览器更严重

**正解：用 `100dvh`（动态视口单位）**

```css
.fullscreen {
  height: 100dvh;          /* ✅ 随地址栏实时变化 */
  /* height: 100vh;        ❌ 会出错 */
}
```

**兼容性兜底**（老 WebView）：

```css
.fullscreen {
  height: 100vh;                    /* 老浏览器先吃这个 */
  height: -webkit-fill-available;   /* iOS 老版本 */
  height: 100dvh;                   /* 现代浏览器覆盖 */
}
```

**另一条路**：用 `position: fixed; inset: 0` 代替高度计算，它天然跟随可视区域。

```css
.fullscreen {
  position: fixed;
  inset: 0;          /* top/right/bottom/left 全 0 */
}
```

**这是移动端全屏弹层最稳的写法。**

---

## 五、软键盘：iOS 与 Android 表现完全不同

### 5.1 症状对照

| 平台 | 症状 |
|---|---|
| **iOS Safari** | 键盘弹起时 `position: fixed` 元素被顶起；页面整体上推；关键盘后不归位 |
| **Android Chrome** | 默认 `resize` 视口，布局会重排（相对可预期） |
| **Android 微信 X5** | 各厂商不一致，华为/小米表现不同 |
| **iOS 微信** | 键盘弹起时 `window.innerHeight` **不变**（这是关键差异） |

### 5.2 正解：`visualViewport`

```js
const vv = window.visualViewport
if (vv) {
  const onResize = () => {
    // vv.height 才是真正的可视高度（键盘弹起后会变小）
    document.documentElement.style.setProperty('--vh', `${vv.height}px`)
    // 判断键盘是否弹起：可视高度明显小于布局高度
    const keyboardOpen = vv.height < window.innerHeight * 0.8
    document.body.classList.toggle('keyboard-open', keyboardOpen)
  }
  vv.addEventListener('resize', onResize)
  onResize()
}
```

**`window.innerHeight` 在 iOS 微信里键盘弹起时不变，`visualViewport.height` 会变。** 这是判断键盘状态的唯一可靠方式。

### 5.3 底部输入框被键盘遮挡

```css
/* 用 --vh 变量代替 100vh */
.chat-container {
  height: calc(var(--vh, 1vh) * 100);
}
.chat-input {
  position: fixed;
  bottom: 0;
  padding-bottom: calc(8px + env(safe-area-inset-bottom));
}
/* 键盘弹起时把输入框顶上去 */
body.keyboard-open .chat-input {
  transform: translateY(calc(-1 * var(--keyboard-height, 0px)));
}
```

### 5.4 更简单的方案（多数场景够用）

**底部输入框不要用 `position: fixed`**，用 flex 布局：

```css
.page {
  display: flex;
  flex-direction: column;
  height: 100dvh;
}
.content { flex: 1; overflow-y: auto; }
.input-bar { flex-shrink: 0; }
```

键盘弹起时浏览器自动重排 flex，**不需要 JS**。这是最省事的做法。

---

## 六、滚动相关的三个坑

### 6.1 弹窗打开时底层页面还能滚（滚动穿透）

```ts
// 打开弹窗时
const scrollY = window.scrollY
document.body.style.position = 'fixed'
document.body.style.top = `-${scrollY}px`
document.body.style.width = '100%'

// 关闭时恢复
document.body.style.position = ''
document.body.style.top = ''
window.scrollTo(0, scrollY)
```

**只加 `overflow: hidden` 在 iOS 上不够**，必须用 `position: fixed` + 保存 scrollY。

### 6.2 惯性滚动失效 / 卡顿

```css
.scroll-area {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;   /* iOS 惯性滚动，必须有 */
  overscroll-behavior: contain;        /* 阻止滚动链传导到父级 */
}
```

### 6.3 touch 事件要 passive

```js
el.addEventListener('touchstart', handler, { passive: true })
```

**不加 `passive: true`，浏览器要等 JS 执行完才知道会不会 `preventDefault`，滚动会明显卡顿。**

---

## 七、输入框的两个致命细节

### 7.1 字体小于 16px 会触发 iOS 自动放大

```css
input, textarea, select {
  font-size: 16px;    /* 小于 16px 时 iOS Safari 聚焦会 zoom，且不会自动缩回 */
}
```

**这是 iOS 上最常见的“页面莫名被放大”的原因。** 设计稿要 14px 就用 `transform: scale()` 或接受 16px。

### 7.2 样式重置

```css
input, textarea {
  -webkit-appearance: none;        /* 去掉 iOS 原生样式 */
  border-radius: 0;                /* iOS 会给圆角 */
  -webkit-tap-highlight-color: transparent;   /* 去掉点击灰块 */
}
```

---

## 八、1px 边框（Retina 屏变粗）

```css
/* 方案：伪元素 + scale */
.hairline-bottom {
  position: relative;
}
.hairline-bottom::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 1px;
  background: #eee;
  transform: scaleY(0.5);
  transform-origin: 0 100%;
}
```

DPR = 3 时用 `scaleY(0.3333)`，用媒体查询适配：

```css
@media (-webkit-min-device-pixel-ratio: 3) {
  .hairline-bottom::after { transform: scaleY(0.3333); }
}
```

---

## 九、布局约束（硬指标）

| 项 | 约束 | 理由 |
|---|---|---|
| **点击区域** | ≥ 44×44 px | iOS HIG 标准；小于这个容易点错 |
| **正文字号** | ≥ 14px，推荐 16px | 12px 以下移动端难读 |
| **行高** | 1.5–1.6 | 太密难读 |
| **不要用 `:hover`** | 用 `:active` 代替 | 移动端没有 hover，会导致样式卡在 hover 态 |
| **`touch-action`** | 滑动组件设 `none` 或 `pan-y` | 防止手势冲突 |
| **图片** | `object-fit: cover` + 固定宽高比 | 防止布局跳动（CLS） |
| **长列表** | > 100 条用虚拟滚动 | 否则 DOM 节点过多卡死 |
| **动画** | 只用 `transform` 和 `opacity` | 触发合成层，不引起重排 |
| **滚动容器** | 必须设 `-webkit-overflow-scrolling: touch` | 惯性滚动 |
| **字体** | 用系统字体栈，不加载大字体文件 | 首屏速度 |

### 系统字体栈

```css
font-family: -apple-system, BlinkMacSystemFont, "PingFang SC",
             "Helvetica Neue", "Microsoft YaHei", sans-serif;
```

---

## 十、iOS / Android 差异清单（按踩坑频率排）

| # | 问题 | iOS | Android | 修复 |
|---|---|---|---|---|
| 1 | 100vh 不准 | 严重 | 轻 | `100dvh` 或 `inset: 0` |
| 2 | 键盘顶起 fixed | 严重 | 中 | flex 布局 / `visualViewport` |
| 3 | 输入框放大 | 严重 | 无 | `font-size: 16px` |
| 4 | 安全区域 | 严重（刘海） | 轻 | `env(safe-area-inset-*)` |
| 5 | 滚动穿透 | 严重 | 中 | `position: fixed` + scrollY |
| 6 | 点击高亮灰块 | 有 | 有 | `-webkit-tap-highlight-color` |
| 7 | 1px 变粗 | 有 | 有 | `transform: scaleY(0.5)` |
| 8 | `position: fixed` 输入框 | 错位 | 厂商差异 | 避免在输入框上用 fixed |
| 9 | `border-radius + overflow: hidden` | 正常 | 老 WebView 裁剪失效 | 加 `transform: translateZ(0)` |
| 10 | `flex` 子项溢出 | 正常 | 需 `min-height: 0` | 显式设置 |
| 11 | `100%` 高度链断裂 | 正常 | 需逐层设高 | 用 flex 或 dvh |
| 12 | 日期选择器 | 原生滚轮，不可样式化 | 原生 | 复杂场景用自定义组件 |

---

## 十一、真机调试（Windows 开发者的现实）

### Android —— 最方便

1. 手机开「开发者选项」→「USB 调试」
2. Chrome 打开 `chrome://inspect`
3. 找到设备 → inspect

**完整可用，等同于桌面 DevTools。**

### iOS —— Windows 上没法用 Web Inspector

Safari 的 Web Inspector 只能在 **macOS** 上开。Windows 开发者只能用页面内的调试面板：

| 工具 | 用法 | 评价 |
|---|---|---|
| **vConsole** | `npm i vconsole`，开发环境 `new VConsole()` | 看 console、network、元素，**最常用** |
| **Eruda** | CDN 引入一行 script | 功能更全（含 DOM 树），移动端体验好 |
| **Charles / Fiddler** | 代理抓包 | 看网络请求、改包 |
| **微信开发者工具** | 内置远程调试，**但只对微信内网页有效** | 调微信 H5 必须用 |

**推荐组合**：开发环境自动挂 vConsole，线上不挂。

```ts
// main.tsx
if (import.meta.env.DEV) {
  import('vconsole').then(({ default: VConsole }) => new VConsole())
}
```

### Safari 远程调试（有 Mac 时）

```
iPhone：设置 → Safari → 高级 → 网页检查器 打开
Mac Safari：开发 → 你的 iPhone → 选中页面
```

### 云真机（无 Mac 无 iPhone 时）

- BrowserStack / Sauce Labs（付费，真实设备）
- 微信开发者工具的「真机调试」（仅微信内）

---

## 十二、测试清单（上线前过一遍）

### 视口与滚动

- [ ] 上下滚动时地址栏收起/展开，页面高度不会跳
- [ ] 底部固定栏没被 iPhone 底部横条压住
- [ ] 弹窗打开时底层页面不能滚
- [ ] 弹窗关闭后页面回到原滚动位置
- [ ] 长列表滚动有惯性，不卡

### 键盘

- [ ] 底部输入框聚焦时不被键盘遮挡
- [ ] 键盘收起后布局回到原位
- [ ] 输入框聚焦时页面不放大（iOS）
- [ ] 表单页键盘弹起后能滚到下一个字段

### 点击与手势

- [ ] 按钮点击区域 ≥ 44px
- [ ] 没有 hover 样式卡住
- [ ] 点击没有灰色高亮块
- [ ] 左右滑动不触发浏览器返回（`overscroll-behavior`）

### 视觉

- [ ] 1px 边框在 DPR 2/3 设备上不粗
- [ ] 圆角在安卓老 WebView 没被裁掉
- [ ] 图片不变形、不引起布局跳动
- [ ] 文字不小于 14px

### 兼容

- [ ] iOS Safari 真机通过
- [ ] iOS 微信内置浏览器通过
- [ ] Android Chrome 通过
- [ ] Android 微信 X5 通过
- [ ] 华为 / 小米 / 三星各一台（有条件时）

---

## 十三、反面清单

1. ❌ viewport 漏了 `viewport-fit=cover`，然后写 `env()` 却不生效
2. ❌ 用 `100vh` 做全屏容器
3. ❌ 输入框 `font-size: 12px`（iOS 会放大）
4. ❌ 底部固定栏不处理 `safe-area-inset-bottom`
5. ❌ 弹窗打开只加 `overflow: hidden`（iOS 无效）
6. ❌ 用 `window.innerHeight` 判断键盘状态（iOS 微信不变）
7. ❌ touch 监听不加 `{ passive: true }`
8. ❌ 用 `:hover` 做交互反馈
9. ❌ 按钮高 32px（点不准）
10. ❌ 只在 Chrome 桌面模拟器里测，不上真机
11. ❌ 用 Windows 直接调 iOS Safari（做不到，要 vConsole）
12. ❌ 长列表 500 条全渲染（不用虚拟滚动）
