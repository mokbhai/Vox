# Vox - Makefile for building and development

.PHONY: all build clean install dev help test lint

APP_NAME = Vox
BUILD_DIR = build
DIST_DIR = dist

# Default target
all: build

# Build the .app bundle
build:
	python setup.py py2app

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR) $(DIST_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Install to /Applications
install: build
	cp -R $(DIST_DIR)/$(APP_NAME).app /Applications/

# Run in development mode (requires pbs -flush after changes)
dev:
	python main.py

# Flush services cache (required after service changes)
flush:
	killall cfprefsd 2>/dev/null || true
	/sbin/pbs -flush

# Run tests
test:
	python -m pytest tests/ -v

# Lint code
lint:
	python -m ruff vox/
	python -m mypy vox/

# Show help
help:
	@echo "Vox - AI-powered text rewriting"
	@echo ""
	@echo "Targets:"
	@echo "  all     - Build the .app bundle (default)"
	@echo "  build   - Build the .app bundle"
	@echo "  clean   - Remove build artifacts"
	@echo "  install - Install to /Applications"
	@echo "  dev     - Run in development mode"
	@echo "  flush   - Flush macOS services cache"
	@echo "  test    - Run tests"
	@echo "  lint    - Lint code"
	@echo ""
	@echo "Installation:"
	@echo "  make install && make flush"
