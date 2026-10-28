---
name: motion-animation-spec
description: 界面动效与过渡动画的规范。包含动效的三个功能目的、时长分级表（微交互 100ms 到页面切换 350ms，上限 400ms）、四条缓动曲线、进出不对称原则（退出为进入的 0.7 倍）、页面切换淡入与 8px 位移、弹窗 0.95 缩放与抽屉滑入、toast 下滑与堆叠、列表项增删的高度收起、数字滚动时长、loading 延迟 300ms 防闪烁、prefers-reduced-motion、只动 transform 与 opacity 的性能规则。当加页面切换过渡、弹窗与抽屉动画、toast 出现消失、列表增删动画，或觉得动效卡顿时使用。
---

# 定位：动效是功能，不是装饰

动画只做三件事：

1. **空间连续性** —— 我从哪来、到哪去（页面切换、抽屉从右侧滑入）
2. **状态因果** —— 这个变化是因为我刚点了什么（按钮按下、行删除）
3. **注意力引导** —— 把视线引到重要的地方（新消息、错误提示）

**做不到这三件事的动画就是噪音。**

---

## 一、时长分级（起点值，不是通用定律）

> **重要修正**：不要断言「150–300ms 是通用要求」。
> 这是起点，不是定律 —— 距离越远、信息越重要，时长应越长；反馈类（按下、hover）要尽可能快。
> 固定一个区间套所有交互，本身就是一种粗糙。

下表是**起点参考**：

| 类型 | 时长 | 缓动 |
|---|---|---|
| 微交互（hover、按下） | **100–150ms** | `ease-out` |
| 状态切换（颜色、透明度） | **150–200ms** | `ease-out` |
| 小元素进出（toast、tooltip） | **进 220 / 出 150ms** | `ease-out` / `ease-in` |
| 弹窗、抽屉 | **进 250–280 / 出 180ms** | `cubic-bezier(.4,0,.2,1)` |
| 页面切换 | **250–350ms** | 同上 |
| 数字滚动（内容变化） | **600–800ms** | `easeOutExpo` |

### 两条铁律

**① 上限 400ms。** 超过就有"卡"的感觉——用户在等动画播完，而不是在等数据。

**② 进出不对称：退出 = 进入 × 0.7。**

进入慢一点（让用户看清这是什么），退出快一点（他已经在走了，别耽误）。

```css
--dur-enter: 280ms;
--dur-exit:  180ms;
```

---

## 二、缓动曲线（四条，够用）

```css
:root {
  --ease-out:    cubic-bezier(0.0, 0, 0.2, 1);     /* 进入：快起慢停 */
  --ease-in:     cubic-bezier(0.4, 0, 1, 1);       /* 退出：慢起快走 */
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);     /* 位移：两头柔和 */
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);/* 弹性：慎用 */
}
```

| 禁止 | 原因 |
|---|---|
| `linear` | 机械感，像机械臂 |
| 默认 `ease` | 曲线太钝，起停都不利落 |
| `ease-spring` 用在弹窗 | 弹窗弹跳像玩具；只适合点赞、下拉刷新 |

---

## 三、页面切换

### 三种方案

| 方案 | 效果 | 适用 |
|---|---|---|
| **无动画** | 瞬间切换 | 后台管理**默认**，最快 |
| **淡入 + 微位移** | 柔和 | 内容页切换 |
| 共享元素过渡（FLIP） | 连贯 | 列表 → 详情、卡片展开 |

**后台系统推荐：淡入 + 8px 上移**

```css
.page-enter        { opacity: 0; transform: translateY(8px); }
.page-enter-active {
  opacity: 1; transform: translateY(0);
  transition: opacity 200ms var(--ease-out), transform 200ms var(--ease-out);
}
```

**8px 是最舒服的距离**。20px 以上像"飞进来"，很廉价。

### 不要做的

- ❌ **左右滑动切换页面**（后台管理里很怪，只有 tab 切换和移动端手势才用）
- ❌ 缩放整页（`scale(0.9)` 那种）
- ❌ 页面切换时白屏等数据

### 必须有即时反馈

路由切换后内容加载慢时，**顶部进度条先出现**（nprogress 那种），不要白屏等着。

---

## 四、弹窗（Modal）

### 进入：缩放 0.95 → 1

