"""
Preferences window with sidebar navigation for Vox.

Provides a window with Settings and About pages accessible via sidebar.
"""
import objc
import AppKit
import Foundation
import threading
from typing import Optional, Callable

from vox.config import get_config
from vox.api import RewriteMode, DISPLAY_NAMES
from vox.hotkey import (
    KEY_CODE_TO_CHAR,
    MODIFIER_SYMBOLS,
    format_hotkey_display,
    modifier_mask_to_string,
    parse_modifiers,
)
from vox.speech import (
    WhisperModelManager,
    SUPPORTED_LANGUAGES,
    WHISPER_MODELS,
)


class EditableTextField(AppKit.NSTextField):
    """NSTextField subclass that supports Cmd+C/V/X/A in modal sessions."""

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
    """NSTextField subclass that records a keyboard shortcut."""

    def initWithFrame_(self, frame):
        self = objc.super(HotkeyRecorderField, self).initWithFrame_(frame)
        if self is None:
            return None
        self._modifiers_mask = 0
        self._key_char = ""
        self._recording = False
        return self

    def set_hotkey(self, modifiers_str, key_str):
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
        return bool(self._key_char)

    def becomeFirstResponder(self):
        result = objc.super(HotkeyRecorderField, self).becomeFirstResponder()
        if result:
            self._recording = True
            self.setStringValue_("Press shortcut...")
        return result

    def resignFirstResponder(self):
        if self._recording:
            self._recording = False
            if self._key_char:
                self.setStringValue_(format_hotkey_display(self._modifiers_mask, self._key_char))
            else:
                self.setStringValue_("None")
        return objc.super(HotkeyRecorderField, self).resignFirstResponder()

    def performKeyEquivalent_(self, event):
        if not self._recording:
            return objc.super(HotkeyRecorderField, self).performKeyEquivalent_(event)
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

    def _process_key_event(self, event):
        keycode = event.keyCode()
        if keycode in (0x33, 0x75, 0x35):  # Backspace, Delete, Escape
            self._modifiers_mask = 0
            self._key_char = ""
            self._recording = False
            self.setStringValue_("None")
            if self.window():
                self.window().makeFirstResponder_(None)
            return

        char = KEY_CODE_TO_CHAR.get(keycode)
        if char is None:
            return

        flags = event.modifierFlags()
        mask = 0
        for flag, _ in MODIFIER_SYMBOLS:
            if flags & flag:
                mask |= flag

        if not mask:
            return

        self._modifiers_mask = mask
        self._key_char = char
        self._recording = False
        self.setStringValue_(format_hotkey_display(mask, char))

        if self.window():
            self.window().makeFirstResponder_(None)


