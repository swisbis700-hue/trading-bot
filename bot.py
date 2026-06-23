import time
import os
import threading
import requests
from flask import Flask

API_KEY    = os.environ.get("MEXC_API_KEY")
API_SECRET = os.environ.get("MEXC_API_SECRET")
BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")

SYMBOL      = "BTCUSDT"
QTY         = "0.00001"
INTERVAL    = "1m"
CHECK_EVERY = 30

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def send_telegram(msg):
    try:
        requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print(f"Telegram error: {e}")

def get_candles(symbol="BTCUSDT", interval="1m", limit=100):
    url = "https://api.mexc.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        closes = [float(c[4]) for c in data]
        highs  = [float(c[2]) for c in data]
        lows   = [float(c[3]) for c in data]
        return closes, highs, lows
    except Exception as e:
        print(f"MEXC candles error: {e}")
        return [], [], []

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
    if prev_ema21 <= prev_ema50 and curr_ema21 > curr_ema50 and rsi_val < 70:
        sl = price - (1.5 * atr_val)
        tp = price + (3 * abs(price - sl))
        return {"signal": "BUY", "price": price, "sl": round(sl, 2), "tp": round(tp, 2), "rsi": round(rsi_val, 1)}
    if prev_ema21 >= prev_ema50 and curr_ema21 < curr_ema50 and rsi_val > 30:
        sl = price + (1.5 * atr_val)
        tp = price - (3 * abs(sl - price))
        return {"signal": "SELL", "price": price, "sl": round(sl, 2), "tp": round(tp, 2), "rsi": round(rsi_val, 1)}
    return None

def place_order(side):
    import hmac
    import hashlib
    from urllib.parse import urlencode

    timestamp = str(int(time.time() * 1000))
    params = {
        "symbol": SYMBOL,
        "side": side,
        "type": "MARKET",
        "quantity": QTY,
        "timestamp": timestamp
    }
    query = urlencode(params)
    signature = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = signature

    try:
        res = requests.post(
            "https://api.mexc.com/api/v3/order",
            params=params,
            headers={"X-MEXC-APIKEY": API_KEY},
            timeout=10
        )
        return res.json()
    except Exception as e:
        print(f"Order error: {e}")
        return None

def bot_loop():
    print("Bot started...")
    send_telegram("🤖 البوت بدأ - يراقب BTCUSDT على MEXC")
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
                    print(f"{sig} | {price} | SL:{sl} | TP:{tp}")
                    side = "BUY" if sig == "BUY" else "SELL"
                    result = place_order(side)
                    if result and "orderId" in result:
                        msg = (
                            f"{'🟢' if sig == 'BUY' else '🔴'} {sig}\n"
                            f"💰 السعر: {price}\n"
                            f"🛑 SL: {sl}\n"
                            f"🎯 TP: {tp}\n"
                            f"📊 RSI: {rsi_val}"
                        )
                        send_telegram(msg)
                        last_signal = sig
                    else:
                        send_telegram(f"⚠️ فشل {sig}: {result}")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CHECK_EVERY)

thread = threading.Thread(target=bot_loop)
thread.daemon = True
thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
