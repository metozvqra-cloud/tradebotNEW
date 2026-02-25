"""
Telegram Client - Handle all Telegram bot messaging
"""

import requests
import random
from typing import List
from logger import Logger
from config import BOT_TOKEN, CHAT_ID, TELEGRAM_TIMEOUT, LESSONS


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: int, logger: Logger, timeout: int = 5):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger = logger
        self.timeout = timeout
    
    def send_message(self, text: str) -> bool:
        """Send message to Telegram chat"""
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                },
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Telegram send error: {e}")
            return False
    
    # =========================
    # STARTUP & STATUS
    # =========================
    def startup(self):
        """Send startup message"""
        self.send_message(
            "🟢 <b>FlowX | Team is online</b>\n\n"
            "We monitor the gold market together.\n"
            "Signals are shared only when risk is controlled.\n\n"
            "<i>Quality over quantity.</i>"
        )
    
    def sys_status(self, msg: str):
        """Send system status message"""
        self.send_message(f"⚙️ <b>System</b>\n\n{msg}")
    
    # =========================
    # SESSION BRIEFINGS
    # =========================
    def morning_briefing(self, range_val: float, volatility: float, trend: str):
        """Send morning briefing after Asian session"""
        self.send_message(
            "🌅 <b>Morning Briefing – FlowX</b>\n\n"
            "Добро утро.\n\n"
            "FlowX беше на линия през цялата нощ.\n"
            "Пазарът беше наблюдаван тик по тик,\n"
            "без предположения – само данни.\n\n"
            "📊 <b>Asian Session – какво се случи</b>\n"
            f"• Диапазон (range): {range_val:.2f}\n"
            f"• Волатилност (ATR): {volatility:.2f}\n"
            f"• Структурен bias: {trend}\n\n"
            "🧠 <b>Как FlowX интерпретира това</b>\n"
            "• Asian session оформи рамката за деня\n"
            "• Ликвидността е изградена, но не и изразходвана\n"
            "• Това създава потенциал за реакция, не за бързане\n\n"
            "📍 <b>Какво да очакваме днес</b>\n"
            "• London ще тества границите на Asian range\n"
            "• NY ще реши дали има continuation или капан\n"
            "• Фалшивите движения са възможни – търсим потвърждение\n\n"
            "🎯 <b>Фокус за деня</b>\n"
            "Търпение. Селективност. Контрол.\n"
            "FlowX ще действа само при ясно предимство.\n\n"
            "<i>Пазарът не бяга.\n"
            "Лошите входове – да.\n"
            "Добрите – идват, когато си спокоен.</i>"
        )
    
    def evening_briefing(self):
        """Send evening briefing"""
        self.send_message(
            "🌙 <b>Evening Briefing</b>\n\n"
            "Денят приключва.\n"
            "Дисциплината е по-важна от резултата.\n\n"
            "Утре има нови възможности."
        )
    
    def after_hours_warning(self):
        """After-hours monitoring warning"""
        self.send_message(
            "👁️ <b>After-Hours Monitoring</b>\n\n"
            "Пазарът е по-ненадежден.\n"
            "Системата наблюдава, но не преследва движения."
        )
    
    # =========================
    # SIGNALS
    # =========================
    def send_signal(self, direction: str, price: float, sl: float, 
                   tps: List[float], session: str):
        """Send trade signal"""
        self.send_message(
            f"🟢 <b>{direction} XAUUSD ({session})</b>\n\n"
            f"Entry: <b>{price:.2f}</b>\n"
            f"TP1: {tps[0]:.2f}\n"
            f"TP2: {tps[1]:.2f}\n"
            f"TP3: {tps[2]:.2f}\n"
            f"SL: {sl:.2f}\n\n"
            "⚠️ <i>Trade carefully. Market is never certain.</i>"
        )
    
    def no_signal(self, reason: str):
        """Send no-signal notification"""
        self.send_message(
            "📊 <b>No Signal</b>\n\n"
            f"Причина: <b>{reason}</b>\n\n"
            "Липсата на трейд е съзнателно решение."
        )
    
    # =========================
    # TRADE UPDATES
    # =========================
    def tp_hit(self, tp_level: int, is_final: bool = False):
        """Send TP hit notification"""
        if is_final:
            self.send_message("🏁 <b>TP3 HIT – TRADE CLOSED</b>")
        else:
            self.send_message(f"🟢 <b>TP{tp_level} HIT</b>")
    
    def sl_hit(self):
        """Send SL hit notification"""
        self.send_message("🔴 <b>SL HIT</b>")
    
    def breakeven_warning(self):
        """Send breakeven move warning"""
        self.send_message(
            "⚠️ <b>BE WARNING</b>\n\n"
            "Пазарът губи импулс след TP1.\n"
            "👉 <b>Препоръка:</b> преместете SL на BE.\n\n"
            "🔒 Пазим капитала."
        )
    
    def news_alert(self, event_name: str, minutes_away: int):
        """Send economic news alert"""
        self.send_message(
            f"📺 <b>HIGH IMPACT NEWS</b>\n\n"
            f"Event: {event_name}\n"
            f"In: {minutes_away} minutes\n\n"
            "⏸️ <i>Bot paused. Volatility incoming.</i>"
        )
    
    # =========================
    # DAILY REPORTS
    # =========================
    def daily_performance_report(self, signals: int, wins: int, losses: int):
        """Send daily performance report"""
        winrate = (wins / signals * 100) if signals > 0 else 0
        
        self.send_message(
            "📊 <b>FlowX Daily Performance</b>\n\n"
            f"📈 Total signals: <b>{signals}</b>\n"
            f"✅ Wins: <b>{wins}</b>\n"
            f"❌ Losses: <b>{losses}</b>\n"
            f"🔥 Winrate: <b>{winrate:.1f}%</b>\n\n"
            "🔒 Risk managed. Capital protected."
        )
    
    def lesson_of_the_day(self):
        """Send random lesson"""
        lesson = random.choice(LESSONS)
        self.send_message(f"📖 <b>Lesson of the Day</b>\n\n\"{lesson}\"")
