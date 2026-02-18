"""
Global hot key handling for Vox using Quartz CGEventTap.

Uses CGEventTapCreate on a dedicated background thread with its own CFRunLoop,
matching the proven pattern used by pynput's macOS keyboard listener.
"""
import threading

import AppKit
import Quartz
from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)


# CGEvent modifier flag constants
kCGEventFlagMaskCommand = Quartz.kCGEventFlagMaskCommand
kCGEventFlagMaskAlternate = Quartz.kCGEventFlagMaskAlternate
kCGEventFlagMaskControl = Quartz.kCGEventFlagMaskControl
kCGEventFlagMaskShift = Quartz.kCGEventFlagMaskShift
kCGEventKeyDown = Quartz.kCGEventKeyDown
kCGEventTapDisabledByTimeout = Quartz.kCGEventTapDisabledByTimeout
kCGEventTapDisabledByUserInput = Quartz.kCGEventTapDisabledByUserInput
kCGKeyboardEventKeycode = Quartz.kCGKeyboardEventKeycode
kCGKeyboardEventAutorepeat = Quartz.kCGKeyboardEventAutorepeat


def has_accessibility_permission() -> bool:
    """Check if Accessibility permission is granted."""
    try:
        return AXIsProcessTrusted()
    except Exception as e:
        print(f"Error checking accessibility permission: {e}")
        return False


def request_accessibility_permission() -> bool:
    """
    Request Accessibility permission from the user.

    Shows the system permission dialog if not already granted.
    """
    try:
        options = {kAXTrustedCheckOptionPrompt: True}
        return AXIsProcessTrustedWithOptions(options)
    except Exception as e:
        print(f"Error requesting accessibility permission: {e}")
        return False


# Key code mapping for common keys
KEY_CODES = {
    'a': 0x00, 'b': 0x0B, 'c': 0x08, 'd': 0x02, 'e': 0x0E,
    'f': 0x03, 'g': 0x05, 'h': 0x04, 'i': 0x22, 'j': 0x26,
    'k': 0x28, 'l': 0x25, 'm': 0x2E, 'n': 0x2D, 'o': 0x1F,
    'p': 0x23, 'q': 0x0C, 'r': 0x0F, 's': 0x01, 't': 0x11,
    'u': 0x20, 'v': 0x09, 'w': 0x0D, 'x': 0x07, 'y': 0x10,
    'z': 0x06,
    '0': 0x1D, '1': 0x12, '2': 0x13, '3': 0x14, '4': 0x15,
    '5': 0x17, '6': 0x16, '7': 0x1A, '8': 0x1C, '9': 0x19,
}

# Modifier flag constants (CGEvent values)
MODIFIER_FLAGS = {
    'cmd': kCGEventFlagMaskCommand,
    'command': kCGEventFlagMaskCommand,
    'option': kCGEventFlagMaskAlternate,
    'opt': kCGEventFlagMaskAlternate,
    'alt': kCGEventFlagMaskAlternate,
    'control': kCGEventFlagMaskControl,
    'ctrl': kCGEventFlagMaskControl,
    'shift': kCGEventFlagMaskShift,
}

# Mask covering all four modifier bits we check
ALL_MODIFIER_FLAGS_MASK = (
    kCGEventFlagMaskCommand
    | kCGEventFlagMaskAlternate
    | kCGEventFlagMaskControl
    | kCGEventFlagMaskShift
)


# Reverse mapping: key code -> character
KEY_CODE_TO_CHAR = {code: char for char, code in KEY_CODES.items()}

# Ordered list of (CGEvent flag, display symbol) for building shortcut strings
MODIFIER_SYMBOLS = [
    (kCGEventFlagMaskControl, "⌃"),
    (kCGEventFlagMaskAlternate, "⌥"),
    (kCGEventFlagMaskShift, "⇧"),
    (kCGEventFlagMaskCommand, "⌘"),
]


def format_hotkey_display(modifier_mask: int, key_char: str) -> str:
    """
    Format a hotkey combination as a symbol string like "⌘⌥V".

    Args:
        modifier_mask: Combined CGEvent modifier flags.
        key_char: The key character (e.g. "v").

    Returns:
        Display string with modifier symbols and uppercase key.
    """
    symbols = ""
    for flag, symbol in MODIFIER_SYMBOLS:
        if modifier_mask & flag:
            symbols += symbol
    return symbols + key_char.upper()


