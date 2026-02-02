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


class SettingsDialog(AppKit.NSPanel):
    """Settings dialog for Vox."""

    def init(self):
        """Initialize the settings dialog."""
        screen = AppKit.NSScreen.mainScreen()
        screen_frame = screen.visibleFrame()

        window_width = 450
        window_height = 320
        x = (screen_frame.size.width - window_width) / 2
        y = (screen_frame.size.height - window_height) / 2

        frame = Foundation.NSMakeRect(x, y, window_width, window_height)

        self = objc.super(SettingsDialog, self).initWithContentRect_styleMask_backing_defer_(
            frame,
            AppKit.NSWindowStyleMaskTitled |
            AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered,
            False,
        )

        if self is None:
            return None

        self.setTitle_("Vox Settings")
        self.setLevel_(AppKit.NSFloatingWindowLevel)

        # Content view
        content_view = self.contentView()
        content_view.setWantsLayer_(True)
        content_view.setLayer_(
            AppKit.CALayer.layer().initWithFrame_(
                Foundation.NSMakeRect(0, 0, window_width, window_height)
            )
        )
        content_view.layer().setBackgroundColor_(
            AppKit.NSColor.controlBackgroundColor().CGColor()
        )

        # Configuration
        self.config = get_config()
        self.save_callback = None

        y_offset = window_height - 50

        # Title
        title = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 410, 30)
        )
        title.setStringValue_("Settings")
        title.setFont_(AppKit.NSFont.boldSystemFontOfSize_(20))
        title.setBezeled_(False)
        title.setDrawsBackground_(False)
        title.setEditable_(False)
        title.setSelectable_(False)
        content_view.addSubview_(title)

        y_offset -= 50

        # API Key Section
        api_label = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 410, 20)
        )
        api_label.setStringValue_("OpenAI API Key:")
        api_label.setBezeled_(False)
        api_label.setDrawsBackground_(False)
        api_label.setEditable_(False)
        api_label.setSelectable_(False)
        content_view.addSubview_(api_label)

        y_offset -= 30

        self.api_field = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 410, 30)
        )
        self.api_field.setPlaceholderString_("sk-...")
        current_key = self.config.get_api_key()
        if current_key:
            self.api_field.setStringValue_(current_key)
        content_view.addSubview_(self.api_field)

        y_offset -= 50

        # Model Section
        model_label = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 410, 20)
        )
        model_label.setStringValue_("Model:")
        model_label.setBezeled_(False)
        model_label.setDrawsBackground_(False)
        model_label.setEditable_(False)
        model_label.setSelectable_(False)
        content_view.addSubview_(model_label)

        y_offset -= 30

        self.model_field = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 410, 30)
        )
        self.model_field.setPlaceholderString_("gpt-4o-mini")
        self.model_field.setStringValue_(self.config.model)
        content_view.addSubview_(self.model_field)

        y_offset -= 50

        # Base URL Section
        url_label = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 410, 20)
        )
        url_label.setStringValue_("Base URL (optional):")
        url_label.setBezeled_(False)
        url_label.setDrawsBackground_(False)
        url_label.setEditable_(False)
        url_label.setSelectable_(False)
        content_view.addSubview_(url_label)

        y_offset -= 30

        self.url_field = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 410, 30)
        )
        self.url_field.setPlaceholderString_("https://api.openai.com/v1")
        if self.config.base_url:
            self.url_field.setStringValue_(self.config.base_url)
        content_view.addSubview_(self.url_field)

        y_offset -= 50

        # Launch at Login checkbox
        self.launch_checkbox = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, y_offset, 200, 25)
        )
        self.launch_checkbox.setButtonType_(AppKit.NSSwitchButton)
        self.launch_checkbox.setTitle_("Launch at login")
        self.launch_checkbox.setState_(AppKit.NSControlStateValueOn if self.config.auto_start else AppKit.NSControlStateValueOff)
        content_view.addSubview_(self.launch_checkbox)

        # Save and Cancel buttons
        cancel_button = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(280, 20, 80, 30)
        )
        cancel_button.setTitle_("Cancel")
        cancel_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        cancel_button.setTarget_(self)
        cancel_button.setAction_("cancel:")
        content_view.addSubview_(cancel_button)

        save_button = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(360, 20, 70, 30)
        )
        save_button.setTitle_("Save")
        save_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        save_button.setKeyEquivalent_("\r")  # Return key
        save_button.setTarget_(self)
        save_button.setAction_("save:")
        content_view.addSubview_(save_button)

        return self

    def setSaveCallback_(self, callback):
        """Set the callback for saving settings."""
        self.save_callback = callback

    def save_(self, sender):
        """Handle save button."""
        api_key = self.api_field.stringValue().strip()
        model = self.model_field.stringValue().strip() or "gpt-4o-mini"
        base_url = self.url_field.stringValue().strip() or None
        auto_start = self.launch_checkbox.state() == AppKit.NSControlStateValueOn

        if self.save_callback:
            self.save_callback(api_key, model, base_url, auto_start)

        self.close()

    def cancel_(self, sender):
        """Handle cancel button."""
        self.close()

    def show(self):
        """Show the dialog."""
        self.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)


