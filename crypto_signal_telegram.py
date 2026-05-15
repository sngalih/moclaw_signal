import requests
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from datetime import datetime

TELEGRAM_TOKEN = "8355508359:AAGYH42UAyXO6rnAJc9FwOb6JZxGM1dqBAA"
CHAT_ID = "124128087"
BASE_URL = "https://api.kucoin.com"

TOP_PAIRS = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT", "XRP-USDT",
    "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "DOT-USDT",
    "LTC-USDT", "UNI-USDT", "ATOM-USDT", "NEAR-USDT",
    "APT-USDT", "ARB-USDT", "OP-USDT", "INJ-USDT", "SUI-USDT",
    "TON-USDT"
]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, json=payload, timeout=10)
    return r.json()

def get_klines(symbol, interval="4hour", limit=200):
    url = f"{BASE_URL}/api/v1/market/candles"
    params = {"type": interval, "symbol": symbol, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if data.get("code") != "200000" or not data.get("data"):
        raise ValueError(f"No data: {data.get('msg','')}")
    rows = list(reversed(data["data"]))
    df = pd.DataFrame(rows, columns=["open_time","open","close","high","low","volume","turnover"])
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col])
    df["open_time"] = pd.to_datetime(df["open_time"].astype(int), unit="s")
    return df

def calculate_signals(df):
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    scores = []
    details = []

    # RSI
    rsi = RSIIndicator(close, window=14).rsi().dropna().iloc[-1]
    if rsi < 35:
        scores.append(2); details.append(f"RSI={rsi:.1f} oversold ✅")
    elif rsi < 45:
        scores.append(1); details.append(f"RSI={rsi:.1f} mendekati oversold")
    elif rsi > 70:
        scores.append(-2); details.append(f"RSI={rsi:.1f} overbought ❌")
    elif rsi > 60:
        scores.append(-1); details.append(f"RSI={rsi:.1f} mendekati overbought")
    else:
        scores.append(0); details.append(f"RSI={rsi:.1f} netral")

    # MACD
    macd_obj = MACD(close)
    ml = macd_obj.macd().dropna(); sl = macd_obj.macd_signal().dropna()
    if ml.iloc[-2] < sl.iloc[-2] and ml.iloc[-1] > sl.iloc[-1]:
        scores.append(2); details.append("MACD crossover bullish ✅")
    elif ml.iloc[-1] > sl.iloc[-1]:
        scores.append(1); details.append("MACD > sinyal")
    elif ml.iloc[-2] > sl.iloc[-2] and ml.iloc[-1] < sl.iloc[-1]:
        scores.append(-2); details.append("MACD crossover bearish ❌")
    else:
        scores.append(-1); details.append("MACD < sinyal")

    # EMA 20/50
    e20 = EMAIndicator(close, window=20).ema_indicator().dropna()
    e50 = EMAIndicator(close, window=50).ema_indicator().dropna()
    if e20.iloc[-1] > e50.iloc[-1]:
        scores.append(2 if e20.iloc[-2] <= e50.iloc[-2] else 1)
        details.append("EMA20 > EMA50 (uptrend)" + (" 🔀" if e20.iloc[-2] <= e50.iloc[-2] else ""))
    else:
        scores.append(-2 if e20.iloc[-2] >= e50.iloc[-2] else -1)
        details.append("EMA20 < EMA50 (downtrend)" + (" 🔀" if e20.iloc[-2] >= e50.iloc[-2] else ""))

    # Bollinger Bands
    bb = BollingerBands(close, window=20, window_dev=2)
    price = close.iloc[-1]
    bl = bb.bollinger_lband().dropna().iloc[-1]
    bh = bb.bollinger_hband().dropna().iloc[-1]
    bm = bb.bollinger_mavg().dropna().iloc[-1]
    if price <= bl:
        scores.append(2); details.append("Sentuh BB bawah ✅")
    elif price <= bm:
        scores.append(1); details.append("Di bawah BB tengah")
    elif price >= bh:
        scores.append(-2); details.append("Sentuh BB atas ❌")
    else:
        scores.append(-1); details.append("Di atas BB tengah")

    # Volume
    avg_vol = volume.iloc[-21:-1].mean()
    vol_ratio = volume.iloc[-1] / avg_vol if avg_vol > 0 else 1
    if vol_ratio > 1.5:
        scores.append(1); details.append(f"Volume spike {vol_ratio:.1f}x ✅")
    elif vol_ratio < 0.5:
        scores.append(-1); details.append(f"Volume rendah {vol_ratio:.1f}x")
    else:
        scores.append(0); details.append(f"Volume normal {vol_ratio:.1f}x")

    # Stochastic
    stoch = StochasticOscillator(high, low, close, window=14, smooth_window=3)
    k = stoch.stoch().dropna().iloc[-1]
    d = stoch.stoch_signal().dropna().iloc[-1]
    k1 = stoch.stoch().dropna().iloc[-2]
    d1 = stoch.stoch_signal().dropna().iloc[-2]
    if k < 20 and k > d and k1 <= d1:
        scores.append(2); details.append(f"Stoch K={k:.0f} oversold+cross ✅")
    elif k > 80 and k < d and k1 >= d1:
        scores.append(-2); details.append(f"Stoch K={k:.0f} overbought+cross ❌")
    elif k < 30:
        scores.append(1); details.append(f"Stoch K={k:.0f} oversold zone")
    elif k > 70:
        scores.append(-1); details.append(f"Stoch K={k:.0f} overbought zone")
    else:
        scores.append(0); details.append(f"Stoch K={k:.0f} netral")

    total = sum(scores)
    max_score = sum(abs(s) for s in scores)
    prob = ((total / max_score) * 50 + 50) if max_score > 0 else 50
    prob = max(0, min(100, prob))
    direction = "LONG" if total > 0 else "SHORT" if total < 0 else "WAIT"
    return {"score": total, "probability": prob, "direction": direction,
            "details": details, "price": price, "rsi": rsi}

