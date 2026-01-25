"""Core tracking logic for monitoring work time."""

import logging
from datetime import datetime

from .database import Database
from .state_checker import is_user_active

logger = logging.getLogger(__name__)


class WorkTracker:
    """Main class for tracking work time."""

    def __init__(self, database: Database = None) -> None:
        """Initialize the work tracker.

        Args:
            database: Database instance. If None, creates a new one with default path.
        """
        self.database = database or Database()

    def update_time(self) -> None:
        """Update time tracking - called by systemd timer every minute.

        Checks if user is active and increments daily time if so.
        """
        try:
            if is_user_active():
                # User is active - add 1 minute (60 seconds) to today's total
                self.database.increment_daily_time(60)
                logger.info("Added 1 minute to daily total (user active)")
            else:
                logger.debug("User not active, skipping time update")

        except Exception as e:
            logger.error(f"Error updating time: {e}", exc_info=True)
            raise

    def get_current_status(self) -> tuple[str, float]:
        """Get current tracking status.

        Returns:
            Tuple of (status_string, today_total_seconds)
        """
        try:
            active = is_user_active()
            status = "active" if active else "inactive"

            today_log = self.database.get_today_log()
            total_seconds = today_log.total_active_time

            return (status, total_seconds)

        except Exception as e:
            logger.error(f"Error getting status: {e}", exc_info=True)
            return ("unknown", 0.0)
