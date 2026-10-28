---
name: react-frontend-architecture
description: React 后台系统的前端预制规范。包含 src 目录分层与各层职责边界、统一登录态（token 存储、自动续期、并发 401 去重、路由守卫、按钮级权限）、axios 拦截器链、TanStack Query 与 Zustand 的状态边界、列表页三态与 URL 同步分页、表单与弹窗规范、AntD 主题 token、前后端类型契约、验收清单。当新建前端工程、设计目录结构、实现登录与权限、写列表页表单页、或评审前端代码是否合规时使用。
---

# 定位：预制件，不是参考资料

新前端工程按本文执行。**不要重新讨论目录名、不要发明状态管理方案、不要把服务端数据塞进 Zustand。**

后端配套见 `web-project-bootstrap`；本文只负责前端。

---

> **上传与图片展示先看 skill `media-file-management`**：前端禁止缓存文件本体，只存 `fileId`；所有端共用同一个上传接口。

> **文件体量硬限见 `web-project-bootstrap` 第五节**：组件 200 行、hooks/utils 150 行、单函数 60 行。拆分模板也在那里。

## 一、技术选型（定死，不再讨论）

| 项 | 选定 | 不用 | 理由 |
|---|---|---|---|
| 框架 | **React 19** | ~~Vue~~（除非项目已是） | 语料最密，agent 一次写对率最高 |
| 构建 | **Vite** | ~~Next.js~~ | **不用 Next**：RSC / Server Actions / hydration 报错是三个独立深坑，纯 SPA 没有 |
| 语言 | **TypeScript** | ~~JS~~ | 类型是前后端契约的载体 |
| UI | **Ant Design 5** | ~~shadcn~~ ~~MUI~~ | Form/Table/Modal 最全，中文文档全 |
| 路由 | **React Router 7** | — | — |
| 服务端状态 | **TanStack Query v5** | ~~Redux~~ ~~SWR~~ | — |
| 客户端状态 | **Zustand** | ~~Redux~~ ~~MobX~~ | — |
| 请求 | **axios** | ~~fetch 裸用~~ | 拦截器链是刚需 |
| 表单 | **antd Form** | ~~手写受控~~ | — |
| 校验 | **zod**（可选） | — | 复杂规则时加 |
| 类型生成 | **openapi-typescript** | ~~手写 interface~~ | 从后端 swagger 生成 |

---

## 二、目录结构与各层职责

```
frontend/src/
├── main.tsx                    ConfigProvider + QueryClientProvider + RouterProvider
├── App.tsx
├── router/
│   ├── index.tsx               路由表，全部 React.lazy 懒加载
│   └── guard.tsx               RequireAuth / RequireRole
├── api/
│   ├── client.ts               axios 实例 + 请求/响应拦截器（唯一出口）
│   ├── auth.ts                 login / logout / refresh / me / changePassword
│   └── <domain>.ts             每个业务域一个文件
├── types/
│   ├── api.d.ts                openapi-typescript 生成，**不手改**
│   └── index.ts                前端自有类型
├── stores/
│   ├── auth.ts                 token / user / permissions
│   └── ui.ts                   侧边栏折叠、主题等 UI 状态
├── hooks/
│   ├── useAuth.ts              登录态读取与操作
│   ├── usePermission.ts        权限判断
│   └── useTable.ts             列表页通用逻辑（分页/筛选/刷新/URL 同步）
├── layouts/
│   ├── AdminLayout.tsx         Sider + Header + Content + 面包屑 + 头像菜单
│   └── BlankLayout.tsx         登录页等无框架页面
├── pages/
│   ├── login/index.tsx
│   └── <domain>/
│       ├── index.tsx           列表页
│       ├── Detail.tsx          详情 / 新建 / 编辑
│       └── components/         该页面私有组件，不外提
├── components/                 全局公共组件
│   ├── ProTable/               antd Table 封装：三态 + 分页 + 工具栏
│   ├── AuthButton/             权限按钮
│   └── PageContainer/          统一页头（标题 + 返回 + 操作区）
├── constants/
│   ├── errcode.ts              与后端 errcode 一一对应
│   └── options.ts              枚举字典（状态、类型 → label/color）
├── utils/
│   ├── format.ts               时间、金额、脱敏
│   └── storage.ts              localStorage 封装（带命名空间前缀）
└── styles/
    ├── global.css
    └── theme.ts                AntD ConfigProvider 的 token
```

