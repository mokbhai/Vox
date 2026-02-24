# Vox - Makefile for building and development

.PHONY: all build clean install dev help test lint sync reset-perms

APP_NAME = Vox
BUILD_DIR = build
DIST_DIR = dist

# Default target
all: build

# Install/sync dependencies with uv
sync:
	uv sync

# Build the .app bundle
build:
	rm -rf $(BUILD_DIR) $(DIST_DIR)
	uv run pyinstaller vox.spec
	@if [ -d "$(DIST_DIR)/$(APP_NAME).app" ]; then \
		echo "Signing $(APP_NAME).app..."; \
		codesign --force --deep --sign - $(DIST_DIR)/$(APP_NAME).app; \
		echo "Build successful: $(DIST_DIR)/$(APP_NAME).app"; \
	else \
		echo "Build failed!"; \
		exit 1; \
	fi

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR) $(DIST_DIR) .venv
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.spec" -exec rm -rf {} + 2>/dev/null || true

# Install to /Applications
install: reset-perms build
	cp -R $(DIST_DIR)/$(APP_NAME).app /Applications/
	codesign --force --deep --sign - /Applications/$(APP_NAME).app
	@echo "Clearing icon cache..."
	touch /Applications/$(APP_NAME).app
	rm -rf ~/Library/Caches/com.apple.iconservices.store 2>/dev/null || true
	sudo rm -rf /Library/Caches/com.apple.iconservices.store 2>/dev/null || true
	@echo "Icon cache cleared. You may need to log out and back in for changes to take effect."

# Reset macOS permissions (Accessibility, Input Monitoring)
reset-perms:
	@./scripts/reset_permissions.sh

# Run in development mode (requires pbs -flush after changes)
dev: sync
	uv run python main.py

# Flush services cache (required after service changes)
flush:
	killall cfprefsd 2>/dev/null || true
	/System/Library/CoreServices/pbs -flush

# Run tests
test: sync
	uv run pytest tests/ -v

# Lint code
lint:
	uv run ruff vox/
	uv run mypy vox/

# Format code
fmt:
	uv run ruff format vox/

# Show help
help:
	@echo "Vox - AI-powered text rewriting"
	@echo ""
	@echo "Targets:"
	@echo "  sync        - Install dependencies with uv"
	@echo "  build       - Build the .app bundle (default)"
	@echo "  clean       - Remove build artifacts"
	@echo "  install     - Install to /Applications (resets permissions first)"
	@echo "  reset-perms - Reset macOS Accessibility/Input Monitoring permissions"
	@echo "  dev         - Run in development mode"
	@echo "  flush       - Flush macOS services cache"
	@echo "  test        - Run tests"
	@echo "  lint        - Lint code"
	@echo "  fmt         - Format code"
	@echo ""
	@echo "Installation:"
	@echo "  make sync && make install && make flush"
