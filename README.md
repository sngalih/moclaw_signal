# 🔔 Moclaw Signal — Crypto Signal & Whale Scanner

Bot sinyal trading crypto otomatis berbasis **KuCoin API** + **Telegram**.

---

## 📦 Isi Repository

| File | Deskripsi |
|------|-----------|
| `crypto_signal_telegram.py` | Sinyal teknikal spot (RSI, MACD, EMA, BB, Stoch) → Telegram |
| `whale_scanner.py` | Whale Momentum Scanner (Volume Spike, CVD, Order Book, Whale Trades) → Telegram |
| `crypto_signal.py` | Versi CLI tanpa Telegram (untuk testing) |

---

## ⚙️ Cara Pakai

### 1. Install dependencies
```bash
pip install pandas numpy requests ta
```

### 2. Edit konfigurasi Telegram
Di `crypto_signal_telegram.py` dan `whale_scanner.py`, ubah:
```python
TELEGRAM_TOKEN = "ISI_TOKEN_BOT_KAMU"
CHAT_ID        = "ISI_CHAT_ID_KAMU"
```

### 3. Jalankan manual
```bash
# Sinyal teknikal
python3 crypto_signal_telegram.py

# Whale scanner
python3 whale_scanner.py
```

### 4. Jalankan otomatis (cron)
```bash
# Sinyal teknikal tiap 4 jam
0 */4 * * * cd /path/to/repo && python3 crypto_signal_telegram.py

# Whale scanner tiap 1 jam
0 * * * * cd /path/to/repo && python3 whale_scanner.py
```

---

## 📊 Strategi

### Crypto Signal (Teknikal)
Menggunakan 6 indikator:
- **RSI** — Deteksi oversold/overbought
- **MACD** — Momentum & crossover
- **EMA 20/50** — Trend direction
- **Bollinger Bands** — Volatilitas & support/resistance
- **Volume** — Konfirmasi pergerakan
- **Stochastic** — Konfirmasi entry

Filter: hanya pair dengan probabilitas > 50%

### Whale Momentum Scanner
5 layer deteksi aktivitas whale:
- **Volume Spike** — Bandingkan volume 24H vs rata-rata 7 hari
- **CVD Proxy** — Net buy/sell pressure dari candle data
- **Price Momentum** — Kecepatan & akselerasi harga
- **Whale Trades** — Transaksi tunggal besar (BTC >$50K, dll)
- **Order Book Imbalance** — Tekanan BID vs ASK real-time

Output: Top 5 pair potensi naik, dikirim dalam 1 pesan gabungan

---

## ⚠️ Disclaimer
Ini bukan saran keuangan. Selalu lakukan riset sendiri (DYOR) dan gunakan manajemen risiko yang baik.
