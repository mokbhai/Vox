"""
Global hot key handling for Vox using NSEvent global monitors.

Monitors for configurable key combination globally.
"""
import AppKit
from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)


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
        if part == 'cmd' or part == 'command':
            mask |= AppKit.NSEventModifierFlagCommand
        elif part == 'option' or part == 'opt' or part == 'alt':
            mask |= AppKit.NSEventModifierFlagOption
        elif part == 'control' or part == 'ctrl':
            mask |= AppKit.NSEventModifierFlagControl
        elif part == 'shift':
            mask |= AppKit.NSEventModifierFlagShift

    return mask


class HotKeyManager:
    """
    Manages global hot key using Quartz CGEventTap.
    """

    def __init__(self):
        """Initialize the hot key manager."""
        self._callback = None
        self._event_monitor = None
        self._event_handler = None  # Keep reference to prevent GC
        self._enabled = True
        self._modifiers_str = "option"
        self._key_str = "v"
        self._target_key_code = 0
        self._target_modifiers = 0
        self._is_registered = False

    def set_callback(self, callback):
        """Set the callback function."""
        self._callback = callback

    def set_hotkey(self, modifiers: str, key: str):
        """Set the hot key combination."""
        self._modifiers_str = modifiers
        self._key_str = key

    def set_enabled(self, enabled: bool):
        """Enable or disable the hot key."""
        self._enabled = enabled
        if not enabled and self._is_registered:
            self.unregister_hotkey()

    def register_hotkey(self) -> bool:
        """Register the global hot key."""
        if not self._enabled:
            return False

        if self._is_registered:
            return True

        print(f"Accessibility permission: {has_accessibility_permission()}", flush=True)

        if not has_accessibility_permission():
            print("Requesting Accessibility permission...")
            request_accessibility_permission()

            import time
            time.sleep(1.0)

            if not has_accessibility_permission():
                self._show_accessibility_dialog()
                return False

        try:
            target_key_code = get_key_code(self._key_str)
            target_modifiers = parse_modifiers(self._modifiers_str)

            print(f"Setting up hot key monitor: {self._modifiers_str}+{self._key_str} (key={target_key_code}, mod={target_modifiers})", flush=True)

            # Store target values as instance attributes for callback access
            self._target_key_code = target_key_code
            self._target_modifiers = target_modifiers

            # Create event tap using NSEvent's global monitor
            # This is the recommended PyObjC approach
            # Note: Global monitors observe events but cannot consume them
            def event_handler(event):
                try:
                    # Get key code
                    key_code = event.keyCode()
                    flags = event.modifierFlags()

                    # Check key code first (cheap check)
                    if key_code != self._target_key_code:
                        return

                    # Check modifiers (mask out device-independent flags)
                    device_flags = flags & AppKit.NSEventModifierFlagDeviceIndependentFlagsMask

                    is_cmd = bool(device_flags & AppKit.NSEventModifierFlagCommand)
                    is_option = bool(device_flags & AppKit.NSEventModifierFlagOption)
                    is_control = bool(device_flags & AppKit.NSEventModifierFlagControl)
                    is_shift = bool(device_flags & AppKit.NSEventModifierFlagShift)

                    # Check if modifiers match
                    matches = True

                    # Check each target modifier
                    if self._target_modifiers & AppKit.NSEventModifierFlagCommand:
                        if not is_cmd:
                            matches = False
                    elif is_cmd:
                        matches = False

                    if self._target_modifiers & AppKit.NSEventModifierFlagOption:
                        if not is_option:
                            matches = False
                    elif is_option and (self._target_modifiers != 0):
                        matches = False

                    if self._target_modifiers & AppKit.NSEventModifierFlagControl:
                        if not is_control:
                            matches = False
                    elif is_control and (self._target_modifiers != 0):
                        matches = False

                    if self._target_modifiers & AppKit.NSEventModifierFlagShift:
                        if not is_shift:
                            matches = False
                    elif is_shift and (self._target_modifiers != 0):
                        matches = False

                    if matches and self._callback:
                        print(f"Hot key triggered: {self._modifiers_str}+{self._key_str}")
                        # Run callback on main thread
                        AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(self._callback)

                except Exception as e:
                    print(f"Error in hot key callback: {e}")
                    import traceback
                    traceback.print_exc()

            # Store handler reference to prevent GC
            self._event_handler = event_handler

            # Use addGlobalMonitorForEventsMatchingMask for global key monitoring
            # This requires Accessibility permission
            mask = AppKit.NSEventMaskKeyDown
            self._event_monitor = AppKit.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                mask,
                event_handler
            )

            if self._event_monitor is None:
                print("Failed to create global event monitor.")
                print("Make sure Vox has Accessibility permission.")
                print("Go to System Settings > Privacy & Security > Accessibility")
                self._show_accessibility_dialog()
                return False

            self._is_registered = True
            print(f"Hot key registered: {self._modifiers_str}+{self._key_str}", flush=True)
            return True

        except Exception as e:
            print(f"Error registering hot key: {e}")
            import traceback
            traceback.print_exc()
            return False

    def unregister_hotkey(self):
        """Unregister the hot key."""
        if not self._is_registered:
            return

        try:
            if self._event_monitor:
                AppKit.NSEvent.removeMonitor_(self._event_monitor)
                self._event_monitor = None

            self._event_handler = None
            self._is_registered = False
            print("Hot key unregistered")

        except Exception as e:
            print(f"Error unregistering hot key: {e}")

    def reregister_hotkey(self):
        """Re-register the hot key."""
        self.unregister_hotkey()
        return self.register_hotkey()

    def _show_accessibility_dialog(self):
        """Show dialog for Accessibility permission."""
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Accessibility Permission Required")
        alert.setInformativeText_(
            "Vox needs Accessibility permission to use global hot keys.\n\n"
            "1. Open System Settings\n"
            "2. Go to Privacy & Security → Accessibility\n"
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
                AppKit.NSURL.URLWithString_("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
            )


def create_hotkey_manager():
    """Factory function to create a hot key manager instance."""
    return HotKeyManager()
