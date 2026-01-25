"""Tests for database module."""

import tempfile
from datetime import date, datetime
from pathlib import Path
from time import sleep

import pytest

from workpulse.database import Database


class TestDatabase:
    """Test suite for Database class."""

    @pytest.fixture
    def temp_db(self) -> Database:
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        db = Database(db_path=db_path)
        yield db
        db.close()
        db_path.unlink(missing_ok=True)

    def test_init_default_path(self, tmp_path, monkeypatch):
        """Test database initialization with default path."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        db = Database()
        assert db.db_path == tmp_path / ".workpulse" / "workpulse.db"
        db.close()

    def test_init_custom_path(self, tmp_path):
        """Test database initialization with custom path."""
        custom_path = tmp_path / "custom.db"
        db = Database(db_path=custom_path)
        assert db.db_path == custom_path
        db.close()

    def test_connect_creates_schema(self, temp_db):
        """Test that connecting creates the database schema."""
        conn = temp_db.connect()
        cursor = conn.cursor()

        # Check that daily_totals table exists
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='daily_totals'
        """
        )
        result = cursor.fetchone()
        assert result is not None

    def test_increment_daily_time_new_date(self, temp_db):
        """Test incrementing time for a new date."""
        temp_db.increment_daily_time(60.0)  # Add 1 minute

        # Verify the record
        conn = temp_db.connect()
        cursor = conn.cursor()
        today = date.today().isoformat()
        cursor.execute(
            "SELECT total_seconds FROM daily_totals WHERE date = ?", (today,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["total_seconds"] == 60.0

    def test_increment_daily_time_existing_date(self, temp_db):
        """Test incrementing time for an existing date."""
        # Add time twice
        temp_db.increment_daily_time(60.0)  # 1 minute
        temp_db.increment_daily_time(120.0)  # 2 minutes

        # Verify the total
        conn = temp_db.connect()
        cursor = conn.cursor()
        today = date.today().isoformat()
        cursor.execute(
            "SELECT total_seconds FROM daily_totals WHERE date = ?", (today,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["total_seconds"] == 180.0  # 3 minutes total

    def test_increment_daily_time_multiple_updates(self, temp_db):
        """Test multiple increments accumulate correctly."""
        # Simulate 5 minutes of tracking (5 calls of 60 seconds each)
        for _ in range(5):
            temp_db.increment_daily_time(60.0)

        conn = temp_db.connect()
        cursor = conn.cursor()
        today = date.today().isoformat()
        cursor.execute(
            "SELECT total_seconds FROM daily_totals WHERE date = ?", (today,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["total_seconds"] == 300.0  # 5 minutes = 300 seconds

    def test_increment_daily_time_sets_last_update(self, temp_db):
        """Test that increment_daily_time sets last_update timestamp."""
        # Increment time
        before = datetime.now()
        temp_db.increment_daily_time(60.0)
        after = datetime.now()

        # Verify last_update is set
        conn = temp_db.connect()
        cursor = conn.cursor()
        today = date.today().isoformat()
        cursor.execute("SELECT last_update FROM daily_totals WHERE date = ?", (today,))
        row = cursor.fetchone()
        assert row is not None
        assert row["last_update"] is not None

        # Parse timestamp and verify it's within expected range
        last_update = datetime.fromisoformat(row["last_update"])
        assert before <= last_update <= after

    def test_increment_daily_time_updates_last_update(self, temp_db):
        """Test that subsequent increments update last_update timestamp."""
        # First increment
        temp_db.increment_daily_time(60.0)

        # Get first timestamp
        conn = temp_db.connect()
        cursor = conn.cursor()
        today = date.today().isoformat()
        cursor.execute("SELECT last_update FROM daily_totals WHERE date = ?", (today,))
        first_update = datetime.fromisoformat(cursor.fetchone()["last_update"])

        # Wait a bit to ensure different timestamp
        sleep(0.1)

        # Second increment
        before = datetime.now()
        temp_db.increment_daily_time(60.0)
        after = datetime.now()

        # Verify last_update was updated
        cursor.execute("SELECT last_update FROM daily_totals WHERE date = ?", (today,))
        second_update = datetime.fromisoformat(cursor.fetchone()["last_update"])

        assert second_update > first_update
        assert before <= second_update <= after

    def test_get_daily_log_existing_date(self, temp_db):
        """Test getting daily log for a date with data."""
        log_date = date(2024, 1, 1)
        date_str = log_date.isoformat()

        # Insert some data
        conn = temp_db.connect()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO daily_totals (date, total_seconds) VALUES (?, ?)",
            (date_str, 3600.0),  # 1 hour
        )
        conn.commit()

        daily_log = temp_db.get_daily_log(log_date)

        assert daily_log.date == log_date
        assert daily_log.total_active_time == 3600.0
        assert daily_log.last_update is None  # No last_update set for old data

    def test_get_daily_log_empty_date(self, temp_db):
        """Test getting daily log for a date with no data."""
        log_date = date(2024, 1, 1)

        daily_log = temp_db.get_daily_log(log_date)

        assert daily_log.date == log_date
        assert daily_log.total_active_time == 0.0
        assert daily_log.last_update is None

    def test_get_today_log(self, temp_db):
        """Test getting today's log."""
        today = date.today()

        # Add some time
        temp_db.increment_daily_time(1800.0)  # 30 minutes

        daily_log = temp_db.get_today_log()

        assert daily_log.date == today
        assert daily_log.total_active_time == 1800.0
        assert daily_log.last_update is not None
        assert isinstance(daily_log.last_update, datetime)

    def test_get_today_log_empty(self, temp_db):
        """Test getting today's log when no data exists."""
        today = date.today()

        daily_log = temp_db.get_today_log()

        assert daily_log.date == today
        assert daily_log.total_active_time == 0.0
        assert daily_log.last_update is None

    def test_increment_and_get_daily_log(self, temp_db):
        """Test that increment and get work together."""
        log_date = date(2024, 1, 1)

        # Manually set date for testing
        conn = temp_db.connect()
        cursor = conn.cursor()
        date_str = log_date.isoformat()

        # Increment time (simulating timer calls)
        cursor.execute(
            """
            INSERT OR IGNORE INTO daily_totals (date, total_seconds)
            VALUES (?, 0)
        """,
            (date_str,),
        )
        cursor.execute(
            """
            UPDATE daily_totals
            SET total_seconds = total_seconds + ?
            WHERE date = ?
        """,
            (60.0, date_str),
        )
        cursor.execute(
            """
            UPDATE daily_totals
            SET total_seconds = total_seconds + ?
            WHERE date = ?
        """,
            (120.0, date_str),
        )
        conn.commit()

        daily_log = temp_db.get_daily_log(log_date)

        assert daily_log.total_active_time == 180.0  # 3 minutes total

    def test_context_manager(self, tmp_path):
        """Test database as context manager."""
        db_path = tmp_path / "test.db"
        with Database(db_path=db_path) as db:
            assert db._connection is not None
            # Increment time to verify it works
            db.increment_daily_time(60.0)

        # Connection should be closed after context exit
        assert db._connection is None

    def test_close(self, temp_db):
        """Test closing the database connection."""
        temp_db.connect()
        assert temp_db._connection is not None

        temp_db.close()
        assert temp_db._connection is None

    def test_multiple_dates(self, temp_db):
        """Test that different dates are tracked separately."""
        date1 = date(2024, 1, 1)
        date2 = date(2024, 1, 2)

        # Manually insert data for different dates
        conn = temp_db.connect()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO daily_totals (date, total_seconds) VALUES (?, ?)",
            (date1.isoformat(), 3600.0),
        )
        cursor.execute(
            "INSERT INTO daily_totals (date, total_seconds) VALUES (?, ?)",
            (date2.isoformat(), 7200.0),
        )
        conn.commit()

        log1 = temp_db.get_daily_log(date1)
        log2 = temp_db.get_daily_log(date2)

        assert log1.total_active_time == 3600.0  # 1 hour
        assert log2.total_active_time == 7200.0  # 2 hours
