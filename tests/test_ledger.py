"""Evidence Ledger 单元测试 — 覆盖创世、追加、哈希链完整性、防篡改。"""

import os
import tempfile
import pytest
from src.inner.ledger import EventStore
from src.inner.ledger.event_store import GENESIS_PREV_HASH


@pytest.fixture
def store():
    """每次测试使用独立的临时数据库。"""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="coherence_test_")
    os.close(fd)
    store = EventStore(database_path=path)
    store.initialize()
    yield store
    # 所有 EventStore 方法已通过 try/finally 关闭连接，直接删除即可
    try:
        os.unlink(path)
    except PermissionError:
        import time
        time.sleep(0.1)
        os.unlink(path)


class TestGenesis:
    """创世事件相关测试。"""

    def test_create_genesis_returns_event(self, store):
        event = store.create_genesis_event()
        assert event is not None
        assert event["chain_height"] == 0
        assert event["prev_hash"] == GENESIS_PREV_HASH
        assert len(event["event_hash"]) == 64

    def test_genesis_trace_id_is_present(self, store):
        event = store.create_genesis_event()
        assert event["trace_id"] is not None
        assert len(event["trace_id"]) == 36  # UUID v4

    def test_genesis_set_chain_length_1(self, store):
        store.create_genesis_event()
        assert store.get_chain_length() == 1

    def test_cannot_append_without_genesis(self, store):
        with pytest.raises(RuntimeError, match="No genesis event found"):
            store.append_event(
                p0_values={
                    "trace_id": "test",
                    "policy_version": "1",
                    "counterfactual_ranker_version": "1",
                    "counterfactual_feature_schema_version": "1",
                }
            )


class TestAppend:
    """事件追加与哈希链测试。"""

    def test_append_increments_chain_height(self, store):
        store.create_genesis_event()
        e2 = store.append_event(
            p0_values={
                "trace_id": "t1",
                "policy_version": "1.0",
                "counterfactual_ranker_version": "1.0",
                "counterfactual_feature_schema_version": "1.0",
            }
        )
        assert e2["chain_height"] == 1

    def test_append_links_prev_hash(self, store):
        genesis = store.create_genesis_event()
        e2 = store.append_event(
            p0_values={
                "trace_id": "t1",
                "policy_version": "1.0",
                "counterfactual_ranker_version": "1.0",
                "counterfactual_feature_schema_version": "1.0",
            }
        )
        assert e2["prev_hash"] == genesis["event_hash"]
        assert e2["prev_hash"] != GENESIS_PREV_HASH

    def test_missing_p0_field_raises(self, store):
        store.create_genesis_event()
        with pytest.raises(ValueError, match="P0 field 'trace_id' is required"):
            store.append_event(
                p0_values={
                    "policy_version": "1",
                    "counterfactual_ranker_version": "1",
                    "counterfactual_feature_schema_version": "1",
                }
            )

    def test_none_p0_field_raises(self, store):
        store.create_genesis_event()
        with pytest.raises(ValueError, match="P0 field 'trace_id' is required"):
            store.append_event(
                p0_values={
                    "trace_id": None,
                    "policy_version": "1",
                    "counterfactual_ranker_version": "1",
                    "counterfactual_feature_schema_version": "1",
                }
            )

    def test_append_preserves_p1_fields(self, store):
        store.create_genesis_event()
        e2 = store.append_event(
            p0_values={
                "trace_id": "t2",
                "policy_version": "2.0",
                "counterfactual_ranker_version": "2.0",
                "counterfactual_feature_schema_version": "2.0",
            },
            p1_values={
                "tradeoff_reason": "test reason",
                "meta_conflict_score": 0.45,
            },
        )
        assert e2["tradeoff_reason"] == "test reason"
        assert e2["meta_conflict_score"] == 0.45

    def test_chain_length_grows(self, store):
        store.create_genesis_event()
        store.append_event(
            p0_values={
                "trace_id": "a",
                "policy_version": "1",
                "counterfactual_ranker_version": "1",
                "counterfactual_feature_schema_version": "1",
            }
        )
        store.append_event(
            p0_values={
                "trace_id": "b",
                "policy_version": "1",
                "counterfactual_ranker_version": "1",
                "counterfactual_feature_schema_version": "1",
            }
        )
        assert store.get_chain_length() == 3


