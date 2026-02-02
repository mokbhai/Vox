"""
Menu bar application for Vox.

Provides a menu bar icon with access to settings and configuration.
"""
import objc
import AppKit
import Foundation
from PyObjCTools import AppHelper
from typing import Optional

from vox.config import get_config
from vox.api import RewriteMode
from vox.service import ServiceProvider


class APIKeyDialog(AppKit.NSPanel):
    """Dialog for entering the OpenAI API key."""

    def __init__(self, callback):
        """
        Initialize the API key dialog.

        Args:
            callback: Function to call with the API key when saved.
        """
        screen = AppKit.NSScreen.mainScreen()
        screen_frame = screen.visibleFrame()

        window_width = 400
        window_height = 150
        x = (screen_frame.size.width - window_width) / 2
        y = (screen_frame.size.height - window_height) / 2

        frame = Foundation.NSMakeRect(x, y, window_width, window_height)

        super().__init__(
            frame,
            AppKit.NSWindowStyleMaskTitled |
            AppKit.NSWindowStyleMaskClosable |
            AppKit.NSWindowStyleMaskMiniaturizable,
            AppKit.NSBackingStoreBuffered,
            False,
        )

        self.callback = callback
        self.setTitle_("Vox - API Key")

        # Create content view
        self._create_ui()

    def _create_ui(self):
        """Create the dialog UI."""
        content_view = AppKit.NSView.alloc().initWithFrame_(self.contentView().frame())
        self.setContentView_(content_view)

        # Label
        label = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, 100, 360, 20)
        )
        label.setStringValue_("Enter your OpenAI API key:")
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        content_view.addSubview_(label)

        # Text field for API key
        self._api_key_field = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, 70, 280, 24)
        )
        self._api_key_field.setPlaceholderString_("sk-...")
        self._api_key_field.setSecure_(True)
        content_view.addSubview_(self._api_key_field)

        # Paste button
        paste_button = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(310, 70, 70, 24)
        )
        paste_button.setTitle_("Paste")
        paste_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        paste_button.setTarget_(self)
        paste_button.setAction_("pasteKey:")
        content_view.addSubview_(paste_button)

        # Save button
        save_button = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(230, 30, 70, 24)
        )
        save_button.setTitle_("Save")
        save_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        save_button.setTarget_(self)
        save_button.setAction_("saveKey:")
        content_view.addSubview_(save_button)

        # Cancel button
        cancel_button = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(310, 30, 70, 24)
        )
        cancel_button.setTitle_("Cancel")
        cancel_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        cancel_button.setTarget_(self)
        cancel_button.setAction_("cancel:")
        content_view.addSubview_(cancel_button)

    def pasteKey_(self, sender):
        """Handle Paste button click."""
        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        clipboard_content = pasteboard.stringForType_(AppKit.NSStringPboardType)
        if clipboard_content:
            self._api_key_field.setStringValue_(clipboard_content)

    def saveKey_(self, sender):
        """Handle Save button click."""
        api_key = self._api_key_field.stringValue()
        self.callback(api_key)
        self.close()

    def cancel_(self, sender):
        """Handle Cancel button click."""
        self.close()

    def show(self):
        """Show the dialog as a modal sheet."""
        # Set existing API key
        config = get_config()
        existing_key = config.get_api_key()
        if existing_key:
            self._api_key_field.setStringValue_(existing_key)

        self.makeKeyAndOrderFront_(None)
        AppKit.NSApp.runModalForWindow_(self)