### 分层职责（违反即打回）

| 目录 | 该做 | 不许做 |
|---|---|---|
| `pages/` | 页面组装、调 hooks、渲染 | 不直接写 axios、不写复杂数据转换 |
| `components/` | 纯展示与交互，props 驱动 | **不调用任何业务 API** |
| `hooks/` | 复用逻辑，返回状态与操作 | 不渲染 UI |
| `api/` | 请求函数定义与类型标注 | 不处理业务状态、不弹提示 |
| `stores/` | 全局客户端状态 | **不放服务端数据**（列表、详情一律走 Query） |
| `utils/` | 纯函数 | 不依赖 React |
| `constants/` | 枚举、错误码映射 | 不含逻辑 |

**最重要一条：服务端数据不进 Zustand。** 列表、详情、统计一律用 TanStack Query 缓存与失效；Zustand 只放 token、用户信息、侧边栏折叠这类客户端状态。混放会导致两份真相打架。

---

## 三、统一登录态（核心）

### 3.1 Token 存哪

| 档位 | access token | refresh token | 适用 |
|---|---|---|---|
| **基础档** | `localStorage` | 无 | 内部系统、无踢人需求 |
| **完整档（默认）** | **内存**（Zustand，不持久化） | **httpOnly cookie** | 后台系统标准做法 |

**默认走完整档**，理由：access 不落 localStorage，XSS 拿不到；refresh 在 httpOnly cookie 里，JS 读不到；刷新页面时用 refresh 换新的 access，用户无感。

基础档只在"一次性小工具"里用，不要用在长期维护的系统上。

### 3.2 登录流程

```
POST /api/auth/login  { username, password }
  → 后端 Set-Cookie: refresh_token=...; HttpOnly; SameSite=Lax; Path=/api/auth
  → 响应体返回 { code:0, data:{ accessToken, expiresIn, user, permissions } }
  → 前端：accessToken 存 Zustand（内存）；user/permissions 存 store；跳转 redirect 或 /
```

### 3.3 自动续期 + 并发 401 去重（必须实现）

多个请求同时 401 时只能刷新一次，其余请求排队等这次刷新的结果。

```ts
// api/client.ts
let refreshing: Promise<string> | null = null

client.interceptors.response.use(
  r => r,
  async (error) => {
    const { response, config } = error
    if (response?.status !== 401 || config._retry) {
      return Promise.reject(error)
    }

    // 登录接口本身 401 不要重试，否则死循环
    if (config.url?.includes('/auth/login') || config.url?.includes('/auth/refresh')) {
      useAuthStore.getState().clear()
      return Promise.reject(error)
    }

    config._retry = true

    // 关键：同一时刻只允许一个刷新请求
    if (!refreshing) {
      refreshing = client.post('/auth/refresh')
        .then(res => {
          const token = res.data.data.accessToken
          useAuthStore.getState().setToken(token)
          return token
        })
        .finally(() => { refreshing = null })
    }

    try {
      const token = await refreshing
      config.headers.Authorization = `Bearer ${token}`
      return client(config)          // 重放原请求
    } catch {
      useAuthStore.getState().clear()
      redirectToLogin()
      return Promise.reject(error)
    }
  }
)
```

**四个必做点**：
1. `_retry` 标记防无限重试
2. `refreshing` 单例防并发重复刷新
3. 登录/刷新接口自身 401 不参与重试
4. 刷新失败 → 清状态 → 跳登录（带 `?redirect=` 当前路径）

### 3.4 请求拦截器

```ts
client.interceptors.request.use(config => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
```

**不要**在这里弹 loading 或 message —— 提示交给业务层，避免重复弹窗。

### 3.5 路由守卫

```tsx
// router/guard.tsx
export function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuthStore(s => s.token)
  const location = useLocation()
  if (!token) {
    return <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname)}`} replace />
  }
  return <>{children}</>
}

