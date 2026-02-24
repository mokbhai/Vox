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
from vox.notifications import LoadingBarManager, ErrorNotifier, RecordingToastManager
from vox.hotkey import (
    create_hotkey_manager,
    KEY_CODE_TO_CHAR,
    MODIFIER_SYMBOLS,
    format_hotkey_display,
    modifier_mask_to_string,
    parse_modifiers,
)
from vox.preferences import show_preferences_window
from vox.speech import (
    AudioRecorder,
    SpeechTranscriber,
    WhisperModelManager,
    SpeechError,
    MicrophonePermissionError,
    ModelNotDownloadedError,
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
        source = CGEventSourceCreate(kCGEventSourceStateCombinedSessionState)

        # Press Cmd
        cmd_down = CGEventCreateKeyboardEvent(source, 0x37, True)
        # Press C
        c_down = CGEventCreateKeyboardEvent(source, 0x08, True)
        # Release C
        c_up = CGEventCreateKeyboardEvent(source, 0x08, False)
        # Release Cmd
        cmd_up = CGEventCreateKeyboardEvent(source, 0x37, False)

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

        # Wait for the copy to complete
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
        cmd_down = CGEventCreateKeyboardEvent(source, 0x37, True)
        # Press V
        v_down = CGEventCreateKeyboardEvent(source, 0x09, True)
        # Release V
        v_up = CGEventCreateKeyboardEvent(source, 0x09, False)
        # Release Cmd
        cmd_up = CGEventCreateKeyboardEvent(source, 0x37, False)

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
        if self.app:
            self.app._show_settings()

    def showAbout_(self, sender):
        """Show about."""
        if self.app:
            self.app._show_about()

    def quit_(self, sender):
        """Quit."""
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

        # Speech-to-text support
        self._speech_model_manager = WhisperModelManager()
        self._transcriber = SpeechTranscriber(self._speech_model_manager)
        self._recording_toast = RecordingToastManager()
        self._is_speech_recording = False

        # Register speech hotkey if enabled
        if self.config.speech_enabled:
            self._apply_speech_hotkey_config()

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

    def _apply_speech_hotkey_config(self):
        """Read speech hotkey from config and apply to the hotkey manager."""
        hk = self.config.get_speech_hotkey()
        self._hotkey_manager.set_speech_hotkey(
            hk["modifiers"], hk["key"], self._handle_speech_hotkey
        )

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
            "Preferences...", "showSettings:", ","
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
        """Show the preferences window."""
        show_preferences_window(self._save_settings)

    def _save_settings(self, api_key: str, model: str, base_url: Optional[str], auto_start: bool,
                      hotkeys_enabled: bool, hotkey_configs: dict,
                      speech_enabled: bool = True, speech_model: str = "base",
                      speech_language: str = "auto", speech_hotkey: dict = None,
                      thinking_mode: bool = False):
        """Save the settings."""
        if api_key:
            self.config.set_api_key(api_key)
            self.service_provider.update_api_key()

        self.config.model = model
        self.config.base_url = base_url
        self.service_provider.update_model()

        if auto_start != self.config.auto_start:
            self.config.set_auto_start(auto_start)

        self.config.thinking_mode = thinking_mode

        # Update hot key settings
        self.config.hotkeys_enabled = hotkeys_enabled
        for mode_value, hk in hotkey_configs.items():
            self.config.set_mode_hotkey(mode_value, hk["modifiers"], hk["key"])

        # Re-register hot keys with new settings
        self._hotkey_manager.set_enabled(hotkeys_enabled)
        self._apply_hotkey_config()
        if hotkeys_enabled:
            self._hotkey_manager.reregister_hotkey()

        # Update speech settings
        self.config.speech_enabled = speech_enabled
        self.config.speech_model = speech_model
        self.config.speech_language = speech_language
        if speech_hotkey:
            self.config.set_speech_hotkey(
                speech_hotkey["modifiers"], speech_hotkey["key"]
            )

        # Re-register speech hotkey
        if speech_enabled:
            self._apply_speech_hotkey_config()
            if self._hotkey_manager.is_registered():
                self._hotkey_manager.reregister_hotkey()

    def _show_about(self):
        """Show the about dialog (opens preferences on About tab)."""
        show_preferences_window(self._save_settings)

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
        thinking_mode = self.config.thinking_mode

        # Show loading bar at top of screen (main thread)
        self._loading_bar.show()

        def _do_rewrite():
            try:
                result = api_client.rewrite(text, mode, thinking_mode)
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

    # Speech-to-Text handlers

    def _handle_speech_hotkey(self, is_keydown: bool):
        """Handle speech hotkey press/release."""
        try:
            if not self.config.speech_enabled:
                return

            if is_keydown:
                self._start_speech_recording()
            else:
                self._stop_and_transcribe()
        except Exception as e:
            print(f"Error in _handle_speech_hotkey: {e}", flush=True)
            import traceback
            traceback.print_exc()
            # Reset recording state on error
            self._is_speech_recording = False
            try:
                self._recording_toast.hide()
            except Exception:
                pass

    def _start_speech_recording(self):
        """Start recording audio for speech-to-text."""
        if self._is_speech_recording:
            return

        # Check microphone permission
        if not AudioRecorder.has_microphone_permission():
            self._show_microphone_permission_dialog()
            return

        # Check if model is downloaded
        model_name = self.config.speech_model
        if not self._speech_model_manager.is_model_downloaded(model_name):
            ErrorNotifier.show_error(
                "Vox - Model Not Downloaded",
                f"Please download the '{model_name}' model in Settings → Speech"
            )
            return

        try:
            # Start recording with level callback
            self._transcriber.start_recording(self._recording_toast.update_level)
            self._is_speech_recording = True
            self._recording_toast.show_recording()
            print("Speech recording started", flush=True)

        except MicrophonePermissionError as e:
            self._show_microphone_permission_dialog()
        except SpeechError as e:
            ErrorNotifier.show_generic_error(str(e))

    def _stop_and_transcribe(self):
        """Stop recording and transcribe the audio."""
        if not self._is_speech_recording:
            return

        self._is_speech_recording = False
        self._recording_toast.show_transcribing()

        model_name = self.config.speech_model
        language = self.config.speech_language

        def _do_transcribe():
            try:
                text = self._transcriber.stop_and_transcribe(model_name, language)

                # Dispatch result to main thread
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._finish_speech(text)
                )
            except ModelNotDownloadedError:
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._fail_speech(f"Model '{model_name}' not downloaded")
                )
            except SpeechError as e:
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._fail_speech(str(e))
                )
            except Exception as e:
                print(f"Transcription error: {e}")
                import traceback
                traceback.print_exc()
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self._fail_speech(f"Transcription failed: {e}")
                )

        threading.Thread(target=_do_transcribe, name="VoxSpeech", daemon=True).start()

    def _finish_speech(self, text: Optional[str]):
        """Called on the main thread after successful transcription."""
        self._recording_toast.hide()

        if text:
            print(f"Transcribed: {text!r}", flush=True)
            paste_text(text)
        else:
            # No speech detected
            ErrorNotifier.show_error(
                "Vox",
                "No speech detected"
            )

    def _fail_speech(self, message: str):
        """Called on the main thread after failed transcription."""
        self._recording_toast.hide()
        ErrorNotifier.show_generic_error(message)

    def _show_microphone_permission_dialog(self):
        """Show dialog for microphone permission."""
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Microphone Permission Required")
        alert.setInformativeText_(
            "Vox needs microphone access for speech-to-text.\n\n"
            "1. Open System Settings\n"
            "2. Go to Privacy & Security → Microphone\n"
            "3. Enable Vox (or Terminal in dev mode)\n\n"
            "Then try again."
        )
        alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
        alert.addButtonWithTitle_("Open System Settings")
        alert.addButtonWithTitle_("Cancel")

        AppKit.NSApp.activateIgnoringOtherApps_(True)

        response = alert.runModal()

        if response == AppKit.NSAlertFirstButtonReturn:
            AppKit.NSWorkspace.sharedWorkspace().openURL_(
                AppKit.NSURL.URLWithString_(
                    "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
                )
            )

    def run(self):
        """Run the application."""
        # Register the service
        self.service_provider.register_services()

        # Register the hot key
        self._hotkey_manager.register_hotkey()

        # Run the app
        AppHelper.runEventLoop(installInterrupt=True)
