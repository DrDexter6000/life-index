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


class TestFuzzyTypoCorrection:
    """C1-a fuzzy fallback (plan §3.C1a.1): Levenshtein ≥0.85, len-diff ≤2."""

    def test_fuzzy_corrects_high_similarity(self) -> None:
        # 'life indxx' Lev sim ≈ 0.900 → corrected
        assert _fuzzy_correct_typo("life indxx") == "life index"

    def test_fuzzy_skips_below_threshold(self) -> None:
        # 'life indxxx' Lev sim ≈ 0.818 → below 0.85, no correction
        assert _fuzzy_correct_typo("life indxxx") is None

    def test_fuzzy_skips_lyf_index(self) -> None:
        # 'lyf index' Lev sim ≈ 0.800 → below threshold (anti-test target)
        assert _fuzzy_correct_typo("lyf index") is None

    def test_fuzzy_skips_lifx_ndex(self) -> None:
        # 'lifx ndex' Lev sim ≈ 0.800 → below threshold
        assert _fuzzy_correct_typo("lifx ndex") is None

    def test_fuzzy_skips_extended_query_by_len_diff(self) -> None:
        # 'Life Index 2.0' len-diff=4 → skipped (legit query, not a typo)
        assert _fuzzy_correct_typo("Life Index 2.0") is None

    def test_fuzzy_skips_cjk(self) -> None:
        # CJK characters → fuzzy disabled (avoid natural-language false positives)
        assert _fuzzy_correct_typo("Life Index 项目") is None

    def test_build_search_plan_uses_fuzzy_fallback(self) -> None:
        plan = build_search_plan("life indxx", reference_date=date(2026, 3, 29))
        assert plan.normalized_query == "life index"


class TestNoiseGateRule8:
    """Rule 8 typo-near-noise: mid-similarity [0.65, 0.85), len-diff ≤2."""

    def test_rule8_blocks_life_indxxx(self) -> None:
        blocked, reason = is_noise_query("life indxxx")
        assert blocked is True
        assert reason == "typo_near_noise"

    def test_rule8_blocks_lyf_index(self) -> None:
        blocked, reason = is_noise_query("lyf index")
        assert blocked is True
        assert reason == "typo_near_noise"

    def test_rule8_blocks_lifx_ndex(self) -> None:
        blocked, reason = is_noise_query("lifx ndex")
        assert blocked is True
        assert reason == "typo_near_noise"

    def test_rule8_does_not_block_exact_typo_target(self) -> None:
        # 'life indx' sim=0.900 → above HI threshold, fuzzy handles it
        blocked, reason = is_noise_query("life indx")
        assert blocked is False or reason != "typo_near_noise"

    def test_rule8_does_not_block_extended_query(self) -> None:
        # 'Life Index 2.0' len-diff=4 → skipped by len guard, NOT noise
        blocked, reason = is_noise_query("Life Index 2.0")
        assert blocked is False
        assert reason is None

    def test_rule8_does_not_block_canonical(self) -> None:
        blocked, reason = is_noise_query("life index")
        assert blocked is False
        assert reason is None


class TestAliasExpansion:
    """C1-b: bilingual alias expansion."""

    def test_alias_map_has_birthday(self) -> None:
        assert _ALIAS_MAP["birthday"] == "生日"
        assert _ALIAS_MAP["生日"] == "birthday"

    def test_build_search_plan_expands_alias(self) -> None:
        plan = build_search_plan("乐乐 birthday", reference_date=date(2026, 3, 29))
        assert "生日" in plan.keywords
        assert "birthday" in plan.keywords

    def test_build_search_plan_alias_in_normalized(self) -> None:
        plan = build_search_plan("乐乐 birthday", reference_date=date(2026, 3, 29))
        assert "生日" in plan.normalized_query

    def test_build_search_plan_no_duplicate_alias(self) -> None:
        plan = build_search_plan("乐乐 birthday 生日", reference_date=date(2026, 3, 29))
        # Should not add duplicate "生日"
        assert plan.normalized_query.count("生日") == 1


class TestL2MetadataMultiTokenOr:
    """L2 metadata query matching uses OR semantics for multi-token queries."""

    def test_multi_token_or_matches_any_token_in_title(self) -> None:
        metadata = {"title": "计划回重庆给小朋友过生日与生活反思", "tags": []}
        assert _matches_filters(metadata, query="乐乐 birthday 生日")

    def test_multi_token_or_matches_any_token_in_tags(self) -> None:
        metadata = {"title": "无关", "tags": ["生日"]}
        assert _matches_filters(metadata, query="乐乐 birthday 生日")

    def test_multi_token_or_no_match(self) -> None:
        metadata = {"title": "完全无关", "tags": ["工作"]}
        assert not _matches_filters(metadata, query="乐乐 birthday 生日")

    def test_single_token_still_exact(self) -> None:
        metadata = {"title": "乐乐", "tags": []}
        assert _matches_filters(metadata, query="乐乐")


class TestRankingL2BonusStacking:
    """L2 metadata bonus is added to existing L3 results."""

    def test_l2_bonus_stacks_on_l3(self) -> None:
        l3 = [
            {
                "path": "/a.md",
                "title": "计划回重庆给小朋友过生日与生活反思",
                "relevance": 83,
            }
        ]
        l2 = [
            {
                "path": "/a.md",
                "title": "计划回重庆给小朋友过生日与生活反思",
                "metadata": {"tags": ["生日"]},
            }
        ]
        merged = merge_and_rank_results([], l2, l3, query="乐乐 birthday 生日")
        assert len(merged) == 1
        # L3=83 + L2 tags match (+3) = 86, then title-promotion if applicable
        assert merged[0]["final_score"] > 83