export function RequireRole({ roles, children }: { roles: string[]; children: ReactNode }) {
  const permissions = useAuthStore(s => s.permissions)
  if (!roles.some(r => permissions.includes(r))) {
    return <Result status="403" title="403" subTitle="没有访问权限" />
  }
  return <>{children}</>
}
```

登录成功后读取 `?redirect=` 跳回原页面，没有则去首页。

### 3.6 按钮级权限

```tsx
// components/AuthButton
export function AuthButton({ perm, children, ...rest }: { perm: string } & ButtonProps) {
  const has = usePermission()
  if (!has(perm)) return null
  return <Button {...rest}>{children}</Button>
}
```

权限码由后端登录接口返回，格式 `域:动作`，如 `order:delete`、`user:reset-password`。**前端不硬编码角色名**，只判断权限码。

### 3.7 登出

```ts
async function logout() {
  try { await api.logout() } finally {   // 后端失败也要清本地
    useAuthStore.getState().clear()
    queryClient.clear()                   // 清掉所有缓存，防下个用户看到上一个的数据
    navigate('/login', { replace: true })
  }
}
```

**`queryClient.clear()` 不能漏** —— 否则换用户登录后会短暂看到上一个人的列表数据。

### 3.8 多标签页同步

```ts
window.addEventListener('storage', (e) => {
  if (e.key === 'auth:logout') {
    useAuthStore.getState().clear()
    queryClient.clear()
    navigate('/login')
  }
})
```

登出时写一个 `localStorage.setItem('auth:logout', Date.now())`，其他标签页收到事件同步退出。

---

## 四、请求层规范

### axios 实例

```ts
export const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE,   // 开发期 '/api'
  timeout: 15000,
})
```

### 响应体解包

后端统一 `{code,msg,data}`。在拦截器里判断 `code !== 0` 时抛出业务错误，业务层只拿 `data`：

```ts
client.interceptors.response.use(res => {
  const body = res.data
  if (body && typeof body.code === 'number' && body.code !== 0) {
    message.error(body.msg || '请求失败')
    return Promise.reject(new BizError(body.code, body.msg))
  }
  return body?.data ?? body
})
```

### 错误提示分工

| 错误类型 | 谁负责提示 |
|---|---|
| 网络断开、超时 | 拦截器统一 `message.error('网络异常')` |
| 业务错误码（4xxx） | 拦截器 `message.error(msg)` |
| 参数错误（1xxx） | 表单内联展示，不弹全局提示 |
| 认证失败（2xxx） | 走刷新流程，最终失败才跳登录 |
| 系统错误（5xxx） | 拦截器提示「服务器繁忙」 |

---

## 五、状态管理边界

| 数据 | 放哪 | 例 |
|---|---|---|
| 服务端列表 / 详情 / 统计 | **TanStack Query** | `useQuery(['orders', params], () => api.listOrders(params))` |
| 提交、删除等写操作 | **useMutation** + `invalidateQueries` | — |
| 登录态、用户、权限 | **Zustand** | `useAuthStore` |
| UI 状态（折叠、主题） | Zustand 或 local state | — |
| 表单临时值 | 组件 local state（antd Form） | — |

```ts
// 写操作后失效相关查询
const { mutate } = useMutation({
  mutationFn: api.deleteOrder,
  onSuccess: () => {
    message.success('删除成功')
    queryClient.invalidateQueries({ queryKey: ['orders'] })
  },
})
```

**禁止**：用 `useEffect` + `useState` 手动取数。这是 React 最大的坑，TanStack Query 已经解决了。

---

## 六、列表页规范（后台最高频，必须统一）

所有列表页用 `ProTable` + `useTable`，不要每个页面重写。

```tsx
const { data, isLoading, error, params, setParams, refresh } = useTable({
  queryKey: 'orders',
  fetcher: api.listOrders,
  defaultParams: { page: 1, pageSize: 20 },
})
```

**硬性要求**：

1. **三态齐全**：`isLoading` → `<Spin>`；`data.list.length === 0` → `<Empty>`；`error` → `<Result status="error">`
2. **筛选与分页写进 URL query**：刷新页面、分享链接、浏览器后退都保持状态
3. **筛选变更时 `page` 重置为 1**
4. **删除前二次确认**：`Modal.confirm`
5. **操作成功后 `message.success` + `refresh()`**
6. **表格行 key 用 `id`**，不要用 index
7. **操作列 fixed: 'right'**，宽 120–180

---

## 七、表单与弹窗

> **用弹窗还是抽屉、字段怎么排、提示用哪种，全部见 skill `ui-ux-decision-guide`。** 本节只给实现规范。

- 用 `antd Form` + `Form.Item rules`，**不手写受控 state**
- 新建与编辑共用一个表单组件，靠 `initialValues` 区分
- 弹窗用 `Modal` 或 `Drawer`，编辑内容多用 `Drawer`
- 提交按钮必须有 `loading={mutation.isPending}`，**防重复提交**
- 关闭弹窗前如果有未保存改动，`Modal` 的 `onCancel` 里二次确认
- 字段校验错误用表单内联，不弹全局 `message`

---

## 八、样式规范

> **涉及手机端或响应式时，先加载 `mobile-responsive-layout`**：viewport、dvh、安全区域、键盘、滚动穿透、1px 边界都有专门规范。

- **主题定制走 AntD token**：`ConfigProvider theme={{ token: { colorPrimary: '#009688' } }}`，不改源码、不写 `!important`
- 页面级样式用 **CSS Modules**（`index.module.css`），禁止全局 class 名污染
- 间距用 4 的倍数：4 / 8 / 12 / 16 / 24 / 32
- 字号阶梯：12 / 14 / 16 / 20 / 24，正文一律 14
- 颜色只用 token 里的语义色（`colorPrimary` / `colorError` / `colorTextSecondary`），**不硬编码十六进制**

---

## 九、前后端契约

| 项 | 规则 |
|---|---|
| 接口类型 | 从后端 `swagger.json` 用 `openapi-typescript` 生成到 `types/api.d.ts`，**不手写** |
| 字段命名 | 前后端统一 camelCase；数据库是 snake_case，由后端 json tag 转换 |
| 分页参数 | 固定 `page` / `pageSize`，返回 `{page,pageSize,total,list}` |
| 时间 | RFC3339 字符串，前端统一用 `dayjs` 格式化，**不在各处手写 `new Date()`** |
| 错误码 | 前端 `constants/errcode.ts` 与后端 `pkg/errcode` 一一对应，加新码两边同改 |
| 枚举 | 后端返回数字码，前端 `constants/options.ts` 映射 label 与 Tag 颜色，**不在 JSX 里写 if-else 判断数字** |

---

## 十、工程化

```ts
// vite.config.ts 必须有的部分
server: {
  port: 5173,
  proxy: { '/api': { target: 'http://localhost:8080', changeOrigin: true } }
},
resolve: { alias: { '@': path.resolve(__dirname, 'src') } }
```

- `@` 别名指向 `src`，**禁止 `../../../` 三级以上相对路径**
- 环境变量一律 `VITE_` 前缀，`.env.development` 里 `VITE_API_BASE=/api`
- 路由全部 `React.lazy` + `<Suspense fallback={<Spin/>}>`
- ESLint + Prettier，`no-unused-vars` 与 `react-hooks/exhaustive-deps` 必须开

---

## 十一、组件优先与防造轮子（本 skill 最重要的一节）

### 11.1 为什么必须用机制而不是规范

agent（和人）会造轮子，根因不是不懂，而是：**不知道项目里有什么 + 正确写法比错写法长 + 没有拦截**。
所以五层防护缺一不可，只写"请使用 AntD 组件"是无效的。

### 11.2 第一层：单一出口，禁止散装导入

`src/components/index.ts` 是**唯一**的组件入口：

```ts
export * from './AuthButton'
export * from './ProTable'
export * from './PageContainer'
export * from './Confirm'
export * from './Toast'
export * from './Total'
export * from './Hint'
export * from './EmptyState'
export * from './StatusTag'
export * from './SearchForm'
```

页面里一律 `import { ProTable, AuthButton, toast } from '@/components'`。
**禁止** `import { Button } from 'antd'`、`import { message } from 'antd'` 直接散装使用。

### 11.3 第二层：ESLint 硬拦截（可直接抄）

```js
// eslint.config.js —— flat config
export default [
  {
    rules: {
      // ① 禁止直接使用 antd 里最容易各写各的四个 API
      'no-restricted-imports': ['error', {
        paths: [{
          name: 'antd',
          importNames: ['message', 'notification', 'Modal', 'Button'],
          message: '请从 @/components 导入封装版：Btn/AuthButton（按钮）、toast（通知）、useConfirm（确认弹窗）。',
        }],
      }],

      // ② 禁止裸 HTML 标签
      'no-restricted-syntax': ['error',
        { selector: "JSXOpeningElement[name.name='button']",
          message: '禁止裸 <button>，请用 <Btn> 或 <AuthButton perm="...">。' },
        { selector: "JSXOpeningElement[name.name='input']",
          message: '禁止裸 <input>，请用 antd Form.Item + Input。' },
        { selector: "CallExpression[callee.object.name='window'][callee.property.name='confirm']",
          message: '禁止 window.confirm，请用 useConfirm()。' },
        { selector: "CallExpression[callee.object.name='window'][callee.property.name='alert']",
          message: '禁止 window.alert，请用 toast。' },
      ],

      // ③ 禁止手写分页文案，统一走 ProTable
      'no-restricted-syntax': ['error',
        { selector: "JSXText[value=/共\s*\d+\s*条/]",
          message: '共 X 条 由 ProTable 统一渲染，不要在页面里手写。' },
      ],
    },
  },
]
```

**关键点**：agent 写完代码，lint 一跑就红，它必须改。这是唯一真正生效的约束。

### 11.4 第三层：让正确用法比造轮子更短

这是最容易被忽略、但最有效的一层。**如果封装版比原生写法长，agent 一定选原生的。**

| 场景 | 错误写法（长） | 封装后（短） |
|---|---|---|
| 确认弹窗 | `Modal.confirm({ title, content, okText, cancelText, okButtonProps:{danger:true}, onOk: async()=>{...} })` | `await confirm('确定删除？', { danger: true })` |
| 通知 | `message.success({ content:'保存成功', duration:2, ... })` | `toast.success('保存成功')` |
| 状态标签 | `<Tag color={status===1?'gold':status===2?'blue':'default'}>{status===1?'待付款':...}</Tag>` | `<StatusTag type="order" value={row.status} />` |
| 总数 | `<span>共 {total} 条</span>` | 由 `<ProTable>` 内置，不用写 |
| 提示 | `<Tooltip title="..."><QuestionCircleOutlined /></Tooltip>` | `<Hint text="..." />` |

**设计原则：封装后必须比原生写法短 50% 以上，否则没人用。**

### 11.5 第四层：组件清单文档（agent 必读）

项目根建 `COMPONENTS.md`，只列"有什么 + 什么时候用"，不写实现：

```markdown
# 项目组件清单

