"""
Notification system for Vox.

Provides toast popups near the cursor for loading state
and macOS notification banners for errors.
"""
import AppKit
import Foundation
from PyObjCTools import AppHelper
from typing import Optional


class ToastWindow(AppKit.NSWindow):
    """A small toast popup window that appears near the cursor."""

    _instance: Optional["ToastWindow"] = None

    def __init__(self):
        """Initialize the toast window."""
        # Get the screen frame for positioning
        screen = AppKit.NSScreen.mainScreen()
        screen_frame = screen.visibleFrame()

        # Create a small panel window
        frame = Foundation.NSMakeRect(0, 0, 200, 50)

        super().__init__(
            frame,
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )

        # Configure appearance
        self.setTitle_("Vox")
        self.setOpaque_(False)
        self.setBackgroundColor_(AppKit.NSColor.colorWithDeviceWhite_alpha_(0.2, 0.9))
        self.setLevel_(AppKit.NSFloatingWindowLevel)

        # Create text field
        text_frame = Foundation.NSMakeRect(10, 10, 180, 30)
        self._text_field = AppKit.NSTextField.alloc().initWithFrame_(text_frame)
        self._text_field.setStringValue_("Rewriting with Vox...")
        self._text_field.setBezeled_(False)
        self._text_field.setDrawsBackground_(False)
        self._text_field.setEditable_(False)
        self._text_field.setSelectable_(False)
        self._text_field.setTextColor_(AppKit.NSColor.whiteColor())
        self._text_field.setAlignment_(AppKit.NSTextAlignmentCenter)
        self._text_field.setFont_(AppKit.NSFont.systemFontOfSize_(13))

        # Add text field to window
        self.setContentView_(AppKit.NSView.alloc().initWithFrame_(frame))
        self.contentView().addSubview_(self._text_field)

        # Round corners
        mask = self.contentView().wantsLayer()
        if mask:
            layer = self.contentView().layer()
            layer.setCornerRadius_(10)

    def show_at_cursor(self):
        """Show the toast window near the mouse cursor."""
        # Get mouse location
        mouse_location = AppKit.NSEvent.mouseLocation()

        # Calculate window position (above and to the right of cursor)
        window_width = self.frame().size.width
        window_height = self.frame().size.height

        x = mouse_location.x + 15
        y = mouse_location.y - window_height - 15

        # Position the window
        self.setFrameTopLeftPoint_(Foundation.NSMakePoint(x, y))
        self.makeKeyAndOrderFront_(None)
        self.orderFrontRegardless()

    def hide(self):
        """Hide the toast window."""
        self.orderOut_(None)

    @classmethod
    def get_instance(cls) -> "ToastWindow":
        """Get the singleton toast window instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class ErrorNotifier:
    """Handles error notifications via macOS Notification Center."""

    @staticmethod
    def show_error(title: str, message: str):
        """
        Show an error notification.

        Args:
            title: The notification title.
            message: The error message.
        """
        # Create a user notification
        notification = AppKit.NSUserNotification.alloc().init()
        notification.setTitle_(title)
        notification.setInformativeText_(message)
        notification.setSoundName_(AppKit.NSUserNotificationDefaultSoundName)

        # Deliver the notification
        center = AppKit.NSUserNotificationCenter.defaultUserNotificationCenter()
        center.deliverNotification_(notification)

    @staticmethod
    def show_api_key_error():
        """Show notification for missing API key."""
        ErrorNotifier.show_error(
            "Vox - API Key Required",
            "Please set your OpenAI API key in Vox settings"
        )

    @staticmethod
    def show_network_error():
        """Show notification for network error."""
        ErrorNotifier.show_error(
            "Vox - Network Error",
            "Network error - check your connection"
        )

    @staticmethod
    def show_rate_limit_error():
        """Show notification for rate limit."""
        ErrorNotifier.show_error(
            "Vox - Rate Limit",
            "OpenAI rate limit reached - please wait"
        )

    @staticmethod
    def show_invalid_key_error():
        """Show notification for invalid API key."""
        ErrorNotifier.show_error(
            "Vox - Invalid API Key",
            "Invalid API key - check Vox settings"
        )

    @staticmethod
    def show_generic_error(error_message: str):
        """Show a generic error notification."""
        ErrorNotifier.show_error(
            "Vox Error",
            error_message
        )


class ToastManager:
    """Manages the toast popup for loading state."""

    def __init__(self):
        """Initialize the toast manager."""
        self._toast: Optional[ToastWindow] = None
        self._is_visible = False

    def show(self, message: str = "Rewriting with Vox..."):
        """
        Show the toast popup near the cursor.

        Args:
            message: The message to display.
        """
        toast = ToastWindow.get_instance()
        toast._text_field.setStringValue_(message)
        toast.show_at_cursor()
        self._is_visible = True

    def hide(self):
        """Hide the toast popup."""
        if self._is_visible:
            toast = ToastWindow.get_instance()
            toast.hide()
            self._is_visible = False

    def is_visible(self) -> bool:
        """Check if toast is currently visible."""
        return self._is_visible
