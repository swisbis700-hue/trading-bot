import flask
import pybit.unified_trading
import os
import requests

app = flask.Flask(__name__)

BOT_TOKEN = "8031506378:AAGj2NApuFjG7FYK349wPque9XSH-XI-hjM"
CHAT_ID = "1801031068"
API_KEY = os.environ.get("BYBIT_API_KEY")
API_SECRET = os.environ.get("BYBIT_API_SECRET")
SYMBOL = "BTCUSDT"
QTY = "0.001"

session = pybit.unified_trading.HTTP(
    testnet=False,
    api_key=API_KEY,
    api_secret=API_SECRET,
)

def send_telegram(msg):
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                 params={"chat_id": CHAT_ID, "text": msg})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = flask.request.get_data(as_text=True)
    if "BUY" in data:
        session.place_order(category="linear", symbol=SYMBOL,
                           side="Buy", orderType="Market", qty=QTY)
        send_telegram("BUY order placed!")
    elif "SELL" in data:
        session.place_order(category="linear", symbol=SYMBOL,
                           side="Sell", orderType="Market", qty=QTY)
        send_telegram("SELL order placed!")
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
