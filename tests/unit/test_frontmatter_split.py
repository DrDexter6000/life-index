#!/usr/bin/env python3
"""
Phase 3B split tests — verify attachment.py and schema.py
are importable directly AND re-exported from frontmatter.py.
"""


class TestAttachmentSplit:
    """Task 3B-1: attachment.py extraction"""

    def test_attachment_importable(self):
        from tools.lib.attachment import normalize_attachment_entries

        assert callable(normalize_attachment_entries)

    def test_attachment_private_helpers_importable(self):
        from tools.lib.attachment import (
            _normalize_attachment_write_input,
            _normalize_attachment_stored_metadata,
            _guess_attachment_content_type,
        )

        assert callable(_normalize_attachment_write_input)
        assert callable(_normalize_attachment_stored_metadata)
        assert callable(_guess_attachment_content_type)

    def test_frontmatter_reexports_attachment(self):
        """frontmatter.py must re-export for backward compat"""
        from tools.lib.frontmatter import normalize_attachment_entries

        assert callable(normalize_attachment_entries)

    def test_same_function_object(self):
        """Re-export must be the exact same function, not a copy"""
        from tools.lib.attachment import normalize_attachment_entries as direct
        from tools.lib.frontmatter import normalize_attachment_entries as reexport

        assert direct is reexport


class TestSchemaSplit:
    """Task 3B-2: schema.py extraction"""

    def test_schema_importable(self):
        from tools.lib.schema import (
            SCHEMA_VERSION,
            validate_metadata,
            migrate_metadata,
            get_schema_version,
            get_required_fields,
            get_recommended_fields,
        )

        assert isinstance(SCHEMA_VERSION, int)
        assert callable(validate_metadata)
        assert callable(migrate_metadata)
        assert callable(get_schema_version)
        assert callable(get_required_fields)
        assert callable(get_recommended_fields)

    def test_frontmatter_reexports_schema(self):
        """frontmatter.py must re-export for backward compat"""
        from tools.lib.frontmatter import (
            SCHEMA_VERSION,
            validate_metadata,
            migrate_metadata,
            get_schema_version,
            get_required_fields,
            get_recommended_fields,
        )

        assert isinstance(SCHEMA_VERSION, int)
        assert callable(validate_metadata)
        assert callable(migrate_metadata)
        assert callable(get_schema_version)
        assert callable(get_required_fields)
        assert callable(get_recommended_fields)

    def test_same_function_objects(self):
        """Re-exports must be the exact same objects"""
        from tools.lib.schema import SCHEMA_VERSION as direct_sv
        from tools.lib.schema import validate_metadata as direct_vm
        from tools.lib.frontmatter import SCHEMA_VERSION as reexport_sv
        from tools.lib.frontmatter import validate_metadata as reexport_vm

        assert direct_sv == reexport_sv
        assert direct_vm is reexport_vm
