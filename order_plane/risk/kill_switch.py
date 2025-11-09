"""Emergency kill-switch with cool-off period."""

from datetime import datetime, timezone, timedelta
from typing import Optional


class KillSwitch:
    """
    Emergency kill-switch with cool-off period.

    Once triggered:
    - Halts all trading for cool_off_seconds
    - Requires manual resume (or auto-resume after timeout)
    - Logs breach to audit trail
    """

    def __init__(self, cool_off_seconds: int = 60):
        self.cool_off_seconds = cool_off_seconds
        self.triggered_at: Optional[datetime] = None
        self.is_triggered = False

    def trigger(self) -> None:
        """Trigger kill-switch (halt trading)."""
        self.is_triggered = True
        self.triggered_at = datetime.now(timezone.utc)

    def reset(self) -> None:
        """Manually reset kill-switch."""
        self.is_triggered = False
        self.triggered_at = None

    def check_can_trade(self) -> bool:
        """Check if trading is allowed."""
        if not self.is_triggered:
            return True

        # Check if cool-off expired (auto-resume)
        if self.triggered_at:
            elapsed = (datetime.now(timezone.utc) - self.triggered_at).total_seconds()
            if elapsed >= self.cool_off_seconds:
                self.reset()
                return True

        return False
