"""
Session Manager - Handle trading sessions and session-specific logic
"""

from datetime import datetime, time as dtime
import pytz
from config import SESSIONS, SESSION_GUARDS


class SessionManager:
    def __init__(self, timezone: pytz.timezone):
        self.tz = timezone
    
    def get_current_session(self, now: datetime = None) -> str:
        """Determine current trading session"""
        if now is None:
            now = datetime.now(self.tz)
        
        t = now.time()
        
        for session_name, times in SESSIONS.items():
            if times["start"] <= t < times["end"]:
                return session_name
        
        return "OFF"
    
    def is_session_opening(self, session: str, now: datetime = None) -> bool:
        """Check if we're in session opening guard period (higher volatility/slippage)"""
        if now is None:
            now = datetime.now(self.tz)
        
        if session not in SESSION_GUARDS:
            return False
        
        guard = SESSION_GUARDS[session]
        t = now.time()
        
        return guard["start"] <= t <= guard["end"]
    
    def is_trading_hours(self, now: datetime = None) -> bool:
        """Check if we're in any active trading session"""
        session = self.get_current_session(now)
        return session != "OFF"
    
    def session_ends_in_minutes(self, session: str, now: datetime = None) -> int:
        """Minutes until session ends"""
        if now is None:
            now = datetime.now(self.tz)
        
        if session not in SESSIONS:
            return 0
        
        end_time = SESSIONS[session]["end"]
        current_seconds = now.time().hour * 3600 + now.time().minute * 60
        end_seconds = end_time.hour * 3600 + end_time.minute * 60
        
        delta = end_seconds - current_seconds
        return max(0, delta // 60)
    
    def get_session_info(self, now: datetime = None) -> dict:
        """Get comprehensive session information"""
        if now is None:
            now = datetime.now(self.tz)
        
        session = self.get_current_session(now)
        
        return {
            "name": session,
            "is_active": session != "OFF",
            "is_opening": self.is_session_opening(session, now),
            "minutes_to_end": self.session_ends_in_minutes(session, now) if session != "OFF" else 0
        }

