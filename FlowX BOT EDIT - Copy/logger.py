"""
Logger - Unified logging with console emojis and file output
"""

from datetime import datetime
import pytz
from typing import Literal

LogLevel = Literal["INFO", "OK", "WARN", "ERR", "THINK", "SYS", "SIG"]

class Logger:
    ICONS = {
        "INFO": "ℹ️", "OK": "🟢", "WARN": "🟡",
        "ERR": "🔴", "THINK": "🧠", "SYS": "⚙️", "SIG": "🎯"
    }
    
    def __init__(self, timezone: pytz.timezone, log_file: str = None):
        self.tz = timezone
        self.log_file = log_file
    
    def log(self, message: str, level: LogLevel = "INFO"):
        """Log message to console and file"""
        now = datetime.now(self.tz).strftime("%H:%M:%S")
        icon = self.ICONS.get(level, "•")
        formatted = f"[{now}] {icon} {message}"
        
        print(formatted)
        
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    timestamp = datetime.now(self.tz).isoformat()
                    f.write(f"[{timestamp}] [{level}] {message}\n")
            except Exception as e:
                print(f"❌ Log file error: {e}")
    
    def info(self, msg: str):
        self.log(msg, "INFO")
    
    def ok(self, msg: str):
        self.log(msg, "OK")
    
    def warn(self, msg: str):
        self.log(msg, "WARN")
    
    def error(self, msg: str):
        self.log(msg, "ERR")
    
    def think(self, msg: str):
        self.log(msg, "THINK")
    
    def sys(self, msg: str):
        self.log(msg, "SYS")
    
    def signal(self, msg: str):
        self.log(msg, "SIG")

