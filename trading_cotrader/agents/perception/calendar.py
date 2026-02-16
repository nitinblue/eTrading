"""
Calendar Agent — Determines trading day, cadences, and market timing.

Uses exchange_calendars for NYSE holidays and early closes.
Reads FOMC dates from workflow_rules.yaml.

Enriches context with:
    - is_trading_day: bool
    - cadences: list[str] (e.g. ["0dte", "weekly"])
    - fomc_today: bool
    - minutes_since_open: int
    - minutes_to_close: int
    - market_open_time / market_close_time: str
"""

from datetime import datetime, date, timedelta
from typing import List
import logging

import pytz

from trading_cotrader.agents.protocol import AgentResult, AgentStatus
from trading_cotrader.config.workflow_config_loader import WorkflowConfig

logger = logging.getLogger(__name__)


class CalendarAgent:
    """Determines today's trading schedule, cadences, and market timing."""

    name = "calendar"

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self._calendar = None

    def _get_calendar(self):
        if self._calendar is None:
            import exchange_calendars
            self._calendar = exchange_calendars.get_calendar('XNYS')
        return self._calendar

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """Check if today is a trading day and determine cadences."""
        try:
            today = date.today()
            cal = self._get_calendar()
            tz = pytz.timezone(self.config.market_hours.timezone)
            now = datetime.now(tz)

            # Check trading day
            import pandas as pd
            ts = pd.Timestamp(today)
            is_trading_day = cal.is_session(ts)

            if not is_trading_day:
                context['is_trading_day'] = False
                context['cadences'] = []
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.COMPLETED,
                    data={'is_trading_day': False},
                    messages=[f"{today} is not a trading day"],
                )

            # Market open/close times
            session_open = cal.session_open(ts)
            session_close = cal.session_close(ts)

            # Convert to Eastern for display
            open_et = session_open.astimezone(tz)
            close_et = session_close.astimezone(tz)

            # Minutes since open / to close
            if now < open_et:
                minutes_since_open = 0
                minutes_to_close = int((close_et - open_et).total_seconds() / 60)
            elif now > close_et:
                minutes_since_open = int((close_et - open_et).total_seconds() / 60)
                minutes_to_close = 0
            else:
                minutes_since_open = int((now - open_et).total_seconds() / 60)
                minutes_to_close = int((close_et - now).total_seconds() / 60)

            # FOMC today?
            fomc_today = str(today) in self.config.schedule.fomc_dates

            # Determine cadences
            cadences = self.get_todays_cadences(today, fomc_today)

            # Enrich context
            context['is_trading_day'] = True
            context['cadences'] = cadences
            context['fomc_today'] = fomc_today
            context['minutes_since_open'] = minutes_since_open
            context['minutes_to_close'] = minutes_to_close
            context['market_open_time'] = open_et.strftime('%H:%M')
            context['market_close_time'] = close_et.strftime('%H:%M')

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={
                    'is_trading_day': True,
                    'cadences': cadences,
                    'fomc_today': fomc_today,
                    'minutes_since_open': minutes_since_open,
                    'minutes_to_close': minutes_to_close,
                },
                messages=[
                    f"Trading day: cadences={cadences}, "
                    f"FOMC={'YES' if fomc_today else 'no'}, "
                    f"{minutes_to_close} min to close"
                ],
            )

        except Exception as e:
            logger.error(f"CalendarAgent failed: {e}")
            # Fail safe: assume trading day
            context['is_trading_day'] = True
            context['cadences'] = ['0dte']
            context['minutes_to_close'] = 999
            context['minutes_since_open'] = 999
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Calendar error (defaulting to trading day): {e}"],
            )

    def get_todays_cadences(self, today: date, fomc_today: bool = False) -> List[str]:
        """
        Determine which trading cadences are active today.

        Mon/Tue/Thu → daily cadences (usually ["0dte"])
        Wed/Fri → daily + wednesday/friday cadences
        FOMC day + skip_0dte_on_fomc → remove 0dte
        Monthly: if any monthly DTE window aligns, add "monthly"
        """
        sched = self.config.schedule
        day_name = today.strftime('%A').lower()

        # Start with daily cadences
        cadences = list(sched.daily)

        # Add day-specific cadences
        if day_name == 'wednesday':
            for c in sched.wednesday:
                if c not in cadences:
                    cadences.append(c)
        elif day_name == 'friday':
            for c in sched.friday:
                if c not in cadences:
                    cadences.append(c)

        # FOMC filter
        if fomc_today and sched.skip_0dte_on_fomc:
            cadences = [c for c in cadences if c != '0dte']

        # Monthly DTE window check
        # Monthly strategies screen when DTE falls in the window
        if sched.monthly_dte_window and len(sched.monthly_dte_window) == 2:
            # We just flag it; the screener agent will determine actual DTE
            if 'monthly' not in cadences:
                cadences.append('monthly')

        return cadences
