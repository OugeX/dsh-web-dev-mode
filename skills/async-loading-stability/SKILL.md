---
name: async-loading-stability
description: 异步加载与页面防抖动的规范。包含 CLS 三大来源（尺寸未知/尺寸变化/元素插入）、骨架屏行数必须等于 pageSize、表格列宽固定与 table-layout:fixed、分页切换不清空数据、容器 min-height、图片 aspect-ratio、按钮 loading 宽度不变、Alert 预留空间、字体 font-display、滚动条 scrollbar-gutter、骨架屏与真实内容的形状匹配、CLS 测量方法与 <0.1 目标。当写列表页骨架屏、切换分页时页面跳动、图片加载后撑开布局、按钮文字变化导致宽度抖动、或做性能优化时使用。
---

# 定位：先占位，再填内容

**所有异步内容都必须有尺寸确定的占位。** 不知道尺寸就不知道会跳多高。

---

## 一、抖动的三个来源（对号入座）

| 来源 | 典型场景 | 解法 |
|---|---|---|
| **尺寸未知** | 图片没写宽高、iframe、异步组件 | 预留 `aspect-ratio` / 固定高度 |
| **尺寸变化** | 骨架 3 行 → 数据 8 行、列宽自适应、按钮文案变长 | 行数与数据一致、列宽固定、按钮宽度不变 |
| **元素插入** | Alert 出现、错误文字、通知条 | 预留空间或改用浮层 |

### 量化目标

**CLS（Cumulative Layout Shift）< 0.1** 为「良好」。

单个元素移动超过**视口高度的 10%** 就算一次明显偏移。

---

## 二、列表页：最常抖动的地方

### 2.1 骨架屏行数 = `pageSize`

```tsx
// ❌ 骨架固定 3 行，数据 20 行 → 加载完高度暴涨
{isLoading && <Skeleton active paragraph={{ rows: 3 }} />}

// ✅ 与 pageSize 一致
const PAGE_SIZE = 20
{isLoading && (
  <div className="skeleton-table">
    {Array.from({ length: PAGE_SIZE }).map((_, i) => (
      <div key={i} className="skeleton-row" />   // 每行高度 = 真实行高
    ))}
  </div>
)}
```

**骨架行高必须等于真实行高**（AntD 表格默认 55px）。差 5px × 20 行 = 100px 的跳动。

### 2.2 表格列宽必须固定

```css
.table { table-layout: fixed; }   /* ★ 不写就是 auto，列宽随内容变 */
```

```tsx
// AntD：用 width 显式指定，不要靠自动分配
const columns = [
  { title: '订单号', dataIndex: 'no',      width: 180 },
  { title: '客户',   dataIndex: 'customer', width: 120, ellipsis: true },
  { title: '金额',   dataIndex: 'amount',   width: 120, align: 'right' },
  { title: '操作',   width: 140, fixed: 'right' },
]
```

**`table-layout: auto` 是最隐蔽的抖动源**：第一页的客户名都短，列宽 80px；第二页有长名字，列宽变成 160px —— 整张表横向跳。

### 2.3 换页时不要清空数据

```tsx
// ❌ 换页先清空 → 闪白 → 再画出新数据，两次跳动
onPageChange: (p) => {
  setData([])           // ← 删掉这行
  setPage(p)
  refetch()
}

// ✅ 保留上一页数据，用 loading 遮罩提示
<Table
  dataSource={data}
  loading={{ spinning: isFetching, tip: '' }}   // 只加遮罩，不清空
/>
```

如果一定要清空，就用**同样行数的骨架**填充，保持高度。

### 2.4 容器预留最小高度

```css
.table-wrapper {
  min-height: 400px;    /* 0 条数据时也不塌陷 */
}
```

否则"有数据 600px / 空数据 120px"会让下方分页器和页脚上下跳。

### 2.5 空态也要占位

空态不能是"表格消失 + 一行小字"，应该是**与表格同高的 Empty 块**：

```tsx
<Empty style={{ minHeight: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }} />
```

---

## 三、图片：必须给尺寸

### 3.1 三种写法，任选其一