```css
.modal-enter        { opacity: 0; transform: scale(0.95); }
.modal-enter-active {
  opacity: 1; transform: scale(1);
  transition: opacity 250ms var(--ease-out), transform 250ms var(--ease-out);
}
.modal-exit         { opacity: 1; transform: scale(1); }
.modal-exit-active  {
  opacity: 0; transform: scale(0.95);
  transition: opacity 180ms var(--ease-in), transform 180ms var(--ease-in);
}
```

**缩放范围 0.92–0.98**：

| 起始比例 | 观感 |
|---|---|
| 0.5 | 像弹弓射出来，低端 |
| 0.8 | 幅度过大，抢眼 |
| **0.95** | **最稳，几乎无感但能感知到"弹出"** |
| 1.0（只淡入） | 也可以，更克制 |

### 遮罩同步

```css
.mask-enter        { opacity: 0; }
.mask-enter-active { opacity: 1; background: rgba(0,0,0,.45); transition: opacity 250ms var(--ease-out); }
```

**遮罩与弹窗同时开始、同时结束**，不要遮罩先出现再弹窗。

---

## 五、抽屉（Drawer）

位移而非缩放：

```css
.drawer-enter        { transform: translateX(100%); }
.drawer-enter-active {
  transform: translateX(0);
  transition: transform 280ms var(--ease-out);
}
.drawer-exit-active  {
  transform: translateX(100%);
  transition: transform 200ms var(--ease-in);
}
```

**280ms**——比弹窗稍长，因为位移距离大（整屏宽度），太快会有"闪过去"的感觉。

**从左滑入**用 `translateX(-100%)`；**从下弹起**（移动端）用 `translateY(100%)` + 圆角上边。

---

## 六、Toast / Message

### 推荐：从上方滑入 12px

```css
.toast-enter        { opacity: 0; transform: translateY(-12px); }
.toast-enter-active {
  opacity: 1; transform: translateY(0);
  transition: opacity 180ms var(--ease-out), transform 220ms var(--ease-out);
}
.toast-exit         { opacity: 1; transform: translateY(0); }
.toast-exit-active  {
  opacity: 0; transform: translateY(-8px);
  transition: opacity 150ms var(--ease-in), transform 150ms var(--ease-in);
}
```

**三个要点**：

1. **位移只有 8–12px**，不是从屏幕外飞进来
2. **退出比进入快**（150 vs 220ms）
3. **退出时反向移动一小段**，比单纯淡出更有"收走"的感觉

### 多条堆叠

新消息从上方插入，已有的向下让位：

```css
.toast-item { transition: transform 220ms var(--ease-out); }
```

用 `transform: translateY(n)` 让位，**不要动 `top`**（会触发重排）。

### 不要做的

- ❌ 从屏幕顶部外滑入（`translateY(-100%)`）—— 距离太长，像通知栏
- ❌ 弹跳
- ❌ 停留时间也做动画（停留就是停留，2–3 秒后消失）

---

## 七、列表项的增删

### 删除：淡出 + 高度收起

```css
.row-exit        { opacity: 1; max-height: 55px; }
.row-exit-active {
  opacity: 0; max-height: 0; overflow: hidden;
  transition: opacity 150ms var(--ease-in), max-height 200ms var(--ease-in);
}
```

**不收起高度的话，下方元素瞬间跳上去**——这是列表页最刺眼的抖动。

**总时长 ≤ 250ms。**

### 新增：淡入 + 轻微上移

```css
.row-enter        { opacity: 0; transform: translateY(-8px); }
.row-enter-active {
  opacity: 1; transform: translateY(0);
  transition: opacity 200ms var(--ease-out), transform 200ms var(--ease-out);
}
```

### 用 FLIP 做位置重排

如果列表项顺序会变（排序、拖拽），用 FLIP 而不是逐个算高度：

```js
// 记录旧位置 → 改 DOM → 算差值 → 用 transform 补回去 → 播动画
const first = el.getBoundingClientRect()
// ...DOM 变化...
const last = el.getBoundingClientRect()
el.style.transform = `translateY(${first.top - last.top}px)`
requestAnimationFrame(() => {
  el.style.transition = 'transform 250ms var(--ease-out)'
  el.style.transform = ''
})
```

---

