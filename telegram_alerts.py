import yfinance as yf
import pandas as pd
import requests
import json
import os
import traceback
from datetime import datetime

# ==========================================
# 1. الإعدادات والمفاتيح
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '')

# ==========================================
# 2. إعدادات إدارة المخاطر
# ==========================================
STOP_LOSS_PERCENT = 3.0
TAKE_PROFIT_PERCENT = 6.0
TRADE_QTY = 1

# ==========================================
# 3. قوائم المراقبة
# ==========================================
GLOBAL_WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY",
    "2222.SR", "1120.SR",
    "ADCB.AD", "FAB.AD",
    "BTC-USD", "ETH-USD",
    "GC=F", "SI=F"
]

ALPACA_TRADABLE = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "SPY", "BTC-USD", "ETH-USD"]

ALERTS_FILE = "last_alerts.json"

# ==========================================
# 4. دوال مساعدة
# ==========================================
def send_telegram_message(message):
    """إرسال رسالة تيليجرام مع حماية كاملة"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ مفاتيح تيليجرام غير متاحة")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url
