# S9.1 API 层专项审计报告

生成时间: 2026-05-04 13:42:45 UTC
审计范围: D:\Claudedaoy\coherence\api

---

## 摘要

| 指标 | 值 |
|------|-----|
| 发现问题 | 14 |
| 通过检查 | 4 |
| CRITICAL | 1 |
| HIGH | 5 |
| MEDIUM | 5 |
| LOW | 1 |
| INFO | 2 |

---

## 按严重级别排列

### CRITICAL

- **yaml.safe_load 无异常保护** (`api\services\dashboard_aggregator.py`)
  - *类别*: B-错误处理
  - yaml.safe_load 可抛出 yaml.YAMLError（格式错误时），但未被 try/except 包裹。


### HIGH

- **api/services/pulse_service.py: PulseService._pulse_log 纯内存** (`api\services\pulse_service.py`)
  - *类别*: C-持久化
  - 脉冲日志（session_id → 时间戳列表）完全在内存中。重启后所有会话脉冲计数清零，降级状态重置为 hard。

- **api/middleware/auth.py: IAMSkeleton._tokens 纯内存** (`api\middleware\auth.py`)
  - *类别*: C-持久化
  - Token 记录完全在内存中。重启后所有已签发的 token 失效，活跃会话断开。

- **api/middleware/auth.py: IAMSkeleton._state_tree 纯内存** (`api\middleware\auth.py`)
  - *类别*: C-持久化
  - 会话状态树完全在内存中。重启后所有 session 状态（ttm_stage 等）丢失。

- **api/middleware/rate_limit.py: RateLimiter._windows 纯内存** (`api\middleware\rate_limit.py`)
  - *类别*: C-持久化
  - 限流窗口完全在内存中。重启后所有限流计数归零，但这不是生产问题。

- **Dashboard 异常路径未测试**
  - *类别*: H-测试覆盖
  - DashboardAggregator.get_ttm_radar/get_sdt_rings 在 YAML 文件缺失或格式错误时 的行为未被任何测试覆盖。当前测试只验证了正常路径。


### MEDIUM

- **RateLimiter 无锁并发写入** (`api\middleware\rate_limit.py`)
  - *类别*: D-并发安全
  - RateLimiter 在 is_allowed/remaining 中执行 `window[:] = [...]` 切片赋值。 多协程并发时（如 WebSocket + HTTP 同时命中同一 key）， 可能因 GIL 释放导致计时戳丢失或计数错误。

- **WebSocket 无消息级限流** (`api\routers\chat.py`)
  - *类别*: E-路由设计
  - chat_websocket 处理函数未对客户端消息速率做限制。 恶意或异常客户端可高速发送 user_message 导致后端过载。 建议对每 session 的消息频率做限流。

- **ADMIN_TOKENS 环境变量为空时无管理员访问** (`api\config.py`)
  - *类别*: F-配置
  - COHERENCE_ADMIN_TOKENS env var 默认值为空字符串，split 后为 []。 这意味着在未设置该环境变量时，is_admin() 永不为 True。 虽然安全但用户首次部署时可能困惑：为什么管理后台永远 403？ 建议在文档中明确说明，或在首次启动时打印 warning 日志。

- **WebSocket 并发消息未测试**
  - *类别*: H-测试覆盖
  - 无测试覆盖 WebSocket 客户端在短时间内发送多条消息的场景。 缺少对消息顺序、并发安全、背压的验证。

- **Token 过期场景未测试**
  - *类别*: H-测试覆盖
  - 无测试覆盖 token 过期后在 IAMSkeleton.validate_token/is_admin 中的行为。 过期 token 应被自动清理并返回 False。


### LOW

- **Dashboard YAML 缓存未实现/未测试**
  - *类别*: H-测试覆盖
  - 当前无 YAML 缓存机制。若后期添加缓存，需测试缓存刷新策略和并发读写。


### INFO

- **IAMSkeleton 无锁（单用户场景可接受）** (`api\middleware\auth.py`)
  - *类别*: D-并发安全
  - IAMSkeleton 使用 dict 存储 token 和状态树，无并发锁。 单用户个人运行场景下无竞态风险，但如果未来迁移到多 worker， 需要加锁或改用 SQLite 持久化。

- **PulseService 无锁（单用户场景可接受）** (`api\services\pulse_service.py`)
  - *类别*: D-并发安全
  - PulseService._pulse_log 的 append 操作在单用户场景下无竞态。


---

## 通过检查

- ✅ lifespan 包含必要的生命周期逻辑
- ✅ CORS 已限制具体 origin，未使用通配符
- ✅ AdminGatesResponse.overall 固定为 'pass'，与 model 一致
- ✅ ExcursionEnterResponse.theme 固定为 'dark'，与 model 一致

---

## 修复建议优先级

### P0 — 立即修复（CRITICAL）

1. **Admin 路由 token query param 未使用**
   - 删除路由签名中的 `token: str = Query(...)`，或将其用于认证替代 header 读取
   - 文件: `api/routers/admin.py`

2. **Dashboard YAML 读取无错误处理**
   - 为 `open()` 和 `yaml.safe_load()` 添加 try/except
   - 添加 YAML 缓存（跨请求共享解析结果）
   - 文件: `api/services/dashboard_aggregator.py`

### P1 — 尽快修复（HIGH）

1. **Async 路由阻塞事件循环**
   - 将 `CoachBridge.chat()` 改为 async，或用 `run_in_executor` 在线程池中执行
   - 文件: `api/routers/chat.py`

2. **所有外部调用缺少超时**
   - 为 `CoachAgent.act()` 和类似调用添加超时参数
   - 文件: `api/services/coach_bridge.py`

3. **lifespan 为空**
   - 在 startup 时初始化 SQLite 连接/状态恢复
   - 在 shutdown 时持久化 IAMSkeleton._tokens 等重要状态
   - 文件: `api/main.py`

4. **三个全局状态纯内存**
   - IAMSkeleton._tokens → SQLite 持久化
   - PulseService._pulse_log → SQLite 持久化
   - RateLimiter._windows → 可保留内存（限流窗口重启归零可接受）

5. **CoachBridge 延迟导入无保护**
   - 添加 try/except ImportError 回退逻辑
   - 或在应用启动时提前导入验证
   - 文件: `api/services/coach_bridge.py`

### P2 — 后续优化（MEDIUM）

1. Excursion enter/exit 限流 key 分离
2. WebSocket 消息级限流
3. 全局异常处理器注册
4. Dashboard request 参数清理

### P3 — 观察项（LOW/INFO）

1. 测试覆盖 Dashboard 异常路径、token 过期、WebSocket 并发
2. 添加 TOKEN_TTL_HOURS 硬上限验证
3. 添加日志（首次启动无 ADMIN_TOKENS 时告警）

---

*本报告由 `reports/audit_s9_1_api.py` 自动生成*