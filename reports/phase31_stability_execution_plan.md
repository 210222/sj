# Phase 31 收尾稳态段执行计划

## 1. 文档目的

本文件是 Phase 31 收尾稳态段的执行计划（非最终冻结 runbook，因部分测试文件待本阶段新增）。
执行对象为以下 5 份元提示词：

- `meta_prompts/coach/230_phase31_orchestrator.xml`
- `meta_prompts/coach/231_s31_a_memory_closure.xml`
- `meta_prompts/coach/232_s31_b_act_order_summary.xml`
- `meta_prompts/coach/233_s31_c_config_consistency.xml`
- `meta_prompts/coach/234_s31_d_regression_gates.xml`

> 消歧义：以上文件名中 S31 表示 Phase 31 子阶段，不表示历史 Phase 10 S3.1 编号体系。

本文件定义：
- 执行顺序
- 每阶段输入
- 每阶段输出
- 每阶段禁止改动边界
- 每阶段测试命令
- GO / NO-GO 判断标准
- 最终 Phase 31 验收标准

---

## 2. 全局约束

### 2.1 禁止修改
- `contracts/**`
- `src/inner/**`
- `src/middle/**`
- `src/outer/**`

### 2.2 禁止漂移
- 禁止 schema drift
- 禁止 reason_code drift
- 禁止通过调整既有编排链顺序绕过问题

### 2.3 工程约束
- 所有 YAML 写入必须使用 `yaml.safe_dump`
- 涉及 config 的修改必须处理模块缓存
- 新增 `save/load/update` 必须同 Phase 完成调用点注入
- 严格串行执行，未 GO 不得进入下一阶段

---

## 3. 执行顺序

### 固定顺序
1. S31.A 记忆链路闭环
2. S31.B act() 顺序与上下文摘要正确性
3. S31.C 配置写入一致性
4. S31.D 测试补强与最终门禁

### 串行纪律
- 未通过 GO_A，禁止进入 S31.B
- 未通过 GO_B，禁止进入 S31.C
- 未通过 GO_C，禁止进入 S31.D
- 任一阶段出现越界修改，立即 NO-GO

---

## 4. 阶段执行说明

### S31.A 记忆链路闭环

#### 目标
从零打通 SessionMemory 的 ai_response 链路（sessions 表加列 + store 写入 + recall 返回，三层全部打通）。

#### 当前真实状态
sessions 表尚无 ai_response 列，store() 未写入该字段，recall() 未返回该字段 —— schema + store + recall 三层都未打通。

#### 主要输入（既有资产）
- `src/coach/agent.py`
- `src/coach/memory.py`
- `tests/test_coach_memory_upgrade.py`
- `tests/test_phase27.py`

#### 本阶段必须新增
- `tests/test_phase31.py` —— 跨文件行为门禁

#### 主要输出
- sessions 表新增 ai_response 列（幂等迁移）
- store() 真实写入 ai_response
- recall() 返回结构中可读 `data.ai_response`
- `_build_context_summary()` 能在下一轮引用上一轮教学内容

#### 禁止事项
- 不重做 FTS
- 不改 contracts
- 不扩展 API schema
- 不把 `_prev_teaching` 和 `ai_response` 变成双主路径
- 不修改 `src/outer/**`

#### 推荐测试
- `python -m pytest tests/test_coach_memory_upgrade.py -q`
- `python -m pytest tests/test_phase27.py -q`
- `python -m pytest tests/test_phase31.py -q`

#### GO_A 标准
- 第 2 轮摘要可引用第 1 轮 AI 教学文本
- `data.ai_response` 非空
- 旧库兼容
- 无越界修改

### S31.B act() 顺序与摘要正确性

#### 目标
让摘要中的上一轮策略、上一轮教学内容与真实最终结果一致。

#### 主要输入（既有资产）
- `src/coach/agent.py`
- `tests/test_phase27.py`

#### 本阶段继续补强
- `tests/test_phase31.py`（承接 A 阶段已创建的文件）

#### 主要输出
- act() 顺序稳定
- action override 结束后再注入摘要
- 摘要与最终 `action_type` 不再错配

#### 禁止事项
- 不新增摘要块
- 不做文案美化型修改
- 不重构整个 act()
- 不改变治理链顺序
- 不修改 `src/outer/**`

#### 推荐测试
- `python -m pytest tests/test_phase27.py -q`
- `python -m pytest tests/test_phase31.py -q`

#### GO_B 标准
- 连续两轮/三轮行为断言通过
- "策略连续性"与真实动作一致
- 不再出现"摘要动作 != 最终动作"

### S31.C 配置写入一致性

#### 目标
统一产品级 `coach_defaults.yaml` 的写入规则与缓存失效策略。

#### 当前真实状态
config_router._write_config() 不调用 _invalidate_cache()（孤儿函数，无任何调用点）；agent._update_config() 使用 yaml.dump 且不清任何缓存。API 侧配置缓存失效闭环尚未建立。