class SettingsDialog(AppKit.NSPanel):
    """Dialog for configuring model and API settings."""

    def __init__(self, callback, config):
        """
        Initialize the settings dialog.

        Args:
            callback: Function to call with (model, base_url) when saved.
            config: Current config object.
        """
        screen = AppKit.NSScreen.mainScreen()
        screen_frame = screen.visibleFrame()

        window_width = 400
        window_height = 220
        x = (screen_frame.size.width - window_width) / 2
        y = (screen_frame.size.height - window_height) / 2

        frame = Foundation.NSMakeRect(x, y, window_width, window_height)

        super().__init__(
            frame,
            AppKit.NSWindowStyleMaskTitled |
            AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered,
            False,
        )

        self.callback = callback
        self.config = config
        self.setTitle_("Vox - Settings")

        self._create_ui()

    def _create_ui(self):
        """Create the dialog UI."""
        content_view = AppKit.NSView.alloc().initWithFrame_(self.contentView().frame())
        self.setContentView_(content_view)

        y_offset = 170

        # Model label
        model_label = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 360, 20)
        )
        model_label.setStringValue_("Model:")
        model_label.setBezeled_(False)
        model_label.setDrawsBackground_(False)
        model_label.setEditable_(False)
        model_label.setSelectable_(False)
        content_view.addSubview_(model_label)

        # Model text field
        y_offset -= 30
        self._model_field = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 360, 24)
        )
        self._model_field.setPlaceholderString_("e.g. gpt-4o-mini, gpt-4o, claude-3-5-sonnet")
        self._model_field.setStringValue_(self.config.model)
        content_view.addSubview_(self._model_field)

        # Base URL label
        y_offset -= 40
        base_url_label = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 360, 20)
        )
        base_url_label.setStringValue_("Base URL (optional):")
        base_url_label.setBezeled_(False)
        base_url_label.setDrawsBackground_(False)
        base_url_label.setEditable_(False)
        base_url_label.setSelectable_(False)
        content_view.addSubview_(base_url_label)

        # Base URL text field
        y_offset -= 30
        self._base_url_field = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 360, 24)
        )
        self._base_url_field.setPlaceholderString_("e.g. https://api.openai.com/v1 (leave empty for default)")
        if self.config.base_url:
            self._base_url_field.setStringValue_(self.config.base_url)
        content_view.addSubview_(self._base_url_field)

        # Info text
        y_offset -= 40
        info = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 360, 30)
        )
        info.setStringValue_("Enter any OpenAI-compatible model name. For custom APIs, set the Base URL.")
        info.setBezeled_(False)
        info.setDrawsBackground_(False)
        info.setEditable_(False)
        info.setSelectable_(False)
        info.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        content_view.addSubview_(info)

        # Save button
        save_button = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(230, 20, 70, 24)
        )
        save_button.setTitle_("Save")
        save_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        save_button.setTarget_(self)
        save_button.setAction_("save:")
        content_view.addSubview_(save_button)

        # Cancel button
        cancel_button = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(310, 20, 70, 24)
        )
        cancel_button.setTitle_("Cancel")
        cancel_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        cancel_button.setTarget_(self)
        cancel_button.setAction_("cancel:")
        content_view.addSubview_(cancel_button)

    def save_(self, sender):
        """Handle Save button click."""
        model = self._model_field.stringValue().strip()
        base_url = self._base_url_field.stringValue().strip() or None
        self.callback(model, base_url)
        self.close()

    def cancel_(self, sender):
        """Handle Cancel button click."""
        self.close()

    def show(self):
        """Show the dialog."""
        self.makeKeyAndOrderFront_(None)
        AppKit.NSApp.runModalForWindow_(self)


class AboutDialog(AppKit.NSPanel):
    """About dialog for Vox."""

    def __init__(self):
        """Initialize the about dialog."""
        screen = AppKit.NSScreen.mainScreen()
        screen_frame = screen.visibleFrame()

        window_width = 300
        window_height = 150
        x = (screen_frame.size.width - window_width) / 2
        y = (screen_frame.size.height - window_height) / 2

        frame = Foundation.NSMakeRect(x, y, window_width, window_height)

        super().__init__(
            frame,
            AppKit.NSWindowStyleMaskTitled |
            AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered,
            False,
        )

        self.setTitle_("About Vox")
        self._create_ui()

    def _create_ui(self):
        """Create the dialog UI."""
        content_view = AppKit.NSView.alloc().initWithFrame_(self.contentView().frame())
        self.setContentView_(content_view)

        # App name
        name = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, 100, 260, 30)
        )
        name.setStringValue_("Vox")
        name.setFont_(AppKit.NSFont.boldSystemFontOfSize_(20))
        name.setBezeled_(False)
        name.setDrawsBackground_(False)
        name.setEditable_(False)
        name.setSelectable_(False)
        name.setAlignment_(AppKit.NSTextAlignmentCenter)
        content_view.addSubview_(name)

        # Version
        version = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, 70, 260, 20)
        )
        version.setStringValue_("Version 0.1.0")
        version.setBezeled_(False)
        version.setDrawsBackground_(False)
        version.setEditable_(False)
        version.setSelectable_(False)
        version.setAlignment_(AppKit.NSTextAlignmentCenter)
        content_view.addSubview_(version)

        # Description
        desc = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, 40, 260, 20)
        )
        desc.setStringValue_("AI-powered text rewriting")
        desc.setBezeled_(False)
        desc.setDrawsBackground_(False)
        desc.setEditable_(False)
        desc.setSelectable_(False)
        desc.setAlignment_(AppKit.NSTextAlignmentCenter)
        content_view.addSubview_(desc)

    def show(self):
        """Show the dialog."""
        self.makeKeyAndOrderFront_(None)


