"""
Notification system for Vox.

Provides toast popups near the cursor for loading state,
a top-of-screen loading bar with shimmer animation,
and macOS notification banners for errors.
"""
import objc
import AppKit
import Foundation
import Quartz
from typing import Optional


class ToastWindow(AppKit.NSWindow):
    """A small toast popup window that appears near the cursor."""

    _instance = None
    _text_field = objc.ivar()

    @classmethod
    def create(cls):
        """Create and initialize the toast window."""
        frame = Foundation.NSMakeRect(0, 0, 200, 50)
        window = cls.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        if window is None:
            return None

        # Configure appearance
        window.setTitle_("Vox")
        window.setOpaque_(False)
        window.setBackgroundColor_(AppKit.NSColor.colorWithDeviceWhite_alpha_(0.2, 0.9))
        # Use floating window level to appear above most windows
        window.setLevel_(AppKit.NSFloatingWindowLevel)

        # Create text field
        text_frame = Foundation.NSMakeRect(10, 10, 180, 30)
        window._text_field = AppKit.NSTextField.alloc().initWithFrame_(text_frame)
        window._text_field.setStringValue_("Rewriting with Vox...")
        window._text_field.setBezeled_(False)
        window._text_field.setDrawsBackground_(False)
        window._text_field.setEditable_(False)
        window._text_field.setSelectable_(False)
        window._text_field.setTextColor_(AppKit.NSColor.whiteColor())
        window._text_field.setAlignment_(AppKit.NSTextAlignmentCenter)
        window._text_field.setFont_(AppKit.NSFont.systemFontOfSize_(13))

        # Add text field to window
        content = AppKit.NSView.alloc().initWithFrame_(frame)
        window.setContentView_(content)
        window.contentView().addSubview_(window._text_field)

        # Round corners
        window.contentView().setWantsLayer_(True)
        layer = window.contentView().layer()
        if layer:
            layer.setCornerRadius_(10)

        return window

    def show_at_cursor(self):
        """Show the toast window near the mouse cursor."""
        mouse_location = AppKit.NSEvent.mouseLocation()
        window_height = self.frame().size.height

        x = mouse_location.x + 15
        y = mouse_location.y - window_height - 15

        self.setFrameTopLeftPoint_(Foundation.NSMakePoint(x, y))
        self.makeKeyAndOrderFront_(None)
        self.orderFrontRegardless()

    def hide(self):
        """Hide the toast window."""
        self.orderOut_(None)

    @classmethod
    def get_instance(cls):
        """Get the singleton toast window instance."""
        if cls._instance is None:
            cls._instance = cls.create()
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


