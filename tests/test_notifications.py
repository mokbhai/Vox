"""Tests for the notifications module."""
import pytest
from unittest.mock import patch, MagicMock, Mock, call
from vox.notifications import (
    ToastWindow,
    ToastManager,
    ErrorNotifier,
)


class TestToastWindow:
    """Tests for ToastWindow class.

    Note: ToastWindow is a PyObjC class that uses objc_ivars and selectors,
    which cannot be easily mocked with unittest.mock. These tests focus on
    the class-level behavior and singleton pattern.
    """

    def test_class_has_instance_attribute(self):
        """Test that ToastWindow has _instance class attribute."""
        assert hasattr(ToastWindow, '_instance')

    def test_class_has_text_field_ivar(self):
        """Test that ToastWindow has _text_field ivar declaration."""
        # This is an objc.ivar() which is a special attribute
        assert hasattr(ToastWindow, '_text_field')

    def test_class_has_create_method(self):
        """Test that ToastWindow has create class method."""
        assert hasattr(ToastWindow, 'create')
        assert callable(ToastWindow.create)

    def test_class_has_get_instance_method(self):
        """Test that ToastWindow has get_instance class method."""
        assert hasattr(ToastWindow, 'get_instance')
        assert callable(ToastWindow.get_instance)

    def test_class_has_show_at_cursor_method(self):
        """Test that ToastWindow has show_at_cursor instance method."""
        # This is an instance method, so we need to check the method exists
        assert hasattr(ToastWindow, 'show_at_cursor')

    def test_class_has_hide_method(self):
        """Test that ToastWindow has hide instance method."""
        assert hasattr(ToastWindow, 'hide')


class TestToastManager:
    """Tests for ToastManager class."""

    def test_init_default_values(self):
        """Test ToastManager initialization with default values."""
        manager = ToastManager()
        assert manager._toast is None
        assert manager._is_visible is False

    @patch('vox.notifications.ToastWindow')
    def test_show_displays_toast(self, mock_window_class):
        """Test show displays toast with message."""
        mock_toast = MagicMock()
        mock_window_class.get_instance.return_value = mock_toast

        manager = ToastManager()
        manager.show("Test message")

        mock_toast._text_field.setStringValue_.assert_called_once_with("Test message")
        mock_toast.show_at_cursor.assert_called_once()
        assert manager._is_visible is True

    @patch('vox.notifications.ToastWindow')
    def test_show_default_message(self, mock_window_class):
        """Test show with default message."""
        mock_toast = MagicMock()
        mock_window_class.get_instance.return_value = mock_toast

        manager = ToastManager()
        manager.show()

        mock_toast._text_field.setStringValue_.assert_called_once()
        # Check default message
        call_args = mock_toast._text_field.setStringValue_.call_args[0][0]
        assert "Rewriting" in call_args or "Vox" in call_args

    @patch('vox.notifications.ToastWindow')
    def test_hide_hides_toast_when_visible(self, mock_window_class):
        """Test hide hides toast when visible."""
        mock_toast = MagicMock()
        mock_window_class.get_instance.return_value = mock_toast

        manager = ToastManager()
        manager._is_visible = True
        manager.hide()

        mock_toast.hide.assert_called_once()
        assert manager._is_visible is False

    @patch('vox.notifications.ToastWindow')
    def test_hide_does_nothing_when_not_visible(self, mock_window_class):
        """Test hide does nothing when toast not visible."""
        mock_toast = MagicMock()
        mock_window_class.get_instance.return_value = mock_toast

        manager = ToastManager()
        manager._is_visible = False
        manager.hide()

        mock_toast.hide.assert_not_called()
        assert manager._is_visible is False

    @patch('vox.notifications.ToastWindow')
    def test_is_visible_returns_true_when_visible(self, mock_window_class):
        """Test is_visible returns True when toast is visible."""
        manager = ToastManager()
        manager._is_visible = True
        assert manager.is_visible() is True

    @patch('vox.notifications.ToastWindow')
    def test_is_visible_returns_false_when_not_visible(self, mock_window_class):
        """Test is_visible returns False when toast not visible."""
        manager = ToastManager()
        assert manager.is_visible() is False

    @patch('vox.notifications.ToastWindow')
    def test_show_multiple_times(self, mock_window_class):
        """Test multiple show/hide cycles."""
        mock_toast = MagicMock()
        mock_window_class.get_instance.return_value = mock_toast

        manager = ToastManager()

        # First show
        manager.show("Message 1")
        assert manager._is_visible is True

        # Hide
        manager.hide()
        assert manager._is_visible is False

        # Show again
        manager.show("Message 2")
        assert manager._is_visible is True

        assert mock_toast.show_at_cursor.call_count == 2
        assert mock_toast.hide.call_count == 1


