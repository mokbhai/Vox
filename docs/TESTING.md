# Testing Guide

This document describes the testing patterns and conventions used in Vox.

## Table of Contents

- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Pytest Configuration](#pytest-configuration)
- [Mocking PyObjC](#mocking-pyobjc)
- [Testing Patterns](#testing-patterns)
- [Coverage](#coverage)

---

## Test Structure

Tests are located in the `tests/` directory, mirroring the module structure:

```
tests/
├── __init__.py
├── test_api.py          # Tests for api.py
├── test_config.py       # Tests for config.py
├── test_hotkey.py       # Tests for hotkey.py
└── test_notifications.py # Tests for notifications.py
```

### Test Class Organization

Group related tests into classes:

```python
class TestConfigConstants:
    """Tests for config module constants."""

    def test_default_models(self):
        """Test DEFAULT_MODELS contains expected models."""
        assert "gpt-4o" in DEFAULT_MODELS


class TestConfig:
    """Tests for Config class."""

    def test_model_property(self, temp_config):
        """Test model property getter and setter."""
        assert temp_config.model == "gpt-4o-mini"
```

---

## Running Tests

### Using Make

```bash
make test
```

### Using uv directly

```bash
uv run pytest tests/ -v
```

### Running specific tests

```bash
# Run tests in a specific file
uv run pytest tests/test_config.py -v

# Run a specific test class
uv run pytest tests/test_config.py::TestConfig -v

# Run a specific test
uv run pytest tests/test_config.py::TestConfig::test_model_property -v

# Run tests matching a pattern
uv run pytest tests/ -k "hotkey" -v
```

---

## Pytest Configuration

### Fixtures

#### Temporary Config Fixture

Create isolated config instances for testing:

```python
@pytest.fixture
def temp_config(self):
    """Create a config instance with a temporary config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("vox.config.Path.home", return_value=Path(tmpdir)):
            reset_config()
            config = Config()
            yield config
```

#### HotKey Manager Fixture

```python
def _make_manager(self):
    """Create a HotKeyManager for testing."""
    manager = HotKeyManager()
    manager.set_hotkeys([("cmd", "d", RewriteMode.FIX_GRAMMAR)])
    manager._enabled = True
    manager._callback = MagicMock()
    manager._tap = MagicMock()
    return manager
```

---

## Mocking PyObjC

### Patching AppKit

```python
from unittest.mock import patch, MagicMock

def test_show_alert(self):
    """Test showing an alert."""
    with patch('vox.hotkey.AppKit') as mock_appkit:
        mock_alert = MagicMock()
        mock_appkit.NSAlert.alloc().init.return_value = mock_alert
        mock_appkit.NSAlertFirstButtonReturn = 1000
        mock_alert.runModal.return_value = 1000

        # Call the function
        manager._show_accessibility_dialog()

        # Verify alert was configured
        mock_alert.setMessageText_.assert_called_once()
```

### Patching Quartz

```python
def test_handle_event(self):
    """Test handling a CGEvent."""
    with patch('vox.hotkey.Quartz') as mock_quartz:
        mock_quartz.kCGEventKeyDown = kCGEventKeyDown
        mock_quartz.CGEventGetIntegerValueField.return_value = 0x02
        mock_quartz.CGEventGetFlags.return_value = kCGEventFlagMaskCommand

        result = manager._handle_cg_event(None, kCGEventKeyDown, mock_event)
```

### Patching Multiple Modules

```python
def test_register_hotkey_success(self):
    """Test successful hot key registration."""
    with patch('vox.hotkey.has_accessibility_permission', return_value=True), \
         patch('vox.hotkey.Quartz') as mock_quartz, \
         patch('vox.hotkey.threading') as mock_threading:
        # Setup mocks
        mock_quartz.CGEventTapCreate.return_value = MagicMock()
        mock_quartz.CFMachPortCreateRunLoopSource.return_value = MagicMock()

        result = manager.register_hotkey()
        assert result is True
```

---

## Testing Patterns

### Testing Properties

```python
def test_model_property(self, temp_config):
    """Test model property getter and setter."""
    # Test default
    assert temp_config.model == "gpt-4o-mini"

    # Test setter
    temp_config.model = "gpt-4o"
    assert temp_config.model == "gpt-4o"

    # Verify persistence
    with open(temp_config.config_file, "r") as f:
        data = yaml.safe_load(f)
    assert data["model"] == "gpt-4o"
```

### Testing Exception Handling

```python
def test_api_key_error(self):
    """Test API key error handling."""
    with pytest.raises(APIKeyError):
        api._handle_openai_error(
            Mock(code="invalid_api_key")
        )

def test_error_conversion(self):
    """Test that OpenAI errors are converted correctly."""
    error = OpenAIError("Rate limit exceeded")
    error.code = "429"

    with pytest.raises(RateLimitError):
        api._handle_openai_error(error)
```

### Testing Callbacks

```python
def test_callback_dispatched_to_main_thread(self):
    """Test that callbacks are dispatched to main thread."""
    with patch('vox.hotkey.AppKit') as mock_appkit:
        mock_queue = MagicMock()
        mock_appkit.NSOperationQueue.mainQueue.return_value = mock_queue

        # Trigger callback
        result = manager._handle_cg_event(None, kCGEventKeyDown, mock_event)

        # Verify dispatch
        mock_queue.addOperationWithBlock_.assert_called_once()

        # Execute the dispatched block
        dispatched_fn = mock_queue.addOperationWithBlock_.call_args[0][0]
        dispatched_fn()
        manager._callback.assert_called_once_with(RewriteMode.FIX_GRAMMAR)
```

### Testing Configuration Migration

```python
def test_migration_from_old_format(self, temp_config):
    """Test migration from old single-hotkey format."""
    # Write old-format config
    old_config = {
        "model": "gpt-4o",
        "hotkey_enabled": True,
        "hotkey_modifiers": "option",
        "hotkey_key": "v",
    }
    with open(temp_config.config_file, "w") as f:
        yaml.dump(old_config, f)

    # Reload to trigger migration
    temp_config.load()

    # Verify migration
    assert temp_config.hotkeys_enabled is True
    hk = temp_config.get_mode_hotkey("fix_grammar")
    assert hk == {"modifiers": "option", "key": "v"}
```

### Testing Singleton Reset

```python
def test_get_config_returns_singleton(self):
    """Test that get_config returns the same instance."""
    with patch("vox.config.Path.home", return_value=Path(tmpdir)):
        reset_config()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

def test_reset_config(self):
    """Test that reset_config creates a new instance."""
    with patch("vox.config.Path.home", return_value=Path(tmpdir)):
        reset_config()
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2
```

### Testing Thread Operations

```python
def test_background_thread_started(self):
    """Test that background thread is started during registration."""
    with patch('vox.hotkey.threading') as mock_threading:
        mock_thread = MagicMock()
        mock_threading.Thread.return_value = mock_thread

        manager.register_hotkey()

        # Verify thread was created with correct params
        mock_threading.Thread.assert_called_once_with(
            target=manager._run_tap_loop,
            name="VoxHotkeyTap",
            daemon=True,
        )
        mock_thread.start.assert_called_once()
```

---

## Coverage

### Running with Coverage

```bash
uv run pytest tests/ --cov=vox --cov-report=html
```

### Coverage Configuration

Coverage is configured in `pyproject.toml`:

```toml
[tool.pytest]
addopts = "--cov=vox --cov-report=term-missing"
```

### What to Test

1. **Public API** - All public functions and methods
2. **Edge Cases** - Empty strings, None values, boundary conditions
3. **Error Handling** - All custom exceptions
4. **Configuration** - Getters, setters, persistence, migration
5. **Threading** - Thread creation, main thread dispatch

### What Not to Test

1. **PyObjC internals** - Mock the framework calls
2. **Private methods** - Test through public interface
3. **Third-party code** - Trust the library

---

## Best Practices

### 1. Use Descriptive Test Names

```python
# Good
def test_set_mode_hotkey_empty_key(self, temp_config):
    """Test set_mode_hotkey with empty key (cleared shortcut)."""

# Avoid
def test_hotkey_1(self):
```

### 2. One Concept Per Test

```python
# Good - separate tests for different scenarios
def test_get_key_code_lowercase(self):
    assert get_key_code('a') == 0x00

def test_get_key_code_uppercase(self):
    assert get_key_code('A') == 0x00

# Avoid
def test_get_key_code(self):
    assert get_key_code('a') == 0x00
    assert get_key_code('A') == 0x00
    assert get_key_code('1') == 0x1D
```

### 3. Use Fixtures for Setup

```python
# Good - reusable fixture
@pytest.fixture
def temp_config(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("vox.config.Path.home", return_value=Path(tmpdir)):
            reset_config()
            yield Config()

def test_something(self, temp_config):
    # temp_config is already set up
```

### 4. Test Both Success and Failure Paths

```python
def test_register_hotkey_success(self):
    """Test successful registration."""
    result = manager.register_hotkey()
    assert result is True

def test_register_hotkey_no_permission(self):
    """Test registration without permission."""
    with patch('vox.hotkey.has_accessibility_permission', return_value=False):
        result = manager.register_hotkey()
        assert result is False
```

### 5. Clean Up in Tests

```python
def test_with_cleanup(self):
    """Test that requires cleanup."""
    manager = HotKeyManager()
    try:
        manager.register_hotkey()
        # assertions
    finally:
        manager.unregister_hotkey()
```

---

## Debugging Tests

### Print Debug Output

```python
def test_something(self, capsys):
    """Test with captured output."""
    # Code that prints
    print("Debug message", flush=True)

    captured = capsys.readouterr()
    assert "Debug message" in captured.out
```

### Using pdb

```python
def test_something(self):
    """Test with debugger."""
    import pdb; pdb.set_trace()
    # Debugger will stop here
```

### Verbose Output

```bash
uv run pytest tests/ -v -s
```

The `-s` flag shows print statements during test execution.
