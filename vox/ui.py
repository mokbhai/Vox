"""
Menu bar application for Vox.

Provides a menu bar icon with access to settings and configuration.
"""
import objc
import AppKit
import Foundation
from PyObjCTools import AppHelper
from typing import Optional
import time

# Import Quartz.CoreGraphics for CGEvent functions
from Quartz.CoreGraphics import (
    CGEventSourceCreate,
    CGEventCreateKeyboardEvent,
    CGEventSetFlags,
    CGEventPost,
    kCGEventSourceStateCombinedSessionState,
    kCGSessionEventTap,
    kCGEventFlagMaskCommand,
)

from vox.config import get_config
from vox.api import RewriteMode, RewriteAPI, APIKeyError, NetworkError, RateLimitError, RewriteError
from vox.service import ServiceProvider
from vox.notifications import ToastManager, ErrorNotifier
from vox.hotkey import create_hotkey_manager


def show_settings_dialog(callback, config):
    """Show settings dialog using NSAlert with custom view."""
    alert = AppKit.NSAlert.alloc().init()
    alert.setMessageText_("Vox Settings")
    alert.setInformativeText_("Configure your OpenAI settings below.")
    alert.setAlertStyle_(AppKit.NSAlertStyleInformational)

    # Get current values
    current_key = config.get_api_key() or ""
    current_model = config.model or "gpt-4o-mini"
    current_url = config.base_url or ""
    current_auto_start = config.auto_start
    current_hotkey_enabled = config.hotkey_enabled
    current_hotkey_modifiers = config.hotkey_modifiers
    current_hotkey_key = config.hotkey_key

    # Create container for all fields (increased height for hot key settings)
    container = AppKit.NSView.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, 0, 380, 325)
    )

    y_offset = 305

    # API Key
    api_label = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, y_offset, 100, 20)
    )
    api_label.setStringValue_("API Key:")
    api_label.setBezeled_(False)
    api_label.setDrawsBackground_(False)
    api_label.setEditable_(False)
    api_label.setSelectable_(False)
    api_label.setAlignment_(AppKit.NSTextAlignmentRight)
    container.addSubview_(api_label)

    api_field = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(110, y_offset, 260, 24)
    )
    api_field.setStringValue_(current_key)
    api_field.setPlaceholderString_("sk-...")
    api_field.setEditable_(True)
    api_field.setSelectable_(True)
    container.addSubview_(api_field)

    y_offset -= 35

    # Model
    model_label = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, y_offset, 100, 20)
    )
    model_label.setStringValue_("Model:")
    model_label.setBezeled_(False)
    model_label.setDrawsBackground_(False)
    model_label.setEditable_(False)
    model_label.setSelectable_(False)
    model_label.setAlignment_(AppKit.NSTextAlignmentRight)
    container.addSubview_(model_label)

    model_field = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(110, y_offset, 260, 24)
    )
    model_field.setStringValue_(current_model)
    model_field.setPlaceholderString_("gpt-4o-mini")
    model_field.setEditable_(True)
    model_field.setSelectable_(True)
    container.addSubview_(model_field)

    y_offset -= 35

    # Base URL
    url_label = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, y_offset, 100, 20)
    )
    url_label.setStringValue_("Base URL:")
    url_label.setBezeled_(False)
    url_label.setDrawsBackground_(False)
    url_label.setEditable_(False)
    url_label.setSelectable_(False)
    url_label.setAlignment_(AppKit.NSTextAlignmentRight)
    container.addSubview_(url_label)

    url_field = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(110, y_offset, 260, 24)
    )
    url_field.setStringValue_(current_url)
    url_field.setPlaceholderString_("https://api.openai.com/v1")
    url_field.setEditable_(True)
    url_field.setSelectable_(True)
    container.addSubview_(url_field)

    y_offset -= 35

    # Launch at login checkbox
    auto_label = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, y_offset, 100, 20)
    )
    auto_label.setStringValue_("Startup:")
    auto_label.setBezeled_(False)
    auto_label.setDrawsBackground_(False)
    auto_label.setEditable_(False)
    auto_label.setSelectable_(False)
    auto_label.setAlignment_(AppKit.NSTextAlignmentRight)
    container.addSubview_(auto_label)

    auto_checkbox = AppKit.NSButton.alloc().initWithFrame_(
        Foundation.NSMakeRect(110, y_offset - 2, 150, 25)
    )
    auto_checkbox.setButtonType_(AppKit.NSSwitchButton)
    auto_checkbox.setTitle_("Launch at login")
    auto_checkbox.setState_(AppKit.NSControlStateValueOn if current_auto_start else AppKit.NSControlStateValueOff)
    container.addSubview_(auto_checkbox)

    y_offset -= 35

    # Separator for hot key section
    y_offset -= 10
    separator = AppKit.NSBox.alloc().initWithFrame_(Foundation.NSMakeRect(10, y_offset, 360, 1))
    separator.setBoxType_(AppKit.NSBoxSeparator)
    container.addSubview_(separator)

    y_offset -= 30

    # Hot Key section label
    hotkey_header = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, y_offset, 380, 20)
    )
    hotkey_header.setStringValue_("Hot Key")
    hotkey_header.setBezeled_(False)
    hotkey_header.setDrawsBackground_(False)
    hotkey_header.setEditable_(False)
    hotkey_header.setSelectable_(False)
    hotkey_header.setFont_(AppKit.NSFont.boldSystemFontOfSize_(13))
    container.addSubview_(hotkey_header)

    y_offset -= 30

    # Hot key enabled checkbox
    hotkey_enable_label = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, y_offset, 100, 20)
    )
    hotkey_enable_label.setStringValue_("Hot Key:")
    hotkey_enable_label.setBezeled_(False)
    hotkey_enable_label.setDrawsBackground_(False)
    hotkey_enable_label.setEditable_(False)
    hotkey_enable_label.setSelectable_(False)
    hotkey_enable_label.setAlignment_(AppKit.NSTextAlignmentRight)
    container.addSubview_(hotkey_enable_label)

    hotkey_enable_checkbox = AppKit.NSButton.alloc().initWithFrame_(
        Foundation.NSMakeRect(110, y_offset - 2, 150, 25)
    )
    hotkey_enable_checkbox.setButtonType_(AppKit.NSSwitchButton)
    hotkey_enable_checkbox.setTitle_("Enable hot key")
    hotkey_enable_checkbox.setState_(AppKit.NSControlStateValueOn if current_hotkey_enabled else AppKit.NSControlStateValueOff)
    container.addSubview_(hotkey_enable_checkbox)

    y_offset -= 35

    # Hot key modifiers
    hotkey_mod_label = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, y_offset, 100, 20)
    )
    hotkey_mod_label.setStringValue_("Modifiers:")
    hotkey_mod_label.setBezeled_(False)
    hotkey_mod_label.setDrawsBackground_(False)
    hotkey_mod_label.setEditable_(False)
    hotkey_mod_label.setSelectable_(False)
    hotkey_mod_label.setAlignment_(AppKit.NSTextAlignmentRight)
    container.addSubview_(hotkey_mod_label)

    hotkey_mod_field = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(110, y_offset, 260, 24)
    )
    hotkey_mod_field.setStringValue_(current_hotkey_modifiers)
    hotkey_mod_field.setPlaceholderString_("option, cmd+shift, etc.")
    hotkey_mod_field.setEditable_(True)
    hotkey_mod_field.setSelectable_(True)
    container.addSubview_(hotkey_mod_field)

    y_offset -= 35

    # Hot key key
    hotkey_key_label = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, y_offset, 100, 20)
    )
    hotkey_key_label.setStringValue_("Key:")
    hotkey_key_label.setBezeled_(False)
    hotkey_key_label.setDrawsBackground_(False)
    hotkey_key_label.setEditable_(False)
    hotkey_key_label.setSelectable_(False)
    hotkey_key_label.setAlignment_(AppKit.NSTextAlignmentRight)
    container.addSubview_(hotkey_key_label)

    hotkey_key_field = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(110, y_offset, 50, 24)
    )
    hotkey_key_field.setStringValue_(current_hotkey_key.upper())
    hotkey_key_field.setPlaceholderString_("V")
    hotkey_key_field.setEditable_(True)
    hotkey_key_field.setSelectable_(True)
    container.addSubview_(hotkey_key_field)

    hotkey_help = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(170, y_offset, 200, 20)
    )
    hotkey_help.setStringValue_("(e.g., V, R, etc.)")
    hotkey_help.setBezeled_(False)
    hotkey_help.setDrawsBackground_(False)
    hotkey_help.setEditable_(False)
    hotkey_help.setSelectable_(False)
    hotkey_help.setTextColor_(AppKit.NSColor.secondaryLabelColor())
    hotkey_help.setFont_(AppKit.NSFont.systemFontOfSize_(11))
    container.addSubview_(hotkey_help)

    alert.setAccessoryView_(container)

    alert.addButtonWithTitle_("Save")
    alert.addButtonWithTitle_("Cancel")

    # Activate app first
    AppKit.NSApp.activateIgnoringOtherApps_(True)

    response = alert.runModal()

    if response == AppKit.NSAlertFirstButtonReturn:
        api_key = api_field.stringValue().strip()
        model = model_field.stringValue().strip() or "gpt-4o-mini"
        base_url = url_field.stringValue().strip() or None
        auto_start = auto_checkbox.state() == AppKit.NSControlStateValueOn
        hotkey_enabled = hotkey_enable_checkbox.state() == AppKit.NSControlStateValueOn
        hotkey_modifiers = hotkey_mod_field.stringValue().strip() or "option"
        hotkey_key = hotkey_key_field.stringValue().strip().lower() or "v"

        if callback:
            callback(api_key, model, base_url, auto_start, hotkey_enabled, hotkey_modifiers, hotkey_key)


