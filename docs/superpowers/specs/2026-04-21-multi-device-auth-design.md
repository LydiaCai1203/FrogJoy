# Multi-Device Auth System Design

## Overview

为 BookReader 实现多设备登录支持，包含三个核心能力：
1. **Refresh Token 机制** — 短期 access token + 长期 refresh token，支持静默续期
2. **服务端 Token 吊销** — Redis 会话存储，支持即时失效
3. **设备管理** — 查看活跃设备列表，踢出指定设备，最多 3 台设备同时在线

移动端技术栈：Flutter（token 存储于 flutter_secure_storage）。

---

## 1. Token 双令牌机制

### Access Token（短期，无状态）
- 格式：JWT (HS256)
- 有效期：24 小时
- Payload：`{ sub: user_id, sid: session_id, exp: ... }`
- 新增 `sid` 字段关联会话，但验证时不查 Redis，保持无状态

### Refresh Token（长期，有状态）
- 格式：不透明字符串（`secrets.token_urlsafe(64)`）
- 有效期：30 天
- 存储：Redis 中存 SHA-256 hash，客户端持有原始值
- 每次刷新时轮换（旧 token 立即失效）

### 刷新流程

```
Client                          Server
  |-- POST /auth/refresh -------->|
  |   { refresh_token }           |
  |                               |-- SHA-256(refresh_token)
  |                               |-- Redis: 查找匹配的 session
  |                               |-- 验证未过期、未被吊销
  |                               |-- 生成新 access_token (JWT, 24h)
  |                               |-- 生成新 refresh_token（轮换）
  |                               |-- 更新 Redis session
  |<-- { access_token,           -|
  |      refresh_token }          |
```

---

## 2. Redis 会话存储结构

### Key 设计

```
session:{session_id}  →  Hash {
    user_id:        string      # 用户 ID
    refresh_hash:   string      # SHA-256(refresh_token)
    device_name:    string      # "iPhone 15" / "Chrome on macOS"
    device_type:    string      # "mobile" / "web" / "tablet"
    created_at:     ISO string  # 会话创建时间
    last_active:    ISO string  # 最后活跃时间（刷新时更新）
}
TTL = 30 天（与 refresh token 同步过期）

user:sessions:{user_id}  →  Set { session_id_1, session_id_2, ... }
TTL = 30 天
```

### 设计理由
- `session:{sid}` 哈希表：refresh 时通过 session_id 直接查到会话，O(1)
- `user:sessions:{uid}` 集合：列出用户所有设备、批量删除
- 两者 TTL 同步，自动清理过期数据，无需定时任务

### 与现有 Redis 数据的关系
- 保留现有 `user:last_active:{user_id}`（admin 面板使用）
- session 中的 `last_active` 是设备级粒度，不冲突

---

## 3. API 接口设计

### 新增接口

#### `POST /auth/refresh`
- Body: `{ refresh_token: string }`
- 返回: `{ access_token, refresh_token, token_type: "bearer" }`
- 错误: 401（token 无效/过期）

#### `GET /auth/devices`
- Header: `Authorization: Bearer {access_token}`
- 返回: `[{ session_id, device_name, device_type, last_active, is_current }]`

#### `DELETE /auth/devices/{session_id}`
- Header: `Authorization: Bearer {access_token}`
- 返回: `{ message: "设备已退出" }`
- 约束: 不能踢出自己当前 session

#### `POST /auth/logout-all`
- Header: `Authorization: Bearer {access_token}`
- 返回: `{ message: "已退出所有设备" }`
- 行为: 删除用户所有 session（包括自己），客户端需重新登录

### 现有接口改动

#### `POST /auth/login`
- 请求新增可选字段: `{ ..., device_name?, device_type? }`
- 响应改为: `{ access_token, refresh_token, token_type: "bearer" }`
- 登录时检查设备数，超过 3 台返回 `409 Conflict`

