"""Tests for state_checker module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from workpulse.state_checker import is_user_active


class TestIsUserActive:
    """Test suite for is_user_active function."""

    @patch("workpulse.state_checker._is_system_suspended")
    @patch("workpulse.state_checker.subprocess.run")
    @patch("workpulse.state_checker.os.getenv")
    def test_user_active_not_locked(self, mock_getenv, mock_subprocess, mock_suspended):
        """Test is_user_active when user is active and not locked."""
        mock_suspended.return_value = False

        def getenv_side_effect(key, default=None):
            if key == "USER":
                return "testuser"
            elif key == "USERNAME":
                return None
            return default if default else None

        mock_getenv.side_effect = getenv_side_effect

        # Mock list-sessions output (format: SESSION_ID UID USERNAME SEAT TTY STATE LOCKED)
        list_sessions_result = MagicMock()
        list_sessions_result.returncode = 0
        list_sessions_result.stdout = "c1 1000 testuser seat0 - active no"

        # Mock show-session output (active, not locked)
        show_session_result = MagicMock()
        show_session_result.returncode = 0
        show_session_result.stdout = "Active=yes\nLockedHint=no"

        mock_subprocess.side_effect = [list_sessions_result, show_session_result]

        assert is_user_active() is True

    @patch("workpulse.state_checker._is_system_suspended")
    @patch("workpulse.state_checker.subprocess.run")
    @patch.dict(os.environ, {"USER": "testuser"})
    def test_user_active_but_locked(self, mock_subprocess, mock_suspended):
        """Test is_user_active when user is active but locked."""
        mock_suspended.return_value = False

        # Mock list-sessions output (format: SESSION_ID UID USERNAME SEAT TTY STATE LOCKED)
        list_sessions_result = MagicMock()
        list_sessions_result.returncode = 0
        list_sessions_result.stdout = "c1 1000 testuser seat0 - active no"

        # Mock show-session output (active, but locked)
        show_session_result = MagicMock()
        show_session_result.returncode = 0
        show_session_result.stdout = "Active=yes\nLockedHint=yes\n"

        mock_subprocess.side_effect = [list_sessions_result, show_session_result]

        assert is_user_active() is False

    @patch("workpulse.state_checker._is_system_suspended")
    @patch("workpulse.state_checker.subprocess.run")
    @patch.dict(os.environ, {"USER": "testuser"})
    def test_user_inactive(self, mock_subprocess, mock_suspended):
        """Test is_user_active when user session is inactive."""
        mock_suspended.return_value = False

        # Mock list-sessions output (format: SESSION_ID UID USERNAME SEAT TTY STATE LOCKED)
        list_sessions_result = MagicMock()
        list_sessions_result.returncode = 0
        list_sessions_result.stdout = "c1 1000 testuser seat0 - active no"

        # Mock show-session output (inactive)
        show_session_result = MagicMock()
        show_session_result.returncode = 0
        show_session_result.stdout = "Active=no\nLockedHint=no\n"

        mock_subprocess.side_effect = [list_sessions_result, show_session_result]

        assert is_user_active() is False

    @patch("workpulse.state_checker.subprocess.run")
    @patch.dict(os.environ, {"USER": "testuser"})
    def test_no_session_found(self, mock_subprocess):
        """Test is_user_active when no session is found for user."""
        # Mock list-sessions output (no matching user) (format: SESSION_ID UID USERNAME SEAT TTY STATE LOCKED)
        list_sessions_result = MagicMock()
        list_sessions_result.returncode = 0
        list_sessions_result.stdout = "c1 1001 otheruser seat0 - active no"

        mock_subprocess.return_value = list_sessions_result

        assert is_user_active() is False

    @patch("workpulse.state_checker.subprocess.run")
    @patch.dict(os.environ, {"USER": "testuser"})
    def test_list_sessions_fails(self, mock_subprocess):
        """Test is_user_active when list-sessions command fails."""
        # Mock list-sessions failure
        list_sessions_result = MagicMock()
        list_sessions_result.returncode = 1
        list_sessions_result.stderr = "Command failed"

        mock_subprocess.return_value = list_sessions_result

        assert is_user_active() is False

    @patch("workpulse.state_checker.subprocess.run")
    @patch.dict(os.environ, {"USER": "testuser"})
    def test_show_session_fails(self, mock_subprocess):
        """Test is_user_active when show-session command fails."""
        # Mock list-sessions output (format: SESSION_ID UID USERNAME SEAT TTY STATE LOCKED)
        list_sessions_result = MagicMock()
        list_sessions_result.returncode = 0
        list_sessions_result.stdout = "c1 1000 testuser seat0 - active no"

        # Mock show-session failure
        show_session_result = MagicMock()
        show_session_result.returncode = 1
        show_session_result.stderr = "Command failed"

        mock_subprocess.side_effect = [list_sessions_result, show_session_result]

        assert is_user_active() is False

    @patch("workpulse.state_checker.subprocess.run")
    def test_no_username_available(self, mock_subprocess):
        """Test is_user_active when username cannot be determined."""
        # Remove USER and USERNAME from environment
        with patch.dict(os.environ, {}, clear=True):
            assert is_user_active() is False

    @patch("workpulse.state_checker.subprocess.run")
    @patch.dict(os.environ, {"USER": "testuser"})
    def test_timeout_exception(self, mock_subprocess):
        """Test is_user_active when subprocess times out."""
        import subprocess

        mock_subprocess.side_effect = subprocess.TimeoutExpired("loginctl", 5)

        assert is_user_active() is False

    @patch("workpulse.state_checker.subprocess.run")
    @patch.dict(os.environ, {"USER": "testuser"})
    def test_generic_exception(self, mock_subprocess):
        """Test is_user_active when generic exception occurs."""
        mock_subprocess.side_effect = Exception("Unexpected error")

        assert is_user_active() is False

    @patch("workpulse.state_checker._is_system_suspended")
    @patch("workpulse.state_checker.subprocess.run")
    @patch("workpulse.state_checker.os.getenv")
    def test_multiple_sessions_finds_correct_one(
        self, mock_getenv, mock_subprocess, mock_suspended
    ):
        """Test is_user_active with multiple sessions finds correct user."""
        mock_suspended.return_value = False

        def getenv_side_effect(key, default=None):
            if key == "USER":
                return "testuser"
            elif key == "USERNAME":
                return None
            return default if default else None

        mock_getenv.side_effect = getenv_side_effect

        # Mock list-sessions output with multiple users (format: SESSION_ID UID USERNAME SEAT TTY STATE LOCKED)
        list_sessions_result = MagicMock()
        list_sessions_result.returncode = 0
        list_sessions_result.stdout = "c1 1001 otheruser seat0 - active no\nc2 1000 testuser seat1 - active no\nc3 1002 anotheruser seat2 - active no"

        # Mock show-session output (active, not locked)
        show_session_result = MagicMock()
        show_session_result.returncode = 0
        show_session_result.stdout = "Active=yes\nLockedHint=no"

        mock_subprocess.side_effect = [list_sessions_result, show_session_result]

        assert is_user_active() is True
        # Verify show-session was called with correct session ID
        assert mock_subprocess.call_count == 2
        show_call = mock_subprocess.call_args_list[1]
        assert "c2" in show_call[0][0]  # Session ID should be c2

    @patch("workpulse.state_checker._is_system_suspended")
    @patch("workpulse.state_checker.subprocess.run")
    @patch("workpulse.state_checker.os.getenv")
    def test_uses_username_env_var(self, mock_getenv, mock_subprocess, mock_suspended):
        """Test is_user_active uses USERNAME when USER is not available."""
        mock_suspended.return_value = False

        def getenv_side_effect(key, default=None):
            if key == "USER":
                return None
            elif key == "USERNAME":
                return "testuser"
            return default if default else None

        mock_getenv.side_effect = getenv_side_effect

        # Mock list-sessions output (format: SESSION_ID UID USERNAME SEAT TTY STATE LOCKED)
        list_sessions_result = MagicMock()
        list_sessions_result.returncode = 0
        list_sessions_result.stdout = "c1 1000 testuser seat0 - active no"

        # Mock show-session output
        show_session_result = MagicMock()
        show_session_result.returncode = 0
        show_session_result.stdout = "Active=yes\nLockedHint=no"

        mock_subprocess.side_effect = [list_sessions_result, show_session_result]

        assert is_user_active() is True