class AboutDialog(AppKit.NSPanel):
    """About dialog for Vox."""

    def init(self):
        """Initialize the about dialog."""
        screen = AppKit.NSScreen.mainScreen()
        screen_frame = screen.visibleFrame()

        window_width = 350
        window_height = 200
        x = (screen_frame.size.width - window_width) / 2
        y = (screen_frame.size.height - window_height) / 2

        frame = Foundation.NSMakeRect(x, y, window_width, window_height)

        self = objc.super(AboutDialog, self).initWithContentRect_styleMask_backing_defer_(
            frame,
            AppKit.NSWindowStyleMaskTitled |
            AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered,
            False,
        )

        if self is None:
            return None

        self.setTitle_("About Vox")

        content_view = self.contentView()

        # App name
        name = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, 130, 310, 30)
        )
        name.setStringValue_("Vox")
        name.setFont_(AppKit.NSFont.boldSystemFontOfSize_(24))
        name.setBezeled_(False)
        name.setDrawsBackground_(False)
        name.setEditable_(False)
        name.setSelectable_(False)
        name.setAlignment_(AppKit.NSTextAlignmentCenter)
        content_view.addSubview_(name)

        # Version
        version = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(20, 100, 310, 20)
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
            Foundation.NSMakeRect(20, 60, 310, 40)
        )
        desc.setStringValue_("AI-powered text rewriting\nthrough macOS contextual menu.")
        desc.setBezeled_(False)
        desc.setDrawsBackground_(False)
        desc.setEditable_(False)
        desc.setSelectable_(False)
        desc.setAlignment_(AppKit.NSTextAlignmentCenter)
        content_view.addSubview_(desc)

        # OK button
        ok_button = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(135, 15, 80, 30)
        )
        ok_button.setTitle_("OK")
        ok_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        ok_button.setTarget_(self)
        ok_button.setAction_("close:")
        content_view.addSubview_(ok_button)

        return self

    def show(self):
        """Show the dialog."""
        self.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)


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
        settings_item.setTarget_(self)
        self.menu.addItem_(settings_item)

        # Separator
        self.menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # About
        about_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "About Vox", "showAbout:", ""
        )
        about_item.setTarget_(self)
        self.menu.addItem_(about_item)

        # Separator
        self.menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # Quit
        quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Vox", "quit:", "q"
        )
        quit_item.setTarget_(self)
        self.menu.addItem_(quit_item)

    # Menu item actions

    def showSettings_(self, sender):
        """Show the settings dialog."""
        dialog = SettingsDialog.alloc().init()
        dialog.setSaveCallback_(self._save_settings)
        dialog.show()

    def _save_settings(self, api_key: str, model: str, base_url: Optional[str], auto_start: bool):
        """Save the settings."""
        if api_key:
            self.config.set_api_key(api_key)
            self.service_provider.update_api_key()

        self.config.model = model
        self.config.base_url = base_url
        self.service_provider.update_model()

        if auto_start != self.config.auto_start:
            self.config.set_auto_start(auto_start)

    def showAbout_(self, sender):
        """Show the about dialog."""
        dialog = AboutDialog.alloc().init()
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
