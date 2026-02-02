"""Tests for the API module."""
import pytest
from vox.api import RewriteMode, DISPLAY_NAMES, SYSTEM_PROMPTS


class TestRewriteMode:
    """Tests for RewriteMode enum."""

    def test_display_names_exist(self):
        """Test that all modes have display names."""
        for mode in RewriteMode:
            assert mode in DISPLAY_NAMES

    def test_system_prompts_exist(self):
        """Test that all modes have system prompts."""
        for mode in RewriteMode:
            assert mode in SYSTEM_PROMPTS
            assert isinstance(SYSTEM_PROMPTS[mode], str)
            assert len(SYSTEM_PROMPTS[mode]) > 0

    def test_display_names(self):
        """Test display names are correct."""
        assert DISPLAY_NAMES[RewriteMode.FIX_GRAMMAR] == "Fix Grammar"
        assert DISPLAY_NAMES[RewriteMode.PROFESSIONAL] == "Professional"
        assert DISPLAY_NAMES[RewriteMode.CONCISE] == "Concise"
        assert DISPLAY_NAMES[RewriteMode.FRIENDLY] == "Friendly"