写任何页面前先读本文件。**下列组件已存在，禁止重新实现。**

| 组件 | 用途 | 关键 props |
|---|---|---|
| `<Btn>` | 所有按钮，含 size/type 预设 | type: primary/danger/text |
| `<AuthButton perm="x:y">` | 需权限控制的按钮，无权限不渲染 | perm |
| `<ProTable>` | 所有列表页表格，内置三态+分页+工具栏 | columns, useTable 返回 |
| `<PageContainer>` | 页面头部（标题/返回/操作区） | title, extra |
| `<SearchForm>` | 列表页筛选栏 | items, onSearch |
| `<StatusTag type="order" value={v}>` | 状态标签，颜色与文案来自 constants/options | type, value |
| `<Total value={n} unit="元">` | 数字展示，千分位/两位小数 | value, unit, precision |
| `<Hint text="...">` | 说明图标 + 气泡提示 | text |
| `<EmptyState type="list">` | 空状态，统一文案与插图 | type |
| `toast.success/error/warning` | **所有**通知，禁止 message.xxx | — |
| `useConfirm()` | **所有**二次确认，返回 Promise | — |
| `useTable({queryKey, fetcher})` | 列表页取数+分页+URL 同步 | — |
| `usePermission()` | 权限判断 | — |
```

### 11.6 第五层：提交前检查脚本

```bash
#!/usr/bin/env bash
# scripts/check-conventions.sh
set -e
fail=0

