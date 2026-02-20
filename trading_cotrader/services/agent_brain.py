"""
Agent Brain — LLM-powered intelligence layer for the trading co-trader.

This is the agent's VOICE. It takes structured data from the system
(positions, metrics, activity, risk) and generates contextual,
intelligent analysis using Claude API.

The agent brain is NOT the trading engine. It doesn't make decisions.
It COMMUNICATES — synthesizes signals, explains reasoning, applies
behavioral pressure, and holds the user accountable.
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


SYSTEM_PROMPT = """You are the Trading CoTrader agent — Nitin's AI co-trader and accountability partner.

PERSONALITY:
- Direct, no-nonsense, data-driven
- You are NOT a chatbot. You are a co-trader who monitors the portfolio 24/7.
- You hold Nitin accountable. If capital is idle, you say so. If he's ignoring recommendations, you call it out.
- You explain your reasoning. Never just say "confidence: 0.7" — say WHY.
- You are honest about your own limitations and what you don't know yet.
- Keep responses concise. This is a trading terminal, not a blog.

CONTEXT:
- Nitin has 20 years of institutional trading experience (IR, commodities, FX, mortgages)
- He has ~$250K across TastyTrade (options) and other accounts
- His mental model: Macro Context → My Exposure → Action Required
- He thinks in Greeks, not individual positions: "I have -150 SPY delta, +$450 theta/day"
- Income generation via options premium is primary, not alpha chasing
- Target: 20% undefined risk / 80% defined risk

