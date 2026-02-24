# Vox Documentation

Welcome to the Vox documentation. This directory contains comprehensive guides for understanding, developing, and extending the Vox application.

## Documentation Index

| Document | Description |
|----------|-------------|
| [DEVELOPMENT.md](DEVELOPMENT.md) | Setting up the development environment, common tasks, building, and release process |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, data flows, and design decisions |
| [PYTHON_PATTERNS.md](PYTHON_PATTERNS.md) | Python conventions, patterns, and best practices used in the codebase |
| [PYOBJC_GUIDE.md](PYOBJC_GUIDE.md) | Guide for working with PyObjC and macOS APIs |
| [TESTING.md](TESTING.md) | Testing patterns, mocking PyObjC, and coverage |

## Quick Start

### For New Developers

1. Start with [DEVELOPMENT.md](DEVELOPMENT.md) to set up your environment
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system design
3. Review [PYTHON_PATTERNS.md](PYTHON_PATTERNS.md) for coding conventions

### For AI Agents

1. Read [../CLAUDE.md](../CLAUDE.md) first for project overview
2. Reference [PYTHON_PATTERNS.md](PYTHON_PATTERNS.md) for code patterns
3. Use [PYOBJC_GUIDE.md](PYOBJC_GUIDE.md) for macOS-specific APIs

### For Adding Features

1. Check [DEVELOPMENT.md](DEVELOPMENT.md) for common task patterns
2. Follow patterns in [PYTHON_PATTERNS.md](PYTHON_PATTERNS.md)
3. Add tests following [TESTING.md](TESTING.md)

## Key Concepts

### Module Overview

- **`main.py`** - Entry point; initializes menu bar app and services
- **`service.py`** - macOS Services API integration; contextual menu support
- **`ui.py`** - Menu bar app, settings UI, keyboard simulation
- **`api.py`** - OpenAI API client; rewrite modes and prompts
- **`config.py`** - Configuration management; settings persistence
- **`hotkey.py`** - Global hot key handling via Quartz CGEventTap
- **`notifications.py`** - Toast notifications, loading indicators
- **`preferences.py`** - Preferences window UI

### Data Flow

1. **Context Menu**: Select text → Right-click → Choose mode → API rewrite → Replace text
2. **Hot Keys**: Press shortcut → Copy selected text → API rewrite → Paste result

### Key Technologies

- **PyObjC** - Python-Objective-C bridge for macOS APIs
- **Quartz** - Core Graphics for event handling and keyboard simulation
- **OpenAI API** - Text transformation via GPT models
- **PyYAML** - Configuration file management

## Support

For issues or feature requests, please open an issue on the project repository.