class TestErrorNotifier:
    """Tests for ErrorNotifier class."""

    def test_show_error_creates_notification(self):
        """Test show_error creates and delivers notification."""
        with patch('vox.notifications.AppKit') as mock_appkit:
            mock_notification = MagicMock()
            mock_appkit.NSUserNotification.alloc().init.return_value = mock_notification
            mock_center = MagicMock()
            mock_appkit.NSUserNotificationCenter.defaultUserNotificationCenter.return_value = mock_center
            mock_appkit.NSUserNotificationDefaultSoundName = "Default"

            ErrorNotifier.show_error("Test Title", "Test Message")

            mock_notification.setTitle_.assert_called_with("Test Title")
            mock_notification.setInformativeText_.assert_called_with("Test Message")
            mock_notification.setSoundName_.assert_called()
            mock_center.deliverNotification_.assert_called_with(mock_notification)

    def test_show_api_key_error(self):
        """Test show_api_key_error shows appropriate notification."""
        with patch('vox.notifications.AppKit') as mock_appkit:
            mock_notification = MagicMock()
            mock_appkit.NSUserNotification.alloc().init.return_value = mock_notification
            mock_center = MagicMock()
            mock_appkit.NSUserNotificationCenter.defaultUserNotificationCenter.return_value = mock_center
            mock_appkit.NSUserNotificationDefaultSoundName = "Default"

            ErrorNotifier.show_api_key_error()

            title_arg = mock_notification.setTitle_.call_args[0][0]
            message_arg = mock_notification.setInformativeText_.call_args[0][0]

            assert "API Key" in title_arg
            assert "OpenAI" in message_arg or "API key" in message_arg.lower()

    def test_show_network_error(self):
        """Test show_network_error shows appropriate notification."""
        with patch('vox.notifications.AppKit') as mock_appkit:
            mock_notification = MagicMock()
            mock_appkit.NSUserNotification.alloc().init.return_value = mock_notification
            mock_center = MagicMock()
            mock_appkit.NSUserNotificationCenter.defaultUserNotificationCenter.return_value = mock_center
            mock_appkit.NSUserNotificationDefaultSoundName = "Default"

            ErrorNotifier.show_network_error()

            title_arg = mock_notification.setTitle_.call_args[0][0]
            message_arg = mock_notification.setInformativeText_.call_args[0][0]

            assert "Network" in title_arg
            assert "connection" in message_arg.lower()

    def test_show_rate_limit_error(self):
        """Test show_rate_limit_error shows appropriate notification."""
        with patch('vox.notifications.AppKit') as mock_appkit:
            mock_notification = MagicMock()
            mock_appkit.NSUserNotification.alloc().init.return_value = mock_notification
            mock_center = MagicMock()
            mock_appkit.NSUserNotificationCenter.defaultUserNotificationCenter.return_value = mock_center
            mock_appkit.NSUserNotificationDefaultSoundName = "Default"

            ErrorNotifier.show_rate_limit_error()

            title_arg = mock_notification.setTitle_.call_args[0][0]
            message_arg = mock_notification.setInformativeText_.call_args[0][0]

            assert "Rate Limit" in title_arg
            assert "OpenAI" in message_arg

    def test_show_invalid_key_error(self):
        """Test show_invalid_key_error shows appropriate notification."""
        with patch('vox.notifications.AppKit') as mock_appkit:
            mock_notification = MagicMock()
            mock_appkit.NSUserNotification.alloc().init.return_value = mock_notification
            mock_center = MagicMock()
            mock_appkit.NSUserNotificationCenter.defaultUserNotificationCenter.return_value = mock_center
            mock_appkit.NSUserNotificationDefaultSoundName = "Default"

            ErrorNotifier.show_invalid_key_error()

            title_arg = mock_notification.setTitle_.call_args[0][0]
            message_arg = mock_notification.setInformativeText_.call_args[0][0]

            assert "Invalid" in title_arg and "API Key" in title_arg
            assert "check vox settings" in message_arg.lower()

    def test_show_generic_error(self):
        """Test show_generic_error shows appropriate notification."""
        with patch('vox.notifications.AppKit') as mock_appkit:
            mock_notification = MagicMock()
            mock_appkit.NSUserNotification.alloc().init.return_value = mock_notification
            mock_center = MagicMock()
            mock_appkit.NSUserNotificationCenter.defaultUserNotificationCenter.return_value = mock_center
            mock_appkit.NSUserNotificationDefaultSoundName = "Default"

            ErrorNotifier.show_generic_error("Something went wrong")

            title_arg = mock_notification.setTitle_.call_args[0][0]
            message_arg = mock_notification.setInformativeText_.call_args[0][0]

            assert "Vox Error" in title_arg or "Error" in title_arg
            assert "Something went wrong" in message_arg

    def test_show_generic_error_with_long_message(self):
        """Test show_generic_error with long error message."""
        with patch('vox.notifications.AppKit') as mock_appkit:
            mock_notification = MagicMock()
            mock_appkit.NSUserNotification.alloc().init.return_value = mock_notification
            mock_center = MagicMock()
            mock_appkit.NSUserNotificationCenter.defaultUserNotificationCenter.return_value = mock_center
            mock_appkit.NSUserNotificationDefaultSoundName = "Default"

            long_message = "This is a very long error message that contains a lot of details about what went wrong"
            ErrorNotifier.show_generic_error(long_message)

            message_arg = mock_notification.setInformativeText_.call_args[0][0]
            assert long_message in message_arg

    def test_all_error_methods_set_sound(self):
        """Test that all error methods set notification sound."""
        with patch('vox.notifications.AppKit') as mock_appkit:
            mock_notification = MagicMock()
            mock_appkit.NSUserNotification.alloc().init.return_value = mock_notification
            mock_center = MagicMock()
            mock_appkit.NSUserNotificationCenter.defaultUserNotificationCenter.return_value = mock_center
            mock_appkit.NSUserNotificationDefaultSoundName = "Default"

            # Test each method
            ErrorNotifier.show_api_key_error()
            ErrorNotifier.show_network_error()
            ErrorNotifier.show_rate_limit_error()
            ErrorNotifier.show_invalid_key_error()
            ErrorNotifier.show_generic_error("Test")

            # Sound should be set 5 times (once per call)
            assert mock_notification.setSoundName_.call_count == 5

    def test_all_error_methods_deliver_notification(self):
        """Test that all error methods deliver notification."""
        with patch('vox.notifications.AppKit') as mock_appkit:
            mock_notification = MagicMock()
            mock_appkit.NSUserNotification.alloc().init.return_value = mock_notification
            mock_center = MagicMock()
            mock_appkit.NSUserNotificationCenter.defaultUserNotificationCenter.return_value = mock_center
            mock_appkit.NSUserNotificationDefaultSoundName = "Default"

            # Test each method
            ErrorNotifier.show_api_key_error()
            ErrorNotifier.show_network_error()
            ErrorNotifier.show_rate_limit_error()
            ErrorNotifier.show_invalid_key_error()
            ErrorNotifier.show_generic_error("Test")

            # Notification should be delivered 5 times
            assert mock_center.deliverNotification_.call_count == 5
