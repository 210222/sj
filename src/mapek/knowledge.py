"""MAPE-K Knowledge — 知识仓库：Facts CRUD + 策略历史 + 实验证据 + 置信度衰减。"""

import uuid
from datetime import datetime, timezone


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Knowledge:
    """MAPE-K 知识仓库：三个仓库 + 置信度衰减 + 生命周期管理。

    - facts: 结构化断言（内存镜像，schema 对齐 data.py facts 表）
    - strategy_history: MAPE-K Plan 输出历史
    - experiment_evidence: 实验证据（Phase 7 MRT 准备）
    """

    def __init__(self, confidence_decay_rate: float = 0.05,
                 archival_after_days: int = 30):
        self._decay_rate = confidence_decay_rate
        self._archival_days = archival_after_days
        self._facts: dict[str, dict] = {}
        self._strategy_history: list[dict] = []
        self._experiments: list[dict] = []

    # ── Facts 操作 ──────────────────────────────────────────────

    def add_fact(self, fact: dict) -> str:
        """添加事实。自动生成 fact_id 和时间戳。"""
        now = _now_utc()
        fid = fact.get("fact_id") or f"fact_{uuid.uuid4().hex[:12]}"

        entry = {
            "fact_id": fid,
            "claim": fact.get("claim", ""),
            "evidence_ids": fact.get("evidence_ids", "[]"),
            "confidence": fact.get("confidence", 0.5),
            "timestamp_utc": fact.get("timestamp_utc", now),
            "ttl_seconds": fact.get("ttl_seconds"),
            "context_scope": fact.get("context_scope"),
            "reversibility_flag": fact.get("reversibility_flag", 1),
            "source_tag": fact.get("source_tag", "hypothesis"),
            "lifecycle_status": "active",
            "created_at_utc": now,
            "updated_at_utc": now,
        }
        self._facts[fid] = entry
        return fid

    def get_fact(self, fact_id: str) -> dict | None:
        return self._facts.get(fact_id)

    def query_facts(self, query: dict) -> list[dict]:
        """按条件查询。支持 source_tag/context_scope/lifecycle_status/min_confidence。"""
        results = list(self._facts.values())
        if "source_tag" in query:
            results = [f for f in results
                       if f.get("source_tag") == query["source_tag"]]
        if "context_scope" in query:
            results = [f for f in results
                       if f.get("context_scope") == query["context_scope"]]
        if "lifecycle_status" in query:
            results = [f for f in results
                       if f.get("lifecycle_status") == query["lifecycle_status"]]
        if "min_confidence" in query:
            min_c = query["min_confidence"]
            results = [f for f in results if (f.get("confidence") or 0) >= min_c]
        return results

    def update_fact(self, fact_id: str, updates: dict) -> bool:
        """更新事实字段。"""
        if fact_id not in self._facts:
            return False
        now = _now_utc()
        for key in ("claim", "confidence", "evidence_ids",
                     "context_scope", "lifecycle_status"):
            if key in updates:
                self._facts[fact_id][key] = updates[key]
        self._facts[fact_id]["updated_at_utc"] = now
        return True

    # ── 策略历史 ────────────────────────────────────────────────

    def record_strategy(self, strategy: dict) -> None:
        entry = dict(strategy)
        entry["recorded_at"] = _now_utc()
        self._strategy_history.append(entry)

    def get_strategy_history(self, limit: int = 10) -> list[dict]:
        return self._strategy_history[-limit:]

    # ── 实验证据 (Phase 7 MRT 准备) ─────────────────────────────

    def record_experiment(self, experiment: dict) -> None:
        entry = dict(experiment)
        entry["recorded_at"] = _now_utc()
        self._experiments.append(entry)

    def get_experiments(self, variant_id: str | None = None) -> list[dict]:
        if variant_id:
            return [e for e in self._experiments
                    if e.get("variant_id") == variant_id]
        return list(self._experiments)

    # ── 置信度管理 ──────────────────────────────────────────────

    def decay_confidence(self) -> int:
        """对所有 active facts 执行置信度衰减。返回受影响数。"""
        count = 0
        for fact in self._facts.values():
            if fact.get("lifecycle_status") != "active":
                continue
            old_conf = fact.get("confidence", 0.5)
            fact["confidence"] = round(max(0.0, old_conf - self._decay_rate), 4)
            count += 1
        return count

    def archive_expired(self) -> int:
        """归档过期事实：TTL 到期 或 超过 archival_days 未更新。"""
        now = datetime.now(timezone.utc)
        count = 0
        for fact in list(self._facts.values()):
            if fact.get("lifecycle_status") != "active":
                continue

            ttl = fact.get("ttl_seconds")
            if ttl is not None:
                ts = fact.get("timestamp_utc", "")
                try:
                    created = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if (now - created).total_seconds() > ttl:
                        fact["lifecycle_status"] = "archived"
                        count += 1
                        continue
                except Exception:
                    pass

            updated_str = fact.get("updated_at_utc", "")
            try:
                updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                if (now - updated).days > self._archival_days:
                    fact["lifecycle_status"] = "archived"
                    count += 1
            except Exception:
                pass
        return count

    # ── 统计 ────────────────────────────────────────────────────

    def stats(self) -> dict:
        active = sum(1 for f in self._facts.values()
                      if f.get("lifecycle_status") == "active")
        archived = sum(1 for f in self._facts.values()
                        if f.get("lifecycle_status") == "archived")
        return {
            "total_facts": len(self._facts),
            "active_facts": active,
            "archived_facts": archived,
            "strategy_records": len(self._strategy_history),
            "experiment_records": len(self._experiments),
        }
