"""Step 5: No-Assist Evaluator — 可调阈值。"""

# 分数 → level 映射阈值（合约区间）
SCORE_THRESHOLD_INDEPENDENT = 0.7   # >= 0.7 → independent
SCORE_THRESHOLD_PARTIAL = 0.4       # >= 0.4 → partial, < 0.4 → dependent

# assist_used 分数上限（使用辅助时不判 independent）
ASSIST_USED_SCORE_CAP = 0.69

# 文本质量扣分
MIN_ANSWER_LENGTH = 8                # 低于此长度降分
LENGTH_PENALTY_FACTOR = 0.3         # 长度过短时扣分比例
EMPTY_ANSWER_SCORE = 0.0             # 空答案分数
TEMPLATE_PATTERNS = [
    "as an ai", "i cannot", "i'm unable", "i am unable",
    "i apologize", "sorry, i cannot", "i don't have",
]

# 推理痕迹加分
REASONING_KEYWORDS = [
    "first", "second", "third", "finally", "therefore",
    "because", "since", "thus", "hence", "consequently",
    "however", "on the other hand", "alternatively",
    "to summarize", "in conclusion", "for example",
    "let me check", "let me verify", "i think", "my reasoning",
    "step", "check", "verify", "double-check",
]
REASONING_BONUS_PER_HIT = 0.05
REASONING_BONUS_MAX = 0.35

# reference_answer 相似度（纯 Python 规则，不引入重依赖）
REF_SIMILARITY_WEIGHT = 0.20         # 相似度对总分的最大贡献
REF_OVERLAP_THRESHOLD_HIGH = 0.50    # > 50% 词汇重叠 → 高分
REF_OVERLAP_THRESHOLD_LOW = 0.10     # < 10% 词汇重叠 → 低分

# 规则版本
RULE_VERSION = "na_v1.0.0"
