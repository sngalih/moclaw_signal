import requests
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from datetime import datetime

BASE_URL = "https://api.kucoin.com"

# Top pairs berdasarkan volume USDT (KuCoin format: BTC-USDT)
TOP_PAIRS = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT", "XRP-USDT",
    "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "DOT-USDT",
    "LTC-USDT", "UNI-USDT", "ATOM-USDT", "NEAR-USDT",
    "APT-USDT", "ARB-USDT", "OP-USDT", "INJ-USDT", "SUI-USDT",
    "TON-USDT"
]

def get_klines(symbol, interval="4hour", limit=200):
    url = f"{BASE_URL}/api/v1/market/candles"
    params = {"type": interval, "symbol": symbol, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if data.get("code") != "200000" or not data.get("data"):
        raise ValueError(f"No data: {data.get('msg','')}")
    # KuCoin returns newest first, reverse to oldest first
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

    # 1. RSI
    rsi_series = RSIIndicator(close, window=14).rsi()
    rsi = rsi_series.dropna().iloc[-1]
    if rsi < 35:
        scores.append(2); details.append(f"RSI={rsi:.1f} (oversold 🟢)")
    elif rsi < 45:
        scores.append(1); details.append(f"RSI={rsi:.1f} (mendekati oversold 🟡)")
    elif rsi > 70:
        scores.append(-2); details.append(f"RSI={rsi:.1f} (overbought 🔴)")
    elif rsi > 60:
        scores.append(-1); details.append(f"RSI={rsi:.1f} (mendekati overbought 🟠)")
    else:
        scores.append(0); details.append(f"RSI={rsi:.1f} (netral ⚪)")

    # 2. MACD
    macd_obj = MACD(close)
    macd_line = macd_obj.macd().dropna()
    signal_line = macd_obj.macd_signal().dropna()
    m1, m0 = macd_line.iloc[-2], macd_line.iloc[-1]
    s1, s0 = signal_line.iloc[-2], signal_line.iloc[-1]
    if m1 < s1 and m0 > s0:
        scores.append(2); details.append("MACD crossover bullish 🟢")
    elif m0 > s0:
        scores.append(1); details.append("MACD di atas sinyal 🟡")
    elif m1 > s1 and m0 < s0:
        scores.append(-2); details.append("MACD crossover bearish 🔴")
    else:
        scores.append(-1); details.append("MACD di bawah sinyal 🟠")

    # 3. EMA 20/50 cross
    ema20 = EMAIndicator(close, window=20).ema_indicator().dropna()
    ema50 = EMAIndicator(close, window=50).ema_indicator().dropna()
    e20_0, e20_1 = ema20.iloc[-1], ema20.iloc[-2]
    e50_0, e50_1 = ema50.iloc[-1], ema50.iloc[-2]
    if e20_0 > e50_0:
        if e20_1 <= e50_1:
            scores.append(2); details.append("EMA20 baru cross EMA50 ke atas 🟢")
        else:
            scores.append(1); details.append("EMA20 > EMA50 (trend naik) 🟡")
    else:
        if e20_1 >= e50_1:
            scores.append(-2); details.append("EMA20 baru cross EMA50 ke bawah 🔴")
        else:
            scores.append(-1); details.append("EMA20 < EMA50 (trend turun) 🟠")

    # 4. Bollinger Bands
    bb = BollingerBands(close, window=20, window_dev=2)
    bb_low = bb.bollinger_lband().dropna().iloc[-1]
    bb_high = bb.bollinger_hband().dropna().iloc[-1]
    bb_mid = bb.bollinger_mavg().dropna().iloc[-1]
    price = close.iloc[-1]
    if price <= bb_low:
        scores.append(2); details.append("Harga sentuh BB bawah (rebound?) 🟢")
    elif price <= bb_mid:
        scores.append(1); details.append("Harga di bawah BB tengah 🟡")
    elif price >= bb_high:
        scores.append(-2); details.append("Harga sentuh BB atas (koreksi?) 🔴")
    else:
        scores.append(-1); details.append("Harga di atas BB tengah 🟠")

    # 5. Volume Spike
    avg_vol = volume.iloc[-21:-1].mean()
    cur_vol = volume.iloc[-1]
    vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 1
    if vol_ratio > 1.5:
        scores.append(1); details.append(f"Volume spike {vol_ratio:.1f}x rata-rata 🟢")
    elif vol_ratio < 0.5:
        scores.append(-1); details.append(f"Volume rendah {vol_ratio:.1f}x rata-rata 🟠")
    else:
        scores.append(0); details.append(f"Volume normal {vol_ratio:.1f}x rata-rata ⚪")

    # 6. Stochastic
    stoch = StochasticOscillator(high, low, close, window=14, smooth_window=3)
    k = stoch.stoch().dropna().iloc[-1]
    d = stoch.stoch_signal().dropna().iloc[-1]
    k1 = stoch.stoch().dropna().iloc[-2]
    d1 = stoch.stoch_signal().dropna().iloc[-2]
    if k < 20 and k > d and k1 <= d1:
        scores.append(2); details.append(f"Stoch K={k:.1f} oversold + bullish cross 🟢")
    elif k > 80 and k < d and k1 >= d1:
        scores.append(-2); details.append(f"Stoch K={k:.1f} overbought + bearish cross 🔴")
    elif k < 30:
        scores.append(1); details.append(f"Stoch K={k:.1f} zona oversold 🟡")
    elif k > 70:
        scores.append(-1); details.append(f"Stoch K={k:.1f} zona overbought 🟠")
    else:
        scores.append(0); details.append(f"Stoch K={k:.1f} netral ⚪")

    total = sum(scores)
    max_score = sum(abs(s) for s in scores)
    prob = ((total / max_score) * 50 + 50) if max_score > 0 else 50
    prob = max(0, min(100, prob))

    direction = "LONG 📈" if total > 0 else "SHORT 📉" if total < 0 else "WAIT ⏸"

    return {
        "score": total,
        "probability": prob,
        "direction": direction,
        "details": details,
        "price": price,
        "rsi": rsi,
    }

def calculate_tp_sl(price, direction, df):
    atr = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range().dropna().iloc[-1]
    if "LONG" in direction:
        tp1 = price + atr * 1.5
        tp2 = price + atr * 3.0
        sl = price - atr * 1.0
    elif "SHORT" in direction:
        tp1 = price - atr * 1.5
        tp2 = price - atr * 3.0
        sl = price + atr * 1.0
    else:
        return None
    rr = abs(tp1 - price) / abs(sl - price) if sl != price else 0
    return {"tp1": tp1, "tp2": tp2, "sl": sl, "rr": rr, "atr": atr}

def fmt(val):
    if val >= 1000:
        return f"${val:,.2f}"
    elif val >= 1:
        return f"${val:,.4f}"
    else:
        return f"${val:,.6f}"

print(f"\n{'='*65}")
print(f"  🔔 SINYAL CRYPTO SPOT — {datetime.now().strftime('%d %b %Y %H:%M')}")
print(f"  Source: KuCoin  |  TF: 4H  |  Filter: Probabilitas > 50%")
print(f"{'='*65}\n")

results = []
for symbol in TOP_PAIRS:
    try:
        df = get_klines(symbol, interval="4hour", limit=200)
        if len(df) < 60:
            continue
        sig = calculate_signals(df)
        sig["symbol"] = symbol.replace("-USDT","USDT")
        sig["df"] = df
        results.append(sig)
    except Exception as e:
        pass  # skip silently

filtered = [r for r in results if r["probability"] > 50 and "WAIT" not in r["direction"]]
filtered.sort(key=lambda x: x["probability"], reverse=True)

if not filtered:
    print("  Tidak ada sinyal valid saat ini.\n  Semua pasang dalam kondisi netral / mixed.\n")
else:
    for r in filtered:
        price = r["price"]
        tpsl = calculate_tp_sl(price, r["direction"], r["df"])
        strength = "🔥 KUAT" if r["probability"] >= 70 else "✅ MODERAT" if r["probability"] >= 60 else "⚡ LEMAH"
        print(f"┌─ {r['symbol']}  {r['direction']}  [{strength}]")
        print(f"│  Harga Saat Ini : {fmt(price)}")
        print(f"│  Probabilitas   : {r['probability']:.1f}%  |  Skor: {r['score']:+d}/10")
        if tpsl:
            print(f"│  TP1 / TP2      : {fmt(tpsl['tp1'])} / {fmt(tpsl['tp2'])}")
            print(f"│  Stop Loss      : {fmt(tpsl['sl'])}  |  R:R ≈ 1:{tpsl['rr']:.1f}")
        print(f"│  Sinyal:")
        for d in r["details"]:
            print(f"│    • {d}")
        print(f"└{'─'*55}")
        print()

# Ringkasan
long_count = sum(1 for r in filtered if "LONG" in r["direction"])
short_count = sum(1 for r in filtered if "SHORT" in r["direction"])
print(f"  📊 Ringkasan: {len(filtered)} sinyal aktif — LONG: {long_count} | SHORT: {short_count}")
print(f"  🕐 Update: {datetime.now().strftime('%H:%M:%S')}")

print(f"\n{'─'*65}")
print(f"  ⚠️  DISCLAIMER: Bukan saran keuangan. Lakukan riset sendiri")
print(f"     (DYOR). Gunakan manajemen risiko. Jangan invest lebih")
print(f"     dari yang sanggup kamu rugi. Past performance ≠ future.")
print(f"{'─'*65}\n")
