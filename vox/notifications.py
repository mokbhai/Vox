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
    MENU_BAR_OFFSET = 25  # minimum offset for menu bar
    NOTCH_EXTRA = 10  # extra padding below notch

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
        """Place the bar at the top center of the main screen, below the notch/menu bar."""
        screen = AppKit.NSScreen.mainScreen()
        if screen is None:
            return
        screen_frame = screen.frame()

        # Start with menu bar offset
        offset = self.MENU_BAR_OFFSET

        # Add notch offset if present (macOS 12+)
        if hasattr(screen, 'safeAreaInsets'):
            insets = screen.safeAreaInsets()
            if insets.top > 0:
                # On notched displays, safeAreaInsets.top includes notch height
                offset = insets.top + self.NOTCH_EXTRA

        x = screen_frame.origin.x + (screen_frame.size.width - self.BAR_WIDTH) / 2
        y = (screen_frame.origin.y + screen_frame.size.height
             - self.BAR_HEIGHT - offset)
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


class RecordingToast(AppKit.NSWindow):
    """A toast window showing recording status with audio level indicator."""

    _instance = None
    _level_view = objc.ivar()
    _text_field = objc.ivar()
    _fill_view = objc.ivar()

    TOAST_WIDTH = 180
    TOAST_HEIGHT = 44
    LEVEL_WIDTH = 100
    LEVEL_HEIGHT = 6
    CORNER_RADIUS = 8

    @classmethod
    def create(cls):
        """Create and initialize the recording toast window."""
        frame = Foundation.NSMakeRect(0, 0, cls.TOAST_WIDTH, cls.TOAST_HEIGHT)
        window = cls.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        if window is None:
            return None

        window.setTitle_("VoxRecording")
        window.setOpaque_(False)
        window.setBackgroundColor_(AppKit.NSColor.clearColor())
        window.setLevel_(AppKit.NSFloatingWindowLevel)
        window.setIgnoresMouseEvents_(True)
        window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
        )

        # Create container view with rounded corners
        container = AppKit.NSView.alloc().initWithFrame_(frame)
        container.setWantsLayer_(True)
        layer = container.layer()
        layer.setCornerRadius_(cls.CORNER_RADIUS)
        layer.setBackgroundColor_(
            AppKit.NSColor.colorWithDeviceWhite_alpha_(0.15, 0.92).CGColor()
        )
        window.setContentView_(container)

        # Create text field
        text_frame = Foundation.NSMakeRect(
            (cls.TOAST_WIDTH - cls.LEVEL_WIDTH) / 2 - 10,
            24,
            cls.LEVEL_WIDTH + 20,
            18
        )
        window._text_field = AppKit.NSTextField.alloc().initWithFrame_(text_frame)
        window._text_field.setStringValue_("Recording...")
        window._text_field.setBezeled_(False)
        window._text_field.setDrawsBackground_(False)
        window._text_field.setEditable_(False)
        window._text_field.setSelectable_(False)
        window._text_field.setTextColor_(AppKit.NSColor.whiteColor())
        window._text_field.setAlignment_(AppKit.NSTextAlignmentCenter)
        window._text_field.setFont_(AppKit.NSFont.systemFontOfSize_(12, weight=0.5))
        container.addSubview_(window._text_field)

        # Create audio level bar (VU meter)
        level_x = (cls.TOAST_WIDTH - cls.LEVEL_WIDTH) / 2
        level_frame = Foundation.NSMakeRect(
            level_x, 10, cls.LEVEL_WIDTH, cls.LEVEL_HEIGHT
        )
        window._level_view = AppKit.NSView.alloc().initWithFrame_(level_frame)
        window._level_view.setWantsLayer_(True)
        level_layer = window._level_view.layer()
        level_layer.setCornerRadius_(cls.LEVEL_HEIGHT / 2)
        level_layer.setBackgroundColor_(
            AppKit.NSColor.colorWithWhite_alpha_(0.3, 1.0).CGColor()
        )
        container.addSubview_(window._level_view)

        # Create level fill bar
        fill_frame = Foundation.NSMakeRect(0, 0, 0, cls.LEVEL_HEIGHT)
        window._fill_view = AppKit.NSView.alloc().initWithFrame_(fill_frame)
        window._fill_view.setWantsLayer_(True)
        fill_layer = window._fill_view.layer()
        fill_layer.setCornerRadius_(cls.LEVEL_HEIGHT / 2)
        fill_layer.setBackgroundColor_(
            AppKit.NSColor.systemRedColor().CGColor()
        )
        window._level_view.addSubview_(window._fill_view)

        return window

    def _position_at_cursor(self):
        """Position the toast near the mouse cursor."""
        mouse_location = AppKit.NSEvent.mouseLocation()
        x = mouse_location.x + 15
        y = mouse_location.y - self.TOAST_HEIGHT - 15
        self.setFrameTopLeftPoint_(Foundation.NSMakePoint(x, y))

    def show_recording(self):
        """Show the recording toast with 'Recording...' text."""
        self._text_field.setStringValue_("Recording...")
        self._position_at_cursor()
        self.orderFrontRegardless()
        self._reset_level()

    def update_level(self, level: float):
        """Update the audio level indicator (0.0-1.0)."""
        if self._fill_view is None:
            return

        # Clamp level to 0-1
        level = max(0.0, min(1.0, level))

        # Update fill bar width
        fill_width = self.LEVEL_WIDTH * level
        fill_frame = Foundation.NSMakeRect(0, 0, fill_width, self.LEVEL_HEIGHT)
        self._fill_view.setFrame_(fill_frame)

        # Update color based on level (green -> yellow -> red)
        if level < 0.5:
            # Green to yellow
            r = level * 2
            g = 1.0
            b = 0.0
        else:
            # Yellow to red
            r = 1.0
            g = 1.0 - (level - 0.5) * 2
            b = 0.0

        color = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0)
        self._fill_view.layer().setBackgroundColor_(color.CGColor())

    def _reset_level(self):
        """Reset the level indicator to zero."""
        if self._fill_view:
            fill_frame = Foundation.NSMakeRect(0, 0, 0, self.LEVEL_HEIGHT)
            self._fill_view.setFrame_(fill_frame)

    def show_transcribing(self):
        """Update the toast to show 'Transcribing...' text."""
        self._text_field.setStringValue_("Transcribing...")
        self._reset_level()

    def hide(self):
        """Hide the toast window."""
        self.orderOut_(None)

    @classmethod
    def get_instance(cls):
        """Get the singleton recording toast instance."""
        if cls._instance is None:
            cls._instance = cls.create()
        return cls._instance


class RecordingToastManager:
    """Manages the recording toast for speech-to-text."""

    def __init__(self):
        self._is_visible = False

    def show_recording(self):
        """Show the recording toast."""
        toast = RecordingToast.get_instance()
        if toast:
            toast.show_recording()
            self._is_visible = True

    def update_level(self, level: float):
        """Update the audio level indicator."""
        toast = RecordingToast.get_instance()
        if toast:
            toast.update_level(level)

    def show_transcribing(self):
        """Update to show transcribing state."""
        toast = RecordingToast.get_instance()
        if toast:
            toast.show_transcribing()

    def hide(self):
        """Hide the recording toast."""
        if self._is_visible:
            toast = RecordingToast.get_instance()
            if toast:
                toast.hide()
            self._is_visible = False

    def is_visible(self) -> bool:
        """Check if the toast is currently visible."""
        return self._is_visible