#### `POST /auth/logout`（新增，替代前端纯本地登出）
- Header: `Authorization: Bearer {access_token}`
- 行为: 删除当前 session_id 对应的 Redis 记录

#### `GET /auth/guest-token`
- 响应改为: `{ access_token, refresh_token, token_type: "bearer" }`
- 设备信息: device_type="web", device_name="Guest"

### 不变的接口
- `POST /auth/register`、`POST /auth/verify`、`POST /auth/resend-verification`
- `GET /auth/me`、`GET/PUT /auth/theme`、`GET/PUT /auth/font-size`
- access token 的验证逻辑不变（无状态，不查 Redis）

---

## 4. 最大设备数限制

- 每个用户最多 **3 个活跃 session**
- 登录时检查 `user:sessions:{user_id}` 集合大小（SCARD）
- 超过限制：返回 `409 Conflict`，body: `{ detail: "已达最大设备数(3)，请先退出其他设备", devices: [...] }`
  - 响应中附带当前设备列表，方便客户端直接展示
- 客户端收到 409 后引导用户到设备管理页面踢出旧设备
- Guest 账户不受此限制

---

## 5. 客户端适配

### Web 端（React，现有 AuthContext.tsx）

- localStorage 存储从 `auth_token` 改为 `access_token` + `refresh_token`
- 新增 `refreshAccessToken()` 方法
- API 请求拦截：收到 401 时自动调用 refresh，成功后重试原请求；refresh 也失败则跳转登录
- `logout()` 改为先调用 `POST /auth/logout`，再清本地存储
- guest token 走同样的 refresh 流程

### 刷新竞争处理

多个并发请求同时收到 401 时，避免多次 refresh：

```
维护一个 refreshPromise 变量
第一个 401 触发 refresh，后续请求等待同一个 promise
refresh 完成后所有等待的请求用新 token 重试
```

### Flutter 端（未来）
- token 存储：`flutter_secure_storage`（加密存储）
- 刷新策略：Dio interceptor，逻辑与 Web 端一致
- 登录时传 `device_name`（设备型号）和 `device_type: "mobile"`

---

## 6. 安全性与边界处理

### Refresh Token 轮换安全
- 每次 refresh 生成新 refresh token，旧的立即失效
- 重放检测：已轮换的旧 refresh token 被使用（hash 不匹配）→ 删除该 session，强制重新登录
- refresh token 只在 `/auth/refresh` 接口使用，不随普通请求发送

### 密码变更 / 账户禁用
- 修改密码时：调用 logout-all，清除所有 session
- 管理员禁用账户（is_active=False）时：清除该用户所有 session

### Redis 宕机容错
- access token 验证不依赖 Redis，24h 内正常使用
- refresh 失败时客户端回退到登录页，不崩溃
- 设备列表接口返回空数组或 503，不影响核心阅读功能

### Guest 账户特殊处理
- Guest session 的 device_name 固定为 "Guest"
- Guest 不展示设备管理 UI（前端隐藏）
- Guest 的 session 数不受 3 台限制

### 不做的事
- 不记录 IP / 地理位置
- 不做 access token 黑名单（24h 过期足够短）
- admin-backend 的鉴权暂不改动（独立系统，后续按需对齐）

---

## 7. 涉及的文件

### 后端改动
- `epub-tts-backend/app/services/auth_service.py` — 新增 refresh token 生成、轮换、session CRUD
- `epub-tts-backend/app/middleware/auth.py` — access token payload 新增 sid 字段解析
- `epub-tts-backend/app/routers/auth.py` — login/logout/refresh/devices 接口改动
- `epub-tts-backend/shared/schemas/auth.py` — 新增请求/响应 schema

### 前端改动
- `epub-tts-frontend/src/contexts/AuthContext.tsx` — token 存储、refresh 逻辑、logout 改造
- `epub-tts-frontend/src/api/` — 请求拦截器，401 自动 refresh
