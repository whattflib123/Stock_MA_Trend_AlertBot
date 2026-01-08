import yfinance as yf
import pandas as pd
import requests

# ========= Telegram 設定 =========
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

# ========= 股票清單 =========
STOCK_LIST = ["ASML", "COST", "AMZN", "MSFT", "AMD", "AAPL", "GOOGL", "META"]

NEAR_PERCENT = 0.01  # 1%

# ========= EMA 週期設定（使用者可修改） =========
EMA_LONG = 576
EMA_MEDIUM = 169

# ========= Telegram 傳訊 =========
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, data=payload)
        if r.status_code != 200:
            print(f"Telegram 推送失敗: {r.text}")
    except Exception as e:
        print(f"Telegram 推送例外: {e}")

# ========= 趨勢 emoji =========
def trend_emoji(latest):
    sma50 = to_float(latest["SMA50"])
    sma200 = to_float(latest["SMA200"])

    if sma50 < sma200:
        return "🔴"
    elif sma50 > sma200:
        return "🟢"
    else:
        return ""

# ========= 技術指標 =========
def add_indicators(df):
    df[f"EMA{EMA_LONG}"] = df["Close"].ewm(span=EMA_LONG).mean()
    df[f"EMA{EMA_MEDIUM}"] = df["Close"].ewm(span=EMA_MEDIUM).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    return df

def to_float(v):
    if isinstance(v, pd.Series):
        return float(v.iloc[0])
    return float(v)

def near_info(price, ma_value):
    price = to_float(price)
    ma_value = to_float(ma_value)
    diff_pct = (price - ma_value) / ma_value
    return diff_pct, abs(diff_pct) <= NEAR_PERCENT

# ========= 主邏輯（合併傳訊） =========
def detect_and_notify(stock_list):

    group_ema_long = []
    group_sma200 = []
    group_ema_medium = []

    for symbol in stock_list:
        try:
            df = yf.download(symbol, period="3y", interval="1d", progress=False)

            if df.empty:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = add_indicators(df)
            latest = df.iloc[-1]
            price = latest["Close"]

            emoji = trend_emoji(latest)

            # 條件 1：EMA長期（最高優先）
            diff, ok = near_info(price, latest[f"EMA{EMA_LONG}"])
            if ok:
                group_ema_long.append(
                    f"{emoji}{symbol} 限價 {price:.2f} 距離 {diff*100:.2f}%"
                )
                continue

            # 條件 2：SMA200
            diff, ok = near_info(price, latest["SMA200"])
            if ok:
                group_sma200.append(
                    f"{emoji}{symbol} 限價 {price:.2f} 距離 {diff*100:.2f}%"
                )
                continue

            # 條件 3：EMA中期
            diff, ok = near_info(price, latest[f"EMA{EMA_MEDIUM}"])
            if ok:
                group_ema_medium.append(
                    f"{emoji}{symbol} 限價 {price:.2f} 距離 {diff*100:.2f}%"
                )

        except Exception as e:
            print(f"{symbol} 錯誤：{e}")

    # ========= 統一送 Telegram =========
    if group_ema_long:
        msg = f"接近EMA{EMA_LONG}\n" + "\n".join(group_ema_long)
        send_telegram_message(msg)
        print(msg)

    if group_sma200:
        msg = "接近SMA200\n" + "\n".join(group_sma200)
        send_telegram_message(msg)
        print(msg)

    if group_ema_medium:
        msg = f"接近EMA{EMA_MEDIUM}\n" + "\n".join(group_ema_medium)
        send_telegram_message(msg)
        print(msg)

# ========= 執行 =========
if __name__ == "__main__":
    detect_and_notify(STOCK_LIST)