def show_about_dialog(hotkey_modifiers: str = "option", hotkey_key: str = "v"):
    """Show about dialog."""
    # Format hot key for display
    hotkey_display = f"{hotkey_modifiers.upper()}+{hotkey_key.upper()}"
    alert = AppKit.NSAlert.alloc().init()
    alert.setMessageText_("Vox")
    alert.setInformativeText_(
        "AI-powered text rewriting through macOS contextual menu.\n\n"
        "Version 0.1.0\n\n"
        f"Right-click any text to rewrite with AI.\n"
        f"Press {hotkey_display} with selected text for quick access."
    )
    alert.setAlertStyle_(AppKit.NSAlertStyleInformational)
    alert.addButtonWithTitle_("OK")
    AppKit.NSApp.activateIgnoringOtherApps_(True)
    alert.runModal()


class ModePickerDialog(AppKit.NSObject):
    """Dialog for selecting a rewrite mode when triggered via hot key."""

    def init(self):
        """Initialize the mode picker."""
        self = objc.super(ModePickerDialog, self).init()
        if self is None:
            return None
        self._callback = None
        self._selected_mode = None
        self._frontmost_app = None  # Store the frontmost app before showing dialog
        return self

    def show_mode_picker(self, callback):
        """
        Show a mode picker dialog.

        Args:
            callback: Function to call with selected RewriteMode.

        Returns:
            The frontmost app (NSRunningApplication) before the dialog was shown,
            or None if it couldn't be determined.
        """
        # Clear any previous callback to prevent memory leaks
        self._callback = None
        self._callback = callback
        self._selected_mode = None

        # Save the current frontmost application before showing dialog
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        self._frontmost_app = workspace.frontmostApplication()

        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Rewrite with Vox")
        alert.setInformativeText_("Choose a rewrite style:")
        alert.setAlertStyle_(AppKit.NSAlertStyleInformational)

        # Add buttons for each mode
        for mode, display_name in RewriteAPI.get_all_modes():
            alert.addButtonWithTitle_(display_name)

        # Add cancel button
        alert.addButtonWithTitle_("Cancel")

        # Activate app and show modal
        AppKit.NSApp.activateIgnoringOtherApps_(True)
        response = alert.runModal()

        # Map button response to mode
        # NSAlert returns NSAlertFirstButtonReturn (1000) for first button, 1001 for second, etc.
        button_index = response - AppKit.NSAlertFirstButtonReturn
        modes = list(RewriteMode)
        if 0 <= button_index < len(modes):
            self._selected_mode = modes[button_index]
            if self._callback:
                # Clear callback before calling to prevent memory leaks
                cb = self._callback
                self._callback = None
                cb(self._selected_mode)
        else:
            # Clear callback on cancel
            self._callback = None

        return self._frontmost_app


