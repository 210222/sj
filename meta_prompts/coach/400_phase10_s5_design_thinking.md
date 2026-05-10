# Phase 10 S5 — 代码沙箱 元提示词设计思考

> 编制日期: 2026-05-05
> 对齐源: Phase 10 S1+S2+S3+S4, Phase 10 落地方案 §5
> 前置条件: 1192 tests pass, LLM 可生成教学内容

---

## 0. 为什么这份思考文档

S5（代码沙箱）是 Phase 10 中风险最高的一层。让 LLM 生成的代码在系统中执行，一旦沙箱设计不当，会导致：

1. **代码注入** — LLM 生成的代码包含恶意指令（`rm -rf /`、读取敏感文件）
2. **资源耗尽** — 死循环、大内存分配拖垮主机
3. **数据泄露** — 代码访问文件系统或网络，上传用户数据

所以 S5 的核心设计目标不是"让代码跑起来"，而是"让代码安全地跑起来，且在用户知情同意的前提下"。

---

## 1. 核心架构决策

### 1.1 沙箱方案选择

| 方案 | 安全等级 | 复杂度 | 依赖 | 适用场景 |
|------|---------|--------|------|---------|
| subprocess + timeout | 低 | 低 | 零依赖 | 简单代码执行 |
| Docker 容器 | 高 | 高 | Docker | 生产环境 |
| RestrictedPython | 中 | 中 | 需安装 | Python-only |
| **subprocess + 资源限制 + 路径白名单** | **中高** | **低** | **零依赖** | **个人单用户系统** |

**决策**: subprocess + 资源限制 + 路径白名单。理由：
- 无需额外安装 Docker 或第三方包
- 资源限制（timeout, 内存, CPU）通过 subprocess 的 `preexec_fn` + `resource` 模块实现
- 文件系统白名单：代码只能访问指定 sandbox 目录
- 网络隔离：通过 `subprocess` 环境变量控制
- 对于 P0 风险（删除系统文件）: 以非特权用户运行、只读 `/`、sandbox 目录可写

### 1.2 执行流程 — 为什么必须在主权脉冲之后

```
LLM 生成含代码的 payload
  → S2 校验（对齐 → 过滤 → 校验）
  → 门禁管线
  → 用户看到代码 + "要运行吗？"（主权脉冲）
  → 用户确认 → 沙箱执行
  → 执行结果 → 教练据此继续教学
```

**关键约束**: 代码执行必须用户显式确认。LLM 生成的代码展示给用户（通过 payload 的 `code` 字段），但不自动执行。

### 1.3 代码存储格式

LLM 在 JSON payload 中返回 `code` 和 `language` 字段：

```json
{
    "statement": "试试这段 Python 代码...",
    "code": "print('hello world')",
    "language": "python",
    "topics": ["print", "hello world"]
}
```

`code` 字段是可选的。不包含 `code` 字段时，行为与 S1-S4 完全一致。

### 1.4 执行结果注入

沙箱执行结果需要能注入到下一轮 LLM prompt 中：

```
Round N: LLM 生成代码 → 用户确认执行 → 结果保存
Round N+1: LLM prompt 中注入 "代码执行结果: ..."
```

结果通过 `ArchivalMemory` 存储，S4.1 的记忆注入会将其带入下一轮 prompt。

### 1.5 安全红线

- **禁止执行未经过滤的代码** — S2 安全过滤必须在代码执行之前
- **禁止默认自动执行** — 必须用户确认（主权脉冲）
- **禁止访问文件系统** — sandbox 子进程只能读写 sandbox 目录
- **禁止网络访问** — 子进程隔离网络
- **禁止长时间运行** — timeout 硬限制（默认 10s，可配）
- **禁止 root/system 权限** — 子进程以当前用户运行（不提权）

---

## 2. S5 与已有机制的关系

| 组件 | S5 做什么 | 关系 |
|------|----------|------|
| `LLMDSLAligner` | code/language 成为通用字段 | 通用字段列表扩展 |
| `LLMSafetyFilter` | code 字段中的 forbidden 短语过滤 | 字符串字段递归扫描，code 字段会被自动过滤 |
| `LLMOutputValidator` | code/language 可选字段 | 不强制要求，已有 statement 校验不变 |
| Sovereign Pulse | 代码执行前必须触发脉冲确认 | 复用现有脉冲机制 |
| `ArchivalMemory` | 存储代码执行结果 | 复用，S4 的记忆注入自动带出 |
| `coach_defaults.yaml` | sandbox 配置节新增 | timeout, max_memory, allowed_languages |

---

## 3. 边界情况处理

### 3.1 代码执行超时

```
timeout=10s → subprocess 超时 → 杀死进程
→ 返回 {"error": "timeout", "detail": "执行超时（10s）"}
→ LLM 下轮可据此调整代码复杂度
```

### 3.2 代码执行报错

```
用户代码有语法错误 → subprocess 返回 stderr
→ 返回 {"error": "syntax", "detail": "NameError: ..."}
→ LLM 下轮可修正代码
```

### 3.3 无限循环

```
用户确认执行 while True: pass
→ timeout=10s → 杀死进程
→ LLM:"代码似乎进入了无限循环，我们加个终止条件试试"
```

### 3.4 代码不含 code 字段

```
LLM 输出 {"statement": "我们来学习 Python"}
→ 不含 code 字段
→ 不走沙箱路径，与 S1-S4 完全一致
```

### 3.5 多语言支持

```
language = "python" | "javascript" | "bash"
→ 通过 subprocess 调用对应解释器
→ 不在 allowed_languages 列表中的语言拒绝执行
```

---

## 4. 测试策略

### 4.1 沙箱测试

```
test_sandbox.py:
  - 简单代码正确执行
  - 代码超时被杀死
  - 代码报错返回 stderr
  - 无限循环被 timeout 终止
  - 未支持语言返回错误
  - 空代码返回错误
```

### 4.2 集成测试

```
test_s5_integration.py:
  - LLM 返回含 code 字段的 payload → 存入 action payload
  - 用户确认 → sandbox 执行
  - 结果存入 memory
  - 不含 code 字段时不走沙箱路径
```

---

## 5. S5 在整个 Phase 10 中的位置

```
Phase 10:
  S1: LLM 客户端 + 基础集成      ← GO ✅
  S2: 输出校验 + 安全对齐        ← GO ✅
  S3: WebSocket 流式推送          ← 元提示词已创建
  S4: 记忆增强 + 多轮上下文       ← 元提示词已创建
  S5: 代码沙箱                   ← 本次
```

S5 完成意味着 Phase 10 的完整落地方案全部就绪。

---

## 6. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| LLM 生成恶意代码 | 低 | 高 | subprocess 沙箱 + timeout + 无网络 |
| 死循环耗尽资源 | 中 | 中 | timeout 硬限制（10s）+ 可配置 |
| 沙箱逃逸 | 极低 | 高 | 不以 root 运行 + 无提权操作 |
| LLM 在 code 字段中注入 forbidden 短语 | 低 | 低 | S2.2 filter_payload 递归扫描字符串，code 字段会被自动扫描 |
| 用户误确认执行有害代码 | 低 | 高 | 沙箱路径白名单 + 无网络 + 只读系统文件 |
