#!/usr/bin/env python3
"""Contract: retrieval coverage follows the read-only signature verdict (D4).

The search preflight knows, after any repair, whether the index is still not
current: a path whose read fails keeps its signature not-current however often
the repair retries. ``index_status.signature_current`` records that verdict and
``retrieval_coverage`` must report ``index_not_fresh`` for it — an
``auto_updated: true`` repair result alone does not prove completeness.
"""

import os
from pathlib import Path

import pytest


def _write_journal(payload: dict) -> Path:
    from tools.write_journal.core import write_journal

    result = write_journal(dict(payload))
    assert result.get("journal_path"), result.get("error")
    return Path(result["journal_path"])


def _payload(date: str, title: str, content: str) -> dict:
    return {
        "title": title,
        "content": content,
        "date": date,
        "topic": "work",
        "tags": ["signature-verdict-contract"],
    }


def _build_rebuild() -> None:
    from tools.build_index import build_all

    assert build_all(incremental=False)["success"] is True


class DeniedReads:
    """Make every content read of one file raise ``OSError``."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, denied: Path) -> None:
        self.denied = denied
        self.real_read_bytes = Path.read_bytes
        self.real_read_text = Path.read_text
        denied_path = Path(denied)
        real_read_bytes = self.real_read_bytes
        real_read_text = self.real_read_text

        def denying_bytes(self, *args, **kwargs):
            if Path(self) == denied_path:
                raise PermissionError(f"synthetic unreadable file: {denied_path}")
            return real_read_bytes(self, *args, **kwargs)

        def denying_text(self, *args, **kwargs):
            if Path(self) == denied_path:
                raise PermissionError(f"synthetic unreadable file: {denied_path}")
            return real_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_bytes", denying_bytes)
        monkeypatch.setattr(Path, "read_text", denying_text)

    def restore(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "read_bytes", self.real_read_bytes)
        monkeypatch.setattr(Path, "read_text", self.real_read_text)


def _search(query: str) -> dict:
    from tools.search_journals.core import hierarchical_search

    return hierarchical_search(query=query)


def _merged_paths(response: dict) -> set[str]:
    return {
        str(item.get("path") or item.get("journal_route_path") or "").replace("\\", "/")
        for item in (response.get("merged_results") or [])
    }


class TestCoverageUsesTheSignatureVerdict:
    def test_successful_repair_of_an_unreadable_file_is_still_partial(
        self, isolated_data_dir, monkeypatch
    ):
        """P2 reproduction: a repair that cannot read a changed file is partial.

        B's signature changes; every read of B raises ``OSError`` for the whole
        request (both the index scan's ``read_bytes`` and the fallback scan's
        ``read_text``); A matches the query. The preflight repair succeeds
        (``auto_updated`` is true) but B is still not current, so the retrieval
        must not claim completeness.
        """
        token = "d4sharedtoken"
        a = _write_journal(_payload("2026-07-01", "A", f"alpha {token}"))
        b = _write_journal(_payload("2026-07-02", "B", f"beta {token}"))
        _build_rebuild()

        # B changes: only a re-read could make the index current again. Setting
        # the signature via a real write keeps the change inside the tool's own
        # (mtime, size) rule.
        b.write_text(
            b.read_text(encoding="utf-8") + "\n\noutside append changes the size\n",
            encoding="utf-8",
        )
        os.utime(b, (b.stat().st_atime + 10, b.stat().st_mtime + 10))

        denied = DeniedReads(monkeypatch, b)
        try:
            response = _search(token)
        finally:
            denied.restore(monkeypatch)

        assert response.get("success") is True, response.get("error")
        paths = _merged_paths(response)
        assert str(a).replace("\\", "/") in paths, "A must still be found"
        assert any(
            str(b).replace("\\", "/") in path for path in paths
        ), "B's earlier row still matches"

        index_status = response.get("index_status") or {}
        assert index_status.get("auto_updated") is True, index_status
        assert index_status.get("signature_current") is False, index_status

        coverage = response.get("retrieval_coverage") or {}
        assert coverage.get("status") == "partial", coverage
        assert "index_not_fresh" in coverage.get("partial_reasons", []), coverage

    def test_a_current_index_records_signature_current_true(self, isolated_data_dir):
        token = "d4currenttoken"
        _write_journal(_payload("2026-07-03", "A", f"alpha {token}"))
        _build_rebuild()

        from tools.lib.metadata_cache import ensure_cache_version_current

        ensure_cache_version_current()
        response = _search(token)

        assert response.get("success") is True
        assert (response.get("index_status") or {}).get("signature_current") is True
        coverage = response.get("retrieval_coverage") or {}
        assert coverage.get("status") == "complete", coverage

    def test_no_real_signature_check_leaves_the_key_absent(self, isolated_data_dir):
        """A test-double freshness report ran no signature check: key absent."""
        from unittest.mock import patch

        from tools.lib.index_freshness import FreshnessReport

        token = "d4doubletoken"
        _write_journal(_payload("2026-07-04", "A", f"alpha {token}"))
        _build_rebuild()

        fresh_report = FreshnessReport(
            fts_fresh=True, vector_fresh=True, overall_fresh=True, issues=[]
        )
        with patch("tools.lib.index_freshness.check_full_freshness", return_value=fresh_report):
            response = _search(token)

        index_status = response.get("index_status") or {}
        assert "signature_current" not in index_status
        coverage = response.get("retrieval_coverage") or {}
        assert coverage.get("status") == "complete", coverage


class TestIndexFreshnessSignal:
    """Unit pin of the coverage signal itself."""

    def _signals(self, index_status: dict) -> list[str]:
        from tools.search_journals.coverage import collect_coverage_signals

        reasons, _applied = collect_coverage_signals({"index_status": index_status})
        return reasons

    def test_signature_current_false_reports_the_reason_even_after_a_repair(self):
        assert self._signals({"auto_updated": True, "signature_current": False}) == [
            "index_not_fresh"
        ]

    def test_signature_current_true_reports_nothing(self):
        assert self._signals({"auto_updated": False, "signature_current": True}) == []

    def test_an_absent_key_keeps_the_previous_behaviour(self):
        assert self._signals({"auto_updated": True}) == []
        assert self._signals({"auto_updated": False}) == []
        assert self._signals({}) == []

        from tools.search_journals.coverage import collect_coverage_signals

        stale_reasons, _applied = collect_coverage_signals(
            {"warnings": ["index_stale: fts_signature_mismatch"]}
        )
        assert stale_reasons == ["index_not_fresh"]
