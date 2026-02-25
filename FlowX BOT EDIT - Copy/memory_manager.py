"""
Memory Manager - Handles persistent state storage
Saves and loads bot state from JSON file
"""

import json
import os
from datetime import datetime
import pytz

class MemoryManager:
    def __init__(self, filepath: str, timezone: pytz.timezone):
        self.filepath = filepath
        self.tz = timezone
        self.data = self._load()
    
    def _load(self) -> dict:
        """Load memory from JSON file"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Memory load error: {e}, starting fresh")
                return self._init_memory()
        return self._init_memory()
    
    def _init_memory(self) -> dict:
        """Initialize empty memory structure"""
        return {
            "morning_sent": False,
            "evening_sent": False,
            "asian_snapshot": {
                "range": 0.0,
                "trend": "NEUTRAL",
                "volatility": 0.0
            },
            "last_signal_time": None,
            "signals_today": 0,
            "wins_today": 0,
            "losses_today": 0,
            "sessions_tracked": []
        }
    
    def save(self):
        """Save memory to JSON file"""
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"❌ Memory save error: {e}")
    
    def get(self, key: str, default=None):
        """Get value from memory"""
        return self.data.get(key, default)
    
    def set(self, key: str, value):
        """Set value in memory"""
        self.data[key] = value
        self.save()
    
    def update_asian_snapshot(self, range_val: float, trend: str, volatility: float):
        """Update asian session snapshot"""
        self.data["asian_snapshot"] = {
            "range": range_val,
            "trend": trend,
            "volatility": volatility
        }
        self.save()
    
    def increment_daily_stat(self, stat: str):
        """Increment daily statistics"""
        if stat not in self.data:
            self.data[stat] = 0
        self.data[stat] += 1
        self.save()
    
    def reset_daily_stats(self):
        """Reset daily trading statistics"""
        self.data["signals_today"] = 0
        self.data["wins_today"] = 0
        self.data["losses_today"] = 0
        self.save()

