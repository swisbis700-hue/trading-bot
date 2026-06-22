import time
import os
import requests
import pybit.unified_trading

# ==================== الإعدادات ====================
API_KEY    = os.environ.get("BYBIT_API_KEY")
API_SECRET = os.environ.get("BYBIT_API_SECRET")
BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")

SYMBOL      = "BTCUSDT"
QTY         = "0.001"
INTERVAL    = "60"    # الإطار الزمني بالدقائق: 1, 3, 5, 15, 30, 60, 240, D
CHECK_EVERY = 60      # كل كم ثانية يتحقق

# ==================== Bybit ====================
session = pybit.unified_trading.HTTP(
    testnet=False,
    api_key=API_KEY,
    api_secret=API_SECRET,
)

# ==================== Telegram ====================
def send_telegram(msg):
    try:
        requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print(f"Telegram error: {e}")

# ==================== جلب الشموع من Bybit ====================
def get_candles(symbol="BTCUSDT", interval="60", limit=100):
    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        candles = data["result"]["list"]
        # Bybit يرجع الشموع من الأحدث للأقدم، نعكسها
        candles = list(reversed(candles))
        closes = [float(c[4]) for c in candles]
        highs  = [float(c[2]) for c in candles]
        lows   = [float(c[3]) for c in candles]
        return closes, highs, lows
    except Exception as e:
        print(f"Bybit candles error: {e}")
        return [], [], []

# ==================== حساب المؤشرات ====================
def ema(values, period):
    k = 2 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result

def rsi(values, period=14):
    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    if len(gains) < period:
        return 50
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def atr(highs, lows, closes, period=14):
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        trs.append(tr)
    return sum(trs[-period:]) / period if len(trs) >= period else 0

# ==================== استراتيجية EMA Pullback ====================
def check_signal(closes, highs, lows):
    if len(closes) < 60:
        return None

    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)
    rsi_val = rsi(closes, 14)
    atr_val = atr(highs, lows, closes, 14)
    price = closes[-1]

    prev_ema21 = ema21[-2]
    prev_ema50 = ema50[-2]
    curr_ema21 = ema21[-1]
    curr_ema50 = ema50[-1]

    # إشارة BUY
    if prev_ema21 <= prev_ema50 and curr_ema21 > curr_ema50 and rsi_val < 70:
        sl = price - (1.5 * atr_val)
        tp = price + (3 * abs(price - sl))
        return {"signal": "BUY", "price": price, "sl": round(sl, 2), "tp": round(tp, 2), "rsi": round(rsi_val, 1)}

    # إشارة SELL
    if prev_ema21 >= prev_ema50 and curr_ema21 < curr_ema50 and rsi_val > 30:
        sl = price + (1.5 * atr_val)
        tp = price - (3 * abs(sl - price))
        return {"signal": "SELL", "price": price, "sl": round(sl, 2), "tp": round(tp, 2), "rsi": round(rsi_val, 1)}

    return None

# ==================== تنفيذ الأوردر ====================
def place_order(side):
    try:
        result = session.place_order(
            category="linear",
            symbol=SYMBOL,
            side=side,
            orderType="Market",
            qty=QTY
        )
        return result
    except Exception as e:
        print(f"Order error: {e}")
        return None

# ==================== الحلقة الرئيسية ====================
print("🤖 البوت شغال...")
send_telegram("🤖 البوت بدأ - يراقب " + SYMBOL + " على إطار " + INTERVAL + " دقيقة")

last_signal = None

while True:
    try:
        closes, highs, lows = get_candles(SYMBOL, INTERVAL, 100)

        if closes:
            signal = check_signal(closes, highs, lows)

            if signal and signal["signal"] != last_signal:
                sig = signal["signal"]
                price = signal["price"]
                sl = signal["sl"]
                tp = signal["tp"]
                rsi_val = signal["rsi"]

                print(f"📡 إشارة: {sig} | السعر: {price} | SL: {sl} | TP: {tp} | RSI: {rsi_val}")

                side = "Buy" if sig == "BUY" else "Sell"
                result = place_order(side)

                if result:
                    msg = (
                        f"{'🟢' if sig == 'BUY' else '🔴'} إشارة {sig}\n"
                        f"💰 السعر: {price}\n"
                        f"🛑 وقف الخسارة: {sl}\n"
                        f"🎯 الهدف: {tp}\n"
                        f"📊 RSI: {rsi_val}\n"
                        f"⏱ الإطار: {INTERVAL} دقيقة"
                    )
                    send_telegram(msg)
                    last_signal = sig
                else:
                    send_telegram(f"⚠️ فشل تنفيذ أوردر {sig}")
        else:
            print("⚠️ ما جاءت بيانات من Bybit")

    except Exception as e:
        print(f"Error: {e}")
        send_telegram(f"⚠️ خطأ في البوت: {e}")

    time.sleep(CHECK_EVERY)
