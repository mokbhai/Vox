#!/bin/bash
# Reset macOS Accessibility and Input Monitoring permissions for Vox
# This ensures a clean permission state after reinstall

BUNDLE_ID="com.voxapp.rewrite"
APP_NAME="Vox"

echo "Resetting permissions for $APP_NAME..."

# Quit the app if running
if pgrep -x "$APP_NAME" > /dev/null 2>&1; then
    echo "Quitting $APP_NAME..."
    pkill -x "$APP_NAME" 2>/dev/null || true
    sleep 1
fi

# Reset TCC permissions (Accessibility, Input Monitoring, etc.)
# This requires admin privileges
echo "Resetting Accessibility and Input Monitoring permissions..."
echo "(You may be prompted for your password)"

# Reset Accessibility permissions
sudo tccutil reset Accessibility "$BUNDLE_ID" 2>/dev/null || true

# Reset all TCC permissions (includes Input Monitoring)
sudo tccutil reset All "$BUNDLE_ID" 2>/dev/null || true

echo "Permissions reset complete."