```html
<!-- ① 宽高属性（最简单，浏览器自动算比例） -->
<img src="..." width="320" height="200" alt="">

<!-- ② CSS aspect-ratio -->
<img src="..." style="width: 100%; aspect-ratio: 16 / 9; object-fit: cover" alt="">

<!-- ③ 固定高度容器 + object-fit -->
<div style="height: 200px; overflow: hidden">
  <img src="..." style="width: 100%; height: 100%; object-fit: cover" alt="">
</div>
```

**没有宽高的图片，加载完必然撑开布局**——这是 CLS 的第一大来源。

### 3.2 占位背景

```css
.img-wrapper {
  background: #f5f5f5;              /* 加载前是灰块，不是空白 */
  border-radius: 8px;
  overflow: hidden;
}
```

### 3.3 头像列表尤其注意

20 个头像如果都没定尺寸，加载完整个列表会往下推 20 次。

```tsx
<Avatar size={40} src={user.avatarUrl} />
// size 显式给定，AntD 会预留空间
```

---

## 四、按钮：loading 时宽度不能变

```tsx
// ❌ 「登录」→「登录中…」宽度变化，按钮和旁边元素一起跳
<Button loading={submitting}>{submitting ? '登录中…' : '登录'}</Button>

// ✅ 方案 A：固定宽度
<Button loading={submitting} style={{ width: 120 }}>登录</Button>

// ✅ 方案 B：文案不变，只加 loading 图标
<Button loading={submitting}>登录</Button>
```

**推荐方案 B**：AntD 的 `loading` 会在左侧加 spinner，按钮宽度变化约 16px —— 用 `min-width` 兜住：

```css
.ant-btn { min-width: 88px; }
```

---

## 五、提示条与错误信息

### 5.1 Alert 会推动内容

```tsx
// ❌ 出现时把下方内容全推下去
{showAlert && <Alert message="账户未实名" />}

// ✅ 方案 A：预留空间（高度固定）
<div style={{ minHeight: showAlert ? 'auto' : 0 }}>
  {showAlert && <Alert ... />}
</div>

// ✅ 方案 B：浮层，不占流（更推荐）
<div style={{ position: 'fixed', top: 64, left: 0, right: 0, zIndex: 100 }}>
  {showAlert && <Alert ... />}
</div>
```

**判断标准**：这条提示是不是必须常驻被看到？
- 是 → 预留空间
- 只是临时提醒 → 用 `message` 或浮层

### 5.2 表单错误（已在 form-design-spec 说过）

error 与 help text **占同一位置、固定高度**，否则报错时下方所有字段往下推。

---

## 六、字体加载导致的抖动

### 6.1 用系统字体栈（零延迟）

```css
font-family: -apple-system, BlinkMacSystemFont, "PingFang SC",
             "Microsoft YaHei", "Helvetica Neue", sans-serif;
```

### 6.2 必须用自定义字体时

```css
@font-face {
  font-family: 'CustomFont';
  src: url('/fonts/custom.woff2') format('woff2');
  font-display: swap;        /* ★ 先用系统字体渲染，加载完替换 */
  /* 用 size-adjust / ascent-override 对齐度量，减少替换时的跳动 */
  size-adjust: 105%;
}
```

**`font-display: swap` 的代价是字体会"闪一下"**（FOUT），但比"白屏等字体"（FOIT）体验好。要彻底消除就用 `preload` + 字体子集化。

---

## 七、滚动条出现/消失

**问题**：内容从短变长 → 出现滚动条 → 页面可用宽度少 15px → 所有居中元素横向跳一下。

```css
/* ✅ 方案 A：始终预留滚动条槽位（现代浏览器） */
html { scrollbar-gutter: stable; }

/* ✅ 方案 B：始终显示滚动条 */
html { overflow-y: scroll; }
```

**弹窗打开时**也要处理：`body { overflow: hidden }` 会让滚动条消失 → 页面横向跳 15px。

```js
// 打开弹窗时补齐宽度
const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
document.body.style.paddingRight = `${scrollbarWidth}px`
document.body.style.overflow = 'hidden'
```

---

## 八、骨架屏设计规范

### 8.1 形状必须匹配真实内容

| 真实内容 | 骨架 |
|---|---|
| 头像 40×40 圆形 | 40×40 圆形灰块 |
| 标题一行 24px | 高度 24px，宽度 60% |
| 正文三行 | 三行，每行高度 = 行高 |
| 按钮 88×32 | 88×32 圆角矩形 |
| 表格 20 行 | 20 行，行高 55px |