def get_selected_text() -> Optional[str]:
    """
    Get the currently selected text by simulating Cmd+C.

    Returns:
        The selected text, or None if no text was selected.
    """
    try:
        # Save current clipboard content
        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        saved_content = pasteboard.stringForType_(AppKit.NSPasteboardTypeString)

        # Simulate Cmd+C to copy selected text
        # We use CGEvent to simulate keypresses
        source = CGEventSourceCreate(kCGEventSourceStateCombinedSessionState)

        # Press Cmd
        cmd_down = CGEventCreateKeyboardEvent(
            source, 0x37, True  # 0x37 is Cmd key
        )
        # Press C
        c_down = CGEventCreateKeyboardEvent(
            source, 0x08, True  # 0x08 is C key
        )
        # Release C
        c_up = CGEventCreateKeyboardEvent(
            source, 0x08, False
        )
        # Release Cmd
        cmd_up = CGEventCreateKeyboardEvent(
            source, 0x37, False
        )

        # Set flags to include Cmd
        cmd_flags = kCGEventFlagMaskCommand
        CGEventSetFlags(c_down, cmd_flags)
        CGEventSetFlags(c_up, cmd_flags)

        # Send events
        CGEventPost(kCGSessionEventTap, cmd_down)
        time.sleep(0.01)
        CGEventPost(kCGSessionEventTap, c_down)
        time.sleep(0.01)
        CGEventPost(kCGSessionEventTap, c_up)
        time.sleep(0.01)
        CGEventPost(kCGSessionEventTap, cmd_up)

        # Wait a bit for the copy to complete
        time.sleep(0.05)

        # Get the copied text
        selected_text = pasteboard.stringForType_(AppKit.NSPasteboardTypeString)

        # Restore previous clipboard content
        if saved_content:
            pasteboard.clearContents()
            pasteboard.setString_forType_(saved_content, AppKit.NSPasteboardTypeString)

        return selected_text

    except Exception as e:
        print(f"Error getting selected text: {e}")
        import traceback
        traceback.print_exc()
        return None


