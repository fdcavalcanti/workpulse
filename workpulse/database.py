"""Database operations for storing time tracking data."""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .models import DailyLog


class Database:
    """Database manager for workpulse time tracking data."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize the database connection.

        Args:
            db_path: Path to the database file. If None, uses default location
                     (~/.workpulse/workpulse.db)
        """
        if db_path is None:
            home = Path.home()
            db_dir = home / ".workpulse"
            db_dir.mkdir(mode=0o700, exist_ok=True)
            db_path = db_dir / "workpulse.db"

        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Get or create database connection.

        Returns:
            SQLite connection object
        """
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path), check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
            self._initialize_schema()
        return self._connection

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _initialize_schema(self) -> None:
        """Initialize database schema if it doesn't exist."""
        conn = self.connect()
        cursor = conn.cursor()

        # Create daily_totals table to store total active time per day
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_totals (
                date TEXT PRIMARY KEY,
                total_seconds REAL NOT NULL DEFAULT 0,
                last_update TEXT
            )
        """
        )

        # Migrate existing databases: add last_update column if it doesn't exist
        try:
            cursor.execute(
                """
                ALTER TABLE daily_totals
                ADD COLUMN last_update TEXT
            """
            )
        except sqlite3.OperationalError:
            # Column already exists, ignore
            pass

        conn.commit()

    def increment_daily_time(self, seconds: float) -> None:
        """Increment today's total active time.

        This method adds time to today's total. If no record exists for today,
        it creates one. Otherwise, it updates the existing record.
        The last_update timestamp is set to the current time.

        Args:
            seconds: Number of seconds to add (typically 60 for 1 minute)
        """
        today = date.today()
        date_str = today.isoformat()
        now = datetime.now().isoformat()

        conn = self.connect()
        cursor = conn.cursor()

        # Try to update existing record
        cursor.execute(
            """
            UPDATE daily_totals
            SET total_seconds = total_seconds + ?, last_update = ?
            WHERE date = ?
        """,
            (seconds, now, date_str),
        )

        # If no row was updated, insert a new one
        if cursor.rowcount == 0:
            cursor.execute(
                """
                INSERT INTO daily_totals (date, total_seconds, last_update)
                VALUES (?, ?, ?)
            """,
                (date_str, seconds, now),
            )

        conn.commit()

    def get_daily_log(self, log_date: date) -> DailyLog:
        """Get daily summary for a specific date.

        Args:
            log_date: Date to query

        Returns:
            DailyLog object with aggregated data
        """
        conn = self.connect()
        cursor = conn.cursor()

        date_str = log_date.isoformat()

        cursor.execute(
            """
            SELECT total_seconds, last_update
            FROM daily_totals
            WHERE date = ?
        """,
            (date_str,),
        )

        row = cursor.fetchone()
        total_seconds = float(row["total_seconds"]) if row else 0.0

        last_update = None
        if row and row["last_update"]:
            try:
                last_update = datetime.fromisoformat(row["last_update"])
            except (ValueError, TypeError):
                # Handle invalid timestamp format gracefully
                last_update = None

        return DailyLog(
            date=log_date,
            total_active_time=total_seconds,
            last_update=last_update,
        )

    def get_today_log(self) -> DailyLog:
        """Get today's daily summary.

        Returns:
            DailyLog object for today
        """
        return self.get_daily_log(date.today())

    def __enter__(self) -> "Database":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Context manager exit."""
        self.close()