def modifier_mask_to_string(mask: int) -> str:
    """
    Convert a CGEvent modifier mask to a config-compatible string like "cmd+option".

    Args:
        mask: Combined CGEvent modifier flags.

    Returns:
        Plus-separated modifier names suitable for config storage.
    """
    flag_to_name = {
        kCGEventFlagMaskCommand: "cmd",
        kCGEventFlagMaskAlternate: "option",
        kCGEventFlagMaskControl: "control",
        kCGEventFlagMaskShift: "shift",
    }
    names = [name for flag, name in flag_to_name.items() if mask & flag]
    return "+".join(names) if names else "option"


def get_key_code(key_str: str) -> int:
    """Get key code for a key character."""
    key = key_str.lower()
    if len(key) == 0:
        return 0x09  # Default to V
    return KEY_CODES.get(key[0], 0x09)


def parse_modifiers(modifiers_str: str) -> int:
    """Parse modifier string to CGEvent flag mask."""
    mask = 0
    parts = modifiers_str.lower().replace(' ', '+').split('+')
    for part in parts:
        mask |= MODIFIER_FLAGS.get(part, 0)
    return mask


class HotKeyManager:
    """
    Manages global hot keys using Quartz CGEventTap.

    The event tap runs on a dedicated background thread with its own CFRunLoop,
    matching the pattern used by pynput's proven macOS keyboard listener.

    Supports multiple hotkey targets, each mapped to a RewriteMode.
    """

    def __init__(self):
        """Initialize the hot key manager."""
        self._callback = None
        self._enabled = True
        # List of (key_code, mod_mask, mode) tuples
        self._hotkey_targets = []
        self._is_registered = False
        # CGEventTap state
        self._tap = None
        self._tap_callback = None
        self._run_loop_source = None
        self._run_loop = None
        self._tap_thread = None

    def set_callback(self, callback):
        """Set the callback function. Called with (mode) argument."""
        self._callback = callback

    def set_hotkeys(self, configs):
        """Set multiple hotkey targets.

        Args:
            configs: List of (modifiers_str, key_str, mode) tuples.
                     Entries with empty key_str are skipped.
        """
        self._hotkey_targets = []
        for modifiers_str, key_str, mode in configs:
            if not key_str:
                continue
            key_code = get_key_code(key_str)
            mod_mask = parse_modifiers(modifiers_str)
            self._hotkey_targets.append((key_code, mod_mask, mode))

    def set_enabled(self, enabled: bool):
        """Enable or disable the hot keys."""
        self._enabled = enabled
        if not enabled and self._is_registered:
            self.unregister_hotkey()

    def register_hotkey(self) -> bool:
        """Register the global hot keys using CGEventTap."""
        if not self._enabled:
            return False

        if self._is_registered:
            return True

        if not self._hotkey_targets:
            print("No hotkey targets configured, skipping registration", flush=True)
            return False

        print(f"Accessibility permission: {has_accessibility_permission()}", flush=True)

        if not has_accessibility_permission():
            print("Requesting Accessibility permission...")
            request_accessibility_permission()
            if not has_accessibility_permission():
                self._show_accessibility_dialog()
                return False

        try:
            for key_code, mod_mask, mode in self._hotkey_targets:
                mod_str = modifier_mask_to_string(mod_mask)
                key_char = KEY_CODE_TO_CHAR.get(key_code, "?")
                print(
                    f"Registering hotkey: {mod_str}+{key_char} -> {mode.value} "
                    f"(key={key_code}, mod={mod_mask})",
                    flush=True,
                )

            # Build the callback
            def tap_callback(proxy, event_type, event, user_info):
                return self._handle_cg_event(proxy, event_type, event)

            self._tap_callback = tap_callback

            # Event mask: key down + modifier changes
            event_mask = (
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
                | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
                | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            )

            # Create the event tap
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                event_mask,
                tap_callback,
                None,
            )

            if tap is None:
                print(
                    "CGEventTapCreate returned None — Accessibility is granted, "
                    "likely missing Input Monitoring permission.",
                    flush=True,
                )
                self._show_input_monitoring_dialog()
                return False

            self._tap = tap

            # Create run loop source
            self._run_loop_source = Quartz.CFMachPortCreateRunLoopSource(
                None, tap, 0
            )

            # Start background thread with its own CFRunLoop
            self._tap_thread = threading.Thread(
                target=self._run_tap_loop,
                name="VoxHotkeyTap",
                daemon=True,
            )
            self._tap_thread.start()

            self._is_registered = True
            print(f"Hot keys registered ({len(self._hotkey_targets)} targets)", flush=True)
            return True

        except Exception as e:
            print(f"Error registering hot key: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _run_tap_loop(self):
        """Background thread running its own CFRunLoop for the event tap."""
        self._run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(
            self._run_loop,
            self._run_loop_source,
            Quartz.kCFRunLoopDefaultMode,
        )
        Quartz.CGEventTapEnable(self._tap, True)
        print("CGEventTap run loop started on background thread", flush=True)
        Quartz.CFRunLoopRun()
        print("CGEventTap run loop exited", flush=True)

    def _handle_cg_event(self, proxy, event_type, event):
        """Handle a CGEvent from the tap callback (runs on background thread)."""
        try:
            if event_type == kCGEventTapDisabledByTimeout:
                print("CGEventTap disabled by timeout — re-enabling", flush=True)
                Quartz.CGEventTapEnable(self._tap, True)
                return event

            if event_type == kCGEventTapDisabledByUserInput:
                return event

            if event_type != Quartz.kCGEventKeyDown:
                return event

            keycode = Quartz.CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)

            # Skip key-repeat events
            autorepeat = Quartz.CGEventGetIntegerValueField(event, kCGKeyboardEventAutorepeat)
            if autorepeat:
                return event

            # Check modifier flags
            flags = Quartz.CGEventGetFlags(event)
            relevant_flags = flags & ALL_MODIFIER_FLAGS_MASK

            # Check against all registered hotkey targets
            for target_key_code, target_modifiers, mode in self._hotkey_targets:
                if keycode == target_key_code and relevant_flags == target_modifiers:
                    if self._enabled and self._callback:
                        key_char = KEY_CODE_TO_CHAR.get(keycode, "?")
                        print(f"Hot key triggered: {mode.value} ({key_char})", flush=True)
                        # Capture mode in lambda default arg to avoid closure issues
                        AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                            lambda m=mode: self._callback(m)
                        )
                    return event

            return event

        except Exception as e:
            print(f"Error in CGEventTap callback: {e}")
            import traceback
            traceback.print_exc()
            return event

    def unregister_hotkey(self):
        """Unregister the hot key."""
        if not self._is_registered:
            return

        try:
            if self._tap:
                Quartz.CGEventTapEnable(self._tap, False)

            if self._run_loop:
                Quartz.CFRunLoopStop(self._run_loop)

            if self._tap_thread:
                self._tap_thread.join(timeout=2.0)

            self._tap = None
            self._tap_callback = None
            self._run_loop_source = None
            self._run_loop = None
            self._tap_thread = None
            self._is_registered = False
            print("Hot key unregistered")

        except Exception as e:
            print(f"Error unregistering hot key: {e}")

    def reregister_hotkey(self):
        """Re-register the hot key."""
        self.unregister_hotkey()
        return self.register_hotkey()

    def _show_accessibility_dialog(self):
        """Show dialog for Accessibility and Input Monitoring permissions."""
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Permissions Required")
        alert.setInformativeText_(
            "Vox needs two permissions to use global hot keys:\n\n"
            "1. Open System Settings → Privacy & Security\n"
            "2. Enable Accessibility for Vox (or Terminal in dev mode)\n"
            "3. Enable Input Monitoring for Vox (or Terminal in dev mode)\n\n"
            "Then restart Vox."
        )
        alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
        alert.addButtonWithTitle_("Open Accessibility")
        alert.addButtonWithTitle_("Open Input Monitoring")
        alert.addButtonWithTitle_("Cancel")

        AppKit.NSApp.activateIgnoringOtherApps_(True)

        response = alert.runModal()

        if response == AppKit.NSAlertFirstButtonReturn:
            AppKit.NSWorkspace.sharedWorkspace().openURL_(
                AppKit.NSURL.URLWithString_(
                    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
                )
            )
        elif response == AppKit.NSAlertSecondButtonReturn:
            AppKit.NSWorkspace.sharedWorkspace().openURL_(
                AppKit.NSURL.URLWithString_(
                    "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
                )
            )

    def _show_input_monitoring_dialog(self):
        """Show dialog for Input Monitoring permission."""
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Input Monitoring Permission Required")
        alert.setInformativeText_(
            "Vox needs Input Monitoring permission to detect global hot keys.\n\n"
            "1. Open System Settings\n"
            "2. Go to Privacy & Security → Input Monitoring\n"
            "3. Find Terminal or Vox and enable it\n\n"
            "Then restart Vox."
        )
        alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
        alert.addButtonWithTitle_("Open System Settings")
        alert.addButtonWithTitle_("Cancel")

        AppKit.NSApp.activateIgnoringOtherApps_(True)

        response = alert.runModal()

        if response == AppKit.NSAlertFirstButtonReturn:
            AppKit.NSWorkspace.sharedWorkspace().openURL_(
                AppKit.NSURL.URLWithString_(
                    "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
                )
            )


def create_hotkey_manager():
    """Factory function to create a hot key manager instance."""
    return HotKeyManager()
