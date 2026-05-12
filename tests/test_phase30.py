"""Phase 30: 技能知识图谱验证."""
import json, tempfile, os
from src.coach.diagnostic_engine import SkillGraph, SkillMasteryStore
from src.coach.composer import PolicyComposer

TEST_GRAPH = {
    "python_list": {"prerequisites": ["python_variable", "python_loop"], "related": ["python_dict"]},
    "python_loop": {"prerequisites": ["python_variable"], "related": ["python_list"]},
    "python_variable": {"prerequisites": [], "related": ["python_loop"]},
    "python_dict": {"prerequisites": ["python_list", "python_variable"], "related": []},
}


def _make_graph() -> SkillGraph:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(TEST_GRAPH, tmp)
    tmp.close()
    g = SkillGraph(tmp.name)
    os.unlink(tmp.name)
    return g


class TestSkillGraph:

    def test_load_graph(self):
        g = _make_graph()
        prereqs = g.get_prerequisites("python_list")
        assert "python_loop" in prereqs
        assert "python_variable" in prereqs

    def test_empty_graph_no_crash(self):
        g = SkillGraph("nonexistent.json")
        assert g._graph == {}

    def test_dependents(self):
        g = _make_graph()
        deps = g.get_dependents("python_list")
        assert "python_dict" in deps

    def test_unmastered_prereqs(self):
        g = _make_graph()
        missing = g.has_unmastered_prerequisites(
            "python_list", {"python_variable": 0.9, "python_loop": 0.3})
        assert "python_loop" in missing

    def test_propagation_no_effect_if_no_gain(self):
        store = SkillMasteryStore()
        store._mastery = {"python_list": 0.5, "python_dict": 0.5}
        g = _make_graph()
        old_dict = store._mastery["python_dict"]
        store.update("python_list", False, g)  # wrong => no gain => no propagation
        assert store._mastery["python_dict"] == old_dict


class TestComposerGraph:

    def test_select_with_prereqs(self):
        # python_variable not in mastery (0 < 0.6) → all skills have unmastered prereq
        # → fallback: pick the most fundamental missing prerequisite
        mastery = {"python_list": 0.9, "python_loop": 0.3, "python_dict": 0.4}
        g = _make_graph()
        topic = PolicyComposer._select_topic_by_mastery(
            {"skills": mastery}, skill_graph=g)
        assert topic == "python_variable", f"expected python_variable (fundamental prereq), got {topic}"

    def test_select_without_graph_fallback(self):
        mastery = {"python_list": 0.9, "python_loop": 0.3}
        topic = PolicyComposer._select_topic_by_mastery({"skills": mastery})
        assert topic == "python_loop"
