"""
🐋 WHALE MOMENTUM SCANNER
Top 5 bullish pairs — 1 pesan gabungan
"""

import requests
import pandas as pd
from datetime import datetime
import time

TELEGRAM_TOKEN = "8355508359:AAGYH42UAyXO6rnAJc9FwOb6JZxGM1dqBAA"
CHAT_ID = "124128087"
BASE_URL = "https://api.kucoin.com"

WHALE_THRESHOLD = {
    "BTC-USDT": 50000, "ETH-USDT": 30000,
    "BNB-USDT": 15000, "SOL-USDT": 15000,
    "DEFAULT": 10000,
}

SCAN_PAIRS = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT", "XRP-USDT",
    "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "DOT-USDT",
    "LTC-USDT", "UNI-USDT", "ATOM-USDT", "NEAR-USDT",
    "APT-USDT", "ARB-USDT", "OP-USDT", "INJ-USDT", "SUI-USDT",
    "TON-USDT", "TRX-USDT", "PEPE-USDT", "WIF-USDT", "BONK-USDT",
    "JUP-USDT", "SEI-USDT", "TIA-USDT", "PYTH-USDT", "STRK-USDT"
]

def send_telegram(text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10
    )

def get_klines(symbol, interval="1hour", limit=168):
    r = requests.get(f"{BASE_URL}/api/v1/market/candles",
                     params={"type": interval, "symbol": symbol, "limit": limit}, timeout=10)
    data = r.json()
    if data.get("code") != "200000" or not data.get("data"):
        return None
    rows = list(reversed(data["data"]))
    df = pd.DataFrame(rows, columns=["open_time","open","close","high","low","volume","turnover"])
    for col in ["open","high","low","close","volume","turnover"]:
        df[col] = pd.to_numeric(df[col])
    return df

def get_recent_trades(symbol):
    r = requests.get(f"{BASE_URL}/api/v1/market/histories",
                     params={"symbol": symbol}, timeout=10)
    data = r.json()
    return data.get("data", [])[:100] if data.get("code") == "200000" else []

def get_orderbook(symbol):
    r = requests.get(f"{BASE_URL}/api/v1/market/orderbook/level2_20",
                     params={"symbol": symbol}, timeout=10)
    data = r.json()
    return data.get("data") if data.get("code") == "200000" else None

def fmt(val):
    if val >= 1000: return f"${val:,.2f}"
    elif val >= 1: return f"${val:,.4f}"
    else: return f"${val:,.6f}"