check() {
  local pat="$1" msg="$2"
  if grep -rnE "$pat" src --include='*.tsx' --include='*.ts' | grep -v 'components/' ; then
    echo "❌ $msg"; fail=1
  fi
}

check 'from ["'"'"']antd["'"'"']'          '存在从 antd 直接导入（应走 @/components）'
check 'message\.(success|error|warning|info)' '存在 message.xxx（应用 toast）'
check 'Modal\.confirm'                      '存在 Modal.confirm（应用 useConfirm）'
check 'window\.(confirm|alert)'             '存在 window.confirm/alert'
check '共\s*[0-9{]+\s*条'                   '手写了"共 X 条"（应由 ProTable 渲染）'
check '[A-Za-z]+ === [0-9] \? ['"'"']'      '疑似在 JSX 里手写状态映射（应用 StatusTag + options）'

exit $fail
```

接进 `package.json`：`"prebuild": "bash scripts/check-conventions.sh"`。
**让 agent 每次构建都撞这个墙**，比任何提示词都管用。

### 11.7 组件实现要点

**`useConfirm`** —— 返回 Promise，不返回 JSX

```tsx
export function useConfirm() {
  const [api, holder] = Modal.useModal()
  const confirm = (content: string, opt?: { danger?: boolean; title?: string }) =>
    new Promise<boolean>(resolve => {
      api.confirm({
        title: opt?.title ?? '确认操作',
        content,
        okText: '确定',
        cancelText: '取消',
        okButtonProps: { danger: opt?.danger },
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      })
    })
  return { confirm, holder }
}
// 用法：const { confirm, holder } = useConfirm(); if (!await confirm('确定删除？', {danger:true})) return
```

**`toast`** —— 全局单例，统一配置

```ts
import { message } from 'antd'   // 只允许在这一个文件里 import antd 的 message
message.config({ maxCount: 3, duration: 2, top: 80 })

