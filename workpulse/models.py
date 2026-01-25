"""Domain models for workpulse."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional


class SessionState(Enum):
    """Represents the state of a login session."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    LOCKED = "locked"
    HIBERNATED = "hibernated"
    UNKNOWN = "unknown"

    @classmethod
    def from_systemd_state(cls, state: str) -> "SessionState":
        """Convert systemd session state string to SessionState enum.

        Args:
            state: Systemd session state string (e.g., "active", "closing")

        Returns:
            Corresponding SessionState enum value
        """
        state_lower = state.lower() if state else ""
        mapping = {
            "active": cls.ACTIVE,
            "closing": cls.ACTIVE,  # Still considered active until closed
        }
        return mapping.get(state_lower, cls.UNKNOWN)

    def is_valid_work_time(self) -> bool:
        """Check if this state represents valid working time.

        Returns:
            True if the state is ACTIVE, False otherwise
        """
        return self == SessionState.ACTIVE


@dataclass
class Session:
    """Represents a time tracking session segment."""

    start_time: datetime
    end_time: Optional[datetime]
    state: SessionState

    @property
    def duration(self) -> Optional[float]:
        """Calculate session duration in seconds.

        Returns:
            Duration in seconds if end_time is set, None otherwise
        """
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds()

    def is_active(self) -> bool:
        """Check if this session is currently active.

        Returns:
            True if end_time is None, False otherwise
        """
        return self.end_time is None


@dataclass
class DailyLog:
    """Represents a daily summary of tracked time."""

    date: date
    total_active_time: float  # Total active time in seconds
    last_update: Optional[datetime] = None  # Timestamp of last update

    @property
    def total_active_hours(self) -> float:
        """Get total active time in hours.

        Returns:
            Total active time converted to hours
        """
        return self.total_active_time / 3600.0

    @property
    def total_active_minutes(self) -> float:
        """Get total active time in minutes.

        Returns:
            Total active time converted to minutes
        """
        return self.total_active_time / 60.0
