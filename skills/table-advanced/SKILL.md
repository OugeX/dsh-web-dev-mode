---
name: table-advanced
description: 表格的进阶设计规范。包含列宽策略（固定/自适应/按内容）与 table-layout:fixed 的必要性、固定列与横向滚动的判断标准、行内编辑与弹窗编辑的选择判据、树形表格与展开行的适用场景、行选择的单选多选与跨页保持、排序筛选分组、大数据量虚拟滚动、表头吸顶、列设置与顺序持久化。当写复杂列表页、列数超过 6 列、需要固定列或横向滚动、要加行内编辑或树形表格、或表格卡顿需要虚拟滚动时使用。
---

# 定位：先定列宽，再谈功能

**表格 80% 的体验问题来自列宽。** 列宽不稳 → 抖动；列太多 → 必须固定列；固定列没配好 → 错位。

---

## 一、列宽策略

### 1.1 必须 `table-layout: fixed`

```css
.table { table-layout: fixed; }   /* AntD Table 已默认，手写原生表格要自己加 */
```

`auto` 会让列宽随内容变化：第一页名字短、列宽 80px，第二页名字长、变 160px —— **整张表横向跳**。

### 1.2 三类列的宽度分配

| 列类型 | 策略 | 例 |
|---|---|---|
| **固定宽**（可预估） | 显式 `width` | 序号 60、日期 160、状态 100、操作 140 |
| **弹性宽**（文本长度不定） | 不设 width + `ellipsis` | 客户名、商品名、备注 |
| **比例宽**（要均分剩余） | 只给最后一列不设宽，其余固定 | — |

```tsx
const columns = [
  { title: '序号',   width: 60,  fixed: 'left' },
  { title: '订单号', width: 180 },
  { title: '客户',   width: 120, ellipsis: true },   // 弹性，超长省略
  { title: '商品',   ellipsis: true },                // 吃掉剩余宽度
  { title: '金额',   width: 120, align: 'right' },
  { title: '状态',   width: 90 },
  { title: '操作',   width: 140, fixed: 'right' },
]
```

**宽度给死的那几列，永远不要自动算。**

### 1.3 长文本：`ellipsis` + Tooltip

```tsx
{
  title: '备注', dataIndex: 'remark', ellipsis: { showTitle: false },
  render: (v) => <Tooltip title={v}><span>{v}</span></Tooltip>,
}
```

**不要**为了让内容完整显示而撑宽列——那样整张表就崩了。

---

## 二、固定列与横向滚动

### 2.1 什么时候需要固定列

**判断标准：总宽 > 容器宽度 × 1.3**

粗略估算：`Σ 列宽 > 1200px` 且容器是 1440 屏时就会出现横向滚动。

| 列数 | 是否固定 |
|---|---|
| ≤ 6 且总宽 < 1000 | **不需要** |
| > 6 或总宽 > 1200 | **固定前 1 列（标识）+ 最后一列（操作）** |

### 2.2 固定列的规则

- **左侧固定**：只固定**一个标识列**（序号或名称），不要固定两列以上
- **右侧固定**：只固定**操作列**
- **固定列必须有背景色**，否则滚动时内容会透出来
- 固定列**不能有 `ellipsis` 的过长内容**，宽度必须够

```css
.ant-table-cell-fix-left,
.ant-table-cell-fix-right {
  background: #fff;          /* 不设会透 */
  z-index: 2;
}
```

### 2.3 横向滚动的三个坑

| 坑 | 修法 |
|---|---|
| 滚动条在表格底部，看不到 | 把滚动容器提到表格外层，或用 `scroll={{ x: 'max-content' }}` |
| 固定列与滚动列高度不一致（内容换行） | 固定列内容必须单行 + `ellipsis` |
| 表头不跟随横向滚动 | AntD 默认跟随；手写表格要给 `thead` 也加 `position: sticky` |

---

## 三、行内编辑

### 3.1 何时用行内编辑

| 场景 | 方案 |
|---|---|
| 改 **1–2 个简单字段**（状态、备注、数量） | **行内编辑** |
| 改多个字段 / 有校验联动 | 抽屉（Drawer） |
| 改关键字段（金额、权限） | 弹窗 + 二次确认 |