**骨架不是装饰，是尺寸预告。** 形状对不上就起不到防抖作用。

### 8.2 动画规范

```css
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
.skeleton {
  background: linear-gradient(90deg, #f2f2f2 25%, #e6e6e6 37%, #f2f2f2 63%);
  background-size: 400% 100%;
  animation: shimmer 1.5s ease infinite;
}

/* 尊重系统的"减少动画"偏好 */
@media (prefers-reduced-motion: reduce) {
  .skeleton { animation: none; }
}
```

**周期 1.5s**，太快显得焦躁，太慢像卡住。

### 8.3 骨架屏 vs Spin 的选择

| 场景 | 用什么 |
|---|---|
| 首屏、整页、列表初次加载 | **骨架屏**（预告布局） |
| 局部刷新、翻页、二次请求 | **Spin 遮罩**（有数据在，只提示更新中） |
| 按钮提交 | Button loading |
| 弹窗内容加载 | 弹窗内骨架 |

---

## 九、路由与代码分割

```tsx
// 懒加载时 fallback 要有高度，否则内容到达时整页跳
<Suspense fallback={<div style={{ minHeight: '100vh' }} />}>
  <Routes>...</Routes>
</Suspense>
```

**路由切换用顶部进度条**（`nprogress` 那种），不要整页白屏。

---

## 十、测量与验证

### 10.1 浏览器

- Chrome DevTools → Performance → 勾选 **Layout Shift**，录屏会标出红色偏移区域
- Lighthouse 的 CLS 分数

### 10.2 代码里监控

```ts
new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (!(entry as any).hadRecentInput) {
      console.warn('布局偏移', {
        value: (entry as any).value,
        sources: (entry as any).sources?.map((s: any) => s.node),
      })
    }
  }
}).observe({ type: 'layout-shift', buffered: true })
```

开发期打开，就能看到每次抖动是哪个元素造成的。

### 10.3 手动验证清单

| 场景 | 观察点 |
|---|---|
| 首屏加载 | 骨架 → 数据的切换有没有跳 |
| 翻页 | 表格高度有没有变 |
| 筛选条件变化 | 结果 0 条时布局有没有塌 |
| 图片列表 | 图片加载完有没有往下推 |
| 点提交 | 按钮宽度有没有变 |
| 出现 Alert | 下方内容有没有下移 |
| 长内容页面滚动 | 滚动条出现时有没有横跳 |
| 弹窗打开 | 背景有没有横跳 |

---

## 十一、验收清单

- [ ] 骨架屏行数 = `pageSize`，行高 = 真实行高
- [ ] 表格 `table-layout: fixed`，所有列有显式 `width`
- [ ] 换页时不清空已有数据，只加 loading 遮罩
- [ ] 表格容器有 `min-height`
- [ ] 空态有与表格同高的占位
- [ ] 所有图片有 `width`/`height` 或 `aspect-ratio`
- [ ] 按钮 loading 时宽度不变（`min-width` 兜底）
- [ ] Alert 要么预留空间，要么用浮层
- [ ] 表单 error 与 help 占同一位置
- [ ] `font-display: swap`
- [ ] `scrollbar-gutter: stable` 或 `overflow-y: scroll`
- [ ] 弹窗打开时补 `padding-right` 防横跳
- [ ] 骨架屏形状匹配真实内容，动画 1.5s，支持 `prefers-reduced-motion`
- [ ] `Suspense` fallback 有高度
- [ ] 开发期用 `PerformanceObserver` 检查过 CLS < 0.1

---

## 十二、反面清单

1. ❌ 骨架固定 3 行，数据 20 行
2. ❌ 表格 `table-layout: auto`
3. ❌ 换页时先 `setData([])`
4. ❌ 图片不写宽高
5. ❌ 按钮文案从「登录」变「登录中…」
6. ❌ 空态只放一行小字，表格高度塌陷
7. ❌ 弹窗打开只设 `overflow: hidden` 不补宽度
8. ❌ 骨架用圆形代替方形，形状不匹配
9. ❌ `Suspense` fallback 是 `null`
10. ❌ 从不测量 CLS，靠感觉判断有没有抖
