"""Phase 97c: Quote extraction -- pre-verified safe phrases for student quoting."""
import re
import pytest


def _extract_safe_phrases(user_input: str, max_phrases: int = 8, min_len: int = 2) -> list[str]:
    """Pure function version of agent.py quote extraction logic for testing."""
    quotable = []
    quoted = re.findall(r'["""](.+?)["""]', user_input)
    quotable.extend(quoted[:3])
    bracket_quoted = re.findall(r'「(.+?)」', user_input)
    quotable.extend(bracket_quoted[:3])
    cn_phrases = re.findall(r'[一-鿿]{2,6}', user_input)
    en_phrases = re.findall(r'\b[a-zA-Z_]{2,}\b', user_input)
    seen = set()
    safe_phrases = []
    for p in quotable + cn_phrases + en_phrases:
        p = p.strip()
        if p and len(p) >= min_len and p not in seen:
            seen.add(p)
            safe_phrases.append(p)
    return safe_phrases[:max_phrases]


class TestQuoteExtraction:
    def test_chinese_quotes(self):
        phrases = _extract_safe_phrases('你说的"矩阵乘法"我不太理解')
        assert "矩阵乘法" in phrases

    def test_bracket_quotes(self):
        phrases = _extract_safe_phrases('「递归」是什么意思？')
        assert "递归" in phrases

    def test_cn_phrases(self):
        phrases = _extract_safe_phrases('我不理解乘法和变换')
        assert len(phrases) >= 1  # should extract 2-char+ Chinese words

    def test_english_terms(self):
        phrases = _extract_safe_phrases('hello world test')
        assert len(phrases) >= 1  # should extract 2+ char English words

    def test_dedup(self):
        phrases = _extract_safe_phrases('矩阵 矩阵 矩阵')
        assert phrases.count("矩阵") <= 1

    def test_max_phrases_limit(self):
        phrases = _extract_safe_phrases(
            '变量的赋值 函数定义 循环结构 条件判断 列表推导 字典操作 集合运算 元组打包 字符串格式化 继承多态')
        assert len(phrases) <= 8

    def test_empty_input(self):
        phrases = _extract_safe_phrases('')
        assert phrases == []

    def test_min_length_filter(self):
        phrases = _extract_safe_phrases('a b c 的', min_len=3)
        assert len(phrases) == 0

    def test_quote_priority(self):
        phrases = _extract_safe_phrases('"矩阵乘法" 矩阵乘法 线性代数')
        # Quoted text appears first
        assert phrases[0] == "矩阵乘法"

    def test_malicious_input(self):
        phrases = _extract_safe_phrases('\x00' * 100)
        assert isinstance(phrases, list)

    def test_mixed_quotes_and_text(self):
        phrases = _extract_safe_phrases('你说的"时间复杂度"和"空间复杂度"我都懂了')
        assert "时间复杂度" in phrases
        assert "空间复杂度" in phrases
