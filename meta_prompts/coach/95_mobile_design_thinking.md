# Phase 9 移动端 — 元提示词设计思考

> 编制日期: 2026-05-04
> 对齐源: Phase 9 完整计划 + `前端和移动端页面设计.txt`
> 前置条件: Phase 9 (S9.1-S9.4) 全部 GO, api_contract.json 待冻结

---

## 0. 为什么这份思考文档

在写元提示词之前，先想清楚以下几个核心问题。如果这些不先想透，生成的元提示词会沦为"写 Flutter 代码"的机械指令，而不是一个可落地的工程方案。

---

## 1. 核心架构决策

### 1.1 为什么 Flutter 而不是 React Native / 原生

设计文档明确指定 Flutter，原因合理：
- **单一代码库覆盖 iOS + Android** — 对个人项目性价比最高
- **Dart 的编译时 null safety** — 与 TypeScript 严格模式理念一致
- **Widget 组合优于继承** — 与 Coherence 组件树思维（TTM 状态驱动 UI 映射）天然对齐
- **不存在引入 JS bridge 的性能断层** — 脉冲动画/滑动确认等交互需要 60fps

### 1.2 状态管理选型

| 方案 | 复杂度 | 测试性 | 适用场景 |
|------|--------|--------|---------|
| setState + InheritedWidget | 低 | 中 | 原型阶段 |
| Provider | 中 | 高 | 中小型 App |
| Riverpod | 中高 | 高 | 中型 App + 编译安全 |
| Bloc | 高 | 高 | 大型团队 |

**决策: Provider** — 理由如下：

1. 本项目是单用户本地 App，不是电商/社交等高并发场景
2. Provider 是 Flutter 官方推荐的入门级状态管理，`ChangeNotifier` 模式与 React hooks 的心智模型相似（熟悉的开发者迁移成本低）
3. 不存在跨页面复杂状态同步的需求（聊天页面 ↔ 仪表盘无强耦合）
4. Provider 的 `ChangeNotifierProvider` + `Consumer` 模式足够覆盖所有场景

### 1.3 离线优先策略

设计文档提到"离线优先"，但需要区分"真正的离线"和"弱网容忍"：

- **Phase 9 移动端第一阶段**: 弱网容忍 — API 请求超时重试 + 本地缓存最近一次仪表盘数据
- **未来阶段**: 真正的离线优先 — SQLite 本地存储 + 队列同步

理由：系统依赖 CoachAgent（后端 Python），没有本地推理能力，真正的离线意味着需要在移动端运行 CoachAgent，这不现实。

### 1.4 导航架构

底部导航栏 4 个 Tab：

```
[对话] [探索] [成长] [设置]
```

- 对话: 聊天界面 + 脉冲面板 + 远足覆盖层（核心高频界面）
- 探索: 学习资源推荐（TTM 状态驱动内容）
- 成长: 仪表盘聚合（TTM 雷达 + SDT 环 + 进度 + 盾牌）
- 设置: 用户偏好 + 角色切换（user/admin/debug）+ 关于

管理后台通过设置页的 RBAC 门禁进入，不占用底部导航 Tab。

---

## 2. 子阶段分解逻辑

### 2.1 为什么分 5 个子阶段

Phase 9 的 Web 前端分了 4 步（S9.1 API→S9.2 Web→S9.3 Admin→S9.4 A11y），但移动端不同：

**Web 前端 API 层是独立的新建步骤**（因为之前不存在），而移动端 API 层已存在。所以移动端的核心工作是**Flutter 客户端本身**。

分 5 步的逻辑：

| 子阶段 | 为什么独立 | 风险 |
|--------|-----------|------|
| **M0: 合约冻结** | api_contract.json 是移动端和未来的契约，必须先冻结。此外需安装 Flutter SDK。 | 低 |
| **M1: 核心基础** | 项目骨架、主题、路由、API 客户端 — 所有后续模块依赖它们。不先搭好，后面每步都卡。 | 中 |
| **M2: 聊天交互** | 最高频使用的界面，也是 WebSocket 集成的关键路径。独立验证实时通信稳定性。 | 高 |
| **M3: 仪表盘** | 纯展示层，依赖 API 数据聚合。与聊天模块无代码耦合，可以独立开发测试。 | 低 |
| **M4: 管理后台** | RBAC 门禁的管理员视图。属于"少人用但很重要"的模块，放在最后不阻塞主路径。 | 低 |

### 2.2 M0 为什么必要

api_contract.json 在 S9.2 结束时就应该冻结，但实际上不存在。如果跳过这一步直接写 Flutter 代码，会出现：
- API 路径硬编码在各个 Dart 文件中
- 请求/响应类型手动定义，容易与后端不一致
- 没有单一真相源，前后端对不齐时无法追责

所以 M0 是**技术债清理**，不是多余步骤。

### 2.3 测试策略的分阶段视角