class LoadingBar(AppKit.NSWindow):
    """A thin pill-shaped loading bar at the top center of the screen.

    Displays an animated shimmer sweep while the API call is in progress.
    Positioned just below the menu bar, it doesn't steal focus or block
    mouse events.
    """

    _instance = None

    BAR_WIDTH = 260
    BAR_HEIGHT = 5
    CORNER_RADIUS = 2.5
    TOP_OFFSET = 0  # flush with top edge of screen

    @classmethod
    def create(cls):
        """Create and initialize the loading bar window."""
        frame = Foundation.NSMakeRect(0, 0, cls.BAR_WIDTH, cls.BAR_HEIGHT)
        window = cls.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        if window is None:
            return None

        window.setTitle_("VoxLoading")
        window.setOpaque_(False)
        window.setHasShadow_(False)
        window.setBackgroundColor_(AppKit.NSColor.clearColor())
        # Status window level — above normal windows, below screen-saver
        window.setLevel_(AppKit.NSStatusWindowLevel + 1)
        window.setIgnoresMouseEvents_(True)
        window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
        )

        # Content view with layer backing
        content = AppKit.NSView.alloc().initWithFrame_(frame)
        content.setWantsLayer_(True)
        window.setContentView_(content)

        layer = content.layer()
        layer.setCornerRadius_(cls.CORNER_RADIUS)
        layer.setMasksToBounds_(True)
        # Subtle dark track
        layer.setBackgroundColor_(
            Quartz.CGColorCreateGenericRGB(0.3, 0.3, 0.4, 0.25)
        )

        # Shimmer gradient sublayer
        gradient = Quartz.CAGradientLayer.layer()
        gradient.setFrame_(Quartz.CGRectMake(0, 0, cls.BAR_WIDTH, cls.BAR_HEIGHT))
        gradient.setCornerRadius_(cls.CORNER_RADIUS)

        # Accent colour: vibrant blue glow
        clear = Quartz.CGColorCreateGenericRGB(0.3, 0.5, 1.0, 0.0)
        bright = Quartz.CGColorCreateGenericRGB(0.35, 0.65, 1.0, 1.0)
        gradient.setColors_([clear, bright, clear])
        gradient.setLocations_([0.0, 0.5, 1.0])
        gradient.setStartPoint_(Quartz.CGPointMake(0.0, 0.5))
        gradient.setEndPoint_(Quartz.CGPointMake(1.0, 0.5))

        layer.addSublayer_(gradient)
        window._gradient = gradient

        return window

    # -- positioning ---------------------------------------------------------

    def _position_top_center(self):
        """Place the bar at the top center of the main screen."""
        screen = AppKit.NSScreen.mainScreen()
        if screen is None:
            return
        screen_frame = screen.frame()
        x = screen_frame.origin.x + (screen_frame.size.width - self.BAR_WIDTH) / 2
        y = (screen_frame.origin.y + screen_frame.size.height
             - self.BAR_HEIGHT - self.TOP_OFFSET)
        self.setFrameOrigin_(Foundation.NSMakePoint(x, y))

    # -- animation -----------------------------------------------------------

    def _start_animation(self):
        """Start the repeating shimmer sweep."""
        gradient = getattr(self, '_gradient', None)
        if gradient is None:
            return

        anim = Quartz.CABasicAnimation.animationWithKeyPath_("locations")
        # Sweep: concentrated highlight moves left → right
        anim.setFromValue_([-0.3, -0.15, 0.0])
        anim.setToValue_([1.0, 1.15, 1.3])
        anim.setDuration_(1.0)
        anim.setRepeatCount_(float('inf'))
        anim.setTimingFunction_(
            Quartz.CAMediaTimingFunction.functionWithName_(
                Quartz.kCAMediaTimingFunctionEaseInEaseOut
            )
        )
        gradient.addAnimation_forKey_(anim, "shimmer")

    def _stop_animation(self):
        """Stop the shimmer animation."""
        gradient = getattr(self, '_gradient', None)
        if gradient is None:
            return
        gradient.removeAnimationForKey_("shimmer")

    # -- show / hide ---------------------------------------------------------

    def show(self):
        """Position at top center, show, and start animating."""
        self._position_top_center()
        self.orderFrontRegardless()
        self._start_animation()

    def hide(self):
        """Stop animating and hide the window."""
        self._stop_animation()
        self.orderOut_(None)

    # -- singleton -----------------------------------------------------------

    @classmethod
    def get_instance(cls):
        """Get the singleton loading bar instance."""
        if cls._instance is None:
            cls._instance = cls.create()
        return cls._instance


class LoadingBarManager:
    """Manages the top-of-screen loading bar."""

    def __init__(self):
        self._is_visible = False

    def show(self):
        """Show the loading bar."""
        bar = LoadingBar.get_instance()
        if bar:
            bar.show()
            self._is_visible = True

    def hide(self):
        """Hide the loading bar."""
        if self._is_visible:
            bar = LoadingBar.get_instance()
            if bar:
                bar.hide()
            self._is_visible = False

    def is_visible(self) -> bool:
        """Check if the loading bar is currently visible."""
        return self._is_visible
