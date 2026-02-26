"""
Workflow Scheduler — APScheduler setup for the workflow engine.

Schedules:
    - Morning boot (5 min before market open)
    - Monitoring cycle (every 30 min during market hours)
    - EOD evaluation (3:30 PM ET)
    - Daily report (4:15 PM ET)
"""

from typing import TYPE_CHECKING
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from trading_cotrader.config.workflow_config_loader import WorkflowConfig

if TYPE_CHECKING:
    from trading_cotrader.agents.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """Configures and runs APScheduler jobs for the workflow engine."""

    def __init__(self, engine: 'WorkflowEngine', config: WorkflowConfig):
        self.engine = engine
        self.config = config
        self.scheduler = BackgroundScheduler(
            timezone=config.market_hours.timezone,
        )

    def start(self):
        """Start all scheduled jobs."""
        tz = self.config.market_hours.timezone

        # Parse market hours
        open_hour, open_min = map(int, self.config.market_hours.open.split(':'))
        close_hour, close_min = map(int, self.config.market_hours.close.split(':'))

        # Boot time: minutes before market open
        boot_min = open_min - self.config.boot_time_minutes_before_open
        boot_hour = open_hour
        if boot_min < 0:
            boot_min += 60
            boot_hour -= 1

        # 1. Morning boot
        self.scheduler.add_job(
            self.engine.run_once,
            CronTrigger(
                hour=boot_hour, minute=boot_min,
                day_of_week='mon-fri', timezone=tz,
            ),
            id='morning_boot',
            name='Morning Boot',
            replace_existing=True,
        )
        logger.info(f"Scheduled morning boot: {boot_hour}:{boot_min:02d} ET")

        # 2. Monitoring cycle (every N minutes during market hours)
        self.scheduler.add_job(
            self.engine.run_monitoring_cycle,
            IntervalTrigger(
                minutes=self.config.cycle_frequency_minutes,
                timezone=tz,
            ),
            id='monitoring_cycle',
            name='Monitoring Cycle',
            replace_existing=True,
        )
        logger.info(f"Scheduled monitoring cycle: every {self.config.cycle_frequency_minutes} min")

        # 3. EOD evaluation
        eod_hour, eod_min = map(int, self.config.eod_eval_time.split(':'))
        self.scheduler.add_job(
            self._eod_trigger,
            CronTrigger(
                hour=eod_hour, minute=eod_min,
                day_of_week='mon-fri', timezone=tz,
            ),
            id='eod_evaluation',
            name='EOD Evaluation',
            replace_existing=True,
        )
        logger.info(f"Scheduled EOD evaluation: {eod_hour}:{eod_min:02d} ET")

        # 4. Daily report
        report_hour, report_min = map(int, self.config.report_time.split(':'))
        self.scheduler.add_job(
            self._report_trigger,
            CronTrigger(
                hour=report_hour, minute=report_min,
                day_of_week='mon-fri', timezone=tz,
            ),
            id='daily_report',
            name='Daily Report',
            replace_existing=True,
        )
        logger.info(f"Scheduled daily report: {report_hour}:{report_min:02d} ET")

        self.scheduler.start()
        logger.info("Workflow scheduler started")

    def stop(self):
        """Shut down the scheduler."""
        self.scheduler.shutdown(wait=False)
        logger.info("Workflow scheduler stopped")

    def _eod_trigger(self):
        """Trigger EOD evaluation if engine is in monitoring state."""
        from trading_cotrader.agents.workflow.states import WorkflowStates
        if self.engine.state == WorkflowStates.MONITORING.value:
            try:
                self.engine.eod()
            except Exception as e:
                logger.error(f"EOD trigger failed: {e}")

    def _report_trigger(self):
        """Trigger daily report."""
        from trading_cotrader.agents.workflow.states import WorkflowStates
        if self.engine.state in (
            WorkflowStates.EOD_EVALUATION.value,
            WorkflowStates.MONITORING.value,
        ):
            try:
                self.engine.report()
            except Exception as e:
                logger.error(f"Report trigger failed: {e}")
