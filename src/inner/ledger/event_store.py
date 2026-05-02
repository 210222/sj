"""Evidence Ledger — 事件存储与哈希链管理。"""

import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from .db import LedgerDB

GENESIS_PREV_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

# ── 并发写入配置 ─────────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_BACKOFF_MS = 50  # 指数退避基数: 50, 100, 200ms

P0_FIELDS = [
    "trace_id",
    "policy_version",
    "counterfactual_ranker_version",
    "counterfactual_feature_schema_version",
]

ALL_DATA_FIELDS = [
    "prev_hash",
    "chain_height",
    "trace_id",
    "policy_version",
    "counterfactual_ranker_version",
    "counterfactual_feature_schema_version",
    "objective_weights_snapshot",
    "tradeoff_reason",
    "protected_metric_guardrail_hit",
    "used_fact_ids",
    "ignored_fact_ids_with_reason",
    "degradation_path",
    "counterfactual_policy_rank",
    "assignment_features",
    "eligibility_rule_id",
    "meta_conflict_score",
    "track_disagreement_level",
    "meta_conflict_alert_flag",
    "event_time_utc",
    "window_id",
    "window_schema_version",
]


def _compute_event_hash(**fields) -> str:
    """计算事件的 SHA-256 哈希。

    将所有数据字段按键名排序后拼接，取 SHA-256。
    event_hash 和 id 不参与运算。
    """
    ordered = {}
    for key in sorted(ALL_DATA_FIELDS):
        val = fields.get(key, None)
        if val is None:
            ordered[key] = ""
        elif isinstance(val, (int, float)):
            ordered[key] = str(val)
        else:
            ordered[key] = str(val)
    payload = json.dumps(ordered, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class EventStore:
    """Append-only 事件存储，哈希链保证完整性。"""

    def __init__(self, database_path: str = "data/coherence.db"):
        self.db = LedgerDB(database_path)

    def initialize(self) -> None:
        """初始化数据库。"""
        self.db.initialize()

    def _latest_event(self, conn) -> dict | None:
        row = conn.execute(
            "SELECT * FROM events ORDER BY chain_height DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def _build_event_fields(
        self,
        prev_hash: str,
        chain_height: int,
        p0_values: dict,
        p1_values: dict,
        event_time_utc: str,
        window_id: str,
        window_schema_version: str,
    ) -> dict:
        """合并所有字段，供哈希计算和插入使用。"""
        fields = {
            "prev_hash": prev_hash,
            "chain_height": chain_height,
            "trace_id": p0_values["trace_id"],
            "policy_version": p0_values["policy_version"],
            "counterfactual_ranker_version": p0_values[
                "counterfactual_ranker_version"
            ],
            "counterfactual_feature_schema_version": p0_values[
                "counterfactual_feature_schema_version"
            ],
            "objective_weights_snapshot": p1_values.get(
                "objective_weights_snapshot"
            ),
            "tradeoff_reason": p1_values.get("tradeoff_reason"),
            "protected_metric_guardrail_hit": p1_values.get(
                "protected_metric_guardrail_hit", 0
            ),
            "used_fact_ids": p1_values.get("used_fact_ids"),
            "ignored_fact_ids_with_reason": p1_values.get(
                "ignored_fact_ids_with_reason"
            ),
            "degradation_path": p1_values.get("degradation_path"),
            "counterfactual_policy_rank": p1_values.get(
                "counterfactual_policy_rank"
            ),
            "assignment_features": p1_values.get("assignment_features"),
            "eligibility_rule_id": p1_values.get("eligibility_rule_id"),
            "meta_conflict_score": p1_values.get("meta_conflict_score"),
            "track_disagreement_level": p1_values.get(
                "track_disagreement_level"
            ),
            "meta_conflict_alert_flag": p1_values.get(
                "meta_conflict_alert_flag", 0
            ),
            "event_time_utc": event_time_utc,
            "window_id": window_id,
            "window_schema_version": window_schema_version,
        }
        return fields

    def create_genesis_event(
        self,
        trace_id: str | None = None,
        policy_version: str = "1.0.0",
        event_time_utc: str | None = None,
        window_id: str | None = None,
    ) -> dict:
        """创建创世事件（chain_height=0, prev_hash=全零）。

        使用 BEGIN IMMEDIATE 保证并发安全：即使多线程同时调用，
        只有一个能成功创建创世事件。
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())
        if event_time_utc is None:
            event_time_utc = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3] + "Z"
        if window_id is None:
            window_id = _default_window_id(event_time_utc)

        p0_values = {
            "trace_id": trace_id,
            "policy_version": policy_version,
            "counterfactual_ranker_version": "1.0.0",
            "counterfactual_feature_schema_version": "1.0.0",
        }

        fields = self._build_event_fields(
            prev_hash=GENESIS_PREV_HASH,
            chain_height=0,
            p0_values=p0_values,
            p1_values={},
            event_time_utc=event_time_utc,
            window_id=window_id,
            window_schema_version="1.0.0",
        )

        event_hash = _compute_event_hash(**fields)

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """INSERT INTO events (
                    event_hash, prev_hash, chain_height,
                    trace_id, policy_version,
                    counterfactual_ranker_version,
                    counterfactual_feature_schema_version,
                    objective_weights_snapshot, tradeoff_reason,
                    protected_metric_guardrail_hit, used_fact_ids,
                    ignored_fact_ids_with_reason, degradation_path,
                    counterfactual_policy_rank, assignment_features,
                    eligibility_rule_id, meta_conflict_score,
                    track_disagreement_level, meta_conflict_alert_flag,
                    event_time_utc, window_id, window_schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_hash,
                    fields["prev_hash"],
                    fields["chain_height"],
                    fields["trace_id"],
                    fields["policy_version"],
                    fields["counterfactual_ranker_version"],
                    fields["counterfactual_feature_schema_version"],
                    fields["objective_weights_snapshot"],
                    fields["tradeoff_reason"],
                    fields["protected_metric_guardrail_hit"],
                    fields["used_fact_ids"],
                    fields["ignored_fact_ids_with_reason"],
                    fields["degradation_path"],
                    fields["counterfactual_policy_rank"],
                    fields["assignment_features"],
                    fields["eligibility_rule_id"],
                    fields["meta_conflict_score"],
                    fields["track_disagreement_level"],
                    fields["meta_conflict_alert_flag"],
                    fields["event_time_utc"],
                    fields["window_id"],
                    fields["window_schema_version"],
                ),
            )
            conn.commit()
            return self.get_event_by_hash(event_hash)
        finally:
            conn.close()

    def append_event(
        self,
        p0_values: dict,
        p1_values: dict | None = None,
        event_time_utc: str | None = None,
        window_id: str | None = None,
    ) -> dict:
        """向链上追加一个新事件（并发安全）。

        使用 BEGIN IMMEDIATE 将"读最新 + 计算哈希 + INSERT"封装在
        同一写事务中。写冲突时自动重试（指数退避）。

        参数：
        - p0_values 必须包含全部 4 个 P0 字段
        - p1_values 为可选的部分 P1 字段

        Raises:
            RuntimeError: 重试耗尽仍无法写入。
        """
        if p1_values is None:
            p1_values = {}

        # 校验 P0 完整性
        for field in P0_FIELDS:
            if field not in p0_values or p0_values[field] is None:
                raise ValueError(f"P0 field '{field}' is required")

        if event_time_utc is None:
            event_time_utc = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3] + "Z"
        if window_id is None:
            window_id = _default_window_id(event_time_utc)

        # 快检：无创世事件是确定性错误，不应重试
        check_conn = self.db.get_connection()
        try:
            if self._latest_event(check_conn) is None:
                raise RuntimeError(
                    "No genesis event found. "
                    "Call create_genesis_event() first."
                )
        finally:
            check_conn.close()

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            conn = self.db.get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")

                # BEGIN IMMEDIATE 之后重新读取，保证读到最新
                latest = self._latest_event(conn)
                if latest is None:
                    raise RuntimeError(
                        "No genesis event found. "
                        "Call create_genesis_event() first."
                    )

                new_height = latest["chain_height"] + 1
                prev_hash = latest["event_hash"]

                fields = self._build_event_fields(
                    prev_hash=prev_hash,
                    chain_height=new_height,
                    p0_values=p0_values,
                    p1_values=p1_values,
                    event_time_utc=event_time_utc,
                    window_id=window_id,
                    window_schema_version="1.0.0",
                )

                event_hash = _compute_event_hash(**fields)

                conn.execute(
                    """INSERT INTO events (
                        event_hash, prev_hash, chain_height,
                        trace_id, policy_version,
                        counterfactual_ranker_version,
                        counterfactual_feature_schema_version,
                        objective_weights_snapshot, tradeoff_reason,
                        protected_metric_guardrail_hit, used_fact_ids,
                        ignored_fact_ids_with_reason, degradation_path,
                        counterfactual_policy_rank, assignment_features,
                        eligibility_rule_id, meta_conflict_score,
                        track_disagreement_level, meta_conflict_alert_flag,
                        event_time_utc, window_id, window_schema_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event_hash,
                        fields["prev_hash"],
                        fields["chain_height"],
                        fields["trace_id"],
                        fields["policy_version"],
                        fields["counterfactual_ranker_version"],
                        fields["counterfactual_feature_schema_version"],
                        fields["objective_weights_snapshot"],
                        fields["tradeoff_reason"],
                        fields["protected_metric_guardrail_hit"],
                        fields["used_fact_ids"],
                        fields["ignored_fact_ids_with_reason"],
                        fields["degradation_path"],
                        fields["counterfactual_policy_rank"],
                        fields["assignment_features"],
                        fields["eligibility_rule_id"],
                        fields["meta_conflict_score"],
                        fields["track_disagreement_level"],
                        fields["meta_conflict_alert_flag"],
                        fields["event_time_utc"],
                        fields["window_id"],
                        fields["window_schema_version"],
                    ),
                )
                conn.commit()
                return self.get_event_by_hash(event_hash)

            except sqlite3.IntegrityError as e:
                # UNIQUE 约束冲突（chain_height 或 event_hash 重复）
                # 可能在极端并发下 BEGIN IMMEDIATE 仍未阻止
                try:
                    conn.rollback()
                except Exception:
                    pass
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(
                        RETRY_BACKOFF_MS / 1000.0 * (2 ** attempt)
                    )

            except sqlite3.OperationalError as e:
                # database is locked
                try:
                    conn.rollback()
                except Exception:
                    pass
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(
                        RETRY_BACKOFF_MS / 1000.0 * (2 ** attempt)
                    )

            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        raise RuntimeError(
            f"append_event failed after {MAX_RETRIES} retries: {last_error}"
        )

    def get_event_by_hash(self, event_hash: str) -> dict | None:
        """按哈希查找事件。"""
        conn = self.db.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM events WHERE event_hash = ?", (event_hash,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_latest_event(self) -> dict | None:
        """获取链上最新事件（最高 chain_height）。"""
        conn = self.db.get_connection()
        try:
            return self._latest_event(conn)
        finally:
            conn.close()

    def get_events_in_window(self, window_id: str) -> list[dict]:
        """获取指定窗口内的所有事件。"""
        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM events WHERE window_id = ? ORDER BY chain_height",
                (window_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def verify_chain_integrity(self) -> dict:
        """验证全链哈希完整性。

        返回 {"valid": bool, "failures": [{"height": n, "reason": str}]}
        """
        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY chain_height"
            ).fetchall()

            if not rows:
                return {
                    "valid": False,
                    "failures": [{"height": -1, "reason": "missing_genesis: chain is empty"}],
                }

            failures = []
            for i, row in enumerate(rows):
                row_dict = dict(row)
                if row_dict["chain_height"] != i:
                    failures.append({
                        "height": row_dict["chain_height"],
                        "reason": f"Expected height {i}, got {row_dict['chain_height']}",
                    })

                if i > 0:
                    prev_row = dict(rows[i - 1])
                    if row_dict["prev_hash"] != prev_row["event_hash"]:
                        failures.append({
                            "height": row_dict["chain_height"],
                            "reason": "prev_hash does not match previous event_hash",
                        })

                # Recompute hash
                fields = {
                    "prev_hash": row_dict["prev_hash"],
                    "chain_height": row_dict["chain_height"],
                    "trace_id": row_dict["trace_id"],
                    "policy_version": row_dict["policy_version"],
                    "counterfactual_ranker_version": row_dict[
                        "counterfactual_ranker_version"
                    ],
                    "counterfactual_feature_schema_version": row_dict[
                        "counterfactual_feature_schema_version"
                    ],
                    "objective_weights_snapshot": row_dict.get(
                        "objective_weights_snapshot"
                    ),
                    "tradeoff_reason": row_dict.get("tradeoff_reason"),
                    "protected_metric_guardrail_hit": row_dict.get(
                        "protected_metric_guardrail_hit", 0
                    ),
                    "used_fact_ids": row_dict.get("used_fact_ids"),
                    "ignored_fact_ids_with_reason": row_dict.get(
                        "ignored_fact_ids_with_reason"
                    ),
                    "degradation_path": row_dict.get("degradation_path"),
                    "counterfactual_policy_rank": row_dict.get(
                        "counterfactual_policy_rank"
                    ),
                    "assignment_features": row_dict.get(
                        "assignment_features"
                    ),
                    "eligibility_rule_id": row_dict.get(
                        "eligibility_rule_id"
                    ),
                    "meta_conflict_score": row_dict.get(
                        "meta_conflict_score"
                    ),
                    "track_disagreement_level": row_dict.get(
                        "track_disagreement_level"
                    ),
                    "meta_conflict_alert_flag": row_dict.get(
                        "meta_conflict_alert_flag", 0
                    ),
                    "event_time_utc": row_dict["event_time_utc"],
                    "window_id": row_dict["window_id"],
                    "window_schema_version": row_dict[
                        "window_schema_version"
                    ],
                }
                computed_hash = _compute_event_hash(**fields)
                if computed_hash != row_dict["event_hash"]:
                    failures.append({
                        "height": row_dict["chain_height"],
                        "reason": f"Hash mismatch: stored={row_dict['event_hash'][:16]}..., computed={computed_hash[:16]}...",
                    })

            return {"valid": len(failures) == 0, "failures": failures}
        finally:
            conn.close()

    def get_chain_length(self) -> int:
        """返回当前链长度（事件总数）。"""
        conn = self.db.get_connection()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM events").fetchone()
            return row["cnt"]
        finally:
            conn.close()


def _default_window_id(event_time_utc: str) -> str:
    """根据事件时间生成默认的 30min window_id。

    委托到 contracts/clock.json 定义的统一 clock 模块入口。
    确保所有事件的 window_id 来源一致，避免口径漂移。
    """
    from src.inner.clock import get_window_30min
    return get_window_30min(event_time_utc)