def calculate_tp_sl(price, direction, df):
    atr = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range().dropna().iloc[-1]
    if direction == "LONG":
        tp1, tp2, sl = price + atr*1.5, price + atr*3.0, price - atr*1.0
    elif direction == "SHORT":
        tp1, tp2, sl = price - atr*1.5, price - atr*3.0, price + atr*1.0
    else:
        return None
    rr = abs(tp1-price) / abs(sl-price) if sl != price else 0
    return {"tp1": tp1, "tp2": tp2, "sl": sl, "rr": rr}

def fmt(val):
    if val >= 1000: return f"${val:,.2f}"
    elif val >= 1: return f"${val:,.4f}"
    else: return f"${val:,.6f}"

def run():
    now = datetime.now().strftime("%d %b %Y %H:%M")
    results = []
    for symbol in TOP_PAIRS:
        try:
            df = get_klines(symbol)
            if len(df) < 60: continue
            sig = calculate_signals(df)
            sig["symbol"] = symbol.replace("-USDT", "USDT")
            sig["df"] = df
            results.append(sig)
        except:
            pass

    filtered = [r for r in results if r["probability"] > 50 and r["direction"] != "WAIT"]
    filtered.sort(key=lambda x: x["probability"], reverse=True)

    long_c = sum(1 for r in filtered if r["direction"] == "LONG")
    short_c = sum(1 for r in filtered if r["direction"] == "SHORT")

    # Header
    header = (
        f"🔔 <b>SINYAL CRYPTO SPOT</b>\n"
        f"📅 {now} WIB | TF: 4H\n"
        f"📊 {len(filtered)} sinyal — 📈 LONG: {long_c} | 📉 SHORT: {short_c}\n"
        f"{'─'*30}"
    )
    send_telegram(header)

    if not filtered:
        send_telegram("⏸ Tidak ada sinyal valid saat ini.\nSemua pair dalam kondisi netral.")
        return

    # Kirim per batch agar tidak kena limit Telegram
    batch = []
    for r in filtered:
        price = r["price"]
        tpsl = calculate_tp_sl(price, r["direction"], r["df"])
        dir_emoji = "📈 LONG" if r["direction"] == "LONG" else "📉 SHORT"
        strength = "🔥" if r["probability"] >= 70 else "✅" if r["probability"] >= 60 else "⚡"

        msg = f"{strength} <b>{r['symbol']}</b> — {dir_emoji} ({r['probability']:.0f}%)\n"
        msg += f"💰 Harga: {fmt(price)}\n"
        if tpsl:
            msg += f"🎯 TP1: {fmt(tpsl['tp1'])} | TP2: {fmt(tpsl['tp2'])}\n"
            msg += f"🛑 SL: {fmt(tpsl['sl'])} | R:R 1:{tpsl['rr']:.1f}\n"
        msg += f"📝 " + " · ".join(r["details"][:3])

        batch.append(msg)
        if len(batch) == 5:
            send_telegram("\n\n".join(batch))
            batch = []

    if batch:
        send_telegram("\n\n".join(batch))

    # Footer
    send_telegram(
        "─────────────────────\n"
        "⚠️ <i>Bukan saran keuangan. DYOR selalu.\n"
        "Gunakan risk management. Jangan invest\n"
        "lebih dari yang sanggup kamu rugi.</i>"
    )

if __name__ == "__main__":
    run()
