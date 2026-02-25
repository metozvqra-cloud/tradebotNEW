"""
News Filter - Monitor economic calendar and block trades during high-impact events
"""

import requests
from datetime import datetime, timedelta
import pytz
from typing import Tuple, Optional
from logger import Logger
from config import ECON_API_KEY, NEWS_LOOKAHEAD_MINUTES, NEWS_COOLDOWN_MINUTES


class NewsFilter:
    def __init__(self, api_key: str, logger: Logger, timezone: pytz.timezone):
        self.api_key = api_key
        self.logger = logger
        self.tz = timezone
        self.last_check = None
        self.cache = None
        self.cache_duration = 300  # Cache for 5 minutes
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid"""
        if self.last_check is None or self.cache is None:
            return False
        
        return (datetime.now() - self.last_check).total_seconds() < self.cache_duration
    
    def _fetch_calendar(self, date_str: str) -> list:
        """Fetch economic calendar from FMP API"""
        try:
            url = (
                f"https://financialmodelingprep.com/api/v3/economic_calendar"
                f"?from={date_str}&to={date_str}&apikey={self.api_key}"
            )
            
            response = requests.get(url, timeout=5)
            return response.json() if response.status_code == 200 else []
        
        except Exception as e:
            self.logger.error(f"Economic calendar API error: {e}")
            return []
    
    def high_impact_news_soon(self, now: datetime = None) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if high-impact US news event is coming soon
        
        Returns:
            (has_news, event_name, minutes_away)
        """
        if now is None:
            now = datetime.now(self.tz)
        
        # Use cache if valid
        if self._is_cache_valid() and self.cache is not None:
            data = self.cache
        else:
            date_str = now.strftime("%Y-%m-%d")
            data = self._fetch_calendar(date_str)
            self.last_check = datetime.now()
            self.cache = data
        
        if not data:
            return False, None, None
        
        for event in data:
            # Filter: high impact US events only
            if event.get("impact") != "High":
                continue
            if event.get("country") != "US":
                continue
            
            try:
                event_time = datetime.strptime(
                    event["date"], "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=self.tz)
            except:
                continue
            
            minutes_to_event = (event_time - now).total_seconds() / 60
            
            # Block if within lookahead or cooldown window
            if -NEWS_COOLDOWN_MINUTES <= minutes_to_event <= NEWS_LOOKAHEAD_MINUTES:
                event_name = event.get("event", "High Impact News")
                self.logger.warn(f"HIGH-IMPACT NEWS: {event_name} in {minutes_to_event:.0f} min")
                return True, event_name, int(minutes_to_event)
        
        return False, None, None
    
    def should_trade(self, now: datetime = None) -> Tuple[bool, Optional[str]]:
        """
        Determine if trading should be allowed (news-wise)
        
        Returns:
            (can_trade, reason_if_blocked)
        """
        has_news, event_name, minutes = self.high_impact_news_soon(now)
        
        if has_news:
            reason = f"HIGH-IMPACT NEWS: {event_name} ({minutes}m away)"
            return False, reason
        
        return True, None

