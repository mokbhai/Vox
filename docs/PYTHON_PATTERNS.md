# Python Patterns and Conventions

This document describes the Python patterns and conventions used throughout the Vox codebase. Following these patterns ensures consistency and maintainability.

## Table of Contents

- [Import Organization](#import-organization)
- [Type Hints](#type-hints)
- [Properties and Setters](#properties-and-setters)
- [Singleton Pattern](#singleton-pattern)
- [Error Handling](#error-handling)
- [Threading Patterns](#threading-patterns)
- [Configuration Management](#configuration-management)
- [Factory Functions](#factory-functions)

---

## Import Organization

Imports are organized in three sections, separated by blank lines:

```python
# 1. Standard library
import sys
import threading
from pathlib import Path
from typing import Optional, Callable

# 2. Third-party libraries
import yaml
from openai import OpenAI, OpenAIError

# 3. Local imports
from vox.config import get_config
from vox.api import RewriteMode
```

### Standard Library Imports

- Use explicit imports (`from x import y`) for commonly used items
- Use module imports (`import x`) for less common usage
- Group related imports on the same line

```python
# Good
from typing import Optional, Callable, Dict, List

# Avoid
from typing import Optional
from typing import Callable
from typing import Dict
```

### PyObjC Imports

PyObjC imports follow a specific pattern:

```python
# Framework-level imports
import AppKit
import Foundation
import Quartz

# Specific functions from ApplicationServices
from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)
```

---

## Type Hints

All public functions and methods should have type hints.

### Function Signatures

```python
def get_api_key(self) -> Optional[str]:
    """Retrieve the OpenAI API key from config."""
    return self._config.get("api_key")

def set_mode_hotkey(self, mode_value: str, modifiers: str, key: str):
    """Set the hotkey for a specific mode."""
    ...
```

### Class Attributes

Use `objc.ivar()` for instance variables in PyObjC classes:

```python
class ToastWindow(AppKit.NSWindow):
    _instance = None
    _text_field = objc.ivar()  # PyObjC instance variable
```

### Optional Types

```python
from typing import Optional

def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
```

---

## Properties and Setters

Use `@property` decorators for configuration access with automatic persistence:

```python
class Config:
    @property
    def model(self) -> str:
        """Get the configured OpenAI model."""
        return self._config.get("model", DEFAULT_CONFIG["model"])

    @model.setter
    def model(self, value: str):
        """Set the OpenAI model."""
        self._config["model"] = value
        self.save()  # Auto-persist changes
```

### Benefits

1. Encapsulation of internal storage
2. Automatic validation and persistence
3. Clean API for callers
4. Default value handling

---

## Singleton Pattern

The codebase uses a module-level singleton pattern:

```python
# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config():
    """Reset the global configuration instance (mainly for testing)."""
    global _config
    _config = None
```

### Class-Level Singletons

For PyObjC classes, use class methods:

```python
class ToastWindow(AppKit.NSWindow):
    _instance = None

    @classmethod
    def get_instance(cls):
        """Get the singleton toast window instance."""
        if cls._instance is None:
            cls._instance = cls.create()
        return cls._instance
```

---

## Error Handling

### Custom Exception Hierarchy

Define a clear exception hierarchy:

```python
class RewriteError(Exception):
    """Base exception for rewrite errors."""
    pass


class APIKeyError(RewriteError):
    """Raised when API key is missing or invalid."""
    pass


class NetworkError(RewriteError):
    """Raised when network request fails."""
    pass


class RateLimitError(RewriteError):
    """Raised when API rate limit is reached."""
    pass
```

### Exception Conversion

Convert third-party exceptions to custom exceptions:

```python
def _handle_openai_error(self, error: OpenAIError):
    """Convert OpenAI errors to appropriate RewriteError types."""
    error_message = str(error).lower()
    error_code = getattr(error, "code", None)

    if error_code in ("invalid_api_key", "401"):
        raise APIKeyError("Invalid API key - check Vox settings")
    elif error_code == "429" or "rate" in error_message:
        raise RateLimitError("OpenAI rate limit reached - please wait")
    elif "connection" in error_message or "network" in error_message:
        raise NetworkError("Network error - check your connection")
```

### Exception Handling in API Calls

```python
try:
    result = api_client.rewrite(text, mode)
except APIKeyError:
    ErrorNotifier.show_invalid_key_error()
    self._toast_manager.hide()
except NetworkError:
    ErrorNotifier.show_network_error()
    self._toast_manager.hide()
except RewriteError as e:
    ErrorNotifier.show_generic_error(str(e))
    self._toast_manager.hide()
```

---

## Threading Patterns

### Background Thread for API Calls

Run API calls on background threads to keep UI responsive:

```python
def _process_text_directly(self, text: str, mode: RewriteMode):
    """Process text with the given mode directly."""
    # Show loading UI on main thread
    self._loading_bar.show()

    def _do_rewrite():
        try:
            result = api_client.rewrite(text, mode)
            # Dispatch back to main thread
            AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._finish_rewrite(result)
            )
        except RewriteError as exc:
            AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: self._fail_rewrite(str(exc))
            )

    threading.Thread(target=_do_rewrite, name="VoxRewrite", daemon=True).start()
```

### Background Thread with CFRunLoop

For event monitoring:

```python
def _run_tap_loop(self):
    """Background thread running its own CFRunLoop for the event tap."""
    self._run_loop = Quartz.CFRunLoopGetCurrent()
    Quartz.CFRunLoopAddSource(
        self._run_loop,
        self._run_loop_source,
        Quartz.kCFRunLoopDefaultMode,
    )
    Quartz.CGEventTapEnable(self._tap, True)
    Quartz.CFRunLoopRun()  # Blocks until stopped
```

### Threading Rules

1. **UI updates must happen on the main thread**
2. Use `NSOperationQueue.mainQueue().addOperationWithBlock_()` to dispatch to main thread
3. Use daemon threads for background tasks that should exit with the app
4. Name threads for debugging: `threading.Thread(target=fn, name="VoxRewrite", daemon=True)`

---

## Configuration Management

### Default Configuration Pattern

```python
DEFAULT_CONFIG = {
    "model": "gpt-4o-mini",
    "base_url": None,
    "auto_start": False,
    "hotkeys_enabled": True,
    "hotkeys": {
        "fix_grammar": {"modifiers": "cmd+shift", "key": "g"},
        "professional": {"modifiers": "cmd+shift", "key": "p"},
    },
}
```

### Merging User Configuration

```python
def load(self):
    """Load configuration from file, merging with defaults."""
    self._config = DEFAULT_CONFIG.copy()
    # Deep-copy nested dicts
    self._config["hotkeys"] = {
        k: dict(v) for k, v in DEFAULT_CONFIG["hotkeys"].items()
    }

    if self.config_file.exists():
        with open(self.config_file, "r") as f:
            user_config = yaml.safe_load(f) or {}
        self._config.update(user_config)
```

### Configuration Migration

Handle schema changes gracefully:

```python
# Migrate old single-hotkey format to per-mode format
if "hotkey_key" in user_config and "hotkeys" not in user_config:
    old_mod = user_config.pop("hotkey_modifiers", "cmd")
    old_key = user_config.pop("hotkey_key", "d")
    user_config["hotkeys"] = {...}
    user_config["hotkeys"]["fix_grammar"] = {
        "modifiers": old_mod,
        "key": old_key,
    }
```

---

## Factory Functions

Use factory functions for complex object creation:

```python
def create_hotkey_manager():
    """Factory function to create a hot key manager instance."""
    return HotKeyManager()
```

### Benefits

1. Hides implementation details
2. Allows for future dependency injection
3. Provides clear extension points
4. Simplifies testing with mocks
