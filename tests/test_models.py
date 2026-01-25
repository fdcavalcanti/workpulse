"""Tests for models module."""

from datetime import date, datetime

import pytest

from workpulse.models import DailyLog, Session, SessionState


class TestSessionState:
    """Test suite for SessionState enum."""

    def test_enum_values(self):
        """Test that all expected enum values exist."""
        assert SessionState.ACTIVE.value == "active"
        assert SessionState.SUSPENDED.value == "suspended"
        assert SessionState.LOCKED.value == "locked"
        assert SessionState.HIBERNATED.value == "hibernated"
        assert SessionState.UNKNOWN.value == "unknown"

    def test_from_systemd_state_active(self):
        """Test converting 'active' systemd state."""
        assert SessionState.from_systemd_state("active") == SessionState.ACTIVE

    def test_from_systemd_state_closing(self):
        """Test converting 'closing' systemd state (treated as active)."""
        assert SessionState.from_systemd_state("closing") == SessionState.ACTIVE

    def test_from_systemd_state_unknown(self):
        """Test converting unknown systemd state."""
        assert SessionState.from_systemd_state("unknown_state") == SessionState.UNKNOWN
        assert SessionState.from_systemd_state("") == SessionState.UNKNOWN
        assert SessionState.from_systemd_state(None) == SessionState.UNKNOWN

    def test_from_systemd_state_case_insensitive(self):
        """Test that state conversion is case insensitive."""
        assert SessionState.from_systemd_state("ACTIVE") == SessionState.ACTIVE
        assert SessionState.from_systemd_state("Active") == SessionState.ACTIVE

    def test_is_valid_work_time(self):
        """Test checking if state is valid work time."""
        assert SessionState.ACTIVE.is_valid_work_time() is True
        assert SessionState.SUSPENDED.is_valid_work_time() is False
        assert SessionState.LOCKED.is_valid_work_time() is False
        assert SessionState.HIBERNATED.is_valid_work_time() is False
        assert SessionState.UNKNOWN.is_valid_work_time() is False


class TestSession:
    """Test suite for Session dataclass."""

    def test_session_with_end_time(self):
        """Test creating a session with end time."""
        start = datetime(2024, 1, 1, 9, 0, 0)
        end = datetime(2024, 1, 1, 10, 0, 0)
        state = SessionState.ACTIVE

        session = Session(start_time=start, end_time=end, state=state)

        assert session.start_time == start
        assert session.end_time == end
        assert session.state == state

    def test_session_without_end_time(self):
        """Test creating an ongoing session (no end time)."""
        start = datetime(2024, 1, 1, 9, 0, 0)
        state = SessionState.ACTIVE

        session = Session(start_time=start, end_time=None, state=state)

        assert session.start_time == start
        assert session.end_time is None
        assert session.state == state

    def test_session_duration_with_end_time(self):
        """Test calculating duration when end time is set."""
        start = datetime(2024, 1, 1, 9, 0, 0)
        end = datetime(2024, 1, 1, 10, 30, 0)  # 1.5 hours
        session = Session(start_time=start, end_time=end, state=SessionState.ACTIVE)

        assert session.duration == 5400.0  # 1.5 hours in seconds

    def test_session_duration_without_end_time(self):
        """Test that duration is None when end time is not set."""
        start = datetime(2024, 1, 1, 9, 0, 0)
        session = Session(start_time=start, end_time=None, state=SessionState.ACTIVE)

        assert session.duration is None

    def test_session_is_active_with_end_time(self):
        """Test is_active() when end time is set."""
        start = datetime(2024, 1, 1, 9, 0, 0)
        end = datetime(2024, 1, 1, 10, 0, 0)
        session = Session(start_time=start, end_time=end, state=SessionState.ACTIVE)

        assert session.is_active() is False

    def test_session_is_active_without_end_time(self):
        """Test is_active() when end time is not set."""
        start = datetime(2024, 1, 1, 9, 0, 0)
        session = Session(start_time=start, end_time=None, state=SessionState.ACTIVE)

        assert session.is_active() is True

    def test_session_duration_precise(self):
        """Test duration calculation with precise timing."""
        start = datetime(2024, 1, 1, 9, 0, 0, 0)
        end = datetime(2024, 1, 1, 9, 0, 1, 500000)  # 1.5 seconds
        session = Session(start_time=start, end_time=end, state=SessionState.ACTIVE)

        assert session.duration == pytest.approx(1.5, abs=0.01)


class TestDailyLog:
    """Test suite for DailyLog dataclass."""

    def test_daily_log_creation(self):
        """Test creating a daily log."""
        log_date = date(2024, 1, 1)
        total_time = 3600.0  # 1 hour in seconds

        daily_log = DailyLog(date=log_date, total_active_time=total_time)

        assert daily_log.date == log_date
        assert daily_log.total_active_time == total_time

    def test_total_active_hours(self):
        """Test converting total active time to hours."""
        daily_log = DailyLog(date=date(2024, 1, 1), total_active_time=7200.0)  # 2 hours

        assert daily_log.total_active_hours == 2.0

    def test_total_active_hours_fractional(self):
        """Test converting fractional hours."""
        daily_log = DailyLog(
            date=date(2024, 1, 1), total_active_time=5400.0
        )  # 1.5 hours

        assert daily_log.total_active_hours == 1.5

    def test_total_active_minutes(self):
        """Test converting total active time to minutes."""
        daily_log = DailyLog(
            date=date(2024, 1, 1), total_active_time=3600.0
        )  # 1 hour = 60 minutes

        assert daily_log.total_active_minutes == 60.0

    def test_total_active_minutes_fractional(self):
        """Test converting fractional minutes."""
        daily_log = DailyLog(
            date=date(2024, 1, 1), total_active_time=90.0
        )  # 1.5 minutes

        assert daily_log.total_active_minutes == 1.5

    def test_daily_log_zero_time(self):
        """Test daily log with zero time."""
        daily_log = DailyLog(date=date(2024, 1, 1), total_active_time=0.0)

        assert daily_log.total_active_time == 0.0
        assert daily_log.total_active_hours == 0.0
        assert daily_log.total_active_minutes == 0.0

    def test_daily_log_large_time(self):
        """Test daily log with large time values."""
        # 10 hours
        daily_log = DailyLog(date=date(2024, 1, 1), total_active_time=36000.0)

        assert daily_log.total_active_hours == 10.0
        assert daily_log.total_active_minutes == 600.0
