# 元提示词设计检查清单

基于 frontend_bugs_postmortem.md 提炼的全局规则，供后续所有 Phase 设计时前置验证。

## 一、架构层检查（写代码前）

```
[ ] 跨请求数据: 是否依赖实例变量? 若是, 改为 persistence (SQLite) 存储
    —— CoachAgent 每次 API 请求新建实例, 实例变量跨请求丢失

[ ] yaml 写入: 是否用了 yaml.dump? 若是, 改为 yaml.safe_dump
    —— Windows 下 yaml.dump 产生不可解析输出

[ ] 模块级缓存: 修改 config 后是否清除 sys.modules 缓存?
    —— 否则已运行进程不加载新配置

[ ] 类型兼容: 新增字段在 TypeScript 中是否为 optional?
    —— 否则旧 localStorage 缓存导致前端崩溃

[ ] **调用点注入: 新增的 save/load/update 方法是否被 act() / compose() 调用?**
    [ ] 是 → success_criteria 中含调用验证
    [ ] 否 → 要么找到调用点并注入, 要么在文档中标注"此方法由 XXX 在 Phase N 调用"
    —— 否则方法写好了但没人调, 功能等于没做 (见 Phase 29 的 7 处接线漏调)
```

## 二、副作用分析（写代码时）

```
每个改动在实施前回答:
  [ ] 改了这里, 哪里会坏?
  [ ] 坏了怎么恢复? (回滚策略)
  [ ] 坏了用户能看到什么? (错误提示)
  [ ] 极端输入会怎样? (空值/超长/并发)
  [ ] 旧数据兼容吗? (localStorage/DB 旧格式)
```

## 三、验收检查（写代码后）

```
[ ] 苏醒面板: 新 session 首轮展示 -> 第二轮不再展示
[ ] 上下文: 3 轮对话 -> LLM 回复引用前两轮
[ ] 教学模式: 新用户 -> 首轮 probe -> 后续 scaffold (不再连续 probe)
[ ] 配置开关: PUT /api/v1/config -> YAML 可解析 -> 下次请求读取新值
[ ] 消息持久: 发 3 条 -> 刷新 -> 3 条仍在 -> 换浏览器 -> 服务端可恢复
[ ] WebSocket: 控制台无错误 -> 消息正常收发
[ ] Loading: 发消息 -> 思考动画 -> 回复到达 -> 动画消失
[ ] 全量回归: pytest tests/ -q 全部 passed
```

## 四、元提示词结构 v2

对比 v1 和 v2:

```
v1 (Phase 19-26): context -> task -> success_criteria
v2 (Phase 27+):   context -> risk_analysis -> task -> side_effects -> success_criteria
                      ↑ 新增          ↑ 新增
```

v2 中新增:
- risk_analysis: 改动范围和副作用预测 (前置)
- side_effects: 每个 task 后标注改了这里会破坏什么+如何预防
