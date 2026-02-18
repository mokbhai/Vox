"""
Menu bar application for Vox.

Provides a menu bar icon with access to settings and configuration.
"""
import objc
import AppKit
import Foundation
from PyObjCTools import AppHelper
from typing import Optional
import threading
import time
import os
import sys

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
from vox.api import RewriteMode, RewriteAPI, APIKeyError, NetworkError, RateLimitError, RewriteError, DISPLAY_NAMES
from vox.service import ServiceProvider
from vox.notifications import LoadingBarManager, ErrorNotifier
from vox.hotkey import (
    create_hotkey_manager,
    KEY_CODE_TO_CHAR,
    MODIFIER_SYMBOLS,
    format_hotkey_display,
    modifier_mask_to_string,
    parse_modifiers,
)


def get_menu_bar_icon() -> Optional[AppKit.NSImage]:
    """
    Load the menu bar icon from the bundled resources or development path.

    Returns:
        NSImage configured as a template image, or None if not found.
    """
    # Try bundled location first (when running from .app)
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        icon_path = os.path.join(base_path, 'assets', 'menubar', 'menuIcon44.png')
    else:
        # Development mode - use the assets folder
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_path, 'assets', 'menubar', 'menuIcon44.png')

    if os.path.exists(icon_path):
        image = AppKit.NSImage.alloc().initWithContentsOfFile_(icon_path)
        if image:
            image.setSize_((18, 18))  # Standard menu bar icon size
            image.setTemplate_(True)  # Allows macOS to color it appropriately
            return image

    return None


class EditableTextField(AppKit.NSTextField):
    """NSTextField subclass that supports Cmd+C/V/X/A in NSAlert modal sessions.

    NSAlert's modal run loop intercepts key equivalents before they reach the
    field editor.  This subclass catches Cmd+C/V/X/A in performKeyEquivalent_
    and forwards them via NSApp.sendAction_to_from_() so clipboard operations
    work normally.
    """

    def performKeyEquivalent_(self, event):
        flags = event.modifierFlags()
        if flags & AppKit.NSEventModifierFlagCommand:
            chars = event.charactersIgnoringModifiers()
            action_map = {
                "c": "copy:",
                "v": "paste:",
                "x": "cut:",
                "a": "selectAll:",
            }
            action_sel = action_map.get(chars)
            if action_sel:
                return AppKit.NSApp.sendAction_to_from_(action_sel, None, self)
        return objc.super(EditableTextField, self).performKeyEquivalent_(event)