**判断标准**：用户要改的字段，是"扫一眼就能改"的，还是要"看着上下文填"的？
- 前者 → 行内
- 后者 → 抽屉

### 3.2 行内编辑的交互模式

| 模式 | 触发 | 保存 |
|---|---|---|
| **点击即编辑**（推荐） | 单击单元格 | Enter 保存 / Esc 取消 / blur 保存 |
| 双击编辑 | 双击 | 同上 |
| 编辑图标 | 点铅笔图标 | 显式保存按钮 |

**推荐「单击即编辑 + blur 自动保存」**——最少的点击次数。

但**必须加乐观更新 + 失败回滚**：

```tsx
const mutate = useMutation({
  mutationFn: api.updateField,
  onMutate: async (vars) => {
    await queryClient.cancelQueries(['orders'])
    const prev = queryClient.getQueryData(['orders'])
    queryClient.setQueryData(['orders'], (old) => patch(old, vars))   // 乐观改
    return { prev }
  },
  onError: (_e, _v, ctx) => {
    queryClient.setQueryData(['orders'], ctx.prev)                    // 回滚
    message.error('保存失败，已恢复原值')
  },
})
```

**没有回滚的行内编辑是灾难**：用户以为改了，实际没改。

### 3.3 行内编辑的视觉

- 编辑中的单元格要**有明确边框**（看起来像输入框）
- 保存中显示小型 loading（可以是边框变蓝 + 右上角小圈）
- 保存成功后**闪一下绿色**（150ms），给"已保存"反馈
- **不要整行都变成编辑态**，只编辑那一格

---

## 四、树形表格与展开行

### 4.1 树形表格（有层级的数据）

```tsx
<Table
  dataSource={tree}
  expandable={{ defaultExpandAllRows: false, indentSize: 20 }}
  pagination={false}        // ★ 树形表格通常不分页
/>
```

| 用树形表格 | 不用 |
|---|---|
| 数据本身有父子关系（部门、分类、菜单） | 只是想展示更多详情 |
| 层级 ≤ 3 层 | 层级 > 3（改用级联选择或钻取） |

**树形表格不要分页**——分页会把子节点切断。

### 4.2 展开行（看详情）

```tsx
expandable={{
  expandedRowRender: (record) => <OrderDetail id={record.id} />,
  rowExpandable: (record) => record.hasDetail,
}}
```

| 用展开行 | 用抽屉 |
|---|---|
| 详情很短（3–5 行文本） | 详情复杂（表格、图表、操作） |
| 要**同时看多条**详情做对比 | 只看一条 |
| 不打断列表浏览 | 需要专注 |

**同一时间最多展开 1–2 行**，多了列表会失控。

### 4.3 展开行与分页的冲突

展开状态**换页后要清空**，否则用户会困惑"我展开的行去哪了"。

```tsx
onPageChange: () => setExpandedRowKeys([])
```

---

## 五、行选择

### 5.1 单选 vs 多选

| 用途 | 模式 |
|---|---|
| 选一条做操作（查看、编辑） | **不用 checkbox**，直接点行 |
| 批量操作（删除、导出、改状态） | 多选 checkbox |
| 需要指定"主记录" | 单选 radio |

**默认不要加 checkbox**——只有存在批量操作时才加。

### 5.2 跨页选择

```tsx
rowSelection={{
  selectedRowKeys,
  preserveSelectedRowKeys: true,   // ★ 换页保持
  onChange: setSelectedRowKeys,
}}
```

**必须给明确的视觉反馈**：工具栏显示「已选 3 项（跨 2 页）」。

否则用户翻页后勾选消失，会以为选择丢了。

### 5.3 全选的语义

| 头部的全选 | 含义 |
|---|---|
| 只选当前页 | **默认**，最常见的误解来源 |
| 选全部（含其他页） | 需要单独提供「选择全部 128 条」链接 |

