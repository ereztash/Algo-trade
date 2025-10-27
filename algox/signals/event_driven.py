"""
Event-Driven Signal (FDA Approvals)
===================================

Exploits predictable volatility around FDA approval dates (PDUFA) for biotech stocks.

Strategy:
---------
- Entry: T-5 days before PDUFA date
- Exit: T-2 days before PDUFA date (avoid binary outcome risk)
- Focus on Phase III+ trials (success rate > 60%)
- Filter by market cap > $500M and volume > $5M/day

Rationale:
----------
1. Pre-announcement volatility: Uncertainty drives up implied volatility
2. Mean-reversion: Stock often overreacts before announcement
3. Exit before risk: Binary outcome (approve/reject) is unpredictable

Data Sources:
------------
- FDA PDUFA Calendar: https://www.fda.gov/drugs/development-approval-process-drugs/drug-and-biologic-calendar
- Biopharmcatalyst.com API (if available)
- Manual calendar maintenance (MVP approach)

Example:
--------
    from algox.signals.event_driven import EventDrivenSignal

    signal = EventDrivenSignal(config)
    opportunities = signal.scan_calendar(current_date)  # Returns list of trades
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EventDrivenSignal:
    """
    Event-driven signal generator for FDA approval events.

    Attributes:
        entry_days: Days before PDUFA to enter (default: 5)
        exit_days: Days before PDUFA to exit (default: 2)
        min_phase: Minimum trial phase (default: 3)
        min_market_cap: Minimum market cap in USD
        min_daily_volume: Minimum daily volume in USD
        fda_calendar_url: URL for FDA calendar
    """

    def __init__(self, config: Dict):
        """Initialize event-driven signal generator."""
        event_config = config.get("EVENT_DRIVEN", {})

        self.entry_days = event_config.get("ENTRY_DAYS", 5)
        self.exit_days = event_config.get("EXIT_DAYS", 2)
        self.min_phase = event_config.get("MIN_PHASE", 3)
        self.min_market_cap = event_config.get("MIN_MARKET_CAP", 500_000_000)  # $500M
        self.min_daily_volume = event_config.get("MIN_DAILY_VOLUME", 5_000_000)  # $5M
        self.fda_calendar_url = event_config.get("FDA_CALENDAR_URL", None)

        # Calendar cache (in production, use database)
        self._calendar = self._load_calendar()

    def _load_calendar(self) -> pd.DataFrame:
        """
        Load FDA PDUFA calendar.

        Returns:
            DataFrame with columns: symbol, drug_name, indication, pdufa_date, phase, market_cap
        """
        # TODO: Implement actual FDA scraping or API integration
        # For MVP, use manual/hardcoded calendar

        # Example calendar (to be replaced with real data)
        calendar = pd.DataFrame([
            {
                "symbol": "ABCD",
                "drug_name": "DrugX",
                "indication": "Cancer",
                "pdufa_date": datetime(2025, 11, 15),
                "phase": 3,
                "market_cap": 1_000_000_000,
                "success_probability": 0.65
            },
            # Add more events here...
        ])

        logger.info(f"Loaded {len(calendar)} FDA events from calendar")

        return calendar

    def scrape_fda_calendar(self, url: Optional[str] = None) -> pd.DataFrame:
        """
        Scrape FDA PDUFA calendar from official website.

        Args:
            url: FDA calendar URL (uses self.fda_calendar_url if None)

        Returns:
            DataFrame with calendar events

        Note:
            This is a placeholder. Real implementation requires:
            1. Web scraping or API integration
            2. Error handling
            3. Rate limiting
            4. Data validation
        """
        if url is None:
            url = self.fda_calendar_url

        if url is None:
            logger.warning("No FDA calendar URL provided. Using cached/manual calendar.")
            return self._calendar

        try:
            # Placeholder for actual scraping logic
            logger.info(f"Scraping FDA calendar from {url}")

            # TODO: Implement scraping
            # response = requests.get(url)
            # soup = BeautifulSoup(response.content, 'html.parser')
            # ... parse tables ...

            return self._calendar

        except Exception as e:
            logger.error(f"Error scraping FDA calendar: {e}")
            return self._calendar

    def filter_events(
        self,
        events: pd.DataFrame,
        min_market_cap: Optional[float] = None,
        min_phase: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Filter FDA events by criteria.

        Args:
            events: DataFrame of FDA events
            min_market_cap: Minimum market cap
            min_phase: Minimum trial phase

        Returns:
            Filtered DataFrame
        """
        if events.empty:
            return events

        filtered = events.copy()

        if min_market_cap is not None:
            filtered = filtered[filtered['market_cap'] >= min_market_cap]

        if min_phase is not None:
            filtered = filtered[filtered['phase'] >= min_phase]

        logger.info(f"Filtered FDA events: {len(events)} → {len(filtered)}")

        return filtered

    def scan_calendar(
        self,
        current_date: datetime,
        price_data: Optional[Dict[str, pd.DataFrame]] = None
    ) -> List[Dict]:
        """
        Scan FDA calendar for upcoming opportunities.

        Args:
            current_date: Current date
            price_data: Optional price data for volume filtering

        Returns:
            List of opportunities with format:
            [{
                "symbol": str,
                "action": "ENTRY" or "EXIT",
                "pdufa_date": datetime,
                "days_to_pdufa": int,
                "signal_strength": float
            }]
        """
        opportunities = []

        # Filter calendar
        events = self.filter_events(
            self._calendar,
            min_market_cap=self.min_market_cap,
            min_phase=self.min_phase
        )

        for _, event in events.iterrows():
            pdufa_date = event['pdufa_date']
            days_to_pdufa = (pdufa_date - current_date).days

            # Entry window: T-5 days
            if days_to_pdufa == self.entry_days:
                signal_strength = self._calculate_entry_signal(event, price_data)

                if signal_strength > 0:
                    opportunities.append({
                        "symbol": event['symbol'],
                        "action": "ENTRY",
                        "pdufa_date": pdufa_date,
                        "days_to_pdufa": days_to_pdufa,
                        "signal_strength": signal_strength,
                        "drug_name": event['drug_name'],
                        "indication": event['indication'],
                        "success_probability": event.get('success_probability', 0.5)
                    })

            # Exit window: T-2 days
            elif days_to_pdufa == self.exit_days:
                opportunities.append({
                    "symbol": event['symbol'],
                    "action": "EXIT",
                    "pdufa_date": pdufa_date,
                    "days_to_pdufa": days_to_pdufa,
                    "signal_strength": 1.0,  # Always exit
                    "drug_name": event['drug_name'],
                    "indication": event['indication']
                })

        if opportunities:
            logger.info(f"Found {len(opportunities)} FDA opportunities for {current_date}")

        return opportunities

    def _calculate_entry_signal(
        self,
        event: pd.Series,
        price_data: Optional[Dict[str, pd.DataFrame]]
    ) -> float:
        """
        Calculate entry signal strength for FDA event.

        Args:
            event: Event row from calendar
            price_data: Price data for volume filtering

        Returns:
            Signal strength in [0, 1]
        """
        symbol = event['symbol']

        # Base signal strength from success probability
        signal_strength = event.get('success_probability', 0.5)

        # Volume filter (if price data available)
        if price_data and symbol in price_data:
            df = price_data[symbol]

            if 'close' in df.columns and 'volume' in df.columns:
                # Calculate average daily dollar volume
                recent_data = df.tail(20)
                avg_dollar_volume = (recent_data['close'] * recent_data['volume']).mean()

                if avg_dollar_volume < self.min_daily_volume:
                    logger.warning(f"{symbol}: Insufficient volume (${avg_dollar_volume:,.0f} < ${self.min_daily_volume:,.0f})")
                    return 0.0

                # Boost signal if volume is high
                volume_multiplier = min(avg_dollar_volume / self.min_daily_volume, 2.0)
                signal_strength *= (1 + (volume_multiplier - 1) * 0.2)

        # Clip to [0, 1]
        signal_strength = np.clip(signal_strength, 0, 1)

        return signal_strength

    def generate(
        self,
        current_date: datetime,
        price_data: Optional[Dict[str, pd.DataFrame]] = None
    ) -> Dict[str, Dict]:
        """
        Generate event-driven signals.

        Args:
            current_date: Current date
            price_data: Price data for filtering

        Returns:
            Dictionary of {symbol: {action, signal_strength, metadata}}
        """
        opportunities = self.scan_calendar(current_date, price_data)

        signals = {}
        for opp in opportunities:
            symbol = opp['symbol']
            action = opp['action']

            if action == "ENTRY":
                signal_value = opp['signal_strength']
            elif action == "EXIT":
                signal_value = -1.0  # Exit signal (sell)
            else:
                signal_value = 0.0

            signals[symbol] = {
                "signal": signal_value,
                "action": action,
                "pdufa_date": opp['pdufa_date'],
                "days_to_pdufa": opp['days_to_pdufa'],
                "drug_name": opp.get('drug_name'),
                "indication": opp.get('indication'),
                "success_probability": opp.get('success_probability')
            }

        return signals

    def add_event(
        self,
        symbol: str,
        drug_name: str,
        indication: str,
        pdufa_date: datetime,
        phase: int,
        market_cap: float,
        success_probability: float = 0.5
    ):
        """
        Add event to calendar (for manual maintenance).

        Args:
            symbol: Stock symbol
            drug_name: Drug name
            indication: Medical indication
            pdufa_date: PDUFA date
            phase: Trial phase (1, 2, 3)
            market_cap: Market capitalization
            success_probability: Estimated success probability
        """
        new_event = pd.DataFrame([{
            "symbol": symbol,
            "drug_name": drug_name,
            "indication": indication,
            "pdufa_date": pdufa_date,
            "phase": phase,
            "market_cap": market_cap,
            "success_probability": success_probability
        }])

        self._calendar = pd.concat([self._calendar, new_event], ignore_index=True)

        logger.info(f"Added FDA event: {symbol} - {drug_name} ({pdufa_date})")

    def backtest(
        self,
        price_data: Dict[str, pd.DataFrame],
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Backtest event-driven strategy.

        Args:
            price_data: Historical price data
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with trades and returns
        """
        trades = []

        # Get date range
        date_range = pd.date_range(start_date, end_date, freq='D')

        for current_date in date_range:
            opportunities = self.scan_calendar(current_date, price_data)

            for opp in opportunities:
                symbol = opp['symbol']
                action = opp['action']

                if symbol not in price_data:
                    continue

                # Get price at current date
                df = price_data[symbol]
                if current_date not in df.index:
                    continue

                entry_price = df.loc[current_date, 'close']

                if action == "ENTRY":
                    # Record entry
                    trades.append({
                        "date": current_date,
                        "symbol": symbol,
                        "action": "BUY",
                        "price": entry_price,
                        "pdufa_date": opp['pdufa_date'],
                        "signal_strength": opp['signal_strength']
                    })

                elif action == "EXIT":
                    # Record exit
                    trades.append({
                        "date": current_date,
                        "symbol": symbol,
                        "action": "SELL",
                        "price": entry_price,
                        "pdufa_date": opp['pdufa_date']
                    })

        return pd.DataFrame(trades)
