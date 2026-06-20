#!/usr/bin/env python3
"""Deterministic facet value canonicalization from the user's entity graph."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.entity_graph import load_entity_graph
from tools.lib.entity_schema import ENTITY_TYPES

_FACET_ENTITY_TYPES: dict[str, set[str]] = {
    "project": {"project"},
    "people": {"person"},
    "location": {"place"},
    "tag": set(ENTITY_TYPES),
}


@dataclass(frozen=True)
class CanonicalFacetValue:
    raw_value: str
    value: str


@dataclass(frozen=True)
class FacetCanonicalizer:
    status: str
    canonicalization_hash: str
    diagnostics: list[dict[str, Any]]
    _aliases: dict[str, dict[str, str]]
    _ambiguous: dict[str, set[str]]

    def canonicalize(self, facet: str, value: Any) -> CanonicalFacetValue:
        raw_value = _normalize_label(str(value or ""))
        if not raw_value:
            return CanonicalFacetValue(raw_value="", value="")
        key = _lookup_key(raw_value)
        if key in self._ambiguous.get(facet, set()):
            return CanonicalFacetValue(raw_value=raw_value, value=raw_value)
        canonical = self._aliases.get(facet, {}).get(key, raw_value)
        return CanonicalFacetValue(raw_value=raw_value, value=canonical)

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "canonicalization_hash": self.canonicalization_hash,
            "diagnostics": self.diagnostics,
        }


def _normalize_label(value: str) -> str:
    return " ".join(value.strip().split())


def _lookup_key(value: str) -> str:
    return _normalize_label(value).casefold()


def _hash_alias_map(aliases: dict[str, dict[str, str]], ambiguous: dict[str, set[str]]) -> str:
    payload = {
        "aliases": {
            facet: sorted(mapping.items()) for facet, mapping in sorted(aliases.items()) if mapping
        },
        "ambiguous": {
            facet: sorted(values) for facet, values in sorted(ambiguous.items()) if values
        },
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _empty_canonicalizer(
    *, status: str = "active", diagnostics: list[dict[str, Any]] | None = None
) -> FacetCanonicalizer:
    aliases: dict[str, dict[str, str]] = {facet: {} for facet in _FACET_ENTITY_TYPES}
    ambiguous: dict[str, set[str]] = {facet: set() for facet in _FACET_ENTITY_TYPES}
    return FacetCanonicalizer(
        status=status,
        canonicalization_hash=_hash_alias_map(aliases, ambiguous),
        diagnostics=diagnostics or [],
        _aliases=aliases,
        _ambiguous=ambiguous,
    )


def _register_label(
    *,
    aliases: dict[str, dict[str, str]],
    ambiguous: dict[str, set[str]],
    owners: dict[str, dict[str, str]],
    diagnostics: list[dict[str, Any]],
    facet: str,
    label: str,
    canonical: str,
    entity_id: str,
) -> None:
    normalized = _normalize_label(label)
    if not normalized:
        return
    key = _lookup_key(normalized)
    if key in ambiguous[facet]:
        return
    existing = aliases[facet].get(key)
    existing_owner = owners[facet].get(key)
    if existing is None:
        aliases[facet][key] = canonical
        owners[facet][key] = entity_id
        return
    if existing == canonical and existing_owner == entity_id:
        return
    aliases[facet].pop(key, None)
    owners[facet].pop(key, None)
    ambiguous[facet].add(key)
    diagnostics.append(
        {
            "code": "ambiguous_alias",
            "facet": facet,
            "label": key,
            "canonical_values": sorted({existing, canonical}),
            "entity_ids": sorted({str(existing_owner or ""), entity_id}),
        }
    )


def _build_canonicalizer(entities: list[dict[str, Any]]) -> FacetCanonicalizer:
    aliases: dict[str, dict[str, str]] = {facet: {} for facet in _FACET_ENTITY_TYPES}
    ambiguous: dict[str, set[str]] = {facet: set() for facet in _FACET_ENTITY_TYPES}
    owners: dict[str, dict[str, str]] = {facet: {} for facet in _FACET_ENTITY_TYPES}
    diagnostics: list[dict[str, Any]] = []

    for entity in entities:
        entity_id = str(entity.get("id", "")).strip()
        entity_type = str(entity.get("type", "")).strip()
        canonical = _normalize_label(str(entity.get("primary_name", "")))
        if not canonical:
            continue
        labels = [canonical, *(str(item) for item in entity.get("aliases", []) or [])]
        for facet, allowed_types in _FACET_ENTITY_TYPES.items():
            if entity_type not in allowed_types:
                continue
            for label in labels:
                _register_label(
                    aliases=aliases,
                    ambiguous=ambiguous,
                    owners=owners,
                    diagnostics=diagnostics,
                    facet=facet,
                    label=label,
                    canonical=canonical,
                    entity_id=entity_id,
                )

    return FacetCanonicalizer(
        status="active",
        canonicalization_hash=_hash_alias_map(aliases, ambiguous),
        diagnostics=diagnostics,
        _aliases=aliases,
        _ambiguous=ambiguous,
    )


def load_facet_canonicalizer(data_dir: Path) -> FacetCanonicalizer:
    try:
        entities = load_entity_graph(data_dir / "entity_graph.yaml")
    except Exception as exc:
        return _empty_canonicalizer(
            status="disabled",
            diagnostics=[{"code": "entity_graph_invalid", "message": str(exc)}],
        )
    if not entities:
        return _empty_canonicalizer()
    return _build_canonicalizer(entities)
