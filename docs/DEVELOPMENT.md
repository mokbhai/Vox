# Development Guide

This guide covers setting up the development environment, common development tasks, and best practices for contributing to Vox.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Common Tasks](#common-tasks)
- [Building](#building)
- [Debugging](#debugging)
- [Code Style](#code-style)
- [Release Process](#release-process)

---

## Getting Started

### Prerequisites

- macOS 12.0 or later
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/vox.git
cd vox

# Install dependencies
make sync
# or: uv sync
```

### Running in Development Mode

```bash
# Run the app directly
make dev
# or: uv run python vox/main.py
```

---

## Development Environment

### Project Structure

```
vox/
├── vox/                    # Main source code
│   ├── __init__.py
│   ├── main.py            # Entry point
│   ├── api.py             # OpenAI API client
│   ├── config.py          # Configuration management
│   ├── hotkey.py          # Global hot keys
│   ├── notifications.py   # Toast notifications
│   ├── preferences.py     # Preferences window
│   ├── service.py         # macOS Services
│   └── ui.py              # Menu bar UI
│
├── tests/                  # Test files
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_config.py
│   ├── test_hotkey.py
│   └── test_notifications.py
│
├── assets/                 # Static assets
│   ├── logo.svg
│   ├── logo.icns
│   └── menubar/
│       └── menuIcon44.png
│
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT.md
│   ├── PYOBJC_GUIDE.md
│   ├── PYTHON_PATTERNS.md
│   └── TESTING.md
│
├── scripts/               # Build/utility scripts
├── Makefile               # Common commands
├── pyproject.toml         # Project configuration
└── vox.spec               # PyInstaller spec
```

### Dependencies

Core dependencies (see `pyproject.toml`):

```toml
dependencies = [
    "cairosvg>=2.8.2",           # SVG to image conversion
    "openai>=2.16.0",            # OpenAI API
    "pyinstaller>=6.18.0",       # App bundling
    "pyobjc-core>=12.1",         # Python-ObjC bridge
    "pyobjc-framework-applicationservices>=12.1",
    "pyobjc-framework-cocoa>=12.1",
    "pyobjc-framework-quartz>=12.1",
    "pyyaml>=6.0.3",             # Configuration
]
```

Development dependencies:

```toml
[dependency-groups.dev]
dev = [
    "mypy>=1.19.1",              # Type checking
    "py2app>=0.28.8",            # Alternative bundler
    "pytest>=9.0.2",             # Testing
    "pytest-cov>=7.0.0",         # Coverage
    "ruff>=0.14.14",             # Linting/formatting
]
```

---

## Common Tasks

### Adding a New Rewrite Mode

1. **Define the mode in `api.py`:**

```python
class RewriteMode(Enum):
    """Available rewrite preset modes."""
    FIX_GRAMMAR = "fix_grammar"
    PROFESSIONAL = "professional"
    CONCISE = "concise"
    FRIENDLY = "friendly"
    NEW_MODE = "new_mode"  # Add new mode
```

2. **Add the system prompt:**

```python
SYSTEM_PROMPTS = {
    # ... existing prompts
    RewriteMode.NEW_MODE: (
        "You are a [description]. [Instructions]. "
        "Return only the [output] without explanations."
    ),
}
```

3. **Add display name:**

```python
DISPLAY_NAMES = {
    # ... existing names
    RewriteMode.NEW_MODE: "New Mode",
}
```

4. **Add service method in `service.py`:**

```python
@objc.typedSelector(b"v@:@@o^@")
def newModeService_userData_error_(self, pasteboard, userData, error):
    print("SERVICE CALLED: newModeService", flush=True)
    self._handle_service(pasteboard, RewriteMode.NEW_MODE)
```

5. **Add default hotkey in `config.py`:**

```python
DEFAULT_CONFIG = {
    # ...
    "hotkeys": {
        # ... existing hotkeys
        "new_mode": {"modifiers": "cmd+shift", "key": "n"},
    },
}
```

6. **Update `vox.spec` for Services registration:**

```python
'NSServices': [
    # ... existing services
    {
        'NSMenuItem': {'default': 'New Mode with Vox'},
        'NSMessage': 'newModeService',
        'NSPortName': 'Vox',
        'NSSendTypes': ['NSStringPboardType'],
    },
],
```

7. **Run `make flush` to refresh services cache.**

### Adding a New Configuration Option

1. **Add to `DEFAULT_CONFIG` in `config.py`:**

```python
DEFAULT_CONFIG = {
    # ... existing options
    "new_option": "default_value",
}
```

2. **Add property:**

```python
@property
def new_option(self) -> str:
    """Get the new option."""
    return self._config.get("new_option", DEFAULT_CONFIG["new_option"])

@new_option.setter
def new_option(self, value: str):
    """Set the new option."""
    self._config["new_option"] = value
    self.save()
```

3. **Add tests in `tests/test_config.py`:**

```python
def test_new_option_property(self, temp_config):
    """Test new_option property."""
    assert temp_config.new_option == "default_value"
    temp_config.new_option = "custom_value"
    assert temp_config.new_option == "custom_value"
```

---

## Building

### Build the App Bundle

```bash
make build
```

This creates `dist/Vox.app` using PyInstaller.

### Install to Applications

```bash
make install
```

Copies the built app to `/Applications/Vox.app`.

### Flush Services Cache

Required after modifying service-related code:

```bash
make flush
```

### Full Build Process

```bash
# Clean, build, flush, and install
make clean
make build
make flush
make install
```

---

## Debugging

### Enable Debug Output

Debug print statements use `flush=True`:

```python
print(f"DEBUG: value={value!r}", flush=True)
```

### Running with Console Output

```bash
# Run directly to see console output
uv run python vox/main.py
```

### Checking Service Registration

```python
print(f"Has selector: {self.respondsToSelector_('fixGrammarService:userData:error:')}")
```

### Checking Permissions

```python
print(f"Accessibility permission: {has_accessibility_permission()}", flush=True)
```

### Common Issues

#### Services Not Appearing

1. Run `make flush`
2. Wait 1-2 seconds
3. Restart the target application
4. Check that the service is registered in `vox.spec`

#### Hot Keys Not Working

1. Check Accessibility permission in System Settings
2. Check Input Monitoring permission
3. Look for error messages in console output

#### API Errors

1. Verify API key in settings
2. Check base URL configuration
3. Look for specific error messages (rate limit, network, etc.)

---

## Code Style

### Linting

```bash
make lint
# or: uv run ruff vox/
```

### Formatting

```bash
make fmt
# or: uv run ruff format vox/
```

### Type Checking

```bash
uv run mypy vox/
```

### Style Guidelines

1. **Line length:** 100 characters
2. **Target Python:** 3.11+
3. **Imports:** Standard library, third-party, local (separated by blank lines)
4. **Docstrings:** Use triple-quoted strings for modules, classes, and public methods
5. **Type hints:** Required for all public functions and methods

### Example Code Style

```python
"""
Module docstring describing the purpose of this module.
"""
import sys
from pathlib import Path
from typing import Optional

import AppKit
import yaml

from vox.config import get_config


class ExampleClass:
    """Brief description of the class.

    Longer description if needed.
    """

    def __init__(self, config: Optional[Config] = None):
        """Initialize the class.

        Args:
            config: Optional configuration instance.
        """
        self._config = config or get_config()

    def public_method(self, arg: str) -> str:
        """Brief description of the method.

        Args:
            arg: Description of the argument.

        Returns:
            Description of the return value.
        """
        return self._private_method(arg)

    def _private_method(self, arg: str) -> str:
        """Private methods also have docstrings."""
        return arg.upper()
```

---

## Release Process

### 1. Update Version

Edit `pyproject.toml`:

```toml
[project]
name = "vox"
version = "0.2.0"  # Update this
```

### 2. Update Changelog

Document changes in `CHANGELOG.md` (if it exists) or release notes.

### 3. Run Tests

```bash
make test
make lint
```

### 4. Build and Test

```bash
make clean
make build
make flush
make install

# Manual testing of installed app
open /Applications/Vox.app
```

### 5. Create Release

```bash
git tag v0.2.0
git push origin v0.2.0
```

### 6. Create DMG (Optional)

Use macOS tools to create a distributable DMG:

```bash
# Create DMG
hdiutil create -volname "Vox" \
    -srcfolder dist/Vox.app \
    -ov -format UDZO \
    dist/Vox-0.2.0.dmg
```

---

## Makefile Reference

| Command | Description |
|---------|-------------|
| `make sync` | Install/sync dependencies |
| `make dev` | Run in development mode |
| `make build` | Build the .app bundle |
| `make install` | Install to /Applications |
| `make flush` | Flush services cache |
| `make test` | Run tests |
| `make lint` | Run linter |
| `make fmt` | Format code |
| `make clean` | Clean build artifacts |

---

## Additional Resources

- [Python Patterns](PYTHON_PATTERNS.md) - Python conventions used in this project
- [PyObjC Guide](PYOBJC_GUIDE.md) - Working with macOS APIs
- [Architecture](ARCHITECTURE.md) - System architecture overview
- [Testing Guide](TESTING.md) - Testing patterns and best practices
- [CLAUDE.md](../CLAUDE.md) - Project overview for AI assistants