| 子阶段 | 测试重点 | 工具 | 最低通过 |
|--------|---------|------|---------|
| M1 | Widget 渲染测试 | flutter_test | 5 pass |
| M2 | 聊天组件交互 + WebSocket mock | flutter_test + mockito | 15 pass |
| M3 | 仪表盘数据绑定 + 图表渲染 | flutter_test + golden | 10 pass |
| M4 | RBAC 门禁 + 管理组件 | flutter_test | 10 pass |
| 最终 | 全量回归 | flutter test | 40+ pass |

---

## 3. 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Flutter SDK 安装/版本兼容问题 | 中 | 高 | M0 先验证 `flutter doctor`，不通过不进入 M1 |
| WebSocket 在移动端断连/重连 | 中 | 高 | M2 专门测试 WS 稳定性，实现指数退避重连 |
| 移动端图表库（雷达图/环形图）找不到合适包 | 低 | 中 | M3 预留备选方案：fl_chart → CustomPainter 降级 |
| 与 Web 前端主题色不一致 | 中 | 低 | 从 `frontend/src/styles/theme.ts` 提取 Hex 值生成 Dart 常量 |
| TTM 状态驱动 UI 在 Flutter 中实现复杂 | 低 | 中 | 保持与 stateMachine.ts 相同的 Map 映射模式 |

---

## 4. 与现有系统的集成点

