#!/usr/bin/env python3
"""Tests for the one frontmatter rewrite guard.

``frontmatter_rewrite_blocker()`` answers one question: may an existing file's
frontmatter be written back without losing anything? It must return ``None``
only when parsing the serialized mapping gives back what the serializer is meant
to write for it: the same mapping, apart from the three normalizations the
serializer makes on purpose (``schema_version`` always written, a null known
field left out, a string in a list field written as its comma-separated items).
"""

import pytest

from tools.lib.frontmatter import frontmatter_rewrite_blocker

REWRITABLE = {
    "plain_file": (
        '---\ntitle: "Plain"\ndate: 2026-03-04\ntopic: [life]\n' "tags: [test]\n---\n\nbody\n"
    ),
    "without_frontmatter": "body only\n",
    "empty_block": "---\n---\n\nbody\n",
    "nested_mapping_values": (
        "---\ntitle: T\ndate: 2026-03-04\noccurred:\n"
        "  from: 2008\n  to:\n  precision: year\n---\n\nbody\n"
    ),
    "mapping_in_a_scalar_field": ("---\ntitle:\n  nested: value\ndate: 2026-03-04\n---\n\nbody\n"),
    "numbers_and_booleans": (
        "---\ntitle: 2024\ndate: 2026-03-04\n"
        "count: 42\nrating: 3.14\npublished: true\ndraft: false\n---\n\nbody\n"
    ),
    "timestamps": (
        "---\ntitle: T\ndate: 2026-03-04T10:11:12Z\n" "seen: 2026-03-04 10:11:12\n---\n\nbody\n"
    ),
    # The serializer's own normalizations are not a loss.
    "null_in_a_known_field": "---\ntitle:\ndate: 2026-03-04\nweather: null\n---\n\nbody\n",
    "null_in_an_unknown_field": "---\ntitle: T\ndate: 2026-03-04\ncustom:\n---\n\nbody\n",
    "null_schema_version": "---\nschema_version:\ntitle: T\ndate: 2026-03-04\n---\n\nbody\n",
    "scalar_in_a_list_field": "---\ntitle: T\ndate: 2026-03-04\ntopic: life\n---\n\nbody\n",
    "comma_text_in_a_list_field": (
        "---\ntitle: T\ndate: 2026-03-04\ntags: alpha, beta\n---\n\nbody\n"
    ),
    "empty_text_in_a_list_field": '---\ntitle: T\ndate: 2026-03-04\nmood: ""\n---\n\nbody\n',
    "block_list": "---\ntitle: T\ndate: 2026-03-04\ntags:\n  - a\n  - b\n---\n\nbody\n",
    "multiline_text": (
        "---\ntitle: T\ndate: 2026-03-04\nabstract: |\n  line one\n  line two\n---\n\nbody\n"
    ),
    "list_of_mappings": (
        "---\ntitle: T\ndate: 2026-03-04\nattachments:\n"
        "  - path: a.jpg\n    size: 3\n---\n\nbody\n"
    ),
}


@pytest.mark.parametrize("case", sorted(REWRITABLE))
def test_rewritable_frontmatter_has_no_blocker(case):
    assert frontmatter_rewrite_blocker(REWRITABLE[case]) is None


UNREADABLE = {
    "invalid_yaml": "---\ntitle: [unterminated\ndate: 2026-03-04\n---\n\nbody\n",
    "list_root": "---\n- a\n- b\n---\n\nbody\n",
    "scalar_root": "---\njust a scalar\n---\n\nbody\n",
    "false_root": "---\nfalse\n---\n\nbody\n",
    "recursive_alias": "---\ntitle: T\ncustom: &a [*a]\n---\n\nbody\n",
    "impossible_timestamp": "---\ntitle: T\ndate: 2026-99-99\n---\n\nbody\n",
}


@pytest.mark.parametrize("case", sorted(UNREADABLE))
def test_unreadable_frontmatter_reports_unreadable(case):
    assert frontmatter_rewrite_blocker(UNREADABLE[case]) == "unreadable"


NOT_ROUND_TRIPPABLE = {
    "int_key": "---\ntitle: T\ndate: 2026-03-04\n2024: x\n---\n\nbody\n",
    "float_key": "---\ntitle: T\ndate: 2026-03-04\n1.5: x\n---\n\nbody\n",
    "boolean_key": "---\ntitle: T\ndate: 2026-03-04\ntrue: x\n---\n\nbody\n",
    "null_key": "---\ntitle: T\ndate: 2026-03-04\nnull: x\n---\n\nbody\n",
    "set_value": (
        "---\ntitle: T\ndate: 2026-03-04\n" "tags: !!set {alpha: null, beta: null}\n---\n\nbody\n"
    ),
    "pairs_value": (
        "---\ntitle: T\ndate: 2026-03-04\n" "custom: !!pairs [a: b, c: d]\n---\n\nbody\n"
    ),
    "omap_value": ("---\ntitle: T\ndate: 2026-03-04\ncustom: !!omap [a: b]\n---\n\nbody\n"),
    "private_key": "---\n_custom: x\n---\n\nbody\n",
    "private_key_beside_fields": "---\ntitle: T\ndate: 2026-03-04\n_custom: x\n---\n\nbody\n",
}


@pytest.mark.parametrize("case", sorted(NOT_ROUND_TRIPPABLE))
def test_values_the_serializer_cannot_reproduce_are_not_round_trippable(case):
    assert frontmatter_rewrite_blocker(NOT_ROUND_TRIPPABLE[case]) == "not_round_trippable"


@pytest.mark.parametrize("case", sorted(REWRITABLE))
def test_a_rewritable_frontmatter_comes_back_as_its_rewrite_form(case):
    """What the guard promises: the rewrite reproduces the rewrite form exactly."""
    from tools.lib.frontmatter import (
        _rewrite_form,
        _same_value,
        format_frontmatter,
        parse_frontmatter,
    )

    metadata, body = parse_frontmatter(REWRITABLE[case])
    rewritten, rewritten_body = parse_frontmatter(format_frontmatter(metadata) + "\n\n" + body)

    assert _same_value(rewritten, _rewrite_form(metadata))
    assert rewritten_body.strip() == body.strip()


def test_rewrite_form_names_the_three_normalizations():
    from tools.lib.frontmatter import _rewrite_form
    from tools.lib.schema import SCHEMA_VERSION

    form = _rewrite_form(
        {
            "title": None,
            "weather": None,
            "custom": None,
            "topic": "life",
            "tags": "alpha, beta",
            "mood": "",
            "abstract": "a, b",
            "_custom": "kept",
            2024: "kept",
        }
    )

    assert form == {
        "schema_version": SCHEMA_VERSION,
        "custom": None,
        "topic": ["life"],
        "tags": ["alpha", "beta"],
        "mood": [],
        "abstract": "a, b",
        "_custom": "kept",
        2024: "kept",
    }


@pytest.mark.parametrize(
    "left, right",
    [
        (1, True),
        (1, 1.0),
        ({"a": 1}, {"a": True}),
        ([1.0], [1]),
        ({"a": [1, {"b": 0}]}, {"a": [1, {"b": False}]}),
        ((1, 2), [1, 2]),
        ({"a": 1}, {"a": 1, "b": 2}),
        ([1], [1, 2]),
    ],
)
def test_the_comparison_tells_types_apart(left, right):
    from tools.lib.frontmatter import _same_value

    assert _same_value(left, right) is False
    assert _same_value(left, left) is True
