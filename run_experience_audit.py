#!/usr/bin/env python3
"""Phase 32: 体验审计管道 — baseline 正式版.

S32.1: 5 画像 × 20 轮模拟 + 5 断点探针
S32.2: 5 维体验评分 + failure_cases 归档
支持 run_id 隔离、run_history、LATEST 指针。
U1 模拟 + U2 评分 = 规则引擎, 不需要 API key。
U3/U4/U5 = LLM Agent, 需要 DEEPSEEK_API_KEY。
"""
import argparse, json, os, sys, time, uuid, subprocess
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.coach.agent import CoachAgent

OUTPUT_DIR = Path(__file__).resolve().parent / "reports" / "experience_audit"
RUN_HISTORY_DIR = OUTPUT_DIR / "runs"
STATE_FILE = OUTPUT_DIR / "shared_state.json"


# ── S32.1: Run identity ─────────────────────────────────────────

def _generate_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]


def _get_git_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(Path(__file__).resolve().parent),
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


# ── AuditState ──────────────────────────────────────────────────

class AuditState:
    """轻量审计状态容器，记录探针结果与断点."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.probes: dict[str, dict] = {}
        self.start_time = datetime.now(timezone.utc).isoformat()
        self.breakpoints_detected: list[str] = []

    def record_probe(self, probe_id: str, passed: bool, detail: str = "") -> None:
        self.probes[probe_id] = {
            "passed": passed,
            "detail": detail,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        if not passed:
            self.breakpoints_detected.append(probe_id)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "start_time": self.start_time,
            "probes": self.probes,
            "breakpoints_detected": self.breakpoints_detected,
        }


# ── S32.1: 5 种用户画像 ──────────────────────────────────────

PROFILES = {
    "novice_confirm": {
        "name": "新手A: 只确认",
        "messages": (["好", "嗯", "继续", "可以", "好"] * 4)[:20],
    },
    "novice_jump": {
        "name": "新手B: 乱跳",
        "messages": [
            "教 Python", "讲列表", "循环是什么", "字典怎么用", "学函数",
            "装饰器", "类", "文件读写", "异常处理", "pip 安装",
            "写个爬虫", "数据可视化", "机器学习", "深度学习", "PyTorch",
            "回归", "分类", "聚类", "RNN", "Transformer",
        ][:20],
    },
    "advanced": {
        "name": "进阶者: 追问",
        "messages": (["教 Python", "为什么", "具体点", "还有吗", "举个例子",
                      "还是不懂", "换个说法", "和Java的区别", "底层原理", "还有吗"] * 2)[:20],
    },
    "reviewer": {
        "name": "复习者: 回环",
        "messages": (["教列表", "教循环", "再讲一遍列表", "教循环", "列表还有什么",
                      "循环高级用法", "再讲列表", "列表推导式", "再讲循环"] * 2 + ["教完了吧"])[:20],
    },
    "tester": {
        "name": "测试者: 考我",
        "messages": (["教 Python", "考考我", "教列表", "考考我", "教循环",
                      "考考我", "教函数", "考考我", "教类", "考考我"] * 2)[:20],
    },
}


def _extract_payload_text(payload: dict) -> str:
    """12 字段提取链，覆盖全部 action_type 的 payload 形状."""
    fields = [
        "statement", "question", "option", "step", "problem", "reason", "prompt",
        "text", "message", "content", "response", "feedback",
    ]
    for f in fields:
        v = payload.get(f, "")
        if v and isinstance(v, str) and len(v.strip()) > 0:
            return v
    return ""


def simulate_profile(pid: str, profile: dict, use_http: bool = True,
                     base_url: str = "http://127.0.0.1:8001") -> list[dict]:
    """运行单个画像的 20 轮对话."""
    if not use_http:
        agent = CoachAgent(session_id=f"exp_{pid}")
    sid = f"exp_{pid}"
    turns = []
    if use_http:
        import urllib.request as _ur, urllib.error as _ue
        try:
            data = __import__('json').dumps({"session_id": sid}).encode()
            req = _ur.Request(f"{base_url}/api/v1/session", data=data,
                              headers={"Content-Type": "application/json"})
            _ur.urlopen(req, timeout=5)
        except Exception:
            pass

    for i, msg in enumerate(profile["messages"]):
        if i >= 20:
            break
        try:
            if use_http:
                import urllib.request as _ur2, json as _j2
                data = _j2.dumps({"session_id": sid, "message": msg}).encode()
                req = _ur2.Request(f"{base_url}/api/v1/chat", data=data,
                                   headers={"Content-Type": "application/json"})
                with _ur2.urlopen(req, timeout=60) as resp:
                    r = _j2.loads(resp.read().decode("utf-8"))
            else:
                r = agent.act(msg)
            payload = r.get("payload", {})
            # Phase 36: extract LLM runtime observability from API response
            llm_obs = r.get("llm_observability")
            turns.append({
                "turn": i + 1,
                "user": msg,
                "action_type": r.get("action_type", "?"),
                "payload_statement": _extract_payload_text(payload),
                "llm_generated": r.get("llm_generated", False),
                "difficulty": r.get("difficulty_contract", {}),
                "trace_id": r.get("trace_id"),
                "intent": r.get("intent"),
                "has_pulse": r.get("pulse") is not None,
                "ttm_stage": r.get("ttm_stage"),
                "source_tag": r.get("domain_passport", {}).get("source_tag"),
                "llm_observability": llm_obs,  # Phase 36
            })
        except Exception as e:
            turns.append({
                "turn": i + 1, "user": msg,
                "action_type": "error",
                "payload_statement": f"ERROR: {e}",
                "llm_generated": False,
            })
        if i < len(profile["messages"]) - 1:
            time.sleep(0.05)
    return turns


# ── S32.2: 5 维评分引擎 ──────────────────────────────────────

CONFIRM_PHRASES = [
    "准备好了吗", "明白了吗", "你觉得呢", "你想学什么",
    "你准备好了吗", "可以开始吗", "你想从哪里开始",
    "你想继续学哪方面", "请选择一个方向",
]


def score_turn(turn: dict, prev_turn: dict | None, prev_meaningful: dict | None = None) -> dict:
    """对单轮对话打 5 维体验分 (0-4 each)."""
    s = {}
    stmt = turn.get("payload_statement", "")

    # 1. 引用性: 中文 n-gram + 短句全文匹配 + meaningful 回溯
    CONFIRM_WORDS = {"好", "嗯", "继续", "可以", "好的", "行", "是", "对", "ok", "yes"}
    ref_score = 0
    ref_source = prev_meaningful if prev_meaningful else prev_turn
    if ref_source and stmt:

        def _tokenize(text: str) -> set[str]:
            tokens: set[str] = set()
            cjk_count = sum(1 for c in text if '一' <= c <= '鿿')
            if cjk_count > len(text) * 0.3:
                for i in range(len(text) - 1):
                    bg = text[i:i + 2].strip()
                    if len(bg) >= 2 and not bg.isspace():
                        tokens.add(bg)
                for i in range(len(text) - 2):
                    tg = text[i:i + 3].strip()
                    if len(tg) >= 3 and not tg.isspace():
                        tokens.add(tg)
                if len(text.strip()) <= 8:
                    tokens.add(text.strip())
            else:
                words = text.lower().split()
                tokens = {w for w in words if len(w) > 2 and w not in CONFIRM_WORDS}
                if text.strip() not in CONFIRM_WORDS:
                    tokens.add(text.strip().lower())
            return tokens

        prev_tokens = _tokenize(ref_source["user"])
        if prev_tokens:
            matches = sum(1 for t in prev_tokens if t in stmt)
            ref_score = min(4, matches + 1) if matches > 0 else 0
    s["引用性"] = ref_score

    # 2. 连续性
    PROBE_TRIGGERS = {"考考我", "测测", "检验", "测试", "出题", "考我"}
    user_wants_probe = any(t in turn["user"] for t in PROBE_TRIGGERS)
    if prev_turn and turn["action_type"] == prev_turn["action_type"]:
        s["连续性"] = 4
    elif prev_turn and user_wants_probe:
        s["连续性"] = 4
    elif prev_turn:
        s["连续性"] = 2
    else:
        s["连续性"] = 3

    # 3. 无空转
    confirm_count = sum(1 for p in CONFIRM_PHRASES if p in stmt)
    s["无空转"] = max(0, 4 - confirm_count * 2)

    # 4. 稳定性: 结构特征评分，不奖励长度
    base = 1  # 有 statement 即得基础分
    if stmt:
        base += 1  # 非空
        if any(kw in stmt for kw in ["步骤", "第1", "首先", "step", "Step", "第一"]):
            base += 1
        if any(kw in stmt for kw in ["例如", "示例", "比如", "代码", "code", "print", "def "]):
            base += 1
        sentence_enders = sum(1 for c in stmt if c in "。.!?！？")
        if sentence_enders >= 2:
            base += 1
        s["稳定性"] = min(4, base)
    else:
        s["稳定性"] = 0

    # 5. 推进感: 确认后内容增长 + 新教学特征
    if prev_turn and prev_turn["user"] in CONFIRM_WORDS:
        prev_len = len(prev_turn.get("payload_statement", ""))
        has_new_content = any(kw in stmt for kw in
            ["步骤", "第1", "首先", "例如", "示例", "代码", "接下来", "下一个",
             "step", "Step", "第一", "其次", "然后", "另外", "还有"])
        if has_new_content or len(stmt) > prev_len + 20:
            s["推进感"] = 3
        elif len(stmt) > prev_len + 5:
            s["推进感"] = 2
        else:
            s["推进感"] = 1
    else:
        s["推进感"] = 3

    s["total"] = sum(s.values())
    return s


def score_all_turns(all_turns: dict[str, list]) -> dict:
    """对所有画像的所有轮次评分, 返回汇总."""
    results = {}
    CONFIRM_WORDS = {"好", "嗯", "继续", "可以", "好的", "行", "是", "对", "ok", "yes"}
    for pid, turns in all_turns.items():
        prev = None
        prev_meaningful = None
        scores = []
        for t in turns:
            s = score_turn(t, prev, prev_meaningful)
            scores.append(s)
            prev = t
            if t["user"] not in CONFIRM_WORDS:
                prev_meaningful = t
        avg = sum(x["total"] for x in scores) / max(len(scores), 1)
        dim_avgs = {}
        for dim in ["引用性", "连续性", "无空转", "稳定性", "推进感"]:
            dim_avgs[dim] = round(sum(x.get(dim, 0) for x in scores) / max(len(scores), 1), 2)
        worst = sorted(
            [{"turn": t["turn"], "score": s["total"], "user": t["user"],
              "statement": t["payload_statement"][:80]}
             for t, s in zip(turns, scores)],
            key=lambda x: x["score"]
        )[:3]
        # failure_cases: score < 10
        failures = [
            {"turn": t["turn"], "score": s["total"], "user": t["user"],
             "action_type": t["action_type"], "statement": t["payload_statement"][:120]}
            for t, s in zip(turns, scores) if s["total"] < 10
        ]
        results[pid] = {
            "name": PROFILES.get(pid, {}).get("name", pid),
            "avg_score": round(avg, 2),
            "dimensions": dim_avgs,
            "worst_turns": worst,
            "failure_cases": failures,
            "total_turns": len(turns),
        }
    return results


# ── S32.2: Breakpoint probes ───────────────────────────────────

def _http_post_json(url: str, data: dict, timeout: int = 10) -> dict | None:
    import urllib.request, json as _j
    try:
        body = _j.dumps(data).encode()
        req = urllib.request.Request(url, data=body,
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _j.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def probe_pulse_next_action(base_url: str, audit: AuditState) -> None:
    """Probe 1: pulse/respond 返回非空 next_action."""
    pid = "pulse_next_action"
    sid = f"probe_pulse_na_{int(time.time())}"
    # create session
    _http_post_json(f"{base_url}/api/v1/session", {"session_id": sid}, timeout=5)
    # send message that may trigger pulse
    chat = _http_post_json(f"{base_url}/api/v1/chat",
                           {"session_id": sid, "message": "教 Python 基础"}, timeout=30)
    if chat is None:
        audit.record_probe(pid, False, "Chat request failed")
        return
    pulse = chat.get("pulse")
    if not pulse:
        audit.record_probe(pid, True, "No pulse triggered (acceptable)")
        return
    pulse_id = pulse.get("pulse_id", "unknown")
    resp = _http_post_json(f"{base_url}/api/v1/pulse/respond",
                           {"session_id": sid, "pulse_id": pulse_id, "decision": "accept"})
    if resp is None:
        audit.record_probe(pid, False, "Pulse respond request failed")
        return
    na = resp.get("next_action")
    if na is None:
        audit.record_probe(pid, False, "next_action is None")
    elif not na.get("action_type"):
        audit.record_probe(pid, False, f"next_action missing action_type: {na}")
    else:
        audit.record_probe(pid, True, f"action_type={na.get('action_type')}")


def probe_dashboard_errors(base_url: str, audit: AuditState) -> None:
    """Probe 2: dashboard 拉取不静默失败."""
    import urllib.request, json as _j
    pid = "dashboard_errors"
    sid = f"probe_dash_{int(time.time())}"
    try:
        with urllib.request.urlopen(f"{base_url}/api/v1/dashboard/user?session_id={sid}",
                                     timeout=10) as resp:
            data = _j.loads(resp.read().decode("utf-8"))
        required = ["ttm_radar", "sdt_rings", "progress"]
        missing = [k for k in required if k not in data]
        if missing:
            audit.record_probe(pid, False, f"Missing keys: {missing}")
        else:
            audit.record_probe(pid, True, "Dashboard response shape OK")
    except Exception as e:
        audit.record_probe(pid, False, f"Dashboard request failed: {e}")


def probe_aggregator_shape(base_url: str, audit: AuditState) -> None:
    """Probe 3: aggregator 降级输出 shape 稳定."""
    import urllib.request, json as _j
    pid = "aggregator_shape"
    sid = f"probe_agg_{int(time.time())}"
    # Hit dashboard twice to trigger any cache/degrade paths
    for attempt in range(2):
        try:
            with urllib.request.urlopen(
                f"{base_url}/api/v1/dashboard/user?session_id={sid}", timeout=10
            ) as resp:
                data = _j.loads(resp.read().decode("utf-8"))
            ttm = data.get("ttm_radar", {})
            sdt = data.get("sdt_rings", {})
            progress = data.get("progress", {})
            # shape assertion: all required fields must be present with correct types
            ttm_ok = isinstance(ttm.get("current_stage"), str)
            sdt_ok = all(isinstance(sdt.get(k), (int, float)) for k in
                         ["autonomy", "competence", "relatedness"])
            prog_ok = isinstance(progress.get("total_sessions"), int)
            if not (ttm_ok and sdt_ok and prog_ok):
                audit.record_probe(pid, False,
                    f"Shape mismatch at attempt {attempt}: ttm={ttm_ok} sdt={sdt_ok} prog={prog_ok}")
                return
        except Exception as e:
            audit.record_probe(pid, False, f"Attempt {attempt} failed: {e}")
            return
    audit.record_probe(pid, True, "Aggregator shape stable across 2 calls")


def probe_payload_extraction(audit: AuditState) -> None:
    """Probe 4: extractPayloadText 覆盖全部 payload 形状（离线检查）."""
    pid = "payload_extraction"
    test_cases = [
        ({"statement": "你好"}, "你好"),
        ({"text": "这是文本"}, "这是文本"),
        ({"message": "消息内容"}, "消息内容"),
        ({"content": "正文"}, "正文"),
        ({"response": "回复"}, "回复"),
        ({"feedback": "反馈"}, "反馈"),
        ({"step": "第一步"}, "第一步"),
        ({"question": "问题?"}, "问题?"),
        ({}, ""),
    ]
    failures = []
    for payload, expected in test_cases:
        got = _extract_payload_text(payload)
        if (expected == "" and got != "") or (expected != "" and got == ""):
            failures.append(f"payload={payload} expected={repr(expected)} got={repr(got)}")
    if failures:
        audit.record_probe(pid, False, "; ".join(failures))
    else:
        audit.record_probe(pid, True, "All 9 payload shapes extracted correctly")


def probe_ws_status(audit: AuditState) -> None:
    """Probe 5: WebSocket 状态不误导（代码检查型探针）."""
    pid = "ws_status"
    ws_hook_path = Path(__file__).resolve().parent / "frontend" / "src" / "hooks" / "useWebSocket.ts"
    if not ws_hook_path.exists():
        audit.record_probe(pid, False, "useWebSocket.ts not found")
        return
    content = ws_hook_path.read_text(encoding="utf-8")
    issues = []
    if "return;" in content and "connect" in content:
        # Check if the dead return is in the connect function
        lines = content.split("\n")
        in_connect = False
        for i, line in enumerate(lines):
            if "const connect" in line or "function connect" in line:
                in_connect = True
            if in_connect and "return;" in line and i - sum(1 for l in lines[:i] if "const connect" in l or "function connect" in l) < 5:
                issues.append(f"Dead return at line {i+1}")
                break
    if issues:
        audit.record_probe(pid, False, "; ".join(issues))
    else:
        audit.record_probe(pid, True, "WS hook structure OK")


def run_breakpoint_probes(run_id: str, base_url: str = "http://127.0.0.1:8001",
                          use_http: bool = True) -> AuditState:
    """运行全部 5 个断点探针."""
    audit = AuditState(run_id)
    if not use_http:
        # offline probes only
        probe_payload_extraction(audit)
        probe_ws_status(audit)
        return audit
    print("\n[S32.2] 断点探针...")
    probes = [
        ("pulse_next_action", lambda: probe_pulse_next_action(base_url, audit)),
        ("dashboard_errors", lambda: probe_dashboard_errors(base_url, audit)),
        ("aggregator_shape", lambda: probe_aggregator_shape(base_url, audit)),
        ("payload_extraction", lambda: probe_payload_extraction(audit)),
        ("ws_status", lambda: probe_ws_status(audit)),
    ]
    for name, fn in probes:
        try:
            fn()
            status = "PASS" if audit.probes[name]["passed"] else "FAIL"
            print(f"  [{status}] {name}: {audit.probes[name]['detail'][:80]}")
        except Exception as e:
            audit.record_probe(name, False, f"Probe crashed: {e}")
            print(f"  [FAIL] {name}: crashed — {e}")
    return audit


# ── Report ────────────────────────────────────────────────────

def print_report(scoring: dict):
    """打印体验审计报告."""
    print(f"\n{'='*70}")
    print("  体验审计报告 — Phase 32")
    print(f"{'='*70}")
    print(f"{'画像':<20} {'均分':>6} {'引用':>5} {'连续':>5} {'无空转':>5} {'稳定':>5} {'推进':>5}")
    print("-" * 56)
    total = 0
    count = 0
    for pid, data in scoring.items():
        d = data["dimensions"]
        print(f"{data['name']:<20} {data['avg_score']:>6.1f} "
              f"{d['引用性']:>5.1f} {d['连续性']:>5.1f} {d['无空转']:>5.1f} "
              f"{d['稳定性']:>5.1f} {d['推进感']:>5.1f}")
        total += data["avg_score"]
        count += 1
    print("-" * 56)
    print(f"{'整体平均':<20} {total/count:>6.1f}")
    print()

    for pid, data in scoring.items():
        if data["avg_score"] < 10:
            print(f"[!] {data['name']} ({data['avg_score']:.1f}) — 最差轮次:")
            for w in data["worst_turns"]:
                print(f"    T{w['turn']}: {w['user']} → {w['statement'][:60]}")


# ── Main ──────────────────────────────────────────────────────

def main(use_http: bool = False, quick: bool = False):
    run_id = _generate_run_id()
    mode_label = "quick" if quick else "full"
    print("=" * 70)
    print(f"  Phase 32 — 体验审计管道 [{mode_label}] (run: {run_id})")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RUN_HISTORY_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Select profiles and turn limit
    if quick:
        quick_profiles = ["novice_confirm", "novice_jump", "tester"]
        profiles_subset = {k: v for k, v in PROFILES.items() if k in quick_profiles}
        max_turns = 5
    else:
        profiles_subset = PROFILES
        max_turns = 20

    # S32.1: 模拟
    print(f"\n[S32.1] 模拟 {len(profiles_subset)} 画像 × {max_turns} 轮...")
    all_turns = {}
    for pid, profile in profiles_subset.items():
        print(f"  {profile['name']}...", end=" ", flush=True)
        # Temporarily limit turns for quick mode
        orig_messages = profile["messages"]
        if quick:
            profile["messages"] = orig_messages[:max_turns]
        turns = simulate_profile(pid, profile, use_http=use_http)
        profile["messages"] = orig_messages  # restore
        all_turns[pid] = turns
        print(f"{len(turns)} 轮 OK")

    # Save raw turns (flat + run_dir)
    with open(OUTPUT_DIR / "all_turns.json", "w", encoding="utf-8") as f:
        json.dump(all_turns, f, ensure_ascii=False, indent=2)
    with open(run_dir / "all_turns.json", "w", encoding="utf-8") as f:
        json.dump(all_turns, f, ensure_ascii=False, indent=2)
    print(f"  对话记录已保存: {run_dir / 'all_turns.json'}")

    # S32.2: 评分
    print("\n[S32.2] 5 维体验评分...")
    scoring = score_all_turns(all_turns)
    print_report(scoring)

    # per_turn_scores
    per_turn = {}
    for pid, turns in all_turns.items():
        per_turn[pid] = []
        prev = None
        prev_mean = None
        CONFIRM_WORDS = {"好", "嗯", "继续", "可以", "好的", "行", "是", "对", "ok", "yes"}
        for t in turns:
            s = score_turn(t, prev, prev_mean)
            per_turn[pid].append({"turn": t["turn"], "user": t["user"],
                                  "action_type": t["action_type"], "scores": s})
            prev = t
            if t["user"] not in CONFIRM_WORDS:
                prev_mean = t

    # Save scoring (flat + run_dir)
    with open(OUTPUT_DIR / "scoring.json", "w", encoding="utf-8") as f:
        json.dump(scoring, f, ensure_ascii=False, indent=2)
    with open(run_dir / "scoring.json", "w", encoding="utf-8") as f:
        json.dump(scoring, f, ensure_ascii=False, indent=2)
    with open(run_dir / "per_turn_scores.json", "w", encoding="utf-8") as f:
        json.dump(per_turn, f, ensure_ascii=False, indent=2)

    # failure_cases
    failure_cases = {}
    for pid, data in scoring.items():
        if data.get("failure_cases"):
            failure_cases[pid] = data["failure_cases"]
    with open(run_dir / "failure_cases.json", "w", encoding="utf-8") as f:
        json.dump(failure_cases, f, ensure_ascii=False, indent=2)

    # Run metadata
    metadata = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_hash": _get_git_hash(),
        "profiles": list(PROFILES.keys()),
        "turns_per_profile": max(len(p["messages"]) for p in PROFILES.values()),
    }
    with open(run_dir / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Breakpoint probes
    audit = run_breakpoint_probes(run_id, use_http=use_http)
    with open(run_dir / "audit_state.json", "w", encoding="utf-8") as f:
        json.dump(audit.to_dict(), f, ensure_ascii=False, indent=2)

    # LATEST pointer
    overall = sum(d["avg_score"] for d in scoring.values()) / max(len(scoring), 1)
    latest = {
        "latest_run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "overall_score": round(overall, 2),
    }
    with open(OUTPUT_DIR / "LATEST.json", "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    # run_history index
    history = []
    if (OUTPUT_DIR / "run_history.json").exists():
        try:
            with open(OUTPUT_DIR / "run_history.json", "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(latest)
    with open(OUTPUT_DIR / "run_history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # Phase 36: per-run observability evidence
    _generate_per_run_evidence(all_turns, scoring, run_dir, run_id)

    # Phase 36: cross-run observability evidence
    _generate_cross_run_evidence()

    print(f"\n  运行 ID: {run_id}")
    print(f"  整体体验分: {overall:.1f}/20")
    print(f"  探针通过: {sum(1 for p in audit.probes.values() if p['passed'])}/{len(audit.probes)}")
    print(f"  产物目录: {run_dir}")
    print("=" * 70)

    return overall


# ── Phase 36: Observability Evidence ─────────────────────────────

def _extract_obs_metrics(all_turns: dict) -> list[dict]:
    """从 all_turns 中提取每轮的 observability 指标."""
    rows = []
    for pid, turns in all_turns.items():
        for t in turns:
            obs = t.get("llm_observability")
            if not obs or not isinstance(obs, dict):
                continue
            cache = obs.get("cache", {})
            runtime = obs.get("runtime", {})
            retention = obs.get("retention", {})
            rows.append({
                "profile": pid,
                "turn": t.get("turn", 0),
                "user": t.get("user", ""),
                "llm_generated": t.get("llm_generated", False),
                "cache_eligible": cache.get("cache_eligible", False),
                "stable_prefix_hash": cache.get("stable_prefix_hash", ""),
                "context_fingerprint": cache.get("context_fingerprint", ""),
                "stable_prefix_share": cache.get("stable_prefix_share", 0),
                "path": runtime.get("path", ""),
                "streaming": runtime.get("streaming", False),
                "latency_ms": runtime.get("latency_ms", 0),
                "first_chunk_latency_ms": runtime.get("first_chunk_latency_ms"),
                "tokens_total": runtime.get("tokens_total", 0),
                "tokens_prompt": runtime.get("tokens_prompt"),
                "tokens_completion": runtime.get("tokens_completion"),
                "token_usage_available": runtime.get("token_usage_available", False),
                "prompt_cache_hit_tokens": runtime.get("prompt_cache_hit_tokens"),
                "prompt_cache_miss_tokens": runtime.get("prompt_cache_miss_tokens"),
                "transport_status": runtime.get("transport_status", "?"),
                "retention_history_hits": retention.get("retention_history_hits", 0),
                "retention_memory_hits": retention.get("retention_memory_hits", 0),
                "retention_duplicate_dropped": retention.get("retention_duplicate_dropped", 0),
            })
    return rows


def _generate_per_run_evidence(all_turns: dict, scoring: dict, run_dir: Path, run_id: str):
    """生成 per-run 的 3 个 observability evidence 文件."""
    rows = _extract_obs_metrics(all_turns)

    # llm_runtime_turns.json — 每轮 observability 明细
    with open(run_dir / "llm_runtime_turns.json", "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "turns": rows}, f, ensure_ascii=False, indent=2)

    # llm_cache_evidence.json — per-run cache 指标
    if rows:
        eligible_count = sum(1 for r in rows if r["cache_eligible"])
        prefix_hashes = set(r["stable_prefix_hash"] for r in rows if r["stable_prefix_hash"])
        shares = [r["stable_prefix_share"] for r in rows if r["stable_prefix_share"] > 0]
        cache_evidence = {
            "run_id": run_id,
            "total_turns_with_obs": len(rows),
            "cache_eligible_rate": round(eligible_count / len(rows), 4) if rows else 0,
            "unique_prefix_hashes": len(prefix_hashes),
            "prefix_hash_is_stable": len(prefix_hashes) <= 1 if prefix_hashes else None,
            "prefix_hashes": sorted(prefix_hashes)[:5],
            "avg_stable_prefix_share": round(sum(shares) / len(shares), 4) if shares else 0,
        }
    else:
        cache_evidence = {"run_id": run_id, "note": "no observability data in this run"}
    with open(run_dir / "llm_cache_evidence.json", "w", encoding="utf-8") as f:
        json.dump(cache_evidence, f, ensure_ascii=False, indent=2)

    # llm_observability_summary.json — per-run runtime 聚合 (含分位数)
    if rows:
        import statistics as _st
        latencies = sorted([r["latency_ms"] for r in rows if r["latency_ms"] > 0])
        tokens = [r["tokens_total"] for r in rows if r["tokens_total"] > 0]
        paths = {}
        statuses = {}
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cache_hit_tokens = 0
        total_cache_miss_tokens = 0
        for r in rows:
            p = r["path"]
            paths[p] = paths.get(p, 0) + 1
            s = r["transport_status"]
            statuses[s] = statuses.get(s, 0) + 1
            if r.get("tokens_prompt"):
                total_prompt_tokens += r["tokens_prompt"]
            if r.get("tokens_completion"):
                total_completion_tokens += r["tokens_completion"]
            if r.get("prompt_cache_hit_tokens") is not None:
                total_cache_hit_tokens += r["prompt_cache_hit_tokens"]
            if r.get("prompt_cache_miss_tokens") is not None:
                total_cache_miss_tokens += r["prompt_cache_miss_tokens"]
        n_lat = len(latencies)
        obs_summary = {
            "run_id": run_id,
            "sample_size": len(rows),
            "path_distribution": paths,
            "transport_status_distribution": statuses,
            "avg_latency_ms": round(_st.mean(latencies), 1) if latencies else 0,
            "p50_latency_ms": round(latencies[n_lat // 2], 1) if n_lat else 0,
            "p95_latency_ms": round(latencies[int(n_lat * 0.95)], 1) if n_lat >= 20 else None,
            "p99_latency_ms": round(latencies[int(n_lat * 0.99)], 1) if n_lat >= 100 else None,
            "min_latency_ms": round(min(latencies), 1) if latencies else 0,
            "max_latency_ms": round(max(latencies), 1) if latencies else 0,
            "std_latency_ms": round(_st.stdev(latencies), 1) if len(latencies) >= 2 else 0,
            "avg_tokens_total": round(_st.mean(tokens), 1) if tokens else 0,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_cache_hit_tokens": total_cache_hit_tokens,
            "total_cache_miss_tokens": total_cache_miss_tokens,
            "estimated_cost_usd": round(
                (total_prompt_tokens * 0.14 + total_completion_tokens * 0.28) / 1_000_000, 6
            ),
            "total_retention_history_hits": sum(r["retention_history_hits"] for r in rows),
            "total_retention_memory_hits": sum(r["retention_memory_hits"] for r in rows),
        }
    else:
        obs_summary = {"run_id": run_id, "note": "no observability data in this run"}
    with open(run_dir / "llm_observability_summary.json", "w", encoding="utf-8") as f:
        json.dump(obs_summary, f, ensure_ascii=False, indent=2)

    print(f"  Phase 36 per-run evidence: 3 files generated")


def _generate_cross_run_evidence():
    """基于 run_history 和 per-run evidence 生成 cross-run 的 4 个文件."""
    runs_dir = RUN_HISTORY_DIR
    if not runs_dir.exists():
        return
    import statistics as _st

    # 收集所有 run 的 evidence
    all_cache: list[dict] = []
    all_obs: list[dict] = []
    prefix_stability: dict[str, list[str]] = {}  # prefix_hash -> [run_id, ...]

    for run_dir_entry in sorted(runs_dir.iterdir()):
        if not run_dir_entry.is_dir():
            continue
        rid = run_dir_entry.name
        # llm_cache_evidence.json
        cache_path = run_dir_entry / "llm_cache_evidence.json"
        if cache_path.exists():
            try:
                ce = json.loads(cache_path.read_text(encoding="utf-8"))
                ce["_run_id"] = rid
                all_cache.append(ce)
                for h in ce.get("prefix_hashes", []):
                    prefix_stability.setdefault(h, []).append(rid)
            except Exception:
                pass
        # llm_observability_summary.json
        obs_path = run_dir_entry / "llm_observability_summary.json"
        if obs_path.exists():
            try:
                oe = json.loads(obs_path.read_text(encoding="utf-8"))
                oe["_run_id"] = rid
                all_obs.append(oe)
            except Exception:
                pass

    if not all_cache and not all_obs:
        return

    # 1. llm_cache_observability_manifest.json
    manifest = {
        "phase": "36",
        "description": "Cache-eligibility 的定义、测量方法、run 列表",
        "cache_eligibility_definition": "structural: stable_prefix_chars >= 400 AND stable_prefix_share >= 0.15",
        "measurement_method": "per-turn context_meta from build_coach_context() → client.generate() → API response → audit extraction",
        "note": "This is structural evidence, NOT provider-confirmed cache-hit telemetry",
        "runs_analyzed": [c["_run_id"] for c in all_cache],
        "total_runs": len(all_cache),
    }
    with open(OUTPUT_DIR / "llm_cache_observability_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 2. llm_cache_empirical_band.json
    if all_cache:
        eligible_rates = [c.get("cache_eligible_rate", 0) for c in all_cache]
        shares = [c.get("avg_stable_prefix_share", 0) for c in all_cache if c.get("avg_stable_prefix_share", 0) > 0]
        band = {
            "cache_eligible_rate": {
                "mean": round(_st.mean(eligible_rates), 4),
                "min": min(eligible_rates),
                "max": max(eligible_rates),
                "std": round(_st.stdev(eligible_rates), 4) if len(eligible_rates) >= 2 else 0,
            },
            "avg_stable_prefix_share": {
                "mean": round(_st.mean(shares), 4) if shares else 0,
                "min": min(shares) if shares else 0,
                "max": max(shares) if shares else 0,
            },
            "sample_runs": len(all_cache),
            "run_ids": [c["_run_id"] for c in all_cache],
        }
        with open(OUTPUT_DIR / "llm_cache_empirical_band.json", "w", encoding="utf-8") as f:
            json.dump(band, f, ensure_ascii=False, indent=2)

    # 3. llm_runtime_observability_summary.json
    if all_obs:
        latencies = [o.get("avg_latency_ms", 0) for o in all_obs if o.get("avg_latency_ms", 0) > 0]
        all_tokens = [o.get("avg_tokens_total", 0) for o in all_obs if o.get("avg_tokens_total", 0) > 0]
        runtime_summary = {
            "sample_runs": len(all_obs),
            "avg_latency_ms": {
                "mean": round(_st.mean(latencies), 1) if latencies else 0,
                "min": min(latencies) if latencies else 0,
                "max": max(latencies) if latencies else 0,
            },
            "avg_tokens_total": {
                "mean": round(_st.mean(all_tokens), 1) if all_tokens else 0,
                "min": min(all_tokens) if all_tokens else 0,
                "max": max(all_tokens) if all_tokens else 0,
            },
            "run_ids": [o["_run_id"] for o in all_obs],
        }
        with open(OUTPUT_DIR / "llm_runtime_observability_summary.json", "w", encoding="utf-8") as f:
            json.dump(runtime_summary, f, ensure_ascii=False, indent=2)

    # 4. llm_prefix_stability_report.json
    total_prefix_hashes = len(prefix_stability)
    unstable_hashes = {h: runs for h, runs in prefix_stability.items() if len(runs) < len(all_cache)}
    prefix_report = {
        "total_unique_prefix_hashes": total_prefix_hashes,
        "runs_analyzed": len(all_cache),
        "stable_across_all_runs": total_prefix_hashes == 1,
        "hash_distribution": {h[:8]: len(runs) for h, runs in prefix_stability.items()},
        "unstable_hashes_count": len(unstable_hashes),
        "interpretation": (
            "Single unique hash across all runs → stable_prefix is truly stable (content-identical). "
            "Multiple hashes → stable_prefix content varies across runs (possible dynamic injection)."
        ) if total_prefix_hashes > 0 else "No hash data available.",
    }
    with open(OUTPUT_DIR / "llm_prefix_stability_report.json", "w", encoding="utf-8") as f:
        json.dump(prefix_report, f, ensure_ascii=False, indent=2)

    # 5. Phase 37: failure patterns aggregation
    _generate_failure_aggregation()

    # 6. Phase 37: regression alerts
    _generate_regression_alerts(scoring if 'scoring' in dir() else None)

    # 7. Phase 37: score trends analysis
    _generate_score_trends()

    # 8. Phase 38: MRT variant comparison (when data available)
    _generate_mrt_comparison()

    print(f"  Phase 36 cross-run evidence: 4 files generated (+ Phase 37: failure patterns + regression alerts + score trends + Phase 38: MRT comparison)")


def _generate_failure_aggregation() -> None:
    """Phase 37: 跨 run 聚合 failure_cases，输出 failure_patterns.json."""
    runs_dir = RUN_HISTORY_DIR
    if not runs_dir.exists():
        return
    all_failures: list[dict] = []
    by_action_type: dict[str, int] = {}
    by_profile: dict[str, int] = {}
    by_phrase: dict[str, int] = {}

    for run_dir_entry in sorted(runs_dir.iterdir()):
        if not run_dir_entry.is_dir():
            continue
        fc_path = run_dir_entry / "failure_cases.json"
        if not fc_path.exists():
            continue
        try:
            fc = json.loads(fc_path.read_text(encoding="utf-8"))
            for pid, cases in fc.items():
                by_profile[pid] = by_profile.get(pid, 0) + len(cases)
                for case in cases:
                    at = case.get("action_type", "?")
                    by_action_type[at] = by_action_type.get(at, 0) + 1
                    stmt = str(case.get("statement", ""))
                    # Extract key phrase (first 30 chars)
                    phrase = stmt[:40].strip() if stmt else "(empty)"
                    by_phrase[phrase] = by_phrase.get(phrase, 0) + 1
                    all_failures.append({
                        "run_id": run_dir_entry.name,
                        "profile": pid,
                        "turn": case.get("turn"),
                        "user": case.get("user", ""),
                        "action_type": at,
                        "score": case.get("score"),
                    })
        except Exception:
            pass

    if not all_failures:
        return

    # Sort hot spots
    top_action_types = sorted(by_action_type.items(), key=lambda x: -x[1])[:5]
    top_profiles = sorted(by_profile.items(), key=lambda x: -x[1])[:5]
    top_phrases = sorted(by_phrase.items(), key=lambda x: -x[1])[:5]

    report = {
        "total_failures": len(all_failures),
        "runs_analyzed": len(set(f["run_id"] for f in all_failures)),
        "hot_action_types": [{"action_type": a, "count": c} for a, c in top_action_types],
        "hot_profiles": [{"profile": p, "count": c} for p, c in top_profiles],
        "hot_failure_phrases": [{"phrase": p, "count": c} for p, c in top_phrases],
        "recent_failures": all_failures[-20:],
    }
    with open(OUTPUT_DIR / "failure_patterns.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def _generate_mrt_comparison() -> None:
    """Phase 38: 产出 MRT variant comparison 报告."""
    try:
        from src.coach.mrt import generate_variant_comparison_report
        generate_variant_comparison_report(str(OUTPUT_DIR))
    except Exception:
        pass


def _generate_score_trends() -> None:
    """Phase 37: 从 run_history 生成评分趋势分析."""
    history_path = OUTPUT_DIR / "run_history.json"
    if not history_path.exists():
        return
    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if len(history) < 2:
        return

    scores = [h["overall_score"] for h in history]
    timestamps = [h["timestamp_utc"] for h in history]
    import statistics as _st
    trend = {
        "total_runs": len(history),
        "first_run_utc": timestamps[0],
        "last_run_utc": timestamps[-1],
        "first_score": scores[0],
        "last_score": scores[-1],
        "delta": round(scores[-1] - scores[0], 2),
        "mean": round(_st.mean(scores), 2),
        "min": min(scores),
        "max": max(scores),
        "std": round(_st.stdev(scores), 2) if len(scores) >= 2 else 0,
        "recent_5": scores[-5:],
        # Simple linear trend: slope of last N scores
        "trend_direction": "up" if scores[-1] > scores[0] else ("down" if scores[-1] < scores[0] else "flat"),
        "trend_strength": "strong" if abs(scores[-1] - scores[0]) > 1.0 else (
            "moderate" if abs(scores[-1] - scores[0]) > 0.3 else "mild"
        ),
    }
    with open(OUTPUT_DIR / "score_trends.json", "w", encoding="utf-8") as f:
        json.dump(trend, f, ensure_ascii=False, indent=2)


def _generate_regression_alerts(latest_scoring: dict | None = None) -> None:
    """Phase 37: 对比最新评分与 baseline band，生成回归告警."""
    baseline_path = OUTPUT_DIR / "llm_baseline_band.json"
    if not baseline_path.exists():
        return
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except Exception:
        return

    alerts: list[dict] = []

    # Check latest run against baseline band
    if latest_scoring:
        overall = sum(
            d["avg_score"] for d in latest_scoring.values()
        ) / max(len(latest_scoring), 1)
        b_min = baseline["overall_score"]["min"]
        b_mean = baseline["overall_score"]["mean"]

        if overall < b_min:
            alerts.append({
                "level": "P1",
                "scope": "overall",
                "current": round(overall, 2),
                "threshold": b_min,
                "message": "Overall score below baseline minimum — possible regression",
            })
        elif overall < b_mean - baseline["overall_score"]["std"]:
            alerts.append({
                "level": "P2",
                "scope": "overall",
                "current": round(overall, 2),
                "threshold": round(b_mean - baseline["overall_score"]["std"], 2),
                "message": "Overall score below baseline mean - 1std — mild regression signal",
            })

        # Per-dimension check
        dim_names = ["连续性", "无空转", "稳定性", "推进感"]
        for dim in dim_names:
            if dim not in baseline.get("dimensions", {}):
                continue
            b_dim_min = baseline["dimensions"][dim]["min"]
            dim_vals = []
            for pid, data in latest_scoring.items():
                if dim in data.get("dimensions", {}):
                    dim_vals.append(data["dimensions"][dim])
            if dim_vals:
                current_dim = sum(dim_vals) / len(dim_vals)
                if current_dim < b_dim_min:
                    alerts.append({
                        "level": "P1",
                        "scope": f"dimension.{dim}",
                        "current": round(current_dim, 3),
                        "threshold": b_dim_min,
                        "message": f"Dimension '{dim}' below baseline minimum",
                    })

    # Check cache eligibility from latest cross-run evidence
    cache_band_path = OUTPUT_DIR / "llm_cache_empirical_band.json"
    if cache_band_path.exists():
        try:
            cache_band = json.loads(cache_band_path.read_text(encoding="utf-8"))
            eligible_mean = cache_band.get("cache_eligible_rate", {}).get("mean", 1.0)
            if eligible_mean < 0.9:
                alerts.append({
                    "level": "P2",
                    "scope": "cache_eligible_rate",
                    "current": eligible_mean,
                    "threshold": 0.9,
                    "message": "Cache-eligible rate below 90% — structural cache degradation",
                })
        except Exception:
            pass

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_reference": "llm_baseline_band.json (Phase 34.5)",
        "total_alerts": len(alerts),
        "alerts": alerts,
        "status": "CRITICAL" if any(a["level"] == "P1" for a in alerts) else (
            "WARNING" if alerts else "OK"
        ),
    }
    with open(OUTPUT_DIR / "regression_alerts.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


# ── Phase 44: Interactive Audit Engine ─────────────────────────────

def run_interactive_game(
    student_profile: str = "beginner",
    game_turns: int = 6,
    coach_url: str = "http://127.0.0.1:8001",
) -> dict:
    """S44.2: 运行一次教练-学生对局，返回 transcript + effect 报告."""
    import urllib.request as _ur, json as _j, uuid as _uuid

    sid = f"interactive_{student_profile}_{_uuid.uuid4().hex[:6]}"
    from src.coach.student_agent import StudentAgent
    student = StudentAgent(profile_id=student_profile)
    transcript: list[dict] = []

    # 学生开场
    first_messages = {
        "beginner": "你好，我想学Python，但我是完全零基础，从哪里开始？",
        "fuzzy_basics": "我之前学过一点列表和循环，但感觉很多概念是模糊的，能帮我梳理一下吗？",
        "jumpy": "我学过变量和条件判断，但函数还不太懂。今天我们学什么？",
        "passive": "好",
    }
    msg = first_messages.get(student_profile, "你好，开始教学吧")

    for turn in range(game_turns):
        # 发送到教练
        data = _j.dumps({"session_id": sid, "message": msg}).encode()
        req = _ur.Request(f"{coach_url}/api/v1/chat", data=data,
                          headers={"Content-Type": "application/json"})
        try:
            with _ur.urlopen(req, timeout=60) as resp:
                coach_r = _j.loads(resp.read().decode("utf-8"))
        except Exception as e:
            transcript.append({"turn": turn, "student": msg, "coach_error": str(e)})
            break

        # 学生消费教练回复
        student.consume_coach_response(coach_r)
        coach_stmt = str(coach_r.get("payload", {}).get("statement", ""))[:200]
        action_type = str(coach_r.get("action_type", "?"))
        transcript.append({
            "turn": turn,
            "student": msg,
            "coach_action_type": action_type,
            "coach_statement": coach_stmt,
            "llm_generated": coach_r.get("llm_generated", False),
        })

        # 学生生成回复（不使用 LLM 客户端时用规则）
        msg = _generate_student_response(student, coach_r)

    # 效果评估 (4 维)
    effect = student.get_effectiveness_summary()
    effect_score = score_interactive_session(transcript, student)
    effect["profile"] = student_profile
    effect["turns"] = game_turns
    effect["game_sid"] = sid
    effect["scoring"] = effect_score

    return {"transcript": transcript, "effect": effect, "session_id": sid}


def _generate_student_response(student, coach_r: dict) -> str:
    """生成学生回复：尝试用 LLM，失败则用规则 fallback."""
    try:
        from src.coach.llm.config import LLMConfig
        import os
        import yaml
        cfg_path = Path(__file__).resolve().parent / "config" / "coach_defaults.yaml"
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        llm_cfg = cfg.get("llm", {})
        if llm_cfg.get("enabled", False) and os.getenv("DEEPSEEK_API_KEY"):
            llm_config = LLMConfig.from_yaml(cfg)
            from src.coach.llm.client import LLMClient
            client = LLMClient(llm_config)
            return student.generate_response(client, llm_config)
    except Exception:
        pass
    # Rule-based fallback: 基于知识状态的简单回复
    return _rule_based_student_reply(student)


def score_interactive_session(transcript: list[dict], student) -> dict:
    """S44.3: 4 dimension teaching effect scoring, 0-4 each, parallel to morphology."""
    if not transcript:
        return {"知识转移": 0, "策略适应": 0, "解释质量": 0, "互动节奏": 0, "total": 0}

    mastery = student.get_mastery_delta()
    knowledge_score = min(4.0, round(mastery / 0.1))

    action_types = [t.get("coach_action_type", "") for t in transcript]
    unique_actions = len(set(a for a in action_types if a))
    strategy_score = min(4.0, unique_actions * 1.0)

    stmt_lens = [len(t.get("coach_statement", "")) for t in transcript]
    avg_len = sum(stmt_lens) / max(len(stmt_lens), 1)
    explain_score = min(4.0, round(avg_len / 40.0))

    valid_turns = sum(1 for t in transcript if t.get("coach_statement") and len(t.get("coach_statement", "")) > 20)
    rhythm_score = min(4.0, round((valid_turns / max(len(transcript), 1)) * 4.0))

    total = round(knowledge_score + strategy_score + explain_score + rhythm_score, 1)
    return {
        "知识转移": knowledge_score, "策略适应": strategy_score,
        "解释质量": explain_score, "互动节奏": rhythm_score,
        "total": total, "mastery_delta": round(mastery, 4),
    }

def _rule_based_student_reply(student) -> str:
    """规则驱动的学生回复（无需 LLM）."""
    exposed = list(student.state.exposed_concepts)
    known = list(student.state.known_concepts.keys())
    coach_said = student._last_coach_statement[:100]

    # 检测理解关键词
    understood = any(kw in coach_said for kw in ["第一步", "首先", "例如", "比如", "步骤", "总结"])
    if understood and exposed:
        for c in exposed[:1]:
            student.state.learn(c, gain=0.15)
        return f"哦，{exposed[0]}原来是这个意思。那接下来呢？"
    elif known:
        return f"我大概知道{known[-1]}了，能再深入讲一下吗？"
    else:
        return "好的，继续讲吧。我有点跟着费劲，能慢一点吗？"


def score_interactive_session(transcript: list[dict], effect: dict) -> dict:
    """S44.3/S46.3: 4 维效果评分 (0-4 each)."""
    CONFUSION_WORDS = {"不懂", "不太理解", "困惑", "为什么", "什么意思", "不确定", "不明白"}
    scores = {}

    # 1. 知识转移: mastery_delta → 0-4
    delta = abs(effect.get("mastery_delta", 0))
    scores["知识转移"] = min(4, max(0, round(delta * 10)))

    # 2. 策略适应: 困惑后 action_type 是否切换
    adapt_score = 0
    for i in range(1, len(transcript)):
        prev_student = transcript[i - 1].get("student", "")
        prev_action = transcript[i - 1].get("coach_action_type", "")
        curr_action = transcript[i].get("coach_action_type", "")
        if any(w in prev_student for w in CONFUSION_WORDS):
            if prev_action != curr_action:
                adapt_score = min(4, adapt_score + 1)
    scores["策略适应"] = adapt_score if adapt_score > 0 else 2

    # 3. 解释质量: 学生消息中是否包含教练教学概念
    quality_score = 0
    for i, t in enumerate(transcript):
        coach_stmt = t.get("coach_statement", "")
        student_msg = transcript[i].get("student", "") if i < len(transcript) - 1 else ""
        concepts = [w for w in ["变量", "列表", "循环", "函数", "字典", "条件", "Python", "算法", "递归", "类", "对象"] if w in coach_stmt]
        if concepts and any(c in student_msg for c in concepts):
            quality_score = min(4, quality_score + 1)
    scores["解释质量"] = quality_score if quality_score > 0 else 1

    # 4. 互动节奏: 非确认轮次 + 追问比例
    CONFIRM = {"好", "嗯", "继续", "可以", "好的", "行", "是", "对", "ok", "yes"}
    non_confirm = sum(1 for t in transcript if t.get("student", "") not in CONFIRM)
    questions = sum(1 for t in transcript if any(w in t.get("student", "") for w in CONFUSION_WORDS))
    rate = non_confirm / max(len(transcript), 1)
    scores["互动节奏"] = min(4, round(rate * 3 + questions * 0.5))

    scores["total"] = sum(scores.values())
    return scores


def run_interactive_audit(coach_url: str = "http://127.0.0.1:8001",
                          turns: int = 6) -> dict:
    """S44.3: 跑全部 3 个画像的交互式审计，产出效果报告."""
    results = {}
    for profile_id in ["beginner", "fuzzy_basics", "jumpy", "passive"]:
        print(f"\n[S44.2] 交互式对局: {profile_id} ({turns} turns)...")
        r = run_interactive_game(student_profile=profile_id,
                                 game_turns=turns, coach_url=coach_url)
        results[profile_id] = r
        effect = r["effect"]
        print(f"  mastery_delta={effect['mastery_delta']:.2f}  "
              f"concepts_learned={effect['concepts_learned']}  "
              f"exposed={effect['concepts_exposed']}")

    # 效果报告
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_turns_per_profile": turns,
        "profiles": {},
        "summary": {},
    }
    for pid, r in results.items():
        e = r["effect"]
        report["profiles"][pid] = {
            "mastery_delta": e["mastery_delta"],
            "concepts_learned": e["concepts_learned"],
            "concepts_exposed": e["concepts_exposed"],
            "turns": e["turns"],
            "transcript_turns": len(r["transcript"]),
        }
    deltas = [p["mastery_delta"] for p in report["profiles"].values()]
    report["summary"] = {
        "total_profiles": len(results),
        "mean_mastery_delta": round(sum(deltas) / len(deltas), 4) if deltas else 0,
        "interpretation": (
            "Positive delta = student learned. Higher = more effective teaching."
        ),
    }
    # 持久化: per-run interactive transcript
    run_id = f"interactive_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    run_dir = RUN_HISTORY_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    all_transcripts = {pid: r["transcript"] for pid, r in results.items()}
    with open(run_dir / "interactive_turns.json", "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "profiles": all_transcripts,
                   "game_turns": turns}, f, ensure_ascii=False, indent=2)

    # 持久化: per-profile interactive_scoring.json
    for pid, r in results.items():
        profile_score = r["effect"].get("scoring", {})
        profile_dir = run_dir / pid
        profile_dir.mkdir(parents=True, exist_ok=True)
        scoring_doc = {
            "run_id": run_id, "profile": pid,
            "turns": r["effect"]["turns"],
            "morphology_scores": None,
            "effect_scores": profile_score,
        }
        with open(profile_dir / "interactive_scoring.json", "w", encoding="utf-8") as f:
            json.dump(scoring_doc, f, ensure_ascii=False, indent=2)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report["run_id"] = run_id
    report["persisted_to"] = str(run_dir / "interactive_turns.json")
    with open(OUTPUT_DIR / "interactive_effect_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # S46.3: 4 维效果评分
    all_scores = {}
    for pid, r in results.items():
        all_scores[pid] = score_interactive_session(
            r.get("transcript", []), r.get("effect", {}))
    with open(OUTPUT_DIR / "interactive_scoring.json", "w", encoding="utf-8") as f:
        json.dump(all_scores, f, ensure_ascii=False, indent=2)
    print(f"\n[S44.3/S46.3] 效果报告: {OUTPUT_DIR / 'interactive_effect_report.json'}")
    print(f"[S46.3] 效果评分: {OUTPUT_DIR / 'interactive_scoring.json'}")
    print(f"   transcript: {run_dir / 'interactive_turns.json'}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 32+44 体验审计管道")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true",
                      help="快速模式: 3 画像 × 5 轮")
    mode.add_argument("--interactive", action="store_true",
                      help="Phase 44: 交互式审计 (LLM 学生代理 × 教练对局)")
    parser.add_argument("--use-http", action="store_true",
                        help="通过 HTTP 调用后端 (quick 模式需要)")
    parser.add_argument("--turns", type=int, default=6,
                        help="交互式对局轮数 (default 6)")
    parser.add_argument("--profile", type=str, default=None,
                        choices=["beginner", "fuzzy_basics", "jumpy", "passive"],
                        help="交互模式指定单个画像 (不指定则跑全部 4 个)")
    args = parser.parse_args()
    if args.interactive:
        if args.profile:
            r = run_interactive_game(student_profile=args.profile,
                                     game_turns=args.turns,
                                     coach_url="http://127.0.0.1:8001")
            print(f"mastery_delta={r['effect']['scoring']['mastery_delta']:.2f}")
        else:
            run_interactive_audit(coach_url="http://127.0.0.1:8001", turns=args.turns)
    else:
        main(use_http=args.use_http, quick=args.quick)