class HotkeyRecorderField(AppKit.NSTextField):
    """NSTextField subclass that records a keyboard shortcut.

    When focused it shows "Press shortcut..." and waits for a modifier+key
    combination.  While the user holds modifier keys it previews them as
    symbols (e.g. "⌘⌥...").  Once a valid key is pressed it stores the
    result and displays it (e.g. "⌘⌥V").

    Press Backspace, Delete, or Escape to clear the shortcut.

    After recording, `modifiers_mask` and `key_char` hold the raw values and
    `get_modifiers_string()` / `get_key_string()` return config-compatible
    strings.
    """

    def initWithFrame_(self, frame):
        self = objc.super(HotkeyRecorderField, self).initWithFrame_(frame)
        if self is None:
            return None
        self._modifiers_mask = 0
        self._key_char = ""
        self._recording = False
        self._original_value = ""
        return self

    # -- public API ----------------------------------------------------------

    def set_hotkey(self, modifiers_str, key_str):
        """Initialise from config strings (e.g. "cmd+option", "v")."""
        if not key_str:
            self._modifiers_mask = 0
            self._key_char = ""
            self.setStringValue_("None")
            return
        self._modifiers_mask = parse_modifiers(modifiers_str)
        self._key_char = key_str.lower()
        self.setStringValue_(format_hotkey_display(self._modifiers_mask, self._key_char))

    def get_modifiers_string(self):
        return modifier_mask_to_string(self._modifiers_mask)

    def get_key_string(self):
        return self._key_char.lower() if self._key_char else ""

    def is_assigned(self):
        """Return True if a shortcut key is assigned."""
        return bool(self._key_char)

    # -- focus / recording ---------------------------------------------------

    def becomeFirstResponder(self):
        result = objc.super(HotkeyRecorderField, self).becomeFirstResponder()
        if result:
            self._recording = True
            self._original_value = self.stringValue()
            self.setStringValue_("Press shortcut...")
        return result

    def resignFirstResponder(self):
        if self._recording:
            self._recording = False
            # Show current state
            if self._key_char:
                self.setStringValue_(format_hotkey_display(self._modifiers_mask, self._key_char))
            else:
                self.setStringValue_("None")
        return objc.super(HotkeyRecorderField, self).resignFirstResponder()

    # -- event handling ------------------------------------------------------

    def performKeyEquivalent_(self, event):
        if not self._recording:
            return objc.super(HotkeyRecorderField, self).performKeyEquivalent_(event)
        # Intercept everything while recording
        self._process_key_event(event)
        return True

    def keyDown_(self, event):
        if not self._recording:
            objc.super(HotkeyRecorderField, self).keyDown_(event)
            return
        self._process_key_event(event)

    def flagsChanged_(self, event):
        if not self._recording:
            objc.super(HotkeyRecorderField, self).flagsChanged_(event)
            return
        flags = event.modifierFlags()
        mask = 0
        for flag, _ in MODIFIER_SYMBOLS:
            if flags & flag:
                mask |= flag
        if mask:
            symbols = "".join(sym for f, sym in MODIFIER_SYMBOLS if mask & f)
            self.setStringValue_(symbols + "...")
        else:
            self.setStringValue_("Press shortcut...")

    # -- internal ------------------------------------------------------------

    def _process_key_event(self, event):
        keycode = event.keyCode()

        # Handle clear keys: Backspace (0x33), Delete (0x75), Escape (0x35)
        if keycode in (0x33, 0x75, 0x35):
            self._modifiers_mask = 0
            self._key_char = ""
            self._recording = False
            self.setStringValue_("None")
            if self.window():
                self.window().makeFirstResponder_(None)
            return

        char = KEY_CODE_TO_CHAR.get(keycode)
        if char is None:
            return  # ignore non-mapped keys (e.g. pure modifier press)

        flags = event.modifierFlags()
        mask = 0
        for flag, _ in MODIFIER_SYMBOLS:
            if flags & flag:
                mask |= flag

        if not mask:
            return  # require at least one modifier

        self._modifiers_mask = mask
        self._key_char = char
        self._recording = False
        self.setStringValue_(format_hotkey_display(mask, char))

        # Move focus away to signal completion
        if self.window():
            self.window().makeFirstResponder_(None)


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
    current_hotkeys_enabled = config.hotkeys_enabled

    # Create container for all fields
    container = AppKit.NSView.alloc().initWithFrame_(
        Foundation.NSMakeRect(0, 0, 380, 430)
    )

    y_offset = 410

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

    api_field = EditableTextField.alloc().initWithFrame_(
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

    model_field = EditableTextField.alloc().initWithFrame_(
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

    url_field = EditableTextField.alloc().initWithFrame_(
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
    hotkey_header.setStringValue_("Hot Keys")
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
    hotkey_enable_label.setStringValue_("")
    hotkey_enable_label.setBezeled_(False)
    hotkey_enable_label.setDrawsBackground_(False)
    hotkey_enable_label.setEditable_(False)
    hotkey_enable_label.setSelectable_(False)
    hotkey_enable_label.setAlignment_(AppKit.NSTextAlignmentRight)
    container.addSubview_(hotkey_enable_label)

    hotkey_enable_checkbox = AppKit.NSButton.alloc().initWithFrame_(
        Foundation.NSMakeRect(110, y_offset - 2, 200, 25)
    )
    hotkey_enable_checkbox.setButtonType_(AppKit.NSSwitchButton)
    hotkey_enable_checkbox.setTitle_("Enable hot keys")
    hotkey_enable_checkbox.setState_(AppKit.NSControlStateValueOn if current_hotkeys_enabled else AppKit.NSControlStateValueOff)
    container.addSubview_(hotkey_enable_checkbox)

    y_offset -= 35

    # Per-mode hotkey recorders
    hotkey_recorders = {}
    all_hotkeys = config.get_all_hotkeys()

    for mode in RewriteMode:
        mode_label = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(0, y_offset, 100, 20)
        )
        mode_label.setStringValue_(DISPLAY_NAMES[mode] + ":")
        mode_label.setBezeled_(False)
        mode_label.setDrawsBackground_(False)
        mode_label.setEditable_(False)
        mode_label.setSelectable_(False)
        mode_label.setAlignment_(AppKit.NSTextAlignmentRight)
        container.addSubview_(mode_label)

        recorder = HotkeyRecorderField.alloc().initWithFrame_(
            Foundation.NSMakeRect(110, y_offset, 120, 24)
        )
        hk = all_hotkeys.get(mode.value, {"modifiers": "", "key": ""})
        recorder.set_hotkey(hk["modifiers"], hk["key"])
        recorder.setEditable_(True)
        recorder.setSelectable_(True)
        container.addSubview_(recorder)

        hotkey_recorders[mode.value] = recorder
        y_offset -= 35

    # Help text
    shortcut_help = AppKit.NSTextField.alloc().initWithFrame_(
        Foundation.NSMakeRect(110, y_offset + 10, 260, 20)
    )
    shortcut_help.setStringValue_("Click field, press shortcut. Delete to clear.")
    shortcut_help.setBezeled_(False)
    shortcut_help.setDrawsBackground_(False)
    shortcut_help.setEditable_(False)
    shortcut_help.setSelectable_(False)
    shortcut_help.setTextColor_(AppKit.NSColor.secondaryLabelColor())
    shortcut_help.setFont_(AppKit.NSFont.systemFontOfSize_(11))
    container.addSubview_(shortcut_help)

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
        hotkeys_enabled = hotkey_enable_checkbox.state() == AppKit.NSControlStateValueOn

        # Collect per-mode hotkey configs
        hotkey_configs = {}
        for mode_value, recorder in hotkey_recorders.items():
            hotkey_configs[mode_value] = {
                "modifiers": recorder.get_modifiers_string(),
                "key": recorder.get_key_string(),
            }

        if callback:
            callback(api_key, model, base_url, auto_start, hotkeys_enabled, hotkey_configs)


def show_about_dialog(config):
    """Show about dialog with all assigned shortcuts."""
    all_hotkeys = config.get_all_hotkeys()

    # Build shortcut lines
    shortcut_lines = []
    for mode in RewriteMode:
        hk = all_hotkeys.get(mode.value, {"modifiers": "", "key": ""})
        if hk["key"]:
            mod_mask = parse_modifiers(hk["modifiers"])
            display = format_hotkey_display(mod_mask, hk["key"])
            shortcut_lines.append(f"  {display}  {DISPLAY_NAMES[mode]}")

    shortcuts_text = ""
    if shortcut_lines:
        shortcuts_text = "\n\nShortcuts:\n" + "\n".join(shortcut_lines)

    alert = AppKit.NSAlert.alloc().init()
    alert.setMessageText_("Vox")
    alert.setInformativeText_(
        "AI-powered text rewriting through macOS contextual menu.\n\n"
        "Version 0.1.0\n\n"
        f"Right-click any text to rewrite with AI."
        f"{shortcuts_text}"
    )
    alert.setAlertStyle_(AppKit.NSAlertStyleInformational)
    alert.addButtonWithTitle_("OK")
    AppKit.NSApp.activateIgnoringOtherApps_(True)
    alert.runModal()


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

        # Create loading bar for hotkey progress indication
        self._loading_bar = LoadingBarManager()

        # Create hot key manager
        self._hotkey_manager = create_hotkey_manager()
        self._hotkey_manager.set_callback(self._handle_hotkey)
        self._hotkey_manager.set_enabled(self.config.hotkeys_enabled)
        self._apply_hotkey_config()

        # Create status item
        self._create_status_item()
        self._create_menu()

    def _apply_hotkey_config(self):
        """Read all mode hotkeys from config and apply to the hotkey manager."""
        all_hotkeys = self.config.get_all_hotkeys()
        configs = []
        for mode in RewriteMode:
            hk = all_hotkeys.get(mode.value, {"modifiers": "", "key": ""})
            configs.append((hk["modifiers"], hk["key"], mode))
        self._hotkey_manager.set_hotkeys(configs)

    def _create_status_item(self):
        """Create the status item in the menu bar."""
        status_bar = AppKit.NSStatusBar.systemStatusBar()
        self.status_item = status_bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)

        # Try to use the custom icon, fall back to text "V" if not available
        icon = get_menu_bar_icon()
        if icon:
            self.status_item.button().setImage_(icon)
            self.status_item.button().setImageScaling_(AppKit.NSImageScaleProportionallyDown)
        else:
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
                      hotkeys_enabled: bool, hotkey_configs: dict):
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
        self.config.hotkeys_enabled = hotkeys_enabled
        for mode_value, hk in hotkey_configs.items():
            self.config.set_mode_hotkey(mode_value, hk["modifiers"], hk["key"])

        # Re-register hot keys with new settings
        self._hotkey_manager.set_enabled(hotkeys_enabled)
        self._apply_hotkey_config()
        if hotkeys_enabled:
            self._hotkey_manager.reregister_hotkey()

    def _show_about(self):
        """Show the about dialog."""
        show_about_dialog(self.config)

    def _quit(self):
        """Quit the application."""
        AppKit.NSApp.terminate_(None)

    def _handle_hotkey(self, mode: RewriteMode):
        """Handle a hot key trigger for a specific mode."""
        print(f"Hot key triggered for mode: {mode.value}")

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

            # Process directly — no popup needed
            self._process_text_directly(text, mode)

        except Exception as e:
            print(f"Error handling hot key: {e}")
            import traceback
            traceback.print_exc()

    def _process_text_directly(self, text: str, mode: RewriteMode):
        """
        Process text with the given mode directly (no dialog).

        The API call runs on a background thread so the main-thread run loop
        stays free and Core Animation can render the loading-bar shimmer.

        Args:
            text: The text to rewrite.
            mode: The rewrite mode to use.
        """
        api_key = self.config.get_api_key()
        if not api_key:
            ErrorNotifier.show_api_key_error()
            return

        api_client = RewriteAPI(api_key, self.config.model, self.config.base_url)

        # Show loading bar at top of screen (main thread)
        self._loading_bar.show()

        def _do_rewrite():
            try:
                result = api_client.rewrite(text, mode)
                print(f"Rewritten text: {result!r}")

                # Dispatch paste + hide back to the main thread
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._finish_rewrite(result)
                )
            except (APIKeyError, NetworkError, RateLimitError, RewriteError) as exc:
                msg = str(exc)
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._fail_rewrite(msg)
                )
            except Exception as exc:
                print(f"Error processing text: {exc}")
                import traceback
                traceback.print_exc()
                msg = f"Error: {exc}"
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._fail_rewrite(msg)
                )

        threading.Thread(target=_do_rewrite, name="VoxRewrite", daemon=True).start()

    def _finish_rewrite(self, result: str):
        """Called on the main thread after a successful rewrite."""
        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        pasteboard.clearContents()
        pasteboard.setString_forType_(result, AppKit.NSPasteboardTypeString)

        paste_text(result)
        self._loading_bar.hide()

    def _fail_rewrite(self, message: str):
        """Called on the main thread after a failed rewrite."""
        ErrorNotifier.show_generic_error(message)
        self._loading_bar.hide()

    def run(self):
        """Run the application."""
        # Register the service
        self.service_provider.register_services()

        # Register the hot key
        self._hotkey_manager.register_hotkey()

        # Run the app
        AppHelper.runEventLoop(installInterrupt=True)
