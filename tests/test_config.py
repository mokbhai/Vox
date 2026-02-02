"""Tests for the config module."""
import pytest
import tempfile
import yaml
from pathlib import Path
from vox.config import Config, DEFAULT_CONFIG


class TestConfig:
    """Tests for Config class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir)
            yield config_path

    def test_default_values(self, temp_config_dir):
        """Test that default config values are correct."""
        # We can't fully test this without mocking the home directory,
        # but we can test the DEFAULT_CONFIG dict
        assert "model" in DEFAULT_CONFIG
        assert "auto_start" in DEFAULT_CONFIG
        assert "toast_position" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["model"] == "gpt-4o-mini"
        assert isinstance(DEFAULT_CONFIG["auto_start"], bool)

    def test_keyring_constants(self):
        """Test that keyring constants are defined."""
        from vox.config import KEYRING_SERVICE_NAME, KEYRING_API_KEY_ITEM
        assert KEYRING_SERVICE_NAME == "com.voxapp.rewrite"
        assert KEYRING_API_KEY_ITEM == "openai_api_key"