#### 主要输入（既有资产）
- `api/routers/config_router.py`
- `src/coach/agent.py`
- `api/services/dashboard_aggregator.py`
- `tests/test_api_dashboard.py`
- `tests/test_s16_awakening.py`

#### 本阶段必须新增
- `tests/test_api_config.py` —— /api/v1/config 直接路由测试

#### 本阶段继续补强
- `tests/test_phase31.py` —— 追加配置一致性行为门禁

#### 主要输出
- 产品级 config 写入统一 `safe_dump`
- config 写入后 coach 模块缓存失效
- API 侧配置缓存失效（_invalidate_cache() 接入写入路径）
- API 路径与对话式路径的写配置行为一致

#### 禁止事项
- 不扫全仓 `yaml.dump`
- 不扩张 EXPOSED_KEYS 白名单
- 不修改 auto_affects 语义
- 不承诺强刷已存在实例内部状态
- 不修改 `src/outer/**`

#### 推荐测试
- `python -m pytest tests/test_api_dashboard.py -q`
- `python -m pytest tests/test_s16_awakening.py -q`
- `python -m pytest tests/test_api_config.py -q`
- `python -m pytest tests/test_phase31.py -q`

#### GO_C 标准
- PUT 后 GET 可见
- 新请求不读旧缓存
- 对话式启停与 API 写入结果一致
- 无越界修改

### S31.D 测试补强与最终门禁

#### 目标
把 A/B/C 的关键行为固化为 targeted regression，并以最终全量回归收口。

#### 新测试文件（本阶段必须新增，非可选）
- `tests/test_api_config.py` —— 必须新增，覆盖 /api/v1/config 直接路由测试
- `tests/test_phase31.py` —— 必须新增，承接跨文件行为门禁

#### 补强既有文件
- `tests/test_coach_memory_upgrade.py`
- `tests/test_phase27.py`
- `tests/test_api_dashboard.py`

#### 主要输出
- A/B/C 对应 targeted regression
- 最终 full regression 通过
- 边界门禁检查结果

#### 禁止事项
- 不以"测试绿"为理由修改 protected layers
- 不把断言写成过度绑定文案的脆弱测试
- 不跳过 targeted suite 直接跑全量

#### 推荐测试顺序
1. `python -m pytest tests/test_coach_memory_upgrade.py -q`
2. `python -m pytest tests/test_phase27.py -q`
3. `python -m pytest tests/test_api_dashboard.py -q`
4. `python -m pytest tests/test_api_config.py -q`
5. `python -m pytest tests/test_phase31.py -q`
6. `python -m pytest tests/ -q`

#### GO_D 标准
- targeted suite 全绿
- `python -m pytest tests/ -q` 全绿
- forbidden paths 无修改（contracts/**, src/inner/**, src/middle/**, src/outer/**）
- 无 schema/reason_code drift
- 无"新增 save/load/update 却没接调用点"残留

---

## 5. 最终验收标准

### A 类：记忆闭环
- 同 session 第 1 轮教学文本，第 2 轮能被摘要引用
- 不是空字符串
- 不是占位文本
- 不是中间态草稿

### B 类：顺序与摘要
- 摘要中的"策略连续性"与真实上一轮/本轮动作一致
- action_type 在 override 完成后再进入摘要构建
- 不出现"摘要写 scaffold，返回 probe"

### C 类：配置一致性
- 产品级 config 写入统一 `safe_dump`
- API 路由与对话式启停模块写入格式一致
- 写后下一次读取不再吃旧缓存

### D 类：回归门禁
- A/B/C 都有 targeted tests
- `/api/v1/config` 存在直接测试覆盖（tests/test_api_config.py）
- `test_phase27` 不再只是"块存在"，而是"块内容正确"
- `test_phase31` 跨文件行为门禁存在
- `python -m pytest tests/ -q` 全绿

### 边界类
- 未修改 `contracts/**`
- 未修改 `src/inner/**`
- 未修改 `src/middle/**`
- 未修改 `src/outer/**`

---

## 6. NO-GO 条件

任一命中，Phase 31 立即判定 NO-GO：

1. 修改了禁止目录（contracts/**, src/inner/**, src/middle/**, src/outer/**）
2. 引入 schema drift
3. 引入 reason_code drift
4. 通过改编排链顺序绕过问题
5. 新增 save/load/update 但未接调用点
6. 产品级 config 写入仍有 `yaml.dump` 残留
7. targeted suite 未通过却继续推进下一阶段

---

## 7. 最终结论

Phase 31 完成的判断标准不是"感觉修完了"，而是：

- A/B/C/D 四阶段全部 GO
- targeted regression 全绿
- full regression 全绿
- 边界无越界
- 无漂移

只有同时满足这 5 条，Phase 31 收尾稳态段才算真正完成。
