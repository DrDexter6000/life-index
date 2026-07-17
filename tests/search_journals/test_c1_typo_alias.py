"""Tests for C1-a typo correction and C1-b bilingual alias expansion."""

from datetime import date

from tools.search_journals.l2_metadata import _matches_filters
from tools.search_journals.noise_gate import is_noise_query
from tools.search_journals.query_preprocessor import (
    _ALIAS_MAP,
    _TYPO_CORRECTIONS,
    _fuzzy_correct_typo,
    build_search_plan,
)
from tools.search_journals.ranking import merge_and_rank_results


class TestTypoCorrections:
    """C1-a: typo correction exact-match."""

    def test_typo_dict_has_life_indx(self) -> None:
        assert "life indx" in _TYPO_CORRECTIONS
        assert _TYPO_CORRECTIONS["life indx"] == "life index"

    def test_build_search_plan_applies_typo(self) -> None:
        plan = build_search_plan("life indx", reference_date=date(2026, 3, 29))
        assert plan.normalized_query == "life index"
        assert "life" in plan.keywords
        assert "index" in plan.keywords

    def test_build_search_plan_no_false_positive(self) -> None:
        plan = build_search_plan("life index", reference_date=date(2026, 3, 29))
        assert plan.normalized_query == "life index"


class TestAliasExpansion:
    """C1-b: bilingual alias expansion."""

    def test_alias_map_has_birthday(self) -> None:
        assert _ALIAS_MAP["birthday"] == "生日"
        assert _ALIAS_MAP["生日"] == "birthday"

    def test_build_search_plan_expands_alias(self) -> None:
        plan = build_search_plan("晴岚 birthday", reference_date=date(2026, 3, 29))
        assert "生日" in plan.keywords
        assert "birthday" in plan.keywords

    def test_build_search_plan_alias_in_normalized(self) -> None:
        plan = build_search_plan("晴岚 birthday", reference_date=date(2026, 3, 29))
        assert "生日" in plan.normalized_query

    def test_build_search_plan_no_duplicate_alias(self) -> None:
        plan = build_search_plan("晴岚 birthday 生日", reference_date=date(2026, 3, 29))
        # Should not add duplicate "生日"
        assert plan.normalized_query.count("生日") == 1


class TestL2MetadataMultiTokenOr:
    """L2 metadata query matching uses OR semantics for multi-token queries."""

    def test_multi_token_or_matches_any_token_in_title(self) -> None:
        metadata = {"title": "计划去海边给朋友过生日与生活反思", "tags": []}
        assert _matches_filters(metadata, query="晴岚 birthday 生日")

    def test_multi_token_or_matches_any_token_in_tags(self) -> None:
        metadata = {"title": "无关", "tags": ["生日"]}
        assert _matches_filters(metadata, query="晴岚 birthday 生日")

    def test_multi_token_or_no_match(self) -> None:
        metadata = {"title": "完全无关", "tags": ["工作"]}
        assert not _matches_filters(metadata, query="晴岚 birthday 生日")

    def test_single_token_still_exact(self) -> None:
        metadata = {"title": "晴岚", "tags": []}
        assert _matches_filters(metadata, query="晴岚")


class TestRankingL2BonusStacking:
    """L2 metadata bonus is added to existing L3 results."""

    def test_l2_bonus_stacks_on_l3(self) -> None:
        l3 = [
            {
                "path": "/a.md",
                "title": "计划去海边给朋友过生日与生活反思",
                "relevance": 83,
            }
        ]
        l2 = [
            {
                "path": "/a.md",
                "title": "计划去海边给朋友过生日与生活反思",
                "metadata": {"tags": ["生日"]},
            }
        ]
        merged = merge_and_rank_results([], l2, l3, query="晴岚 birthday 生日")
        assert len(merged) == 1
        # L3=83 + L2 tags match (+3) = 86, then title-promotion if applicable
        assert merged[0]["final_score"] > 83


class TestFuzzyTypoCorrection:
    """C1-a fuzzy: rapidfuzz fallback for near-typo queries."""

    def test_fuzzy_corrects_life_indxx(self) -> None:
        # Single char multi-repeat (ratio ≈ 90.0 > 85)
        assert _fuzzy_correct_typo("life indxx") == "life index"

    def test_fuzzy_corrects_lif_index(self) -> None:
        # Single char deletion (ratio ≈ 94.7 > 85)
        assert _fuzzy_correct_typo("lif index") == "life index"

    def test_fuzzy_leaves_life_indxxx_uncorrected_below_threshold(self) -> None:
        # Standard Levenshtein normalized_similarity = 0.818 < 0.85
        # → should return None (leave to Rule 8).
        assert _fuzzy_correct_typo("life indxxx") is None

    def test_fuzzy_leaves_extended_query_uncorrected_by_len_guard(self) -> None:
        # len-diff=4 > 2, so fuzzy correction does not apply.
        assert _fuzzy_correct_typo("Life Index 2.0") is None

    def test_fuzzy_ignores_cjk_input(self) -> None:
        # Fuzzy correction applies only to ASCII input.
        assert _fuzzy_correct_typo("生活索引") is None

    def test_fuzzy_exact_match_passthrough(self) -> None:
        # exact canonical returns None (exact-match dict handles it)
        assert _fuzzy_correct_typo("life index") is None

    def test_build_search_plan_uses_fuzzy_after_exact_miss(self) -> None:
        plan = build_search_plan("life indxx", reference_date=date(2026, 3, 29))
        assert plan.normalized_query == "life index"


class TestNoiseClassifierRule8:
    """Rule 8 classifies mid-similarity queries as advisory metadata."""

    def test_rule8_classifies_life_indxxx(self) -> None:
        # Standard Levenshtein normalized_similarity = 0.818 in [0.65, 0.85)
        # → should retain the Rule 8 compatibility reason.
        is_advisory, reason = is_noise_query("life indxxx")
        assert is_advisory
        assert reason == "typo_near_noise"

    def test_rule8_classifies_lyf_index(self) -> None:
        # ratio ≈ 84.2 in [65, 85)
        is_advisory, reason = is_noise_query("lyf index")
        assert is_advisory
        assert reason == "typo_near_noise"

    def test_rule8_classifies_lifx_ndex(self) -> None:
        # ratio ≈ 84.2 in [65, 85)
        is_advisory, reason = is_noise_query("lifx ndex")
        assert is_advisory
        assert reason == "typo_near_noise"

    def test_rule8_does_not_classify_extended_query(self) -> None:
        # len-diff=4 > 2, so Rule 8 does not classify it.
        is_advisory, reason = is_noise_query("Life Index 2.0")
        assert not is_advisory
        assert reason is None

    def test_rule8_does_not_classify_chinese_project_name(self) -> None:
        # The ASCII-only classifier does not apply.
        is_advisory, reason = is_noise_query("Life Index 项目")
        assert not is_advisory
        assert reason is None

    def test_rule8_does_not_classify_canonical_itself(self) -> None:
        # ratio = 100.0, outside [65, 85)
        is_advisory, reason = is_noise_query("life index")
        assert not is_advisory
        assert reason is None
