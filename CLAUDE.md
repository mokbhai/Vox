# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation

Comprehensive documentation is available in the `docs/` directory. See **[docs/README.md](docs/README.md)** for an index.

| Document | Purpose |
|----------|---------|
| **[docs/PYTHON_PATTERNS.md](docs/PYTHON_PATTERNS.md)** | Python conventions, imports, type hints, properties, threading |
| **[docs/PYOBJC_GUIDE.md](docs/PYOBJC_GUIDE.md)** | PyObjC patterns, NSObject subclasses, Quartz events, Services API |
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | System design, data flows, module responsibilities |
| **[docs/TESTING.md](docs/TESTING.md)** | Test structure, mocking PyObjC, fixtures |
| **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** | Setup, common tasks, building, debugging |

**Important**: When making code changes, follow the patterns in `docs/PYTHON_PATTERNS.md` and `docs/PYOBJC_GUIDE.md`.

## Project Overview

Vox is a macOS menu bar application that provides AI-powered text rewriting through contextual menu integration. Users select text in any macOS app, right-click, and choose from AI rewrite presets (Fix Grammar, Professional, Concise, Friendly). The rewritten text replaces the selection in-place.

## Architecture

> See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

### Core Modules

- **`vox/main.py`** - Entry point; initializes both the menu bar app and service provider registration
- **`vox/service.py`** - macOS Services API integration via PyObjC; receives text from contextual menu and processes it
- **`vox/ui.py`** - Menu bar app with settings dialog; handles text selection/paste simulation using CGEvent; shows mode picker dialog; includes `EditableTextField` (fixes Cmd+C/V/X/A in NSAlert modals) and `HotkeyRecorderField` (captures keyboard shortcuts)
- **`vox/api.py`** - OpenAI API client; defines rewrite modes with system prompts; supports custom base URLs
- **`vox/config.py`** - Configuration management; stores settings in `~/Library/Application Support/Vox/config.yml`
- **`vox/notifications.py`** - Toast popups near cursor for loading state; macOS notification banners for errors
- **`vox/hotkey.py`** - Global hot key handling using Quartz CGEventTap; requires Accessibility permission; includes display helpers (`format_hotkey_display`, `modifier_mask_to_string`) for symbol-formatted shortcuts

### Data Flow

**Context Menu Flow**: User selects text → Right-click → "Rewrite with Vox" → Choose mode → `ServiceProvider` receives text via pasteboard → API call → Replace text in pasteboard → Toast notification

**Hot Key Flow**: User presses configured hot key with text selected → `HotKeyManager` detects → Simulates Cmd+C → Shows mode picker → Processes text → Simulates Cmd+V

### macOS Integration

- **Services API**: Registered via NSServices in `vox.spec`; appears in contextual menu across all apps
- **PyObjC**: Uses PyObjC for native macOS APIs (Cocoa, Quartz)
- **Permissions**: Accessibility required for global hot keys; Notification required for error banners
- **Auto-start**: Managed via Launch Agent at `~/Library/LaunchAgents/com.voxapp.rewrite.plist`

## Package Manager

Always use `uv` for Python package management:

```bash
# Install/sync dependencies
uv sync

# Run commands
uv run python main.py
uv run pytest tests/ -v
uv run ruff vox/

# Add packages
uv add <package>
uv add --dev <package>
```

## Commands

```bash
# Install dependencies
make sync  (alias for uv sync)

# Build the .app bundle
make build

# Install to /Applications
make install

# Run in development mode
make dev

# Flush services cache (required after service changes)
make flush

# Run tests
make test

# Lint code
make lint

# Format code
make fmt
```

## Development Notes

> See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for development setup and common tasks.

- After modifying service-related code, run `make flush` to refresh the macOS services cache
- Service may take 1-2 seconds to appear after first install
- The app runs with `LSUIElement: True` (no dock icon, only menu bar)
- Bundle identifier: `com.voxapp.rewrite`

## Code Patterns Quick Reference

### PyObjC NSObject Subclass

```python
class MyObject(AppKit.NSObject):
    def init(self):
        self = objc.super(MyObject, self).init()
        if self is None:
            return None
        # Initialize instance variables
        return self
```

### Service Method

```python
@objc.typedSelector(b"v@:@@o^@")
def myService_userData_error_(self, pasteboard, userData, error):
    # Handle service call
```

### Background Thread with Main Thread Dispatch

```python
def _do_work():
    result = api.call()
    AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
        lambda: self._handle_result(result)
    )

threading.Thread(target=_do_work, daemon=True).start()
```

### Configuration Property

```python
@property
def setting(self) -> str:
    return self._config.get("setting", DEFAULT_CONFIG["setting"])

@setting.setter
def setting(self, value: str):
    self._config["setting"] = value
    self.save()
```

See [docs/PYTHON_PATTERNS.md](docs/PYTHON_PATTERNS.md) and [docs/PYOBJC_GUIDE.md](docs/PYOBJC_GUIDE.md) for complete documentation.
