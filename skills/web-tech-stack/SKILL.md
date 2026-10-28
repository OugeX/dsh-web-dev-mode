---
name: web-tech-stack
description: Web 项目的技术栈选型与各栈实现细则。覆盖 ThinkPHP+layui、ThinkPHP API+Vue3+Element、Bootstrap5 直出、Nuxt 3、Next.js、Go+Gin+GORM、Go+Gin+React、Rust+Axum/Actix，以及 H5/小程序/App 跨端方案（Vant、uni-app+Wot Design Uni、Taro+NutUI、React Native）。当需要为 Web 项目选技术栈、判断某个栈该怎么写、或决定做 H5/小程序/App 时使用。
---

# Web 技术栈细则

> **本 skill 是预制标准体系的一部分。** 新项目起手先加载 `web-project-bootstrap` 拿目录树与产物清单。选型决策表在 bootstrap 里，本文只回答「某个栈具体怎么写」，不要在这里重新选型。


> 命中某个栈时读这一节对应条目。只读你需要的，不要整篇套用。

---

## ThinkPHP 模板 + layui

- 布局：`layui-layout layui-layout-admin` + `layui-row` / `layui-col-*`（12 栅格）
- 组件：`layui-form` / `layui-table` / `layui-btn` / `layui-layer`
- 数据：`{volist}` `{if}` 服务端直出
- 禁止：fetch/axios 取数后前端渲染列表；引入构建工具；把 layui 表格改成 div 手写

## ThinkPHP API + Vue 3 + Element Plus

- 布局：`el-container` / `el-row` / `el-col`（24 栅格）
- 组件：Element Plus
- 状态：`ref` / `reactive`；路由 vue-router；构建 Vite
- 请求：axios 封装到 `src/api`
- 接口：RESTful，统一 `{code,msg,data}`

## Bootstrap 5 服务端渲染

- 布局：`container` / `row` / `col-*`（12 栅格）
- 组件：BS5 原生 + 原生 JS 或 Alpine.js
- 禁止：引 jQuery 插件（除非项目已有）

## Nuxt 3

- 目录即路由：`server/api/order/list.get.ts` → `GET /api/order/list`
- 布局 Tailwind；组件按项目既有（Nuxt UI）
- 数据 `useFetch`；ORM 用 Drizzle
- 注意：不要混入 Next.js 的 RSC 概念

## Next.js

- 布局 Tailwind；组件 shadcn
- 数据：Server Actions / RSC
- **注意 RSC 与客户端组件边界**，`"use client"` 位置错了会引发 hydration 报错

## Go + Gin + GORM（服务端渲染或纯 API）

- 目录：`cmd/ internal/ pkg/` 三分布局，main 只做装配
- 路由：`gin.Group` 分组挂中间件
- 数据：GORM；复杂查询才用 sqlx
- 配置：环境变量 + viper
- 响应：统一 `{code,msg,data}`
- 服务端渲染用 `html/template`；分离则只出 API
- 部署：单二进制交叉编译。不要默认写 Dockerfile

## Go 前后端分离（重点）

**分层固定**：router → middleware → handler → service → repository

- handler 不写业务、service 不碰 SQL
- 中间件至少挂：Recover、CORS、请求日志、JWT 鉴权
- 参数校验用 Gin 内置 `binding` tag（validator），不手写 if 判空
- 认证用 `golang-jwt/jwt/v5`，token 放 `Authorization: Bearer`，**不放 URL**
- 响应体 `{code,msg,data}`；分页统一 `{page,pageSize,total,list}`
- JSON 字段一律 camelCase，**显式写 json tag**
- 时间统一 RFC3339 字符串
- 开发期前端用 Vite proxy 把 `/api` 代理到后端，**生产不开宽松 CORS**
- 部署：`go:embed` 把前端 dist 打进二进制，做到「分离开发、单文件部署」；或用 nginx 静态托管 + 反代
- 文档 swaggo/swag；热重载 air
- MySQL 连接池必须设 `SetMaxOpenConns` / `SetMaxIdleConns` / `SetConnMaxLifetime`

## Go + Echo / Chi / Fiber

结构同 Gin，按该框架的中间件与上下文写法，**不要混入 Gin 的写法**。

## Go + Gin + React + MySQL（主力组合）

**后端**按上面 Go 分离细则。

**前端固定**：
- React 19 + TypeScript + Vite（**不要 Next.js**，除非明确要 SSR）
- UI：**Ant Design 5**
- 路由：React Router 7
- 请求：axios
- **状态二分**：服务端状态一律 TanStack Query（`useQuery` / `useMutation`），客户端状态 Zustand
- **禁止 Redux；禁止用 useEffect 取数据**
- 表单：antd Form 或 react-hook-form + zod
- 接口类型不手写：swaggo 产出 swagger.json → `openapi-typescript` 生成 `types/api.d.ts`
- 目录：`src/{pages,components,hooks,api,stores,types}`
- 每个列表页必须实现 loading / empty / error 三态（antd `Spin` / `Empty` / `Result`）

## Rust + Axum

- handler 返回 `impl IntoResponse`
- 共享状态 `State<Arc<AppState>>`
- 错误：`thiserror` 定义 + 实现 `IntoResponse`
- 异步全 tokio；数据 sqlx 编译期校验或 SeaORM
- **handler 里不许有 `unwrap()` / `expect()`**，用 `?` 传播

## Rust + Actix-web

结构同 Axum 约定。注意 actix-web 的 actor 生命周期与 `App`/`HttpServer` 装配方式不同，**不要混写**。

---

## 跨端 / App / 小程序（先分清目标）

| 目标 | 方案 |
|---|---|
| 只是手机上能打开的网页（H5） | Vue3 + **Vant**（Element 同源），或 React + Vant React。不打包不上架 |
| 要上架商店 / 做小程序 | **uni-app（Vue 语法）+ Wot Design Uni**，一套代码出 H5 + 小程序 + APK/iOS |
| 同上但要用 React | **Taro 3/4 + NutUI** |
| 要原生性能、大量系统能力 | **React Native + Expo**，组件与 Web 不通 |

**硬性规则**：
- PC 后台管理**不要**用 uni-app / Taro 做，仍用 Vue3 + Element Plus 或 React + AntD
- 后端只写**一套 REST API** 服务所有端，不要为每端各写一套
- **必须纠正的误解**：React 本身不能构建 App。能构建 App 的是 React Native 或 Taro。用户说"用 React 做 App"时，先问清是 H5、小程序还是上架包，再给方案，**不要顺着错误前提写代码**

---

## 不在上表时

先读项目现有 3 个页面，总结出它的约定，再严格照做。**不要发明新写法。**