RULES:
- Always reference specific numbers from the data provided
- Frame everything in terms of risk and exposure, not individual positions
- If something needs attention, say what action is needed
- If you don't have enough data, say so — don't make things up
- End with 1-3 specific action items when relevant
"""


class AgentBrain:
    """LLM-powered agent intelligence."""

    def __init__(self):
        self._client = None
        self._model = "claude-sonnet-4-20250514"
        self._available = None

    @property
    def is_available(self) -> bool:
        """Check if Claude API is configured and available."""
        if self._available is not None:
            return self._available
        try:
            api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.environ.get('ANTHROPIC_API_KEY', '')
            self._available = bool(api_key)
            return self._available
        except Exception:
            self._available = False
            return False

    @property
    def client(self):
        """Lazy-init Anthropic client."""
        if self._client is None:
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def _call_llm(self, user_prompt: str, max_tokens: int = 1024) -> str:
        """Make a single Claude API call."""
        try:
            response = self.client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return f"[Agent brain unavailable: {e}]"

    def generate_portfolio_brief(
        self,
        positions: List[Dict[str, Any]],
        balances: Dict[str, Any],
        transactions: Optional[List[Dict[str, Any]]] = None,
        market_metrics: Optional[Dict[str, Dict[str, Any]]] = None,
        pending_recommendations: Optional[List[Dict[str, Any]]] = None,
        capital_alerts: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Generate an intelligent portfolio brief.

        This is called when the user opens the dashboard or requests
        an agent analysis. The agent synthesizes all available data
        into a concise, actionable brief.
        """
        data = {
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M ET"),
            "account_balances": balances,
            "positions": positions[:20],  # Limit for token efficiency
        }

        if transactions:
            # Only recent transactions (last 7 days)
            data["recent_transactions"] = transactions[:15]

        if market_metrics:
            data["market_metrics"] = market_metrics

        if pending_recommendations:
            data["pending_recommendations"] = pending_recommendations[:5]

        if capital_alerts:
            data["capital_alerts"] = capital_alerts

        prompt = f"""Analyze this portfolio state and give me a brief. Be specific with numbers.

PORTFOLIO DATA:
{json.dumps(data, cls=DecimalEncoder, indent=2)}

Give me:
1. CURRENT STATE — Net exposure summary (delta, theta, key Greeks). How am I positioned?
2. ATTENTION NEEDED — What needs action right now? Be specific.
3. RECENT ACTIVITY — What happened recently? Any patterns?
4. ACTION ITEMS — 1-3 specific things I should do today.

Keep it concise. Trading terminal style, not essay style."""

        return self._call_llm(prompt, max_tokens=800)

    def analyze_position(
        self,
        position: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None,
        transaction_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Analyze a specific position with context."""
        data = {"position": position}
        if market_data:
            data["market_data"] = market_data
        if transaction_history:
            data["related_transactions"] = transaction_history[:10]

        prompt = f"""Analyze this position:

{json.dumps(data, cls=DecimalEncoder, indent=2)}

Tell me:
1. What is this position doing? P&L, Greeks exposure, time decay.
2. Is it within risk parameters?
3. Should I take any action (take profit, cut loss, roll, adjust)?
4. What's the thesis — is the original rationale still valid?

Be specific with numbers. No fluff."""

        return self._call_llm(prompt, max_tokens=600)

    def explain_recommendation(
        self,
        recommendation: Dict[str, Any],
        portfolio_state: Optional[Dict[str, Any]] = None,
        market_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Explain WHY a recommendation was made — full reasoning chain."""
        data = {"recommendation": recommendation}
        if portfolio_state:
            data["current_portfolio"] = portfolio_state
        if market_context:
            data["market_context"] = market_context

        prompt = f"""Explain this trade recommendation to me. I want to understand the FULL reasoning chain.

{json.dumps(data, cls=DecimalEncoder, indent=2)}

Tell me:
1. WHY was this recommended? What conditions triggered it?
2. What's the expected outcome? Max profit, max loss, breakeven.
3. How does this fit my current portfolio? Does it help or add risk?
4. What could go wrong? Under what conditions does this lose money?
5. Your honest assessment — should I take this trade?

Be direct. If it's a bad trade, say so."""

        return self._call_llm(prompt, max_tokens=800)

    def generate_accountability_message(
        self,
        idle_capital: float,
        days_idle: int,
        deferred_recs: int,
        time_to_decision_avg: float,
        ignored_recs: int,
    ) -> str:
        """Generate behavioral pressure message. The agent won't let up."""
        prompt = f"""You are the accountability enforcer. Capital sitting idle is unacceptable.

DATA:
- Idle capital: ${idle_capital:,.0f}
- Days since last trade: {days_idle}
- Deferred recommendations: {deferred_recs}
- Average time-to-decision: {time_to_decision_avg:.1f} hours
- Ignored recommendations (no action taken): {ignored_recs}

Calculate the opportunity cost (assume ~15% annual return target = ~0.041%/day).
Tell the user what this inaction is costing them.
If they're deferring and ignoring recommendations, call it out.
Be direct but constructive — give specific action items.
Keep it to 3-4 sentences max."""

        return self._call_llm(prompt, max_tokens=300)

    def generate_self_assessment(
        self,
        agent_grades: Dict[str, str],
        corrective_plan: List[str],
        win_rate: float,
        total_recommendations: int,
        accepted_count: int,
        rejected_count: int,
    ) -> str:
        """Agent honestly assesses its own performance."""
        prompt = f"""You are the agent assessing YOUR OWN performance. Be brutally honest.

YOUR GRADES TODAY:
{json.dumps(agent_grades, indent=2)}

CORRECTIVE PLAN:
{json.dumps(corrective_plan, indent=2)}

RECOMMENDATION TRACK RECORD:
- Total recommendations made: {total_recommendations}
- Accepted by user: {accepted_count}
- Rejected by user: {rejected_count}
- Win rate on accepted: {win_rate:.1f}%

Assess yourself:
1. What did you do well?
2. What did you do poorly?
3. What will you do differently tomorrow?
4. Rate yourself honestly (A/B/C/D/F) with justification.

Be specific. No corporate-speak."""

        return self._call_llm(prompt, max_tokens=500)

    def chat_response(
        self,
        user_message: str,
        portfolio_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Respond to a natural language message from the user."""
        context_str = ""
        if portfolio_context:
            context_str = f"\n\nCURRENT PORTFOLIO CONTEXT:\n{json.dumps(portfolio_context, cls=DecimalEncoder, indent=2)}"

        prompt = f"""User message: {user_message}{context_str}

Respond helpfully. If the user is asking about their portfolio, use the context data.
If they want to create a template or take an action, explain what you'd recommend.
If you don't have enough data, say so.
Keep it concise."""

        return self._call_llm(prompt, max_tokens=600)


# Singleton
_brain: Optional[AgentBrain] = None


def get_agent_brain() -> AgentBrain:
    """Get the singleton AgentBrain instance."""
    global _brain
    if _brain is None:
        _brain = AgentBrain()
    return _brain