def paste_text(text: str):
    """
    Paste text to the current application by simulating Cmd+V.

    Args:
        text: The text to paste.
    """
    try:
        # Set clipboard content
        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        pasteboard.clearContents()
        pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString)

        # Simulate Cmd+V to paste
        source = CGEventSourceCreate(kCGEventSourceStateCombinedSessionState)

        # Press Cmd
        cmd_down = CGEventCreateKeyboardEvent(
            source, 0x37, True
        )
        # Press V
        v_down = CGEventCreateKeyboardEvent(
            source, 0x09, True  # 0x09 is V key
        )
        # Release V
        v_up = CGEventCreateKeyboardEvent(
            source, 0x09, False
        )
        # Release Cmd
        cmd_up = CGEventCreateKeyboardEvent(
            source, 0x37, False
        )

        # Set flags to include Cmd
        cmd_flags = kCGEventFlagMaskCommand
        CGEventSetFlags(v_down, cmd_flags)
        CGEventSetFlags(v_up, cmd_flags)

        # Send events
        CGEventPost(kCGSessionEventTap, cmd_down)
        time.sleep(0.01)
        CGEventPost(kCGSessionEventTap, v_down)
        time.sleep(0.01)
        CGEventPost(kCGSessionEventTap, v_up)
        time.sleep(0.01)
        CGEventPost(kCGSessionEventTap, cmd_up)

    except Exception as e:
        print(f"Error pasting text: {e}")
        import traceback
        traceback.print_exc()