## 八、数字变化（统计、total）

老大提到的 total 变化：

```tsx
<CountUp end={total} duration={0.6} easing="easeOutExpo" />
```

| 规则 | 说明 |
|---|---|
| 时长 **600–800ms** | 比 UI 动效长，因为是内容变化，用户要看数字跑 |
| 缓动 `easeOutExpo` | 先快后慢，末尾清晰停下 |
| **首次渲染不动画** | 只在值真正变化时滚 |
| 变化幅度大时才滚 | 128 → 129 直接改，不要滚 |

**但注意**：分页的「共 128 条」**不要做淡入淡出**——它是信息不是装饰，每次翻页闪一下很烦。

**判断标准**：这个数字的变化值不值得用户"看着它变"？
- 值得（仪表盘核心指标）→ 滚动
- 不值得（列表总数）→ 直接替换

---

## 九、加载动画

### 优先级

```
Skeleton（预告布局） > Spinner（局部） > 空白
```

### 延迟显示（关键，最常被忽略）

**加载快于 300ms 时不要显示 loading**，否则会闪一下，比不显示还难受。

```tsx
function useDelayedLoading(isLoading: boolean, delay = 300) {
  const [show, setShow] = useState(false)
  useEffect(() => {
    if (!isLoading) { setShow(false); return }
    const t = setTimeout(() => setShow(true), delay)
    return () => clearTimeout(t)
  }, [isLoading, delay])
  return show
}
```

### Spinner 参数

- 周期 **0.8–1.2s**（太快像卡住，太慢像死了）
- 尺寸跟场景走：按钮内 14px、区块 24px、整页 40px

---

## 十、无障碍：必须支持减少动画

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

前庭功能障碍用户对位移和缩放动画会**生理性不适**（眩晕、恶心）。这不是可选项。

---

## 十一、性能：只动两个属性

| 可动 | 不可动 |
|---|---|
| ✅ `transform` | ❌ `width` / `height` |
| ✅ `opacity` | ❌ `top` / `left` / `right` / `bottom` |
| ✅ `filter`（慎用） | ❌ `margin` / `padding` |
|  | ❌ `background-color`（会重绘，量小可接受） |

**为什么**：`transform` 和 `opacity` 走合成层，不触发 layout / paint；动其他属性每一帧都要重排，60fps 保不住。

### 需要高度动画时

用 `max-height`（配一个足够大的值）或 FLIP，**不要直接动 `height: auto`**（无法动画）。

### will-change 的用法

```css
/* ❌ 一直挂着，占用显存 */
.modal { will-change: transform; }

/* ✅ 动画前加，结束后移除 */
.modal.is-animating { will-change: transform; }
```

---

## 十二、验收清单

- [ ] 所有动画时长在分级表范围内，**没有一个超过 400ms**
- [ ] 退出时长 = 进入 × 0.7 左右
- [ ] 没有用 `linear`，也没有用默认 `ease`
- [ ] 页面切换是淡入 + 8px 位移，不是左右滑动
- [ ] 弹窗缩放 0.92–0.98，遮罩与弹窗同步
- [ ] 抽屉位移 280ms
- [ ] toast 位移 8–12px，退出比进入快
- [ ] 列表删除有高度收起，下方元素平滑上移
- [ ] 数字滚动 600–800ms 且首次渲染不动画
- [ ] loading 延迟 300ms 才显示
- [ ] `prefers-reduced-motion` 已支持
- [ ] 只动 `transform` / `opacity`，无 `width`/`height`/`top` 动画
- [ ] `will-change` 用完移除

---

## 十三、反面清单

1. ❌ 动画 500ms 以上（用户在等动画）
2. ❌ 用 `linear` 或默认 `ease`
3. ❌ 弹窗从 `scale(0.5)` 弹出来
4. ❌ 退出和进入一样慢
5. ❌ 页面切换左右滑动（后台管理）
6. ❌ toast 从屏幕外飞入
7. ❌ 列表删除时下方元素瞬间跳上去
8. ❌ loading 不延迟显示，快速请求闪一下
9. ❌ 动 `height` / `top` 导致掉帧
10. ❌ 不支持 `prefers-reduced-motion`
11. ❌ 「共 128 条」也做淡入淡出
12. ❌ 给所有元素挂 `will-change`
