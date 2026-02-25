"""
Configuration module for FlowX Trading Bot
All constants and settings in one place
"""

import os
from datetime import time as dtime
import pytz

# =========================
# MARKET SETTINGS
# =========================
SYMBOL = "XAUUSDs"
TIMEFRAME_MINUTES = 5
CHECK_INTERVAL_SECONDS = 60

# =========================
# TECHNICAL INDICATORS
# =========================
EMA_FAST = 21
EMA_SLOW = 100
ATR_PERIOD = 14
VOL_PERIOD = 20

# =========================
# TRADE SETTINGS
# =========================
MAX_SIGNALS_PER_SESSION = 5
MIN_COOLDOWN_MINUTES = 15
RISK_RATIO = 1.2  # SL distance multiplier
TP1_RATIO = 0.8   # TP levels as ATR multiples
TP2_RATIO = 1.6
TP3_RATIO = 2.4

# =========================
# TELEGRAM CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8476274388:AAGX21Pa0QRtbq-FMPnq9tbplWz6rt92PIk")
CHAT_ID = int(os.getenv("CHAT_ID", "-1003847722117"))
TELEGRAM_TIMEOUT = 5

# =========================
# TIMEZONE
# =========================
TZ = pytz.timezone("Europe/Sofia")

# =========================
# ECONOMIC CALENDAR (FMP API)
# =========================
ECON_API_KEY = os.getenv("ECON_API_KEY", "vNIQdQWMAe5jcLje16MC1Zk6UnyKfKlh")
NEWS_LOOKAHEAD_MINUTES = 30   # Block BEFORE news
NEWS_COOLDOWN_MINUTES = 10    # Block AFTER news

# =========================
# SESSION TIMES (Sofia timezone)
# =========================
SESSIONS = {
    "ASIAN": {"start": dtime(1, 0), "end": dtime(6, 0)},
    "LONDON": {"start": dtime(7, 30), "end": dtime(11, 30)},
    "NY": {"start": dtime(14, 30), "end": dtime(23, 0)}
}

# Session opening guards (first 15 mins = danger zone)
SESSION_GUARDS = {
    "LONDON": {"start": dtime(8, 0), "end": dtime(8, 15)},
    "NY": {"start": dtime(14, 0), "end": dtime(14, 15)}
}

# =========================
# MESSAGING TIMES
# =========================
MORNING_MESSAGE_TIME = dtime(6, 0)
EVENING_MESSAGE_TIME = dtime(19, 0)
DAILY_REPORT_TIME = dtime(19, 0)

# =========================
# MAGIC NUMBERS
# =========================
MT5_MAGIC = 202402
ORDER_VOLUME = 0.5

# =========================
# FILE PATHS
# =========================
MEMORY_FILE = "memory.json"
LOG_FILE = "flowx_trading.log"

# =========================
# TRADING LESSONS
# =========================
LESSONS = [
    "Търпението е позиция.",
    "Най-добрият трейд понякога е без трейд.",
    "Контролът е по-важен от печалбата.",
    "Дисциплината пази капитала.",
    "Лошите входове бягат бързо.",
    "Добрите входове винаги чакат.",
    "Капиталът е оръжието - пази го."
]

# =========================
# CAPITAL PROTECTION
# =========================
INITIAL_BALANCE = 10000.0  # Starting capital
MAX_DRAWDOWN_PERCENT = 5.0  # Stop trading if -5% drawdown
MAX_DAILY_LOSS = 500.0  # Max daily loss in dollars

