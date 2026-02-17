"""
Workflow State Machine Definition — Uses `transitions` library.

States represent phases of the trading day. Transitions encode
the valid paths between phases, with conditions that must be met.

The engine enters RECOMMENDATION_REVIEW and TRADE_REVIEW as human pause
points where the workflow stops and waits for user input.
"""

from enum import Enum


class WorkflowStates(str, Enum):
    """All possible states of the workflow engine."""
    IDLE = "idle"
    BOOTING = "booting"
    MACRO_CHECK = "macro_check"
    SCREENING = "screening"
    RECOMMENDATION_REVIEW = "recommendation_review"   # human pause
    EXECUTION = "execution"
    MONITORING = "monitoring"                          # home state during market hours
    TRADE_MANAGEMENT = "trade_management"              # evaluate positions: roll, adjust, exit
    TRADE_REVIEW = "trade_review"                      # human pause — review roll/adjust/exit signals
    EOD_EVALUATION = "eod_evaluation"
    REPORTING = "reporting"
    HALTED = "halted"                                  # circuit breaker


# Transition table for the state machine.
# Each dict: trigger (method name), source, dest, optional conditions/unless.
TRANSITIONS = [
    # Boot sequence
    {'trigger': 'boot', 'source': WorkflowStates.IDLE, 'dest': WorkflowStates.BOOTING},
    {'trigger': 'check_macro', 'source': WorkflowStates.BOOTING, 'dest': WorkflowStates.MACRO_CHECK},

    # Macro → screening or skip
    {'trigger': 'screen', 'source': WorkflowStates.MACRO_CHECK, 'dest': WorkflowStates.SCREENING,
     'conditions': ['is_not_risk_off']},
    {'trigger': 'skip_to_monitor', 'source': WorkflowStates.MACRO_CHECK, 'dest': WorkflowStates.MONITORING},

    # Screening → review or skip
    {'trigger': 'review_recs', 'source': WorkflowStates.SCREENING, 'dest': WorkflowStates.RECOMMENDATION_REVIEW,
     'conditions': ['has_recommendations']},
    {'trigger': 'skip_to_monitor', 'source': WorkflowStates.SCREENING, 'dest': WorkflowStates.MONITORING},

    # Recommendation review → execute or skip
    {'trigger': 'execute', 'source': WorkflowStates.RECOMMENDATION_REVIEW, 'dest': WorkflowStates.EXECUTION},
    {'trigger': 'monitor', 'source': [
        WorkflowStates.EXECUTION,
        WorkflowStates.RECOMMENDATION_REVIEW,
        WorkflowStates.SCREENING,
    ], 'dest': WorkflowStates.MONITORING},

    # Monitoring → trade management (roll, adjust, exit evaluation)
    {'trigger': 'manage_trades', 'source': WorkflowStates.MONITORING, 'dest': WorkflowStates.TRADE_MANAGEMENT},

    # Trade management → review or skip
    {'trigger': 'review_trades', 'source': WorkflowStates.TRADE_MANAGEMENT, 'dest': WorkflowStates.TRADE_REVIEW,
     'conditions': ['has_exit_signals']},
    {'trigger': 'skip_to_monitor', 'source': WorkflowStates.TRADE_MANAGEMENT, 'dest': WorkflowStates.MONITORING},

    # Trade review → execute
    {'trigger': 'execute_trade_action', 'source': WorkflowStates.TRADE_REVIEW, 'dest': WorkflowStates.EXECUTION},

    # EOD
    {'trigger': 'eod', 'source': WorkflowStates.MONITORING, 'dest': WorkflowStates.EOD_EVALUATION},
    {'trigger': 'report', 'source': [
        WorkflowStates.EOD_EVALUATION,
        WorkflowStates.TRADE_REVIEW,
    ], 'dest': WorkflowStates.REPORTING},
    {'trigger': 'go_idle', 'source': [
        WorkflowStates.REPORTING,
        WorkflowStates.BOOTING,        # non-trading day
        WorkflowStates.MONITORING,      # manual shutdown
    ], 'dest': WorkflowStates.IDLE},

    # Halt can happen from any state
    {'trigger': 'halt', 'source': '*', 'dest': WorkflowStates.HALTED},
    {'trigger': 'resume', 'source': WorkflowStates.HALTED, 'dest': WorkflowStates.MONITORING},
]
