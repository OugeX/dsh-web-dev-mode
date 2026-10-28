---
name: form-design-spec
description: 表单与输入框的细节设计规范。包含输入框八态状态机与 transition 参数、focus ring 实现、placeholder 与 help text 与 error 的三层文案分工与防跳动布局、必填星号标记规则、校验时机（blur/submit/onChange 清除）与异步校验 debounce、错误汇总与滚动定位、密码/手机号/验证码/金额/日期等特殊输入、移动端表单布局与键盘类型、字数统计与防重复提交。当写表单、调输入框样式与动画、设计错误提示、或发现表单布局在报错时跳动时使用。
---

# 定位：状态、文案、时机，三件事定死

表单的所有争议都在这三处：**输入框长什么样、提示说什么、什么时候说**。

---

## 一、输入框八态（必须全覆盖）

| 状态 | 边框 | 背景 | 其他 |
|---|---|---|---|
| **default** | `#d9d9d9` | `#fff` | — |
| **hover** | `#4096ff` | `#fff` | — |
| **focus** | `#1677ff` | `#fff` | **focus ring**：`box-shadow: 0 0 0 2px rgba(22,119,255,.2)` |
| **filled** | `#d9d9d9` | `#fff` | 值与 placeholder 区分（值用 `colorText`） |
| **error** | `#ff4d4f` | `#fff` | 下方红字，focus 时 ring 变红 |
| **disabled** | `#d9d9d9` | `#f5f5f5` | 文字 `#00000040`，`cursor: not-allowed` |
| **readonly** | `#d9d9d9` | `#fafafa` | 可选中复制，不可编辑 |
| **loading**（异步校验中） | `#d9d9d9` | `#fff` | 右侧 suffix 转圈 |

### focus ring 的实现（不要用 outline）

```css
.input:focus {
  outline: none;
  border-color: #1677ff;
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.2);   /* 用 shadow 而不是 outline */
  transition: border-color .15s, box-shadow .15s;
}
```

**为什么不用 `outline`**：outline 不占布局但无法做圆角、无法控制偏移、部分浏览器样式不一致。`box-shadow` 可控且不引起重排。

### 过渡参数（统一，不要每处不同）

| 属性 | 时长 | 缓动 |
|---|---|---|
| 边框色 | **150ms** | `ease-out` |
| focus ring | **150ms** | `ease-out` |
| 错误文字淡入 | **200ms** | `ease-out` |
| 高度展开（错误占位） | **150ms** | `ease-out` |

**不要用抖动动画**（`transform: translateX` 左右晃）——廉价感强，且会让用户觉得被指责。

---

## 二、三层文案，各司其职（最容易混）

| 层 | 位置 | 内容 | 生命周期 |
|---|---|---|---|
| **label** | 输入框上方/左侧 | 字段名，**必须有** | 常驻 |
| **placeholder** | 输入框内 | **示例值**，不是字段名 | 有值时消失 |
| **help text** | 输入框下方灰字 | 格式说明、注意事项 | 常驻 |
| **error** | 输入框下方红字（**与 help 同位置**） | 具体错误 + 怎么改 | 出错时显示 |

### 三条硬规则

**① placeholder 不能代替 label**

```html
<!-- ❌ 值一填就不知道这是什么字段 -->
<input placeholder="请输入手机号" />
```

```html
<!-- ✅ -->
<label>手机号</label>
<input placeholder="例如 138 0013 8000" />
```

**placeholder 应该是示例，不是指令。** 「例如 138 0013 8000」比「请输入手机号」有用。

**② error 和 help text 占同一个位置**

```tsx
// ✅ 固定高度容器，二者互斥显示，布局不跳
<div className="field-footer" style={{ minHeight: 22 }}>
  {error ? <span className="error">{error}</span> : <span className="help">{help}</span>}
</div>
```

**布局跳动是表单最常见的体验问题**：报错时下面所有字段往下推，用户正在填的那个跑了。

**③ 文案要具体可执行**

| ❌ 差 | ✅ 好 |
|---|---|
| 输入有误 | 手机号应为 11 位数字 |
| 格式错误 | 邮箱缺少 @ 符号 |
| 操作失败 | 验证码已过期，请重新获取 |
| 必填 | 请填写公司名称 |
| 密码错误 | 账号或密码错误（**不要区分哪一个错**，防枚举） |

---

## 三、必填标记

### 规则

- **只标必填，不标选填**（除非选填占多数）
- 星号 `*` 放在 **label 前**：`* 手机号`
- 星号颜色 `#ff4d4f`，但要加无障碍文本

```tsx
<label>
  <span aria-hidden="true" style={{ color: '#ff4d4f' }}>*</span>
  <span className="sr-only">必填</span>
  手机号
</label>
```

**「sr-only」不能省**：读屏用户听不到星号，必须给文本。

### 反过来：选填多于必填时

比如"完善资料"页 12 个字段只有 2 个必填——这时标「(选填)」更省视觉噪音，标题旁加一句「带 (选填) 的可稍后填写」。

---

## 四、校验时机（做错最多的地方）

### 四个时机，各管一件事

| 时机 | 做什么 | 不做什么 |
|---|---|---|
| **onChange** | ① 清除已有错误 ② 长度/字数统计 | **不报新错** |
| **onBlur** | 校验格式（手机号、邮箱、密码长度） | 不校验唯一性（避免每次失焦都请求） |
| **onSubmit** | 全量校验 | — |
| **异步校验** | 唯一性（用户名、手机号是否已注册） | 必须 debounce **500ms** + loading 态 |

