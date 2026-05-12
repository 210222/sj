"""Phase 26: 主动进步反馈验证。"""
from src.coach.agent import CoachAgent


class TestProgressSummary:

    def test_init_variables_exist(self):
        """__init__ 中初始化了 progress 相关变量。"""
        a = CoachAgent()
        assert hasattr(a, '_progress_summary')
        assert hasattr(a, '_last_progress_ts')
        assert hasattr(a, '_last_mastery')

    def test_act_does_not_crash(self):
        """act() 调用不崩溃, 返回有效结果。"""
        a = CoachAgent()
        r = a.act("test")
        assert "action_type" in r

    def test_rate_limit_is_float(self):
        """_last_progress_ts 是 float。"""
        a = CoachAgent()
        assert isinstance(a._last_progress_ts, float)
