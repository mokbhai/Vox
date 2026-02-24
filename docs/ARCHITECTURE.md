# Vox Architecture

This document describes the high-level architecture of Vox, including module responsibilities, data flows, and key design decisions.

## Table of Contents

- [Overview](#overview)
- [Module Structure](#module-structure)
- [Data Flows](#data-flows)
- [Key Components](#key-components)
- [macOS Integration](#macos-integration)
- [Design Decisions](#design-decisions)

---

## Overview

Vox is a macOS menu bar application that provides AI-powered text rewriting through:

1. **Contextual Menu Integration** - Right-click any selected text to access rewrite modes
2. **Global Hot Keys** - Keyboard shortcuts that work in any application
3. **Menu Bar UI** - Settings and preferences accessible from the menu bar

```
┌─────────────────────────────────────────────────────────────┐
│                         Vox App                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Services   │    │   Hotkeys   │    │  Menu Bar   │     │
│  │  (service)  │    │  (hotkey)   │    │    (ui)     │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                │
│                     ┌──────▼──────┐                         │
│                     │  RewriteAPI │                         │
│                     │    (api)    │                         │
│                     └──────┬──────┘                         │
│                            │                                │
│                     ┌──────▼──────┐                         │
│                     │   Config    │                         │
│                     │  (config)   │                         │
│                     └─────────────┘                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Structure

### Core Modules

| Module | Responsibility |
|--------|---------------|
| `main.py` | Entry point; initializes menu bar app and services |
| `service.py` | macOS Services API integration; receives contextual menu calls |
| `ui.py` | Menu bar app, settings UI, keyboard simulation |
| `api.py` | OpenAI API client; rewrite modes and prompts |
| `config.py` | Configuration management; settings persistence |
| `notifications.py` | Toast notifications, loading indicators |
| `hotkey.py` | Global hot key handling via CGEventTap |
| `preferences.py` | Preferences window UI |

### Module Dependencies

```
main.py
    ├── service.py ──► api.py
    │       │          config.py
    │       └── notifications.py
    │
    └── ui.py ──► config.py
            │     hotkey.py
            │     api.py
            │     notifications.py
            │     preferences.py
            │     service.py
```

---

## Data Flows

### Context Menu Flow

```
User selects text in any app
        │
        ▼
User right-clicks → "Rewrite with Vox" → Choose mode
        │
        ▼
┌───────────────────────────────────────────┐
│  macOS calls ServiceProvider method:      │
│  fixGrammarService_userData_error_()      │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Read text from NSPasteboard              │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Show loading toast near cursor           │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Call RewriteAPI.rewrite(text, mode)      │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Write result back to NSPasteboard        │
└───────────────────────────────────────────┘
        │
        ▼
Text is replaced in the original app
```

### Hot Key Flow

```
User presses configured hot key (e.g., ⌘⇧G)
        │
        ▼
┌───────────────────────────────────────────┐
│  CGEventTap intercepts key event          │
│  (runs on background thread)              │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Dispatch to main thread via              │
│  NSOperationQueue.mainQueue()             │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Simulate Cmd+C to copy selected text     │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Show loading bar at top of screen        │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Start background thread for API call     │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  API call completes                       │
│  Dispatch result to main thread           │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  Simulate Cmd+V to paste rewritten text   │
└───────────────────────────────────────────┘
```

---

## Key Components

### ServiceProvider (`service.py`)

The `ServiceProvider` class bridges macOS Services to Vox's rewrite functionality.

```python
class ServiceProvider(AppKit.NSObject):
    def init(self):
        # Initialize API client lazily
        self._api_client = None

    @objc.typedSelector(b"v@:@@o^@")
    def fixGrammarService_userData_error_(self, pasteboard, userData, error):
        # Handle service call
```

**Responsibilities:**
- Register with NSApp as services provider
- Receive text from pasteboard
- Call RewriteAPI
- Write result back to pasteboard
- Show loading/error notifications

### MenuBarApp (`ui.py`)

The main application controller that manages the menu bar interface.

```python
class MenuBarApp:
    def __init__(self, service_provider):
        self.service_provider = service_provider
        self._hotkey_manager = create_hotkey_manager()
        self._loading_bar = LoadingBarManager()
```

**Responsibilities:**
- Create and manage status bar item
- Handle menu actions
- Coordinate hot key manager
- Process text from hot key triggers
- Show settings/preferences

### HotKeyManager (`hotkey.py`)

Manages global keyboard shortcuts using Quartz CGEventTap.

```python
class HotKeyManager:
    def register_hotkey(self) -> bool:
        # Create CGEventTap on background thread

    def _handle_cg_event(self, proxy, event_type, event):
        # Process keyboard events
```

**Responsibilities:**
- Register/unregister event taps
- Match key combinations
- Dispatch callbacks to main thread
- Handle permission requirements

### Config (`config.py`)

Manages application configuration with automatic persistence.

```python
class Config:
    @property
    def model(self) -> str:
        return self._config.get("model", DEFAULT_CONFIG["model"])

    @model.setter
    def model(self, value: str):
        self._config["model"] = value
        self.save()
```

**Responsibilities:**
- Load/save configuration from YAML
- Provide property-based access
- Handle configuration migration
- Manage API key storage

### RewriteAPI (`api.py`)

Wraps OpenAI API for text rewriting operations.

```python
class RewriteAPI:
    def rewrite(self, text: str, mode: RewriteMode) -> str:
        # Call OpenAI API with mode-specific prompt
```

**Responsibilities:**
- Manage OpenAI client
- Define rewrite modes and prompts
- Handle API errors
- Convert to custom exceptions

---

## macOS Integration

### Services Registration

Services are registered via the `NSServices` key in `vox.spec`:

```python
# In vox.spec (for PyInstaller)
info_plist = {
    'NSServices': [
        {
            'NSMenuItem': {'default': 'Fix Grammar with Vox'},
            'NSMessage': 'fixGrammarService',
            'NSPortName': 'Vox',
            'NSSendTypes': ['NSStringPboardType'],
        },
        # ... more services
    ],
}
```

### Event Tap Architecture

```
┌─────────────────────────────────────────┐
│           Background Thread             │
│  ┌─────────────────────────────────┐   │
│  │         CFRunLoop               │   │
│  │  ┌─────────────────────────┐    │   │
│  │  │     CGEventTap          │    │   │
│  │  │  (keyboard events)      │    │   │
│  │  └───────────┬─────────────┘    │   │
│  │              │                  │   │
│  │              ▼                  │   │
│  │  ┌─────────────────────────┐    │   │
│  │  │  NSOperationQueue       │    │   │
│  │  │  dispatch to main       │    │   │
│  │  └─────────────────────────┘    │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│            Main Thread                  │
│  ┌─────────────────────────────────┐   │
│  │     Callback Handler            │   │
│  │  - Get selected text            │   │
│  │  - Show loading                 │   │
│  │  - Start API thread             │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Permissions Required

| Permission | Purpose | API Used |
|------------|---------|----------|
| Accessibility | Global hot keys | `CGEventTapCreate` |
| Input Monitoring | Keyboard event interception | `CGEventTapCreate` |
| Notifications | Error banners | `NSUserNotificationCenter` |

---

## Design Decisions

### 1. Singleton Pattern for Config

**Decision:** Use module-level singleton for configuration.

**Rationale:**
- Configuration is read frequently throughout the app
- Avoids passing config instance through all layers
- Simplifies testing with `reset_config()`

```python
_config: Optional[Config] = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
```

### 2. Background Thread for API Calls

**Decision:** Run API calls on background threads, dispatch UI updates to main thread.

**Rationale:**
- Prevents UI freezing during network requests
- Allows Core Animation to continue rendering
- Follows macOS threading best practices

```python
def _do_rewrite():
    result = api_client.rewrite(text, mode)
    AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
        lambda: self._finish_rewrite(result)
    )

threading.Thread(target=_do_rewrite, daemon=True).start()
```

### 3. Separate Event Tap Thread

**Decision:** Run CGEventTap on its own thread with dedicated CFRunLoop.

**Rationale:**
- Matches pattern used by pynput (proven stable)
- Separates event monitoring from main event loop
- Allows clean shutdown via `CFRunLoopStop()`

### 4. Property-Based Configuration

**Decision:** Use Python properties with auto-save for configuration.

**Rationale:**
- Provides clean API for callers
- Ensures changes are persisted immediately
- Allows validation in setters

```python
@property
def model(self) -> str:
    return self._config.get("model", DEFAULT_CONFIG["model"])

@model.setter
def model(self, value: str):
    self._config["model"] = value
    self.save()  # Auto-persist
```

### 5. Custom Exception Hierarchy

**Decision:** Create custom exceptions for different error types.

**Rationale:**
- Allows specific error handling at call sites
- Enables user-friendly error messages
- Separates API errors from app errors

```python
try:
    result = api.rewrite(text, mode)
except APIKeyError:
    ErrorNotifier.show_api_key_error()
except NetworkError:
    ErrorNotifier.show_network_error()
```

### 6. Dual Input Methods

**Decision:** Support both Services menu and global hot keys.

**Rationale:**
- Services work without accessibility permissions
- Hot keys provide faster access for power users
- Both methods share the same rewrite logic

---

## File Locations

| File | Location |
|------|----------|
| Configuration | `~/Library/Application Support/Vox/config.yml` |
| Launch Agent | `~/Library/LaunchAgents/com.voxapp.rewrite.plist` |
| App Bundle | `/Applications/Vox.app` |

---

## Threading Model

```
┌─────────────────────────────────────────────────────────────┐
│                        Vox Process                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Main Thread                  Background Threads            │
│  ┌─────────────────┐          ┌─────────────────┐          │
│  │  NSRunLoop      │          │  HotKeyTap      │          │
│  │  - UI updates   │◄─────────│  - CGEventTap   │          │
│  │  - Menu events  │          │  - CFRunLoop    │          │
│  │  - Callbacks    │          └─────────────────┘          │
│  └────────┬────────┘                                       │
│           │                  ┌─────────────────┐          │
│           │                  │  RewriteWorker  │          │
│           │◄─────────────────│  - API calls    │          │
│           │                  │  - Network I/O  │          │
│           │                  └─────────────────┘          │
│           │                                                │
│           ▼                                                │
│  All UI updates must happen on main thread                 │
│  via NSOperationQueue.mainQueue()                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
