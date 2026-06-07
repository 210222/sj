"""Phase 97a: Output contract -- programmatic statement compactness tests."""
import pytest
from src.coach.llm.schemas import LLMOutputValidator


class TestCountStatementSentences:
    def test_plain_three_sentences(self):
        assert LLMOutputValidator.count_statement_sentences("A。B。C。") == 3

    def test_single_sentence(self):
        assert LLMOutputValidator.count_statement_sentences("一句话") == 1

    def test_empty_string(self):
        assert LLMOutputValidator.count_statement_sentences("") == 0

    def test_none_input(self):
        assert LLMOutputValidator.count_statement_sentences(None) == 0

    def test_with_katex_inline(self):
        s = "这是公式$\\frac{1}{2}$。解释。"
        assert LLMOutputValidator.count_statement_sentences(s) == 2

    def test_with_katex_multiple(self):
        s = "先看$a=1$。再看$b=2$。最后$c=3$。"
        assert LLMOutputValidator.count_statement_sentences(s) >= 3

    def test_english_mixed(self):
        s = "Hello world. 这是中文。Another sentence."
        assert LLMOutputValidator.count_statement_sentences(s) >= 2

    def test_newline_separator(self):
        s = "第一行\n第二行\n第三行"
        assert LLMOutputValidator.count_statement_sentences(s) == 3

    def test_multiple_katex_in_one_sentence(self):
        s = "公式$a=1$和$b=2$都在这里。另一句。"
        assert LLMOutputValidator.count_statement_sentences(s) == 2

    def test_only_katex(self):
        s = "$a=1$"
        assert LLMOutputValidator.count_statement_sentences(s) == 1


class TestEnforceStatementCompactness:
    def test_no_truncation_needed(self):
        payload = {"statement": "简短回答。一个问题？"}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=4, max_chars=300)
        assert report["truncated"] is False
        assert result["statement"] == payload["statement"]

    def test_truncates_excess_sentences(self):
        payload = {"statement": "第一句。第二句。第三句。第四句。第五句。"}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=3, max_chars=300)
        assert report["truncated"] is True
        count = LLMOutputValidator.count_statement_sentences(result["statement"])
        assert count <= 3

    def test_extracts_question_from_truncated(self):
        payload = {"statement": "这是教学内容第一句。这是第二句。这是第三句。第四句是一个问题？第五句。", "question": ""}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=3, max_chars=300)
        if report.get("truncated"):
            q = result.get("question", "")
            assert "？" in q or "?" in q or q == ""

    def test_preserves_katex(self):
        payload = {"statement": "公式$a=1$。解释。太长第四句。太长第五句。太长第六句。"}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=3, max_chars=300)
        assert "$a=1$" in result["statement"]

    def test_too_short_marks_flag(self):
        payload = {"statement": "很短的句子。"}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=3, max_chars=5)
        assert "statement" in result

    def test_empty_statement_handled(self):
        payload = {"statement": ""}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=4, max_chars=300)
        assert "statement" in result

    def test_missing_statement_key(self):
        payload = {}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=4, max_chars=300)
        assert "statement" not in result
        assert report["truncated"] is False


class TestValidateQuestionPresence:
    def test_has_question(self):
        valid, msg = LLMOutputValidator.validate_question_presence(
            {"question": "你觉得呢？"})
        assert valid is True
        assert msg == ""

    def test_missing_question(self):
        valid, msg = LLMOutputValidator.validate_question_presence({"statement": "..."})
        assert valid is False

    def test_empty_question(self):
        valid, msg = LLMOutputValidator.validate_question_presence({"question": ""})
        assert valid is False