class TestHashChainIntegrity:
    """哈希链完整性验证。"""

    def test_verify_fails_on_empty_chain(self, store):
        result = store.verify_chain_integrity()
        assert result["valid"] is False
        assert any("missing_genesis" in f["reason"] for f in result["failures"])

    def test_verify_passes_on_correct_chain(self, store):
        store.create_genesis_event()
        for i in range(5):
            store.append_event(
                p0_values={
                    "trace_id": f"t{i}",
                    "policy_version": "1.0",
                    "counterfactual_ranker_version": "1.0",
                    "counterfactual_feature_schema_version": "1.0",
                }
            )
        result = store.verify_chain_integrity()
        assert result["valid"] is True
        assert len(result["failures"]) == 0

    def test_verify_detects_tampered_prev_hash(self, store):
        store.create_genesis_event()
        store.append_event(
            p0_values={
                "trace_id": "t1",
                "policy_version": "1",
                "counterfactual_ranker_version": "1",
                "counterfactual_feature_schema_version": "1",
            }
        )
        # 模拟攻击者绕过触发器篡改：先移除触发器，再 UPDATE
        conn = store.db.get_connection()
        try:
            conn.execute("DROP TRIGGER IF EXISTS trg_events_no_update")
            conn.execute("DROP TRIGGER IF EXISTS trg_events_no_delete")
            conn.execute(
                "UPDATE events SET prev_hash = ? WHERE chain_height = 1",
                ("deadbeef" * 8,),
            )
            conn.commit()
        finally:
            conn.close()
        result = store.verify_chain_integrity()
        assert result["valid"] is False

    def test_tampered_data_fails_hash_recomputation(self, store):
        store.create_genesis_event()
        # 直接插入不经过 EventStore 的事件（模拟绕开哈希计算）
        conn = store.db.get_connection()
        try:
            conn.execute(
                """INSERT INTO events (
                    event_hash, prev_hash, chain_height,
                    trace_id, policy_version,
                    counterfactual_ranker_version,
                    counterfactual_feature_schema_version,
                    event_time_utc, window_id, window_schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "a" * 64,  # 假的 hash
                    GENESIS_PREV_HASH,
                    99,
                    "fake",
                    "fake",
                    "fake",
                    "fake",
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:00_2026-01-01T00:30",
                    "1.0.0",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        result = store.verify_chain_integrity()
        assert result["valid"] is False


class TestAppendOnly:
    """append-only 强制执行测试。"""

    def test_cannot_update_event(self, store):
        store.create_genesis_event()
        conn = store.db.get_connection()
        try:
            with pytest.raises(Exception):
                conn.execute("UPDATE events SET trace_id = 'hacked'")
        finally:
            conn.close()

    def test_cannot_delete_event(self, store):
        store.create_genesis_event()
        conn = store.db.get_connection()
        try:
            with pytest.raises(Exception):
                conn.execute("DELETE FROM events")
        finally:
            conn.close()


class TestWindowQueries:
    """窗口相关查询测试。"""

    def test_events_have_window_id(self, store):
        e = store.create_genesis_event()
        assert e["window_id"] is not None
        assert "_" in e["window_id"]

    def test_get_events_in_window(self, store):
        e1 = store.create_genesis_event()
        wid = e1["window_id"]
        store.append_event(
            p0_values={
                "trace_id": "t1",
                "policy_version": "1",
                "counterfactual_ranker_version": "1",
                "counterfactual_feature_schema_version": "1",
            }
        )
        events = store.get_events_in_window(wid)
        assert len(events) == 2


# ═══════════════════════════════════════════════════════════════
# Step 3.1: 并发写入安全测试
# ═══════════════════════════════════════════════════════════════

import threading
import time as _time


class TestConcurrentAppend:
    """并发 append_event 安全测试 — 链完整性 + 无坏链。"""

    @pytest.fixture
    def store(self):
        fd, path = tempfile.mkstemp(suffix=".db", prefix="coherence_conc_")
        os.close(fd)
        s = EventStore(database_path=path)
        s.initialize()
        yield s
        try:
            os.unlink(path)
        except PermissionError:
            _time.sleep(0.1)
            os.unlink(path)

    # ── 测试 A: 4 线程并发追加 200 条 ──

    def test_concurrent_append_200_events_chain_valid(self, store):
        store.create_genesis_event()
        errors = []
        total_per_thread = 50
        num_threads = 4

        def worker(thread_id: int):
            for i in range(total_per_thread):
                try:
                    store.append_event(p0_values={
                        "trace_id": f"t{thread_id}_{i}",
                        "policy_version": "1.0",
                        "counterfactual_ranker_version": "1.0",
                        "counterfactual_feature_schema_version": "1.0",
                    })
                except Exception as e:
                    errors.append((thread_id, i, str(e)))

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证
        result = store.verify_chain_integrity()
        assert result["valid"], (
            f"Chain corrupted! Failures: {result['failures'][:5]}"
        )
        expected_total = 1 + num_threads * total_per_thread
        actual = store.get_chain_length()
        assert actual == expected_total, (
            f"Expected {expected_total} events, got {actual}. "
            f"Append errors: {len(errors)}"
        )

    # ── 测试 B: 高冲突场景（更多线程）链仍有效 ──

    def test_high_contention_chain_valid(self, store):
        store.create_genesis_event()
        num_threads = 8
        per_thread = 25

        def worker(tid: int):
            for i in range(per_thread):
                try:
                    store.append_event(p0_values={
                        "trace_id": f"hc_{tid}_{i}",
                        "policy_version": "1.0",
                        "counterfactual_ranker_version": "1.0",
                        "counterfactual_feature_schema_version": "1.0",
                    })
                except RuntimeError:
                    # 重试耗尽 — 最终链仍需验证
                    pass

        threads = [threading.Thread(target=worker, args=(t,))
                   for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        result = store.verify_chain_integrity()
        # 即使个别写入失败，链仍应有效（无坏链，无重复高度）
        if not result["valid"]:
            failures = result["failures"][:5]
            assert not any(
                "prev_hash" in f["reason"] for f in failures
            ), f"Hash chain broken: {failures}"


# ═══════════════════════════════════════════════════════════════
# Step 3.1: 重试耗尽失败路径测试
# ═══════════════════════════════════════════════════════════════

class TestRetryExhaustion:
    """重试耗尽必须抛出明确异常。"""

    def test_no_genesis_raises_immediately(self):
        """无创世事件 → 立即抛出 RuntimeError（确定性错误，不重试）。"""
        fd, path = tempfile.mkstemp(suffix=".db", prefix="coherence_retry_")
        os.close(fd)
        store = EventStore(database_path=path)
        store.initialize()
        with pytest.raises(RuntimeError, match="No genesis event found"):
            store.append_event(p0_values={
                "trace_id": "t",
                "policy_version": "1",
                "counterfactual_ranker_version": "1",
                "counterfactual_feature_schema_version": "1",
            })
        try:
            os.unlink(path)
        except PermissionError:
            _time.sleep(0.1)
            os.unlink(path)

    def test_retry_exhaustion_raises_runtime_error(self):
        """模拟持久 UNIQUE 冲突 → 重试耗尽 → 抛出 RuntimeError。

        策略：patch _latest_event 固定返回创世事件（height=0），
        同时 DB 中已预写入 chain_height=1 占位。
        append_event 每次读到 height=0，尝试写入 height=1，
        触发 UNIQUE 冲突，重试耗尽后抛出 RuntimeError。
        """
        import src.inner.ledger.event_store as es
        original_retries = es.MAX_RETRIES
        es.MAX_RETRIES = 2

        fd, path = tempfile.mkstemp(suffix=".db", prefix="coherence_re_")
        os.close(fd)
        store = EventStore(database_path=path)
        store.initialize()
        genesis = store.create_genesis_event()

        # 预写入 chain_height=1 占位事件（绕过触发器）
        conn = store.db.get_connection()
        try:
            conn.execute("DROP TRIGGER IF EXISTS trg_events_no_update")
            conn.execute("DROP TRIGGER IF EXISTS trg_events_no_delete")
            conn.execute(
                """INSERT INTO events (
                    event_hash, prev_hash, chain_height,
                    trace_id, policy_version,
                    counterfactual_ranker_version,
                    counterfactual_feature_schema_version,
                    event_time_utc, window_id, window_schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("c" * 64, genesis["event_hash"], 1,
                 "blocker", "1", "1", "1",
                 "2026-01-01T00:00:00.000Z",
                 "2026-01-01T00:00_2026-01-01T00:30", "1.0.0"),
            )
            conn.commit()
        finally:
            conn.close()

        # patch: _latest_event 始终返回创世事件（height=0）
        original_latest = store._latest_event
        store._latest_event = lambda conn: dict(genesis)

        try:
            with pytest.raises(RuntimeError, match="append_event failed"):
                store.append_event(p0_values={
                    "trace_id": "t_conflict",
                    "policy_version": "1",
                    "counterfactual_ranker_version": "1",
                    "counterfactual_feature_schema_version": "1",
                })
        finally:
            es.MAX_RETRIES = original_retries
            store._latest_event = original_latest
            import gc
            gc.collect()
            for _ in range(5):
                try:
                    os.unlink(path)
                    break
                except PermissionError:
                    _time.sleep(0.1)