class PreferencesWindowController(AppKit.NSWindowController):
    """Window controller for the preferences window with sidebar."""

    # Constants
    WINDOW_WIDTH = 580
    WINDOW_HEIGHT = 560
    SIDEBAR_WIDTH = 140
    CONTENT_PADDING = 20
    ROW_HEIGHT = 24
    ROW_SPACING = 32
    LABEL_WIDTH = 100

    def init(self):
        self = objc.super(PreferencesWindowController, self).init()
        if self is None:
            return None

        self._config = get_config()
        self._save_callback = None
        self._content_views = {}
        self._content_container = None
        self._current_page = 0
        self._hotkey_recorders = {}
        self._sidebar_buttons = []

        # Settings UI fields
        self._api_field = None
        self._model_field = None
        self._url_field = None
        self._auto_checkbox = None
        self._thinking_checkbox = None
        self._hotkey_checkbox = None

        # Speech-to-text
        self._speech_model_manager = WhisperModelManager()
        self._speech_hotkey_recorder = None
        self._speech_model_popup = None
        self._speech_download_btn = None
        self._speech_progress = None
        self._speech_enabled_checkbox = None
        self._speech_lang_popup = None

        return self

    def setSaveCallback_(self, callback):
        """Set the callback to be called when settings are saved."""
        self._save_callback = callback

    def showWindow_(self, sender):
        """Create and show the window."""
        if self.window() is None:
            self._create_window()
        AppKit.NSApp.activateIgnoringOtherApps_(True)
        self.window().makeKeyAndOrderFront_(None)

    def _create_window(self):
        """Create the preferences window with sidebar."""
        frame = Foundation.NSMakeRect(100, 100, self.WINDOW_WIDTH, self.WINDOW_HEIGHT)

        style_mask = (
            AppKit.NSWindowStyleMaskTitled
            | AppKit.NSWindowStyleMaskClosable
        )
        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            style_mask,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("Vox Preferences")
        window.setMinSize_((500, 400))
        window.setDelegate_(self)

        content_view = window.contentView()
        content_height = self.WINDOW_HEIGHT

        # Create sidebar
        sidebar_frame = Foundation.NSMakeRect(0, 0, self.SIDEBAR_WIDTH, content_height)
        sidebar = AppKit.NSView.alloc().initWithFrame_(sidebar_frame)
        sidebar.setWantsLayer_(True)
        sidebar.layer().setBackgroundColor_(
            AppKit.NSColor.windowBackgroundColor().CGColor()
        )
        content_view.addSubview_(sidebar)

        # Add separator line
        separator_frame = Foundation.NSMakeRect(self.SIDEBAR_WIDTH - 1, 0, 1, content_height)
        separator = AppKit.NSView.alloc().initWithFrame_(separator_frame)
        separator.setWantsLayer_(True)
        separator.layer().setBackgroundColor_(
            AppKit.NSColor.separatorColor().CGColor()
        )
        content_view.addSubview_(separator)

        # Create content container
        content_width = self.WINDOW_WIDTH - self.SIDEBAR_WIDTH
        content_frame = Foundation.NSMakeRect(self.SIDEBAR_WIDTH, 0, content_width, content_height)
        self._content_container = AppKit.NSView.alloc().initWithFrame_(content_frame)
        content_view.addSubview_(self._content_container)

        # Add sidebar buttons
        sidebar_items = ["Settings", "Speech", "About"]
        button_y = content_height - 50

        for i, title in enumerate(sidebar_items):
            button = AppKit.NSButton.alloc().initWithFrame_(
                Foundation.NSMakeRect(10, button_y - (i * 36), self.SIDEBAR_WIDTH - 20, 28)
            )
            button.setTitle_(title)
            button.setTag_(i)
            button.setAction_("sidebarButtonClicked:")
            button.setTarget_(self)
            button.setBordered_(False)
            button.setAlignment_(AppKit.NSTextAlignmentLeft)
            button.setFont_(AppKit.NSFont.systemFontOfSize_(13))

            if i == 0:
                button.setFont_(AppKit.NSFont.boldSystemFontOfSize_(13))

            sidebar.addSubview_(button)
            self._sidebar_buttons.append(button)

        # Create content views
        self._create_settings_view()
        self._create_speech_view()
        self._create_about_view()

        # Show first page
        self._show_page(0)

        self.setWindow_(window)

    def sidebarButtonClicked_(self, sender):
        """Handle sidebar button click."""
        tag = sender.tag()

        # Update button styles
        for i, button in enumerate(self._sidebar_buttons):
            if i == tag:
                button.setFont_(AppKit.NSFont.boldSystemFontOfSize_(13))
            else:
                button.setFont_(AppKit.NSFont.systemFontOfSize_(13))

        self._show_page(tag)

    def _show_page(self, page_index: int):
        """Show the specified page."""
        for key, view in self._content_views.items():
            view.setHidden_(key != page_index)
        self._current_page = page_index

    def _create_label(self, text: str, y: float, width: float = None) -> AppKit.NSTextField:
        """Create a right-aligned label."""
        if width is None:
            width = self.LABEL_WIDTH
        label = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, width, self.ROW_HEIGHT)
        )
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setAlignment_(AppKit.NSTextAlignmentRight)
        label.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        return label

    def _create_text_field(self, y: float, width: float, placeholder: str = "") -> EditableTextField:
        """Create an editable text field."""
        x = self.CONTENT_PADDING + self.LABEL_WIDTH + 10
        field = EditableTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(x, y, width, self.ROW_HEIGHT)
        )
        field.setPlaceholderString_(placeholder)
        field.setEditable_(True)
        field.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        return field

    def _create_settings_view(self):
        """Create the settings content view."""
        container_width = self._content_container.frame().size.width
        container_height = self._content_container.frame().size.height
        field_width = container_width - self.LABEL_WIDTH - 60

        view = AppKit.NSView.alloc().initWithFrame_(
            Foundation.NSMakeRect(0, 0, container_width, container_height)
        )

        # Title
        title = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, container_height - 36, 200, 24)
        )
        title.setStringValue_("Settings")
        title.setBezeled_(False)
        title.setDrawsBackground_(False)
        title.setEditable_(False)
        title.setSelectable_(False)
        title.setFont_(AppKit.NSFont.boldSystemFontOfSize_(20))
        view.addSubview_(title)

        y = container_height - 75

        # API Key
        view.addSubview_(self._create_label("API Key:", y))
        self._api_field = self._create_text_field(y, field_width, "sk-...")
        self._api_field.setStringValue_(self._config.get_api_key() or "")
        view.addSubview_(self._api_field)
        y -= self.ROW_SPACING

        # Model
        view.addSubview_(self._create_label("Model:", y))
        self._model_field = self._create_text_field(y, field_width, "gpt-4o-mini")
        self._model_field.setStringValue_(self._config.model or "gpt-4o-mini")
        view.addSubview_(self._model_field)
        y -= self.ROW_SPACING

        # Base URL
        view.addSubview_(self._create_label("Base URL:", y))
        self._url_field = self._create_text_field(y, field_width, "https://api.openai.com/v1 (optional)")
        self._url_field.setStringValue_(self._config.base_url or "")
        view.addSubview_(self._url_field)
        y -= self.ROW_SPACING

        # Launch at login
        self._auto_checkbox = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING + self.LABEL_WIDTH + 10, y, 200, self.ROW_HEIGHT)
        )
        self._auto_checkbox.setButtonType_(AppKit.NSSwitchButton)
        self._auto_checkbox.setTitle_("Launch at login")
        self._auto_checkbox.setState_(
            AppKit.NSControlStateValueOn if self._config.auto_start else AppKit.NSControlStateValueOff
        )
        view.addSubview_(self._auto_checkbox)
        y -= self.ROW_SPACING

        # Thinking mode
        self._thinking_checkbox = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING + self.LABEL_WIDTH + 10, y, 250, self.ROW_HEIGHT)
        )
        self._thinking_checkbox.setButtonType_(AppKit.NSSwitchButton)
        self._thinking_checkbox.setTitle_("Thinking mode")
        self._thinking_checkbox.setState_(
            AppKit.NSControlStateValueOn if self._config.thinking_mode else AppKit.NSControlStateValueOff
        )
        view.addSubview_(self._thinking_checkbox)
        y -= 45

        # Separator
        sep = AppKit.NSBox.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, container_width - 40, 1)
        )
        sep.setBoxType_(AppKit.NSBoxSeparator)
        view.addSubview_(sep)
        y -= 30

        # Hot Keys header
        hk_header = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, 200, 20)
        )
        hk_header.setStringValue_("Hot Keys")
        hk_header.setBezeled_(False)
        hk_header.setDrawsBackground_(False)
        hk_header.setEditable_(False)
        hk_header.setSelectable_(False)
        hk_header.setFont_(AppKit.NSFont.boldSystemFontOfSize_(14))
        view.addSubview_(hk_header)
        y -= 30

        # Enable hot keys
        self._hotkey_checkbox = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, 200, self.ROW_HEIGHT)
        )
        self._hotkey_checkbox.setButtonType_(AppKit.NSSwitchButton)
        self._hotkey_checkbox.setTitle_("Enable hot keys")
        self._hotkey_checkbox.setState_(
            AppKit.NSControlStateValueOn if self._config.hotkeys_enabled else AppKit.NSControlStateValueOff
        )
        view.addSubview_(self._hotkey_checkbox)
        y -= 32

        # Hotkey recorders
        self._hotkey_recorders = {}
        all_hotkeys = self._config.get_all_hotkeys()

        for mode in RewriteMode:
            view.addSubview_(self._create_label(DISPLAY_NAMES[mode] + ":", y))

            recorder = HotkeyRecorderField.alloc().initWithFrame_(
                Foundation.NSMakeRect(self.CONTENT_PADDING + self.LABEL_WIDTH + 10, y, 120, self.ROW_HEIGHT)
            )
            hk = all_hotkeys.get(mode.value, {"modifiers": "", "key": ""})
            recorder.set_hotkey(hk["modifiers"], hk["key"])
            recorder.setEditable_(True)
            view.addSubview_(recorder)

            self._hotkey_recorders[mode.value] = recorder
            y -= self.ROW_SPACING

        # Help text
        help_text = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, container_width - 40, 18)
        )
        help_text.setStringValue_("Click a shortcut field and press keys. Press Delete to clear.")
        help_text.setBezeled_(False)
        help_text.setDrawsBackground_(False)
        help_text.setEditable_(False)
        help_text.setSelectable_(False)
        help_text.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        help_text.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        view.addSubview_(help_text)

        # Save button
        save_btn = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(container_width - 100, 15, 80, 28)
        )
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        save_btn.setAction_("saveSettings:")
        save_btn.setTarget_(self)
        view.addSubview_(save_btn)

        self._content_container.addSubview_(view)
        self._content_views[0] = view

    def _create_speech_view(self):
        """Create the speech-to-text content view."""
        container_width = self._content_container.frame().size.width
        container_height = self._content_container.frame().size.height
        field_width = container_width - self.LABEL_WIDTH - 60

        view = AppKit.NSView.alloc().initWithFrame_(
            Foundation.NSMakeRect(0, 0, container_width, container_height)
        )

        # Title
        title = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, container_height - 36, 200, 24)
        )
        title.setStringValue_("Speech")
        title.setBezeled_(False)
        title.setDrawsBackground_(False)
        title.setEditable_(False)
        title.setSelectable_(False)
        title.setFont_(AppKit.NSFont.boldSystemFontOfSize_(20))
        view.addSubview_(title)

        y = container_height - 75

        # Enable Speech
        self._speech_enabled_checkbox = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, 250, self.ROW_HEIGHT)
        )
        self._speech_enabled_checkbox.setButtonType_(AppKit.NSSwitchButton)
        self._speech_enabled_checkbox.setTitle_("Enable Speech-to-Text")
        self._speech_enabled_checkbox.setState_(
            AppKit.NSControlStateValueOn if self._config.speech_enabled else AppKit.NSControlStateValueOff
        )
        view.addSubview_(self._speech_enabled_checkbox)
        y -= 45

        # Model selection
        view.addSubview_(self._create_label("Model:", y))

        # Model popup button
        popup_x = self.CONTENT_PADDING + self.LABEL_WIDTH + 10
        self._speech_model_popup = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            Foundation.NSMakeRect(popup_x, y, 150, self.ROW_HEIGHT), False
        )

        # Add model options with download status
        for model_name in WHISPER_MODELS.keys():
            info = WHISPER_MODELS[model_name]
            downloaded = self._speech_model_manager.is_model_downloaded(model_name)
            label = f"{model_name} ({info['size_mb']}MB)"
            if downloaded:
                label += " ✓"
            self._speech_model_popup.addItemWithTitle_(label)

        # Select current model
        current_model = self._config.speech_model
        model_names = list(WHISPER_MODELS.keys())
        if current_model in model_names:
            self._speech_model_popup.selectItemAtIndex_(model_names.index(current_model))

        self._speech_model_popup.setAction_("modelChanged:")
        self._speech_model_popup.setTarget_(self)
        view.addSubview_(self._speech_model_popup)

        # Download button
        self._speech_download_btn = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(popup_x + 160, y, 100, self.ROW_HEIGHT)
        )
        self._speech_download_btn.setTitle_("Download")
        self._speech_download_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self._speech_download_btn.setAction_("downloadModel:")
        self._speech_download_btn.setTarget_(self)
        self._update_download_button()
        view.addSubview_(self._speech_download_btn)

        y -= self.ROW_SPACING

        # Progress bar (hidden by default)
        self._speech_progress = AppKit.NSProgressIndicator.alloc().initWithFrame_(
            Foundation.NSMakeRect(popup_x, y, 260, 12)
        )
        self._speech_progress.setStyle_(AppKit.NSProgressIndicatorStyleBar)
        self._speech_progress.setMinValue_(0.0)
        self._speech_progress.setMaxValue_(1.0)
        self._speech_progress.setIndeterminate_(False)
        self._speech_progress.setHidden_(True)
        view.addSubview_(self._speech_progress)
        y -= self.ROW_SPACING

        # Language selection
        view.addSubview_(self._create_label("Language:", y))

        self._speech_lang_popup = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            Foundation.NSMakeRect(popup_x, y, 150, self.ROW_HEIGHT), False
        )

        for code, name in SUPPORTED_LANGUAGES.items():
            self._speech_lang_popup.addItemWithTitle_(name)

        # Select current language
        current_lang = self._config.speech_language
        lang_codes = list(SUPPORTED_LANGUAGES.keys())
        if current_lang in lang_codes:
            self._speech_lang_popup.selectItemAtIndex_(lang_codes.index(current_lang))

        view.addSubview_(self._speech_lang_popup)
        y -= self.ROW_SPACING

        # Speech hotkey
        view.addSubview_(self._create_label("Hotkey:", y))

        self._speech_hotkey_recorder = HotkeyRecorderField.alloc().initWithFrame_(
            Foundation.NSMakeRect(popup_x, y, 120, self.ROW_HEIGHT)
        )
        hk = self._config.get_speech_hotkey()
        self._speech_hotkey_recorder.set_hotkey(hk["modifiers"], hk["key"])
        self._speech_hotkey_recorder.setEditable_(True)
        view.addSubview_(self._speech_hotkey_recorder)
        y -= self.ROW_SPACING

        # Help text
        help_text = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, container_width - 40, 36)
        )
        help_text.setStringValue_(
            "Press and hold the hotkey to record. Release to transcribe.\n"
            "The transcribed text will be pasted at the cursor."
        )
        help_text.setBezeled_(False)
        help_text.setDrawsBackground_(False)
        help_text.setEditable_(False)
        help_text.setSelectable_(False)
        help_text.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        help_text.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        view.addSubview_(help_text)

        # Save button
        save_btn = AppKit.NSButton.alloc().initWithFrame_(
            Foundation.NSMakeRect(container_width - 100, 15, 80, 28)
        )
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        save_btn.setAction_("saveSettings:")
        save_btn.setTarget_(self)
        view.addSubview_(save_btn)

        self._content_container.addSubview_(view)
        self._content_views[1] = view

    def _update_download_button(self):
        """Update download button state based on selected model."""
        model_names = list(WHISPER_MODELS.keys())
        selected_idx = self._speech_model_popup.indexOfSelectedItem()
        if selected_idx < 0 or selected_idx >= len(model_names):
            return

        model_name = model_names[selected_idx]
        downloaded = self._speech_model_manager.is_model_downloaded(model_name)

        if downloaded:
            self._speech_download_btn.setTitle_("Downloaded")
            self._speech_download_btn.setEnabled_(False)
        else:
            self._speech_download_btn.setTitle_("Download")
            self._speech_download_btn.setEnabled_(True)

    def modelChanged_(self, sender):
        """Handle model selection change."""
        self._update_download_button()

    def downloadModel_(self, sender):
        """Download the selected model."""
        model_names = list(WHISPER_MODELS.keys())
        selected_idx = self._speech_model_popup.indexOfSelectedItem()
        if selected_idx < 0 or selected_idx >= len(model_names):
            return

        model_name = model_names[selected_idx]
        self._speech_download_btn.setEnabled_(False)
        self._speech_download_btn.setTitle_("Downloading...")
        self._speech_progress.setHidden_(False)
        self._speech_progress.setDoubleValue_(0.0)

        def progress_callback(progress: float):
            self._speech_progress.setDoubleValue_(progress)

        def do_download():
            try:
                self._speech_model_manager.download_model(model_name, progress_callback)
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._download_complete(model_name, None)
                )
            except Exception as e:
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._download_complete(model_name, str(e))
                )

        threading.Thread(target=do_download, name="ModelDownload", daemon=True).start()

    def _download_complete(self, model_name: str, error: Optional[str]):
        """Called on main thread when download completes."""
        self._speech_progress.setHidden_(True)

        if error:
            self._speech_download_btn.setTitle_("Download")
            self._speech_download_btn.setEnabled_(True)
            # Show error alert
            alert = AppKit.NSAlert.alloc().init()
            alert.setMessageText_("Download Failed")
            alert.setInformativeText_(error)
            alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
            alert.runModal()
        else:
            # Update popup label
            model_names = list(WHISPER_MODELS.keys())
            selected_idx = model_names.index(model_name)
            info = WHISPER_MODELS[model_name]
            label = f"{model_name} ({info['size_mb']}MB) ✓"
            self._speech_model_popup.itemAtIndex_(selected_idx).setTitle_(label)
            self._update_download_button()

    def _create_about_view(self):
        """Create the about content view."""
        container_width = self._content_container.frame().size.width
        container_height = self._content_container.frame().size.height

        view = AppKit.NSView.alloc().initWithFrame_(
            Foundation.NSMakeRect(0, 0, container_width, container_height)
        )

        # Title
        title = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, container_height - 36, 200, 24)
        )
        title.setStringValue_("About Vox")
        title.setBezeled_(False)
        title.setDrawsBackground_(False)
        title.setEditable_(False)
        title.setSelectable_(False)
        title.setFont_(AppKit.NSFont.boldSystemFontOfSize_(20))
        view.addSubview_(title)

        y = container_height - 70

        # App name
        app_name = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, 200, 24)
        )
        app_name.setStringValue_("Vox")
        app_name.setBezeled_(False)
        app_name.setDrawsBackground_(False)
        app_name.setEditable_(False)
        app_name.setSelectable_(False)
        app_name.setFont_(AppKit.NSFont.boldSystemFontOfSize_(18))
        view.addSubview_(app_name)
        y -= 25

        # Version
        version = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, 200, 18)
        )
        version.setStringValue_("Version 0.1.0")
        version.setBezeled_(False)
        version.setDrawsBackground_(False)
        version.setEditable_(False)
        version.setSelectable_(False)
        version.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        version.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        view.addSubview_(version)
        y -= 35

        # Description
        desc = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y - 40, container_width - 40, 60)
        )
        desc.setStringValue_(
            "AI-powered text rewriting through macOS contextual menu.\n\n"
            "Select text in any app, right-click, and choose a rewrite mode."
        )
        desc.setBezeled_(False)
        desc.setDrawsBackground_(False)
        desc.setEditable_(False)
        desc.setSelectable_(False)
        desc.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        view.addSubview_(desc)
        y -= 110

        # Shortcuts header
        shortcuts_hdr = AppKit.NSTextField.alloc().initWithFrame_(
            Foundation.NSMakeRect(self.CONTENT_PADDING, y, 200, 18)
        )
        shortcuts_hdr.setStringValue_("Keyboard Shortcuts")
        shortcuts_hdr.setBezeled_(False)
        shortcuts_hdr.setDrawsBackground_(False)
        shortcuts_hdr.setEditable_(False)
        shortcuts_hdr.setSelectable_(False)
        shortcuts_hdr.setFont_(AppKit.NSFont.boldSystemFontOfSize_(14))
        view.addSubview_(shortcuts_hdr)
        y -= 25

        # List shortcuts
        all_hotkeys = self._config.get_all_hotkeys()
        for mode in RewriteMode:
            hk = all_hotkeys.get(mode.value, {"modifiers": "", "key": ""})
            if hk["key"]:
                mod_mask = parse_modifiers(hk["modifiers"])
                display = format_hotkey_display(mod_mask, hk["key"])

                shortcut = AppKit.NSTextField.alloc().initWithFrame_(
                    Foundation.NSMakeRect(self.CONTENT_PADDING, y, container_width - 40, 18)
                )
                shortcut.setStringValue_(f"{display}    {DISPLAY_NAMES[mode]}")
                shortcut.setBezeled_(False)
                shortcut.setDrawsBackground_(False)
                shortcut.setEditable_(False)
                shortcut.setSelectable_(False)
                shortcut.setFont_(AppKit.NSFont.systemFontOfSize_(12))
                view.addSubview_(shortcut)
                y -= 22

        self._content_container.addSubview_(view)
        self._content_views[2] = view

    def saveSettings_(self, sender):
        """Save the settings."""
        api_key = self._api_field.stringValue().strip()
        model = self._model_field.stringValue().strip() or "gpt-4o-mini"
        base_url = self._url_field.stringValue().strip() or None
        auto_start = self._auto_checkbox.state() == AppKit.NSControlStateValueOn
        thinking_mode = self._thinking_checkbox.state() == AppKit.NSControlStateValueOn
        hotkeys_enabled = self._hotkey_checkbox.state() == AppKit.NSControlStateValueOn

        hotkey_configs = {}
        for mode_value, recorder in self._hotkey_recorders.items():
            hotkey_configs[mode_value] = {
                "modifiers": recorder.get_modifiers_string(),
                "key": recorder.get_key_string(),
            }

        # Speech settings
        speech_enabled = self._speech_enabled_checkbox.state() == AppKit.NSControlStateValueOn

        model_names = list(WHISPER_MODELS.keys())
        selected_idx = self._speech_model_popup.indexOfSelectedItem()
        speech_model = model_names[selected_idx] if 0 <= selected_idx < len(model_names) else "base"

        lang_codes = list(SUPPORTED_LANGUAGES.keys())
        selected_lang_idx = self._speech_lang_popup.indexOfSelectedItem()
        speech_language = lang_codes[selected_lang_idx] if 0 <= selected_lang_idx < len(lang_codes) else "auto"

        speech_hotkey = {
            "modifiers": self._speech_hotkey_recorder.get_modifiers_string(),
            "key": self._speech_hotkey_recorder.get_key_string(),
        }

        # Save to config
        if api_key:
            self._config.set_api_key(api_key)

        self._config.model = model
        self._config.base_url = base_url

        if auto_start != self._config.auto_start:
            self._config.set_auto_start(auto_start)

        self._config.thinking_mode = thinking_mode

        self._config.hotkeys_enabled = hotkeys_enabled
        for mode_value, hk in hotkey_configs.items():
            self._config.set_mode_hotkey(mode_value, hk["modifiers"], hk["key"])

        # Save speech settings
        self._config.speech_enabled = speech_enabled
        self._config.speech_model = speech_model
        self._config.speech_language = speech_language
        self._config.set_speech_hotkey(speech_hotkey["modifiers"], speech_hotkey["key"])

        if self._save_callback:
            self._save_callback(
                api_key, model, base_url, auto_start, hotkeys_enabled, hotkey_configs,
                speech_enabled, speech_model, speech_language, speech_hotkey,
                thinking_mode
            )

        self.window().close()

    def windowWillClose_(self, notification):
        """Handle window close."""
        pass


# Singleton
_preferences_controller: Optional[PreferencesWindowController] = None


def show_preferences_window(save_callback: Callable = None):
    """Show the preferences window."""
    global _preferences_controller

    if _preferences_controller is None:
        _preferences_controller = PreferencesWindowController.alloc().init()

    _preferences_controller.setSaveCallback_(save_callback)
    _preferences_controller.showWindow_(None)
