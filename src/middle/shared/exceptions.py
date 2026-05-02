"""M1: 中圈共享异常基类。"""


class MiddlewareError(Exception):
    """中圈所有异常的基类。"""
    pass


class ContractViolationError(MiddlewareError):
    """合约一致性违规——字段/枚举/类型漂移。"""
    pass


class StateEstimationError(MiddlewareError):
    """状态估计失败——输入不足或模型无法产出有效估计。"""
    pass


class SemanticSafetyError(MiddlewareError):
    """语义安全检查未通过。"""
    pass


class DecisionRejectedError(MiddlewareError):
    """双轨决策被稳健轨拒绝。"""
    pass
