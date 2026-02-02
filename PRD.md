# Vox - Product Requirements Document

## Overview
A macOS desktop application that provides AI-powered text rewriting through contextual menu integration. Users select text in any app, right-click, and choose from various AI rewrite presets.

## Core Features

### 1. Contextual Menu Integration
- **Integration Type**: macOS Services API (`NSServices`)
  - This is the native macOS mechanism for text processing services
  - Appears in contextual menus when text is selected across all apps
  - Note: Finder Sync Extensions only work in Finder, not other apps
- **Menu Structure**: Single "Rewrite with Vox" submenu containing all preset options
- **Visibility**: Only appears when text is selected

### 2. Rewrite Presets
Four preset modes available in the contextual menu:
| Preset | Description |
|--------|-------------|
| Fix Grammar | Correct spelling, grammar, and punctuation |
| Professional | Make text formal and business-appropriate |
| Concise | Shorten text while preserving meaning |
| Friendly | Make tone warm and casual |

### 3. Text Replacement Behavior
- **Method**: Replace selected text in-place
- **Undo**: Fully undoable via Cmd+Z in the host application
- **Language**: Auto-detect language (not English-only)

### 4. User Feedback
- **Loading State**: Toast popup appears near mouse cursor during API call
- **Success**: Silent replacement
- **Error**: macOS notification banner explaining the error

### 5. Menu Bar App
- Menu bar icon for accessing settings
- Quick access to:
  - API key configuration
  - OpenAI model selection
  - Auto-start toggle
  - About/Quit

## Technical Requirements

### Stack (Recommended)
- **Language**: Python 3.11+
- **Package Manager**: uv or pip
- **UI Framework**: PyObjC (AppKit bindings) for native macOS APIs
- **API**: OpenAI Python SDK
- **Build System**: py2app for creating .app bundles

### Why Python Works for This Use Case
PyObjC has mature, battle-tested support for macOS Services API:

| Capability | PyObjC Support | Notes |
|------------|----------------|-------|
| **NSServices** | ✅ Fully supported | [SimpleService example](https://pyobjc.readthedocs.io/en/latest/examples/Cocoa/AppKit/SimpleService/) in official docs |
| **NSPasteboard** | ✅ Fully supported | Read/write text for replacement |
| **NSStatusItem** | ✅ Fully supported | Menu bar apps via PyObjC |
| **NSUserNotification** | ✅ Fully supported | Error banners/toasts |
| **Keychain Access** | ✅ Via `security` bindings | Secure API key storage |
| **Performance** | ✅ Adequate | Service calls are I/O bound (API latency), not CPU bound |
| **Distribution** | ✅ py2app | Creates standalone .app bundles |

### Rationale: Python over Swift
Since you know Python and TypeScript:
- **Faster development**: No need to learn a new language
- **PyObjC is mature**: Actively maintained with full AppKit coverage
- **Proven pattern**: SimpleService example shows exactly how to implement text transformation services
- **API integration**: OpenAI Python SDK is first-party and well-maintained

### macOS Integration
- **Contextual Menu**: macOS Services API via PyObjC
  - Use `NSRegisterServicesProvider` to register service handlers
  - Configure `NSServices` in `setup.py` (py2app plist)
  - Text passed via `NSPasteboard`; write back transformed text
  - Automatically integrates with host app's undo system
- **Menu Bar App**: `NSStatusItem` via PyObjC
- **Notifications**: `NSUserNotificationCenter` for error banners
- **Toast Popup**: Custom `NSWindow` with `NSPanel` behavior positioned near cursor
- **Storage**: Keychain via Python `keyring` library or `security` command

### Packaging
- **Format**: .app bundle via py2app
- **Distribution**: Drag-and-drop installation to /Applications
- **Code Signing**: Can be signed with `codesign` tool

### Configuration
- **Location**: `~/Library/Application Support/Vox/config.yml`
- **Settings**:
  - OpenAI API key (stored in Keychain for security)
  - OpenAI model (configurable: gpt-4o, gpt-4o-mini, etc.)
  - Auto-start at login (via launch agent)
  - Toast position preference (optional)

## User Experience

### Primary Flow
1. User selects text in any application
2. User right-clicks to open contextual menu
3. User navigates to "Rewrite with Vox" → chooses preset
4. Toast appears near cursor: "Rewriting with Vox..."
5. API call processes the text
6. Original selection is replaced with rewritten text
7. Toast disappears
8. User can Cmd+Z to undo if desired

### Error States
| Error | Behavior |
|-------|----------|
| No API key | Notification: "Please set your OpenAI API key in Vox settings" |
| Network failure | Notification: "Network error - check your connection" |
| Rate limit | Notification: "OpenAI rate limit reached - please wait" |
| Invalid key | Notification: "Invalid API key - check Vox settings" |
| API error | Notification: "Vox error: [error message]" |

## Non-Requirements (Explicitly Out of Scope)
- Windows or Linux support (macOS only)
- Custom user-defined rewrite prompts (MVP: presets only)
- Hotkey-based triggers (contextual menu only)
- Streaming text replacement (wait for complete response)
- Text length limits (user discretion, no artificial limits)

## Success Criteria
- [ ] Contextual menu appears in all major macOS apps (Safari, Notes, Mail, Messages, etc.)
- [ ] Text replacement is undoable in host applications
- [ ] API calls complete within 3 seconds for typical text (under 500 words)
- [ ] App uses < 100MB RAM when idle (reasonable for Python + PyObjC)
- [ ] Toast notifications are non-intrusive and auto-dismiss
- [ ] Settings changes are applied immediately (service may need `pbs -flush` once)
- [ ] Service registration works via `NSUpdateDynamicServices()`

## Open Questions
- Should we add a "retry" option in the menu bar when an API call fails?
- Should usage statistics (tokens used, cost) be displayed anywhere?
- Should we support multiple API keys for different users on the same machine?