```
移动端 Flutter App
    │
    ├── REST API → FastAPI `/api/v1/*` (已存在)
    │   ├── POST /session          → 会话创建/恢复
    │   ├── POST /chat             → 消息 → DSL 响应
    │   ├── POST /pulse/respond    → 脉冲决策
    │   ├── POST /excursion/enter  → 远足进入
    │   ├── POST /excursion/exit   → 远足退出
    │   ├── GET  /dashboard/user   → 仪表盘数据
    │   ├── GET  /admin/gates/status → 门禁状态
    │   ├── GET  /admin/audit/logs → 审计日志
    │   └── GET  /health           → 健康检查
    │
    ├── WebSocket → ws://host/api/v1/chat/ws (已存在)
    │   ├── → user_message (发送)
    │   ├── ← coach_response (接收)
    │   ├── ← pulse_event (接收)
    │   └── → pulse_decision (发送)
    │
    └── 主题色系 → frontend/src/styles/theme.ts (已存在, 直接提取 Hex)
        ├── warmWhite, softBlue, sageGreen, ...
        ├── deepMocha (主文本), coralCandy (柔性警告)
        └── sandalwoodMist, creamPaper, warmSand, clayBrown, charcoal
```

### 关键约束: 不修改后端一行代码

移动端是纯客户端项目。FastAPI 后端已经过 S9.1 测试+审计，禁止任何修改。
如果移动端发现 API 缺失字段，走以下流程：
1. 记录为"API 缺口"
2. 在 M0 的 api_contract.json 中标记
3. 待用户决定是否升级合约版本

---

## 5. 组件树与 Web 前端的映射关系

| Web 前端组件 | Flutter 对应组件 | 实现差异 |
|-------------|-----------------|---------|
| ChatBubble | ChatBubble widget | 基本相同，Flutter 用 RichText + EdgeInsets |
| ChatInput | ChatInput widget | 基本相同，Flutter 用 TextField + send button |
| PulsePanel | PulsePanel widget | Slide-to-Confirm 在 Flutter 中用 GestureDetector 实现 |
| ExcursionOverlay | ExcursionOverlay widget | Flutter 用 AnimatedContainer + Theme 切换 |
| TTMStageCard | TTMStageCard widget | Radar chart: fl_chart RadarChart |
| SDTEnergyRings | SDTEnergyRings widget | CustomPainter 绘制三个环形 |
| ProgressTimeline | ProgressTimeline widget | ListTile + 自定义布局 |
| GateShieldBadge | GateShieldBadge widget | CustomPaint SVG 路径 |
| GatePipeline | GatePipeline widget | ExpansionTile 列表 |
| AuditLogViewer | AuditLogViewer widget | DataTable + 分页 |
| RiskDashboard | RiskDashboard widget | Card 列表 |
| HealthShield | HealthShield widget | Icon + 着色 |

---

## 6. 测试策略

### 6.1 Widget 测试

每个核心组件至少覆盖：
- 正常渲染（传入合法 props）
- 边界状态（null / 空列表）
- 用户交互（点击/滑动反馈）

### 6.2 API 模拟

使用 `mockito` + `MockWebServer` 模拟后端响应：
- 正常响应路径
- HTTP 4xx/5xx
- 超时
- WebSocket 断连

### 6.3 集成测试

使用 `integration_test` 包模拟完整流程：
1. 启动 App → 创建会话
2. 发送消息 → 接收响应
3. 脉冲出现 → 滑动确认
4. 进入仪表盘 → 查看 TTM 雷达
5. 切换角色 → 查看 GatePipeline

---

## 7. 文件结构设计

```
mobile/
├── pubspec.yaml
├── analysis_options.yaml
├── lib/
│   ├── main.dart                  # 入口 + ProviderScope
│   ├── app.dart                   # MaterialApp + 主题 + 路由
│   ├── config/
│   │   ├── theme.dart             # 色彩系统(与theme.ts一致)
│   │   ├── constants.dart         # API URL + 脉冲阈值常量
│   │   └── routes.dart            # 路由表 + 底部导航
│   ├── api/
│   │   ├── client.dart            # HTTP 客户端封装
│   │   ├── session_api.dart       # 会话 API
│   │   ├── chat_api.dart          # 对话 API
│   │   ├── dashboard_api.dart     # 仪表盘 API
│   │   ├── admin_api.dart         # 管理 API
│   │   └── websocket_client.dart  # WS 客户端
│   ├── models/
│   │   ├── session.dart
│   │   ├── chat_response.dart
│   │   ├── pulse_event.dart
│   │   ├── excursion.dart
│   │   ├── dashboard.dart
│   │   ├── admin_gates.dart
│   │   └── audit_log.dart
│   ├── providers/
│   │   ├── session_provider.dart
│   │   ├── chat_provider.dart
│   │   ├── pulse_provider.dart
│   │   ├── dashboard_provider.dart
│   │   └── auth_provider.dart
│   ├── screens/
│   │   ├── shell.dart             # 底部导航外壳
│   │   ├── chat/
│   │   │   ├── chat_screen.dart
│   │   │   ├── chat_bubble.dart
│   │   │   ├── chat_input.dart
│   │   │   └── pulse_panel.dart
│   │   ├── explore/
│   │   │   └── explore_screen.dart
│   │   ├── growth/
│   │   │   ├── growth_screen.dart
│   │   │   ├── ttm_stage_card.dart
│   │   │   ├── sdt_energy_rings.dart
│   │   │   ├── progress_timeline.dart
│   │   │   └── gate_shield_badge.dart
│   │   ├── settings/
│   │   │   └── settings_screen.dart
│   │   ├── excursion/
│   │   │   └── excursion_overlay.dart
│   │   └── admin/
│   │       ├── admin_screen.dart
│   │       ├── gate_pipeline.dart
│   │       ├── audit_log_viewer.dart
│   │       └── risk_dashboard.dart
│   └── utils/
│       ├── contrast_check.dart    # WCAG AA (移植自frontend)
│       ├── color_adapt.dart       # 环境光适配
│       └── state_machine.dart     # TTM → UI 映射
├── test/
│   ├── api/
│   ├── providers/
│   ├── screens/
│   └── utils/
└── assets/
    └── fonts/
```

---

## 8. 子阶段工期估算

| 子阶段 | 文件数 | 测试数 | 预估工期 |
|--------|--------|--------|---------|
| M0: 合约冻结 | 2 | 0 | ~0.5天 |
| M1: 核心基础 | ~15 | ~5 | ~1天 |
| M2: 聊天交互 | ~10 | ~15 | ~2天 |
| M3: 仪表盘 | ~8 | ~10 | ~1.5天 |
| M4: 管理后台 | ~6 | ~10 | ~1天 |
| **合计** | **~41** | **~40+** | **~6天** |

---

## 9. 关键设计取舍

### 9.1 不使用的 Flutter 特性

- **代码生成 (json_serializable, freezed)**: 在个人项目中引入 codegen 增加构建复杂度，手动编写 fromJson/toJson 即可（模型数量 ~10 个）
- **go_router**: 4 个 Tab 底部导航不需要路由库，`IndexedStack` + `BottomNavigationBar` 足够
- **BLoC**: 对于单用户 App 过于重量级，Provider 足够

### 9.2 主动使用的 Flutter 特性

- **CustomPainter**: 用于 SDT 能量三环 + GateShieldBadge SVG 渲染（性能关键路径）
- **AnimatedWidget**: 脉冲面板的滑动动画 + 远足覆盖层的转场动画
- **InheritedWidget**: 主题色系统全局传递
- **ValueNotifier**: 轻量级状态传递（替代 StreamController）

### 9.3 移动端特有的交互差异

| 交互 | Web 实现 | 移动端实现 |
|------|---------|-----------|
| 滑动确认 | drag events + CSS transform | GestureDetector + AnimatedContainer |
| 远足暗调 | CSS filter + class toggle | ThemeData.dark() + AnimatedTheme |
| 脉冲通知 | 内联 Panel | OverlayEntry + 底部 Sheet |
| 图表交互 | SVG/Canvas 库 | fl_chart + CustomPainter |

---

## 10. 总结

这份思考文档覆盖了从"为什么 Flutter"到"每个子阶段做什么"的完整决策链。核心结论：

1. **Provider + 手动模型 + IndexedStack** — 最简可行架构，不引入不必要的复杂度
2. **5 个子阶段严格串行** — M0→M1→M2→M3→M4，每阶段非 GO 不得进入下一阶段
3. **不修改后端一行代码** — 移动端是纯消费者
4. **与 Web 前端共享合约** — api_contract.json 是单一真相源
5. **测试先行** — 每个组件有 Widget 测试，API 调用有 Mock 测试