class TestSplitSentencesKatexSafe:
    def test_plain_split(self):
        sentences = LLMOutputValidator._split_sentences_katex_safe("A。B。C。")
        assert len(sentences) == 3

    def test_katex_not_split(self):
        sentences = LLMOutputValidator._split_sentences_katex_safe(
            "公式$a=1$在这里。另一句。")
        assert any("$a=1$" in s for s in sentences)

    def test_empty_text(self):
        sentences = LLMOutputValidator._split_sentences_katex_safe("")
        assert sentences == []

    def test_no_boundary(self):
        sentences = LLMOutputValidator._split_sentences_katex_safe("没有分隔符的一句话")
        assert len(sentences) == 1


class TestTruncateCharsKatexSafe:
    def test_truncates_before_katex_block(self):
        text = "前缀文本" + "x" * 100 + " $a=1$ 后缀"
        r = LLMOutputValidator._truncate_chars_katex_safe(text, 50)
        assert len(r) <= 50 and "$a=1$" not in r[:50]

    def test_normal_truncation_no_katex(self):
        r = LLMOutputValidator._truncate_chars_katex_safe("x" * 200, 50)
        assert len(r) == 50

    def test_no_truncation_when_under_limit(self):
        r = LLMOutputValidator._truncate_chars_katex_safe("short", 100)
        assert r == "short"

    def test_katex_at_start_prevents_truncation(self):
        r = LLMOutputValidator._truncate_chars_katex_safe("$a=1$" + "x" * 200, 50)
        assert len(r) <= 50

    def test_multiple_katex_blocks(self):
        text = "x" * 30 + " $a=1$ " + "y" * 30 + " $b=2$ " + "z" * 30
        r = LLMOutputValidator._truncate_chars_katex_safe(text, 25)
        assert len(r) <= 25

    def test_truncation_at_katex_boundary(self):
        text = "x" * 10 + " $formula$ " + "y" * 100
        r = LLMOutputValidator._truncate_chars_katex_safe(text, 11)
        assert "$formula$" not in r or r.endswith("$")


class TestEnforceCompactnessCharLevel:
    def test_char_truncation_applied_after_sentence(self):
        payload = {"statement": "第一句。" + "x" * 400}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=10, max_chars=100)
        assert report["truncated"] and len(result["statement"]) <= 100

    def test_no_false_truncated_flag(self):
        payload = {"statement": "短文本。"}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=10, max_chars=300)
        assert not report["truncated"]

    def test_char_truncation_preserves_katex(self):
        payload = {"statement": "公式 $x=1$ 后面" + "y" * 300}
        result, report = LLMOutputValidator.enforce_statement_compactness(
            payload, max_sentences=10, max_chars=20)
        assert "$x=1$" in result["statement"]


class TestQuestionExtractionNearBoundary:
    markers = ["？", "?", "你觉得", "能不能"]

    def test_extract_question_at_sentence_boundary(self):
        text = "教学内容第一句。第二句。第三句被截在这里。第四句是一个问题？最后。"
        r = LLMOutputValidator._extract_question_near_boundary(text, 21, self.markers)
        assert r is not None and "问题" in r

    def test_extract_question_after_char_truncation(self):
        text = "教学。内容。" + "x" * 50 + " 这是问题？ 结尾。"
        r = LLMOutputValidator._extract_question_near_boundary(text, 10, self.markers)
        assert r is not None and "？" in r

    def test_no_question_when_marker_in_kept(self):
        # 问句完整地在截断之前，且以。收尾，不应提取
        text = "这是问题？这里结束了。还有更多被截断内容。"
        #            ^position 4              ^position 9
        # truncation at 10: ？在kept区(4<10)，问句的。在9<10
        r = LLMOutputValidator._extract_question_near_boundary(text, 10, self.markers)
        assert r is None  # sentence ended cleanly before truncation

    def test_returns_none_for_empty_text(self):
        r = LLMOutputValidator._extract_question_near_boundary("", 5, self.markers)
        assert r is None

    def test_returns_none_when_no_marker(self):
        text = "教学内容。没有问号也没有任何标记词。结束。"
        r = LLMOutputValidator._extract_question_near_boundary(text, 10, self.markers)
        assert r is None