def analyze(symbol, ticker):
    try:
        price = float(ticker.get("last") or 0)
        change_24h = float(ticker.get("changeRate") or 0) * 100
        scores = []
        signals = []

        df = get_klines(symbol)
        if df is None or len(df) < 24:
            return None

        # 1. Volume Spike
        vol_24h = df["volume"].iloc[-24:].sum()
        vol_7d_avg = df["volume"].sum() / 7
        vol_ratio = vol_24h / vol_7d_avg if vol_7d_avg > 0 else 1
        if vol_ratio > 3.0:
            scores.append(3); signals.append(f"Vol spike {vol_ratio:.1f}x 🔥🔥")
        elif vol_ratio > 2.0:
            scores.append(2); signals.append(f"Vol spike {vol_ratio:.1f}x 🔥")
        elif vol_ratio > 1.5:
            scores.append(1); signals.append(f"Vol naik {vol_ratio:.1f}x")
        else:
            scores.append(0); signals.append(f"Vol normal {vol_ratio:.1f}x")

        # 2. CVD Proxy
        df["delta"] = df.apply(lambda r: r["volume"] if r["close"] >= r["open"] else -r["volume"], axis=1)
        cvd = df["delta"].iloc[-24:].sum()
        vol_sum = df["volume"].iloc[-24:].sum()
        cvd_ratio = cvd / vol_sum if vol_sum > 0 else 0
        if cvd_ratio > 0.3:
            scores.append(2); signals.append(f"CVD +{cvd_ratio*100:.0f}% buy pressure 💚")
        elif cvd_ratio > 0.1:
            scores.append(1); signals.append(f"CVD +{cvd_ratio*100:.0f}% mild buy")
        elif cvd_ratio < -0.1:
            scores.append(-1); signals.append(f"CVD {cvd_ratio*100:.0f}% sell pressure")
        else:
            scores.append(0); signals.append(f"CVD {cvd_ratio*100:.0f}% netral")

        # 3. Price Momentum
        if len(df) >= 9:
            p0 = df["close"].iloc[-1]
            p4 = df["close"].iloc[-5]
            p8 = df["close"].iloc[-9]
            mom = (p0 - p4) / p4 * 100 if p4 > 0 else 0
            accel = mom - ((p4 - p8) / p8 * 100 if p8 > 0 else 0)
            if mom > 3 and accel > 1:
                scores.append(3); signals.append(f"Momentum +{mom:.1f}% accel +{accel:.1f}% 🚀")
            elif mom > 1.5:
                scores.append(2); signals.append(f"Momentum +{mom:.1f}% 📈")
            elif mom > 0:
                scores.append(1); signals.append(f"Momentum +{mom:.1f}%")
            else:
                scores.append(0); signals.append(f"Momentum {mom:.1f}%")

        # 4. Whale Trades
        threshold = WHALE_THRESHOLD.get(symbol, WHALE_THRESHOLD["DEFAULT"])
        trades = get_recent_trades(symbol)
        wb, ws, wbv, wsv = 0, 0, 0.0, 0.0
        for t in trades:
            val = float(t["price"]) * float(t["size"])
            if val >= threshold:
                if t["side"] == "buy": wb += 1; wbv += val
                else: ws += 1; wsv += val
        if wb + ws > 0:
            nr = (wbv - wsv) / (wbv + wsv)
            if nr > 0.5: scores.append(3); signals.append(f"Whale {wb}B/{ws}S — BUY dominan 🐋")
            elif nr > 0.2: scores.append(2); signals.append(f"Whale {wb}B/{ws}S — lebih banyak buy 🐋")
            elif nr < -0.2: scores.append(-1); signals.append(f"Whale {wb}B/{ws}S — lebih banyak sell")
            else: scores.append(0); signals.append(f"Whale {wb}B/{ws}S — seimbang")
        else:
            scores.append(0)

        # 5. Order Book Imbalance
        ob = get_orderbook(symbol)
        if ob:
            bv = sum(float(b[1]) * float(b[0]) for b in ob["bids"])
            av = sum(float(a[1]) * float(a[0]) for a in ob["asks"])
            imb = (bv - av) / (bv + av) if (bv + av) > 0 else 0
            if imb > 0.3: scores.append(2); signals.append(f"OB BID kuat {imb*100:.0f}% 📗")
            elif imb > 0.1: scores.append(1); signals.append(f"OB BID lebih besar {imb*100:.0f}%")
            elif imb < -0.1: scores.append(-1); signals.append(f"OB ASK lebih besar {abs(imb)*100:.0f}%")
            else: scores.append(0); signals.append(f"OB seimbang")

        total = sum(scores)
        max_s = sum(abs(s) for s in scores)
        prob = ((total / max_s) * 50 + 50) if max_s > 0 else 50

        return {
            "symbol": symbol.replace("-USDT", "USDT"),
            "price": price,
            "change_24h": change_24h,
            "total_score": total,
            "probability": max(0, min(100, prob)),
            "signals": signals,
        }
    except:
        return None

def run():
    now = datetime.now().strftime("%d %b %Y %H:%M")

    r = requests.get(f"{BASE_URL}/api/v1/market/allTickers", timeout=10)
    all_tickers = {t["symbol"]: t for t in r.json()["data"]["ticker"]}

    results = []
    for symbol in SCAN_PAIRS:
        ticker = all_tickers.get(symbol)
        if not ticker:
            continue
        res = analyze(symbol, ticker)
        if res and res["total_score"] > 0:
            results.append(res)
        time.sleep(0.25)

    # Top 5 potensi naik
    results.sort(key=lambda x: (x["total_score"], x["probability"]), reverse=True)
    top5 = results[:5]

    if not top5:
        send_telegram(
            f"🐋 <b>WHALE SCANNER</b> — {now} WIB\n\n"
            f"🔕 Tidak ada sinyal whale bullish saat ini."
        )
        return

    # Bangun 1 pesan gabungan
    sep = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    msg = f"🐋 <b>WHALE MOMENTUM SCANNER</b>\n"
    msg += f"🕐 {now} WIB  |  Top 5 Potensi Naik\n"
    msg += f"{sep}\n"

    for i, r in enumerate(top5):
        strength = "🔥🔥" if r["probability"] >= 75 else "🔥" if r["probability"] >= 60 else "✅"
        msg += f"\n{medals[i]} <b>{r['symbol']}</b>  {strength}  <code>{r['probability']:.0f}%</code>\n"
        msg += f"💰 {fmt(r['price'])}  <i>({r['change_24h']:+.1f}% 24H)</i>  · Skor <b>{r['total_score']:+d}</b>\n"
        for sig in r["signals"][:3]:
            msg += f"  › {sig}\n"

    msg += f"\n{sep}\n"
    msg += "⚠️ <i>Bukan saran keuangan. DYOR.</i>"

    send_telegram(msg)

if __name__ == "__main__":
    run()
