"""Tests for C1-a typo correction and C1-b bilingual alias expansion."""

from datetime import date

from tools.search_journals.l2_metadata import _matches_filters
from tools.search_journals.query_preprocessor import (
    _ALIAS_MAP,
    _TYPO_CORRECTIONS,
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