class MenuBarApp(AppKit.NSObject):
    """Main menu bar application for Vox."""

    def init(self):
        """Initialize the menu bar app (ObjC initializer)."""
        self = objc.super(MenuBarApp, self).init()
        if self is None:
            return None

        # Placeholder values - will be set after init
        self.service_provider = None
        self.config = None
        self.status_item = None
        self.menu = None
        self.app = None

        return self

    def setupWithService_(self, service_provider):
        """Set up the app with a service provider (called after init)."""
        self.service_provider = service_provider
        self.config = get_config()

        # Create the application
        self.app = AppKit.NSApplication.sharedApplication()
        self.app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        # Create status item
        self._create_status_item()
        self._create_menu()

        return self

    def _create_status_item(self):
        """Create the status item in the menu bar."""
        status_bar = AppKit.NSStatusBar.systemStatusBar()
        self.status_item = status_bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)

        # Set icon (using a simple text icon for now)
        # In production, you'd use an actual icon image
        self.status_item.setTitle_("V")

        # Create menu
        self.menu = AppKit.NSMenu.alloc().init()
        self.status_item.setMenu_(self.menu)

    def _create_menu(self):
        """Create the menu items."""
        self.menu.removeAllItems()

        # API Key
        api_key_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Set API Key...", "showAPIKeyDialog:", ""
        )
        api_key_item.setTarget_(self)
        self.menu.addItem_(api_key_item)

        # Model Selection
        model_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Model: {self.config.model}", "showModelDialog:", ""
        )
        model_item.setTarget_(self)
        self.menu.addItem_(model_item)

        # Separator
        self.menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # Auto-start
        auto_start_title = "Open at Login" if not self.config.auto_start else "✓ Open at Login"
        auto_start_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            auto_start_title, "toggleAutoStart:", ""
        )
        auto_start_item.setTarget_(self)
        self.menu.addItem_(auto_start_item)

        # Separator
        self.menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # About
        about_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "About Vox", "showAbout:", ""
        )
        about_item.setTarget_(self)
        self.menu.addItem_(about_item)

        # Quit
        quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Vox", "quit:", "q"
        )
        quit_item.setTarget_(self)
        self.menu.addItem_(quit_item)

    # Menu item actions

    def showAPIKeyDialog_(self, sender):
        """Show the API key dialog."""
        dialog = APIKeyDialog(self._save_api_key)
        dialog.show()

    def _save_api_key(self, api_key: str):
        """
        Save the API key.

        Args:
            api_key: The API key to save.
        """
        if api_key:
            self.config.set_api_key(api_key)
            self.service_provider.update_api_key()

    def showModelDialog_(self, sender):
        """Show the settings dialog."""
        dialog = SettingsDialog(self._save_settings, self.config)
        dialog.show()

    def _save_settings(self, model: str, base_url: Optional[str]):
        """
        Save the settings.

        Args:
            model: The model to use.
            base_url: The custom base URL (optional).
        """
        self.config.model = model
        self.config.base_url = base_url
        self.service_provider.update_model()
        self._create_menu()  # Refresh menu

    def toggleAutoStart_(self, sender):
        """Toggle auto-start at login."""
        current = self.config.auto_start
        new_state = not current
        self.config.set_auto_start(new_state)
        self._create_menu()  # Refresh menu

    def showAbout_(self, sender):
        """Show the about dialog."""
        dialog = AboutDialog()
        dialog.show()

    def quit_(self, sender):
        """Quit the application."""
        AppKit.NSApp.terminate_(None)

    def run(self):
        """Run the application."""
        # Register the service
        self.service_provider.register_services()

        # Run the app
        AppHelper.runEventLoop(installInterrupt=True)
