"""Simple state checker using loginctl to determine if user is active."""

import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def is_user_active() -> bool:
    """Check if the current user is active (not locked, suspended, or hibernated).

    Uses loginctl to check session state.

    Returns:
        True if user is active, False otherwise
    """
    try:
        # Get current username
        username = os.getenv("USER") or os.getenv("USERNAME")
        if not username:
            logger.warning("Could not determine username")
            return False

        # Get current user's session
        result = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

        if result.returncode != 0:
            logger.warning(f"loginctl list-sessions failed: {result.stderr}")
            return False

        # Find session for current user
        session_id = None
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[2] == username:
                session_id = parts[0]
                break

        if not session_id:
            logger.debug("No session found for current user")
            return False

        # Check session properties: Active and LockedHint
        result = subprocess.run(
            [
                "loginctl",
                "show-session",
                session_id,
                "-p",
                "Active",
                "-p",
                "LockedHint",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

        if result.returncode != 0:
            logger.warning(f"loginctl show-session failed: {result.stderr}")
            return False

        # Parse output
        active = False
        locked = False

        for line in result.stdout.strip().split("\n"):
            if line.startswith("Active="):
                active = line.split("=", 1)[1].strip() == "yes"
            elif line.startswith("LockedHint="):
                locked = line.split("=", 1)[1].strip() == "yes"

        # Check if system is suspended/hibernated
        is_suspended = _is_system_suspended()

        # User is active if: session is active, not locked, and system not suspended
        user_active = active and not locked and not is_suspended

        logger.debug(
            f"State check: active={active}, locked={locked}, suspended={is_suspended}, "
            f"result={user_active}"
        )

        return user_active

    except subprocess.TimeoutExpired:
        logger.warning("loginctl command timed out")
        return False
    except Exception as e:
        logger.error(f"Error checking user state: {e}", exc_info=True)
        return False


def _is_system_suspended() -> bool:
    """Check if system is suspended or hibernated.

    Returns:
        True if system is suspended/hibernated, False otherwise
    """
    try:
        # Check /sys/power/state to see if system is suspended
        # If we can read it and it's not "mem" or "disk", system might be suspended
        # Actually, better to check if we just resumed from suspend
        # For simplicity, check /sys/power/state file
        try:
            with open("/sys/power/state", "r") as f:
                state = f.read().strip()
                # If state contains suspend/hibernate options, system supports it
                # But we can't directly tell if currently suspended (process would be frozen)
                # So we'll rely on loginctl session state
                pass
        except FileNotFoundError:
            pass

        # Alternative: check if we can detect suspend via other means
        # For now, assume not suspended if we're running
        return False

    except Exception as e:
        logger.debug(f"Error checking suspend state: {e}")
        return False