class MenuBarActions(AppKit.NSObject):
    """Simple object to handle menu actions."""

    def init(self):
        """Initialize."""
        self = objc.super(MenuBarActions, self).init()
        self.app = None  # Reference to MenuBarApp
        return self

    def showSettings_(self, sender):
        """Show settings."""
        print("DEBUG: showSettings called")
        if self.app:
            self.app._show_settings()

    def showAbout_(self, sender):
        """Show about."""
        print("DEBUG: showAbout called")
        if self.app:
            self.app._show_about()

    def quit_(self, sender):
        """Quit."""
        print("DEBUG: quit called")
        if self.app:
            self.app._quit()


class MenuBarApp:
    """Main menu bar application for Vox."""

    def __init__(self, service_provider: ServiceProvider):
        """
        Initialize the menu bar app.

        Args:
            service_provider: The service provider instance.
        """
        self.service_provider = service_provider
        self.config = get_config()

        # Create the application
        self.app = AppKit.NSApplication.sharedApplication()
        self.app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        # Create actions object (proper NSObject subclass for selectors)
        self.actions = MenuBarActions.alloc().init()
        self.actions.app = self

        # Create toast manager for notifications
        self._toast_manager = ToastManager()

        # Create mode picker dialog
        self._mode_picker = ModePickerDialog.alloc().init()

        # Create hot key manager
        self._hotkey_manager = create_hotkey_manager()
        self._hotkey_manager.set_callback(self._handle_hotkey)
        self._hotkey_manager.set_enabled(self.config.hotkey_enabled)
        self._hotkey_manager.set_hotkey(self.config.hotkey_modifiers, self.config.hotkey_key)

        # Create status item
        self._create_status_item()
        self._create_menu()

    def _create_status_item(self):
        """Create the status item in the menu bar."""
        status_bar = AppKit.NSStatusBar.systemStatusBar()
        self.status_item = status_bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)

        # Set icon (using a simple text icon for now)
        self.status_item.setTitle_("V")

        # Create menu
        self.menu = AppKit.NSMenu.alloc().init()
        self.status_item.setMenu_(self.menu)

    def _create_menu(self):
        """Create the menu items."""
        self.menu.removeAllItems()

        # Settings
        settings_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Settings...", "showSettings:", ""
        )
        settings_item.setTarget_(self.actions)
        self.menu.addItem_(settings_item)

        # Separator
        self.menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # About
        about_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "About Vox", "showAbout:", ""
        )
        about_item.setTarget_(self.actions)
        self.menu.addItem_(about_item)

        # Separator
        self.menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # Quit
        quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Vox", "quit:", "q"
        )
        quit_item.setTarget_(self.actions)
        self.menu.addItem_(quit_item)

    def _show_settings(self):
        """Show the settings dialog."""
        print("DEBUG: _show_settings called")
        try:
            show_settings_dialog(self._save_settings, self.config)
            print("DEBUG: dialog shown")
        except Exception as e:
            print(f"DEBUG: Error showing dialog: {e}")
            import traceback
            traceback.print_exc()

    def _save_settings(self, api_key: str, model: str, base_url: Optional[str], auto_start: bool,
                      hotkey_enabled: bool, hotkey_modifiers: str, hotkey_key: str):
        """Save the settings."""
        if api_key:
            self.config.set_api_key(api_key)
            self.service_provider.update_api_key()

        self.config.model = model
        self.config.base_url = base_url
        self.service_provider.update_model()

        if auto_start != self.config.auto_start:
            self.config.set_auto_start(auto_start)

        # Update hot key settings
        self.config.hotkey_enabled = hotkey_enabled
        self.config.hotkey_modifiers = hotkey_modifiers
        self.config.hotkey_key = hotkey_key

        # Re-register hot key with new settings
        self._hotkey_manager.set_enabled(hotkey_enabled)
        self._hotkey_manager.set_hotkey(hotkey_modifiers, hotkey_key)
        if hotkey_enabled:
            self._hotkey_manager.reregister_hotkey()

    def _show_about(self):
        """Show the about dialog."""
        show_about_dialog(self.config.hotkey_modifiers, self.config.hotkey_key)

    def _quit(self):
        """Quit the application."""
        AppKit.NSApp.terminate_(None)

    def _handle_hotkey(self):
        """Handle the hot key trigger."""
        print("Hot key triggered!")

        try:
            # Check if API key is configured
            api_key = self.config.get_api_key()
            if not api_key:
                ErrorNotifier.show_api_key_error()
                return

            # Get selected text
            text = get_selected_text()
            if not text or not text.strip():
                print("No text selected")
                return

            print(f"Selected text: {text!r}")

            # Store the text for use after mode selection
            # (selection might be lost after mode picker dialog closes)
            self._pending_rewrite_text = text

            # Show mode picker dialog and capture the frontmost app
            self._frontmost_app_before_picker = self._mode_picker.show_mode_picker(self._process_text_with_mode)

        except Exception as e:
            print(f"Error handling hot key: {e}")
            import traceback
            traceback.print_exc()

    def _process_text_with_mode(self, mode: RewriteMode):
        """
        Process the text with the selected mode.

        Args:
            mode: The rewrite mode to use.
        """
        if mode is None:
            print("Mode selection cancelled")
            return

        try:
            # Get API client
            api_key = self.config.get_api_key()
            if not api_key:
                ErrorNotifier.show_api_key_error()
                return

            api_client = RewriteAPI(api_key, self.config.model, self.config.base_url)

            # Use the stored text from when the hotkey was pressed
            # (selection is likely gone after mode picker dialog)
            text = getattr(self, '_pending_rewrite_text', None)
            if not text:
                print("No text to rewrite")
                return

            # Show loading toast
            mode_name = RewriteAPI.get_display_name(mode)
            self._toast_manager.show(f"{mode_name} with Vox...")

            # Allow the toast to render before blocking on API call
            AppKit.NSApp.currentEvent()  # Process any pending events
            time.sleep(0.01)  # Small delay to ensure UI updates

            # Process the text
            result = api_client.rewrite(text, mode)
            print(f"Rewritten text: {result!r}")

            # First, put the result in the clipboard (so manual paste works)
            pasteboard = AppKit.NSPasteboard.generalPasteboard()
            pasteboard.clearContents()
            pasteboard.setString_forType_(result, AppKit.NSPasteboardTypeString)

            # Try to restore focus to the previous app and paste
            frontmost_app = getattr(self, '_frontmost_app_before_picker', None)
            if frontmost_app and not frontmost_app.isTerminated():
                # Activate the previous app
                success = frontmost_app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)

                # Wait for the app to actually become frontmost before pasting
                if success:
                    workspace = AppKit.NSWorkspace.sharedWorkspace()
                    for _ in range(20):  # Max 1 second (20 * 0.05s)
                        current_frontmost = workspace.frontmostApplication()
                        if (current_frontmost and
                            current_frontmost.processIdentifier() == frontmost_app.processIdentifier()):
                            break
                        time.sleep(0.05)

            # Now paste the text
            paste_text(result)

            # Clear stored text
            self._pending_rewrite_text = None

            # Hide toast
            self._toast_manager.hide()

        except (APIKeyError, NetworkError, RateLimitError, RewriteError) as e:
            ErrorNotifier.show_generic_error(str(e))
            self._toast_manager.hide()
            self._pending_rewrite_text = None

        except Exception as e:
            print(f"Error processing text: {e}")
            import traceback
            traceback.print_exc()
            ErrorNotifier.show_generic_error(f"Error: {e}")
            self._toast_manager.hide()
            self._pending_rewrite_text = None

    def run(self):
        """Run the application."""
        # Register the service
        self.service_provider.register_services()

        # Register the hot key
        self._hotkey_manager.register_hotkey()

        # Run the app
        AppHelper.runEventLoop(installInterrupt=True)