export const toast = {
  success: (m: string) => message.success(m),
  error:   (m: string) => message.error(m),
  warning: (m: string) => message.warning(m),
}
```

**`StatusTag`** —— 文案与颜色来自 `constants/options`，不写在组件里

```tsx
export function StatusTag({ type, value }: { type: string; value: number }) {
  const opt = OPTIONS[type]?.[value]
  if (!opt) return <Tag>{value}</Tag>
  return <Tag color={opt.color}>{opt.label}</Tag>
}
```

---

## 十二、验收清单

### 登录态

- [ ] 登录成功跳转到 `redirect` 指定页，无 redirect 则首页
- [ ] 刷新页面（F5）不掉登录
- [ ] access 过期后请求自动续期，用户无感
- [ ] 多个请求同时 401 只触发一次刷新（Network 面板可验证）
- [ ] 刷新失败 → 清状态 → 跳登录，带 `?redirect=`
- [ ] 未登录访问受保护路由 → 跳登录
- [ ] 无权限访问 → 403 页，不是白屏
- [ ] 无权限的按钮不渲染（不是禁用）
- [ ] 登出后 `queryClient.clear()`，换用户登录看不到上个用户的数据
- [ ] 多标签页：一个标签登出，其他标签同步退出

### 列表页

- [ ] 加载中显示 Spin
- [ ] 0 条显示 Empty
- [ ] 请求失败显示 Result，不白屏
- [ ] 分页与筛选同步到 URL，刷新后保持
- [ ] 筛选变更时 page 重置为 1
- [ ] 删除有二次确认
- [ ] 操作成功后列表自动刷新

### 组件一致（防造轮子）

- [ ] 项目根有 `COMPONENTS.md`，列出全部封装组件与用法
- [ ] `src/components/index.ts` 是唯一组件出口
- [ ] 页面里**没有** `import { Button / message / Modal } from 'antd'`
- [ ] 没有裸 `<button>`、`<input>`、`window.confirm`、`window.alert`
- [ ] 通知一律 `toast`，二次确认一律 `useConfirm`
- [ ] 状态展示一律 `StatusTag` + `constants/options`，**没有 JSX 内三元映射文案**
- [ ] "共 X 条"由 `ProTable` 渲染，页面里没手写
- [ ] ESLint 的 `no-restricted-imports` / `no-restricted-syntax` 已配置
- [ ] `scripts/check-conventions.sh` 已存在并接入 `prebuild`
- [ ] `npm run lint` 与 `npm run build` 均无违规

### 规范

- [ ] 没有 `useEffect` 取数据
- [ ] 没有服务端数据放进 Zustand
- [ ] 没有在 `components/` 里调业务 API
- [ ] 没有手写 API 类型（都来自 `api.d.ts`）
- [ ] 没有硬编码颜色十六进制
- [ ] 没有三级以上相对路径
- [ ] 所有路由懒加载

---

## 十三、Vue 项目的对应写法

若项目已是 Vue，按同样职责映射，不要混用：

| React | Vue3 |
|---|---|
| TanStack Query | `@tanstack/vue-query`（同样用法） |
| Zustand | Pinia |
| React Router 7 | Vue Router 4 |
| antd Form | Element Plus `el-form` + rules |
| `useTable` | 同名的 composable |
| `AuthButton` | 自定义指令 `v-perm` |

**职责边界、登录态流程、列表页三态、契约规则完全一致**，只是语法不同。