```tsx
// AntD 的 tableAlertRender 里给这个链接
{tableAlertRender: ({ selectedRowKeys }) => (
  <span>
    已选 {selectedRowKeys.length} 项
    <a onClick={selectAllAcrossPages}>选择全部 {total} 条</a>
  </span>
)}
```

---

## 六、排序、筛选、分组

### 6.1 排序

- **服务端排序**，不要前端排（前端只能排当前页）
- 可排序列在表头显示排序图标
- 三态切换：无 → 升序 → 降序 → 无
- 默认排序在进入页面时**显式显示**（表头高亮），不要偷偷排

### 6.2 列筛选

- 筛选器挂在表头（漏斗图标）
- 选中后表头**高亮**，并在工具栏显示已选条件
- 筛选变更时 `page` 重置为 1

### 6.3 分组（行合并）

```tsx
{
  title: '部门', dataIndex: 'dept',
  onCell: (record, index, data) => ({
    rowSpan: index > 0 && data[index - 1].dept === record.dept ? 0 : countSameDept(data, index),
  }),
}
```

**只在数据已按该字段排序时用**，否则合并会错乱。

---

## 七、大数据量：虚拟滚动

| 行数 | 方案 |
|---|---|
| < 100 | 普通渲染 |
| 100–500 | 分页（pageSize 20–50） |
| **> 500 且必须一屏看** | **虚拟滚动** |

```tsx
import { TableVirtuoso } from 'react-virtuoso'
// 或 AntD 的 virtual prop（5.x 支持）
<Table virtual scroll={{ y: 600 }} />
```

**虚拟滚动的代价**：
- 行高必须固定（不能自动换行）
- 不能用展开行
- 固定列支持有限
- 打印/截图会缺内容

**能分页就分页，虚拟滚动是最后手段。**

---

## 八、表头吸顶

```css
.ant-table-thead > tr > th {
  position: sticky;
  top: 0;               /* 或者 header 的高度 */
  z-index: 3;
  background: #fafafa;
}
```

**页面有固定头部时**，`top` 要等于头部高度，否则表头会藏在头部下面。

---

## 九、列设置与顺序持久化

列多时给用户「列设置」：

```tsx
<Popover content={<ColumnSetting columns={all} value={visible} onChange={setVisible} />}>
  <Button icon={<SettingOutlined />} />
</Popover>
```

- 选择显示哪些列
- 拖拽调整顺序
- **持久化到 `localStorage`**（按用户 + 页面区分 key）
- 至少要能「恢复默认」

---

## 十、验收清单

- [ ] `table-layout: fixed`，所有列有明确宽度策略
- [ ] 长文本列用 `ellipsis` + Tooltip，不撑宽
- [ ] 总宽 > 1200px 时有左侧固定列（标识）与右侧固定列（操作）
- [ ] 固定列有背景色，无换行
- [ ] 横向滚动时表头跟随
- [ ] 行内编辑有乐观更新 + 失败回滚 + 已保存反馈
- [ ] 行内编辑只改 1–2 个简单字段
- [ ] 树形表格不分页，展开行换页时清空
- [ ] 行选择跨页保持，工具栏显示「跨 N 页」
- [ ] 全选语义明确（当前页 or 全部）
- [ ] 排序是服务端排，三态切换
- [ ] 筛选后 page 重置为 1
- [ ] > 500 行且必须一屏看时才用虚拟滚动
- [ ] 表头吸顶的 `top` 避开固定头部
- [ ] 列设置有持久化与恢复默认

---

## 十一、反面清单

1. ❌ 表格 `table-layout: auto`
2. ❌ 固定两个以上的左侧列
3. ❌ 固定列没有背景色（滚动时透出内容）
4. ❌ 行内编辑没有失败回滚
5. ❌ 行内编辑整行变编辑态
6. ❌ 树形表格开分页
7. ❌ 换页后展开行还留着
8. ❌ 跨页选择不保持，勾选静默丢失
9. ❌ 全选只选当前页但不说明
10. ❌ 前端排序（只能排当前页，是错的）
11. ❌ 200 行就上虚拟滚动（分页更简单）
12. ❌ 表头吸顶被固定头部盖住