### 为什么 onChange 不报错

用户输 `138` 时提示"手机号格式错误"——他还没输完。**这是最招人烦的体验。**

正确做法：

```tsx
const [touched, setTouched] = useState(false)

onChange: (e) => {
  setValue(e.target.value)
  if (touched && error) setError(null)      // 已报过错 → 输入时立即清除
}
onBlur: () => {
  setTouched(true)
  validate(value)                            // 第一次校验
}
```

### 提交时的两个细节

**① 滚动到第一个错误字段并 focus**

```ts
const firstError = document.querySelector('.ant-form-item-has-error input')
firstError?.scrollIntoView({ block: 'center', behavior: 'smooth' })
;(firstError as HTMLInputElement)?.focus()
```

不滚动的话，字段多时用户看不到哪里错了。

**② 多个错误时用顶部 Alert 汇总**

字段超过 6 个且错误不止一处时，顶部加一条：

> 表单有 3 处需要修改

点击可跳转到对应字段。

---

## 五、特殊输入

| 类型 | 要点 |
|---|---|
| **密码** | 右侧眼睛图标切换显示；`autocomplete="current-password"` / `new-password` |
| **手机号** | `inputmode="numeric"` + `autocomplete="tel"`；区号选择器在前 |
| **验证码** | 4–6 格分栏，输入后自动跳下一格，支持整串粘贴填充 |
| **金额** | `InputNumber` + `precision=2` + 千分位显示；右侧单位（元/万元） |
| **日期** | `DatePicker`，**不要手输**；范围选择用 RangePicker |
| **文本域** | `rows=3` 起；右下角字数统计 `12/200`；超限变红但不阻止输入（提交时拦） |

### 验证码分栏输入的关键行为

```tsx
// 粘贴 "1234" 应填满四格，不是只填第一格
onPaste: (e) => {
  const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 4)
  if (text) { fillAll(text); e.preventDefault() }
}
// 输入后自动 focus 下一格；Backspace 空格时回退上一格
```

---

## 六、移动端表单

| 项 | 桌面 | 移动端 |
|---|---|---|
| label 位置 | 左侧对齐 | **顶部对齐**（横向空间不够） |
| 输入框高度 | 40 | **48** |
| 字段间距 | 20 | 24 |
| 字号 | 14 | **≥16（防 iOS 自动放大）** |
| 提交按钮 | 页面内 | **固定底部 + `env(safe-area-inset-bottom)`** |

### 键盘类型（用 `inputmode`，不要靠 type 猜）

```html
<input inputmode="numeric">     <!-- 数字键盘，但仍可输入前导 0 -->
<input inputmode="tel">         <!-- 电话键盘 -->
<input inputmode="email">       <!-- 带 @ 的键盘 -->
<input inputmode="decimal">     <!-- 带小数点的数字 -->
```

**`type="number"` 的坑**：会丢前导 0、滚轮会改值、移动端键盘不一定有小数点。**用 `inputmode` + `type="text"`。**

### autocomplete 一定要写

```html
<input autocomplete="username">
<input autocomplete="current-password">
<input autocomplete="new-password">
<input autocomplete="one-time-code">
<input autocomplete="tel">
```

不写的话，密码管理器无法识别，用户每次手输。

---

## 七、提交按钮

- 文案用**动词**：「登录」「保存」「创建订单」，不要「提交」「确定」
- 提交中：`loading` + 禁用 + 文案变「登录中…」
- **防重复提交**：提交瞬间置 `submitting` 标志，成功/失败后才解除
- 失败后按钮恢复可点，不要卡死
- 危险操作按钮用 `danger`

---

## 八、验收清单

- [ ] 八种状态都有明确视觉，focus 用 box-shadow 而非 outline
- [ ] 过渡统一 150ms，无抖动动画
- [ ] 每个字段都有 label，placeholder 是示例不是字段名
- [ ] error 与 help text 占同一位置，报错时布局不跳动
- [ ] 必填星号在 label 前 + 有 sr-only 文本
- [ ] onChange 不报新错，onBlur 才校验格式
- [ ] 异步校验有 500ms debounce + loading
- [ ] 提交时滚动到第一个错误字段并 focus
- [ ] 密码有显示/隐藏切换
- [ ] 验证码支持整串粘贴
- [ ] 移动端 label 顶部对齐、输入框 48 高、字号 ≥16
- [ ] `inputmode` 与 `autocomplete` 都写了
- [ ] 提交按钮有 loading 与防重复提交

---

## 九、反面清单

1. ❌ 用 placeholder 当 label
2. ❌ 输入过程中实时报「格式错误」
3. ❌ 报错时把下方字段往下推（布局跳动）
4. ❌ 用抖动动画提示错误
5. ❌ 密码框没有显示/隐藏
6. ❌ 验证码不能整串粘贴
7. ❌ 移动端 `type="number"` 导致丢前导 0
8. ❌ 不写 `autocomplete`，密码管理器失效
9. ❌ 提交按钮无 loading，用户点三次
10. ❌ 错误文案写「操作失败」不写原因
11. ❌ 登录失败区分「账号不存在」和「密码错误」（可枚举用户）
