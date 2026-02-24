# PyObjC and macOS APIs Guide

This guide covers the PyObjC patterns and macOS-specific APIs used in Vox. PyObjC is a bridge between Python and Objective-C, allowing Python code to call macOS frameworks directly.

## Table of Contents

- [PyObjC Basics](#pyobjc-basics)
- [NSObject Subclasses](#nsobject-subclasses)
- [Memory Management](#memory-management)
- [AppKit Patterns](#appkit-patterns)
- [Quartz Event Handling](#quartz-event-handling)
- [Services API](#services-api)
- [Notifications](#notifications)
- [Permissions](#permissions)

---

## PyObjC Basics

### Framework Imports

```python
# Import entire frameworks
import AppKit
import Foundation
import Quartz

# Import specific functions/constants
from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)
```

### Method Naming Convention

Objective-C methods are converted to Python using underscores:

```python
# Objective-C: [window setTitle:@"Title"]
window.setTitle_("Title")

# Objective-C: [NSApp setServicesProvider:provider]
AppKit.NSApp.setServicesProvider_(provider)

# Objective-C: [alert runModal]
response = alert.runModal()
```

### Constants and Enums

```python
# Window style masks
AppKit.NSWindowStyleMaskBorderless
AppKit.NSWindowStyleMaskTitled
AppKit.NSWindowStyleMaskClosable

# Alert styles
AppKit.NSAlertStyleWarning
AppKit.NSAlertStyleInformational

# Return values
AppKit.NSAlertFirstButtonReturn
AppKit.NSAlertSecondButtonReturn
```

---

## NSObject Subclasses

### Basic Class Definition

```python
import objc
import AppKit

class ServiceProvider(AppKit.NSObject):
    """Service provider for macOS NSServices integration."""

    def init(self):
        """Initialize the service provider."""
        # Must call super init first
        self = objc.super(ServiceProvider, self).init()
        if self is None:
            return None

        # Initialize instance variables
        self._api_client = None
        return self
```

### The `init` Pattern

The `init` method in PyObjC must follow this pattern:

```python
def init(self):
    # 1. Call super init
    self = objc.super(ClassName, self).init()

    # 2. Check for failure
    if self is None:
        return None

    # 3. Initialize instance variables
    self._property = value

    # 4. Return self
    return self
```

### Instance Variables with `objc.ivar()`

For instance variables that need to be accessible from Objective-C:

```python
class ToastWindow(AppKit.NSWindow):
    _instance = None
    _text_field = objc.ivar()  # ObjC-visible instance variable
```

---

## Memory Management

PyObjC handles most memory management automatically, but be aware of:

### Retain Cycles

Avoid strong references between parent and child objects:

```python
# In delegate patterns, use weak references if possible
class MenuBarActions(AppKit.NSObject):
    def init(self):
        self = objc.super(MenuBarActions, self).init()
        self.app = None  # Reference set externally
        return self
```

### Resource Cleanup

Clean up resources explicitly:

```python
def unregister_hotkey(self):
    """Unregister the hot key and clean up resources."""
    if self._tap:
        Quartz.CGEventTapEnable(self._tap, False)

    if self._run_loop:
        Quartz.CFRunLoopStop(self._run_loop)

    if self._tap_thread:
        self._tap_thread.join(timeout=2.0)

    # Clear references
    self._tap = None
    self._run_loop = None
```

---

## AppKit Patterns

### Creating Windows

```python
def create(cls):
    """Create and initialize a window."""
    frame = Foundation.NSMakeRect(0, 0, 200, 50)
    window = cls.alloc().initWithContentRect_styleMask_backing_defer_(
        frame,
        AppKit.NSWindowStyleMaskBorderless,
        AppKit.NSBackingStoreBuffered,
        False,
    )
    if window is None:
        return None

    # Configure window properties
    window.setOpaque_(False)
    window.setBackgroundColor_(AppKit.NSColor.clearColor())
    window.setLevel_(AppKit.NSFloatingWindowLevel)
    window.setIgnoresMouseEvents_(True)

    return window
```

### Window Levels

```python
# Common window levels (lowest to highest)
AppKit.NSNormalWindowLevel       # Normal windows
AppKit.NSFloatingWindowLevel     # Floating palettes
AppKit.NSMainMenuWindowLevel     # Menu bar
AppKit.NSStatusWindowLevel       # Status bars, popovers
AppKit.NSPopUpMenuWindowLevel    # Pop-up menus
AppKit.NSScreenSaverWindowLevel  # Screen savers
```

### Creating Alerts

```python
def show_permission_dialog(self):
    """Show a permission request dialog."""
    alert = AppKit.NSAlert.alloc().init()
    alert.setMessageText_("Permissions Required")
    alert.setInformativeText_(
        "Vox needs Accessibility permission to use global hot keys."
    )
    alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
    alert.addButtonWithTitle_("Open Settings")
    alert.addButtonWithTitle_("Cancel")

    # Bring app to front
    AppKit.NSApp.activateIgnoringOtherApps_(True)

    response = alert.runModal()

    if response == AppKit.NSAlertFirstButtonReturn:
        # Handle first button
        pass
```

### Menu Bar Status Item

```python
def _create_status_item(self):
    """Create the status item in the menu bar."""
    status_bar = AppKit.NSStatusBar.systemStatusBar()
    self.status_item = status_bar.statusItemWithLength_(
        AppKit.NSVariableStatusItemLength
    )

    # Set icon or title
    icon = get_menu_bar_icon()
    if icon:
        self.status_item.button().setImage_(icon)
        self.status_item.button().setImageScaling_(
            AppKit.NSImageScaleProportionallyDown
        )
    else:
        self.status_item.setTitle_("V")

    # Attach menu
    self.menu = AppKit.NSMenu.alloc().init()
    self.status_item.setMenu_(self.menu)
```

### Creating Menu Items

```python
def _create_menu(self):
    """Create the menu items."""
    self.menu.removeAllItems()

    # Settings item
    settings_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Preferences...", "showSettings:", ","
    )
    settings_item.setTarget_(self.actions)
    self.menu.addItem_(settings_item)

    # Separator
    self.menu.addItem_(AppKit.NSMenuItem.separatorItem())

    # Quit item
    quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Quit Vox", "quit:", "q"
    )
    quit_item.setTarget_(self.actions)
    self.menu.addItem_(quit_item)
```

---

## Quartz Event Handling

### CGEventTap for Global Hot Keys

```python
def register_hotkey(self) -> bool:
    """Register global hot keys using CGEventTap."""
    # Define event mask
    event_mask = (
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
        | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
        | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
    )

    # Create event tap
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,      # Tap location
        Quartz.kCGHeadInsertEventTap,   # Placement
        Quartz.kCGEventTapOptionDefault, # Options (allows suppression)
        event_mask,                      # Event mask
        tap_callback,                    # Callback function
        None,                            # User info
    )

    if tap is None:
        return False

    # Create run loop source
    run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)

    # Start background thread
    self._tap_thread = threading.Thread(
        target=self._run_tap_loop,
        daemon=True,
    )
    self._tap_thread.start()
```

### Event Tap Callback

```python
def _handle_cg_event(self, proxy, event_type, event):
    """Handle a CGEvent from the tap callback."""
    # Handle tap disabled events
    if event_type == Quartz.kCGEventTapDisabledByTimeout:
        Quartz.CGEventTapEnable(self._tap, True)
        return event

    # Only process key down events
    if event_type != Quartz.kCGEventKeyDown:
        return event

    # Get key code and modifiers
    keycode = Quartz.CGEventGetIntegerValueField(
        event, Quartz.kCGKeyboardEventKeycode
    )
    flags = Quartz.CGEventGetFlags(event)

    # Check for hot key match
    if self._matches_hotkey(keycode, flags):
        # Dispatch to main thread
        AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: self._callback()
        )
        return None  # Suppress event

    return event  # Pass event through
```

### Simulating Keyboard Events

```python
def simulate_copy():
    """Simulate Cmd+C to copy selected text."""
    source = Quartz.CGEventSourceCreate(
        Quartz.kCGEventSourceStateCombinedSessionState
    )

    # Key codes
    CMD_KEY = 0x37
    C_KEY = 0x08

    # Create events
    cmd_down = Quartz.CGEventCreateKeyboardEvent(source, CMD_KEY, True)
    c_down = Quartz.CGEventCreateKeyboardEvent(source, C_KEY, True)
    c_up = Quartz.CGEventCreateKeyboardEvent(source, C_KEY, False)
    cmd_up = Quartz.CGEventCreateKeyboardEvent(source, CMD_KEY, False)

    # Set command flag on C events
    Quartz.CGEventSetFlags(c_down, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventSetFlags(c_up, Quartz.kCGEventFlagMaskCommand)

    # Post events
    Quartz.CGEventPost(Quartz.kCGSessionEventTap, cmd_down)
    time.sleep(0.01)
    Quartz.CGEventPost(Quartz.kCGSessionEventTap, c_down)
    time.sleep(0.01)
    Quartz.CGEventPost(Quartz.kCGSessionEventTap, c_up)
    time.sleep(0.01)
    Quartz.CGEventPost(Quartz.kCGSessionEventTap, cmd_up)
```

### Key Code Reference

Common macOS key codes:

```python
KEY_CODES = {
    'a': 0x00, 's': 0x01, 'd': 0x02, 'f': 0x03,
    'h': 0x04, 'g': 0x05, 'z': 0x06, 'x': 0x07,
    'c': 0x08, 'v': 0x09, 'b': 0x0B, 'q': 0x0C,
    'w': 0x0D, 'e': 0x0E, 'r': 0x0F, 'y': 0x10,
    't': 0x11, '1': 0x12, '2': 0x13, '3': 0x14,
    '4': 0x15, '6': 0x16, '5': 0x17, '=': 0x18,
    '9': 0x19, '7': 0x1A, '-': 0x1B, '8': 0x1C,
    '0': 0x1D, ']': 0x1E, 'o': 0x1F, 'u': 0x20,
    '[': 0x21, 'i': 0x22, 'p': 0x23,
}
```

---

## Services API

### Registering Services

Services are defined with typed selectors:

```python
class ServiceProvider(AppKit.NSObject):
    @objc.typedSelector(b"v@:@@o^@")
    def fixGrammarService_userData_error_(self, pasteboard, userData, error):
        """Handle the Fix Grammar service call."""
        self._handle_service(pasteboard, RewriteMode.FIX_GRAMMAR)
```

### Service Method Signature

The type encoding `b"v@:@@o^@"` means:
- `v` - void return
- `@` - object (self)
- `:` - selector
- `@` - NSPasteboard
- `@` - userData (NSString)
- `o^@` - out parameter (NSError**)

### Pasteboard Operations

```python
def _read_text_from_pasteboard(self, pasteboard):
    """Read text from the pasteboard."""
    types = pasteboard.types()
    if AppKit.NSStringPboardType in types:
        return pasteboard.stringForType_(AppKit.NSStringPboardType)
    return None

def _write_text_to_pasteboard(self, pasteboard, text):
    """Write text to the pasteboard."""
    pasteboard.clearContents()
    pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString)
```

### Registering with NSApp

```python
def register_services(self):
    """Register the services with macOS."""
    AppKit.NSApp.setServicesProvider_(self)
```

---

## Notifications

### System Notifications

```python
class ErrorNotifier:
    @staticmethod
    def show_error(title: str, message: str):
        """Show an error notification."""
        notification = AppKit.NSUserNotification.alloc().init()
        notification.setTitle_(title)
        notification.setInformativeText_(message)
        notification.setSoundName_(AppKit.NSUserNotificationDefaultSoundName)

        center = AppKit.NSUserNotificationCenter.defaultUserNotificationCenter()
        center.deliverNotification_(notification)
```

### Custom Toast Windows

```python
class ToastWindow(AppKit.NSWindow):
    def show_at_cursor(self):
        """Show the toast window near the mouse cursor."""
        mouse_location = AppKit.NSEvent.mouseLocation()
        window_height = self.frame().size.height

        x = mouse_location.x + 15
        y = mouse_location.y - window_height - 15

        self.setFrameTopLeftPoint_(Foundation.NSMakePoint(x, y))
        self.orderFrontRegardless()
```

---

## Permissions

### Checking Accessibility Permission

```python
from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)

def has_accessibility_permission() -> bool:
    """Check if Accessibility permission is granted."""
    return AXIsProcessTrusted()

def request_accessibility_permission() -> bool:
    """Request Accessibility permission from the user."""
    options = {kAXTrustedCheckOptionPrompt: True}
    return AXIsProcessTrustedWithOptions(options)
```

### Opening System Preferences

```python
def open_accessibility_settings():
    """Open Accessibility settings in System Preferences."""
    url = AppKit.NSURL.URLWithString_(
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
    )
    AppKit.NSWorkspace.sharedWorkspace().openURL_(url)
```

---

## Debugging Tips

### Print Statements with Flush

Always use `flush=True` for debugging output in GUI apps:

```python
print("Debug message", flush=True)
```

### Checking Method Availability

```python
if self.respondsToSelector_('someMethod:'):
    self.someMethod_(arg)
```

### Verifying Service Registration

```python
print(f"Has selector: {self.respondsToSelector_('fixGrammarService:userData:error:')}")
```
