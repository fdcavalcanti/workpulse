"""Tests for tracker module."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from workpulse.database import Database
from workpulse.tracker import WorkTracker


class TestWorkTracker:
    """Test suite for WorkTracker class."""

    @pytest.fixture
    def temp_db(self) -> Database:
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        db = Database(db_path=db_path)
        db.connect()
        yield db
        db.close()
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def tracker(self, temp_db) -> WorkTracker:
        """Create a WorkTracker instance with temporary database."""
        return WorkTracker(database=temp_db)

    def test_init_default_database(self, tmp_path, monkeypatch):
        """Test WorkTracker initialization with default database."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        tracker = WorkTracker()
        assert tracker.database is not None
        assert isinstance(tracker.database, Database)

    def test_init_custom_database(self, temp_db):
        """Test WorkTracker initialization with custom database."""
        tracker = WorkTracker(database=temp_db)
        assert tracker.database == temp_db

    @patch("workpulse.tracker.is_user_active")
    def test_update_time_user_active(self, mock_is_active, tracker, temp_db):
        """Test update_time when user is active."""
        mock_is_active.return_value = True

        # Initial state - no time logged
        today_log = temp_db.get_today_log()
        assert today_log.total_active_time == 0.0

        # Update time
        tracker.update_time()

        # Should have added 60 seconds
        today_log = temp_db.get_today_log()
        assert today_log.total_active_time == 60.0

    @patch("workpulse.tracker.is_user_active")
    def test_update_time_user_inactive(self, mock_is_active, tracker, temp_db):
        """Test update_time when user is inactive."""
        mock_is_active.return_value = False

        # Initial state - no time logged
        today_log = temp_db.get_today_log()
        assert today_log.total_active_time == 0.0

        # Update time
        tracker.update_time()

        # Should not have added any time
        today_log = temp_db.get_today_log()
        assert today_log.total_active_time == 0.0

    @patch("workpulse.tracker.is_user_active")
    def test_update_time_multiple_updates(self, mock_is_active, tracker, temp_db):
        """Test multiple update_time calls."""
        mock_is_active.return_value = True

        # Update 5 times
        for _ in range(5):
            tracker.update_time()

        # Should have 5 * 60 = 300 seconds
        today_log = temp_db.get_today_log()
        assert today_log.total_active_time == 300.0

    @patch("workpulse.tracker.is_user_active")
    def test_update_time_exception_handling(self, mock_is_active, tracker):
        """Test update_time exception handling."""
        mock_is_active.side_effect = Exception("Test error")

        with pytest.raises(Exception, match="Test error"):
            tracker.update_time()

    @patch("workpulse.tracker.is_user_active")
    def test_get_current_status_active(self, mock_is_active, tracker, temp_db):
        """Test get_current_status when user is active."""
        mock_is_active.return_value = True

        # Add some time first
        temp_db.increment_daily_time(120.0)

        status, total_seconds = tracker.get_current_status()

        assert status == "active"
        assert total_seconds == 120.0

    @patch("workpulse.tracker.is_user_active")
    def test_get_current_status_inactive(self, mock_is_active, tracker, temp_db):
        """Test get_current_status when user is inactive."""
        mock_is_active.return_value = False

        # Add some time first
        temp_db.increment_daily_time(180.0)

        status, total_seconds = tracker.get_current_status()

        assert status == "inactive"
        assert total_seconds == 180.0

    @patch("workpulse.tracker.is_user_active")
    def test_get_current_status_exception_handling(self, mock_is_active, tracker):
        """Test get_current_status exception handling."""
        mock_is_active.side_effect = Exception("Test error")

        status, total_seconds = tracker.get_current_status()

        assert status == "unknown"
        assert total_seconds == 0.0

    @patch("workpulse.tracker.is_user_active")
    def test_get_current_status_no_time_logged(self, mock_is_active, tracker):
        """Test get_current_status when no time has been logged."""
        mock_is_active.return_value = True

        status, total_seconds = tracker.get_current_status()

        assert status == "active"
        assert total_seconds == 0.0
