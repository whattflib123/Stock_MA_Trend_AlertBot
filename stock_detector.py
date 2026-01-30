import os
import yfinance as yf
import pandas as pd
import requests
import tempfile
from pathlib import Path

import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib import transforms

# ========= Telegram 設定 =========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or ""
CHAT_ID = os.getenv("CHAT_ID") or ""



# ========= 股票清單 =========
STOCK_LIST = ["ASML", "COST", "AMZN", "MSFT", "AMD", "AAPL", "GOOGL", "META"]

NEAR_PERCENT = 0.01  # 1%

# ========= EMA 週期設定（使用者可修改） =========
EMA_LONG = 576
EMA_MEDIUM = 169
EMA_LONG_LOWER = 676
EMA_SHORT = 144

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

def send_telegram_photo(photo_path, caption=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "caption": caption or "",
        "parse_mode": "Markdown"
    }
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            r = requests.post(url, data=payload, files=files)
        if r.status_code != 200:
            print(f"Telegram 圖片推送失敗: {r.text}")
    except Exception as e:
        print(f"Telegram 圖片推送例外: {e}")

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
    df[f"EMA{EMA_LONG_LOWER}"] = df["Close"].ewm(span=EMA_LONG_LOWER).mean()
    df[f"EMA{EMA_SHORT}"] = df["Close"].ewm(span=EMA_SHORT).mean()
    df["SMA10"] = df["Close"].rolling(10).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    return df

def plot_last_1y_chart(df, symbol):
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = add_indicators(df)

    df.index = pd.to_datetime(df.index)
    end_date = df.index.max()
    start_date = end_date - pd.DateOffset(years=1)
    df = df.loc[df.index >= start_date]
    if df.empty:
        return None

    add_plots = []
    ema576 = df.get(f"EMA{EMA_LONG}")
    ema676 = df.get(f"EMA{EMA_LONG_LOWER}")
    ema144 = df.get(f"EMA{EMA_SHORT}")
    ema169 = df.get(f"EMA{EMA_MEDIUM}")
    sma10 = df.get("SMA10")
    sma50 = df.get("SMA50")
    sma200 = df.get("SMA200")

    if ema576 is not None and ema576.notna().any():
        add_plots.append(mpf.make_addplot(ema576, color="#00F5FF", linewidths=0.01))
    if ema676 is not None and ema676.notna().any():
        add_plots.append(mpf.make_addplot(ema676, color="#00F5FF", linewidths=0.01))
    if ema144 is not None and ema144.notna().any():
        add_plots.append(mpf.make_addplot(ema144, color="gold", linewidths=0.01))
    if ema169 is not None and ema169.notna().any():
        add_plots.append(mpf.make_addplot(ema169, color="gold", linewidths=0.01))
    if sma10 is not None and sma10.notna().any():
        add_plots.append(mpf.make_addplot(sma10, color="white", linewidths=0.01))
    if sma50 is not None and sma50.notna().any():
        add_plots.append(mpf.make_addplot(sma50, color="#00A3FF", linewidths=0.01))
    if sma200 is not None and sma200.notna().any():
        add_plots.append(mpf.make_addplot(sma200, color="#39ff14", linewidths=0.01))

    hi = float(df["High"].max())
    lo = float(df["Low"].min())
    hi_dt = df["High"].idxmax()
    lo_dt = df["Low"].idxmin()
    last_close = float(df["Close"].iloc[-1])
    mc = mpf.make_marketcolors(
        up="#26A69A",
        down="#EF5350",
        edge="inherit",
        wick="inherit",
        volume="inherit",
    )
    style = mpf.make_mpf_style(
        base_mpf_style="nightclouds",
        marketcolors=mc,
        rc={
            "axes.grid": False,
            "grid.alpha": 0.0,
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#cbd5e1",
            "xtick.color": "#cbd5e1",
            "ytick.color": "#cbd5e1",
        },
    )

    tmp_dir = Path(tempfile.gettempdir())
    price_path = tmp_dir / f"{symbol}_1y.png"

    fig, axlist = mpf.plot(
        df,
        type="candle",
        style=style,
        addplot=add_plots if add_plots else None,
        alines=dict(
            alines=[
                [(hi_dt, hi), (df.index[-1], hi)],
                [(lo_dt, lo), (df.index[-1], lo)],
            ],
            colors=["#8ecae6", "#8ecae6"],
            linestyle="-",
            linewidths=1,
        ),
        hlines=dict(
            hlines=[last_close],
            colors=["#cbd5e1"],
            linestyle="--",
            linewidths=0.8,
        ),
        title=f"{symbol} - Last 1 Year",
        ylabel="Price",
        volume=False,
        returnfig=True,
    )
    for ax in axlist:
        ax.grid(False, which="both")
    price_ax = axlist[0]
    label_transform = transforms.blended_transform_factory(
        price_ax.transAxes, price_ax.transData
    )

    def annotate_line(label, series, color):
        if series is None or not series.notna().any():
            return
        last_val = series.dropna().iloc[-1]
        price_ax.text(
            1.01,
            last_val,
            f"{label} ",
            color="white",
            fontsize=8,
            ha="left",
            va="center",
            transform=label_transform,
            clip_on=False,
        )
        value_transform = label_transform + transforms.ScaledTranslation(36 / 72, 0, fig.dpi_scale_trans)
        price_ax.text(
            1.01,
            last_val,
            f"{last_val:.2f}",
            color=color,
            fontsize=8,
            ha="left",
            va="center",
            transform=value_transform,
            clip_on=False,
        )

    annotate_line("EMA576", ema576, "#00F5FF")
    annotate_line("SMA10", sma10, "white")
    annotate_line("SMA50", sma50, "#2529FF")
    annotate_line("SMA200", sma200, "#39ff14")
    price_ax.text(
        1.01,
        hi,
        f"HIGH {hi:.2f}",
        color="#8ecae6",
        fontsize=8,
        ha="left",
        va="center",
        transform=label_transform,
        clip_on=False,
    )
    price_ax.text(
        1.01,
        lo,
        f"LOW {lo:.2f}",
        color="#8ecae6",
        fontsize=8,
        ha="left",
        va="center",
        transform=label_transform,
        clip_on=False,
    )
    price_ax.text(
        -0.02,
        last_close,
        f" {last_close:.2f}",
        color="#cbd5e1",
        fontsize=8,
        ha="right",
        va="center",
        transform=label_transform,
        clip_on=False,
    )
    fig.savefig(price_path, dpi=150, pad_inches=0.25)
    plt.close(fig)

    return price_path

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
    notified_symbols = []

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
                notified_symbols.append(symbol)
                continue

            # 條件 2：SMA200
            diff, ok = near_info(price, latest["SMA200"])
            if ok:
                group_sma200.append(
                    f"{emoji}{symbol} 限價 {price:.2f} 距離 {diff*100:.2f}%"
                )
                notified_symbols.append(symbol)
                continue

            # 條件 3：EMA中期
            diff, ok = near_info(price, latest[f"EMA{EMA_MEDIUM}"])
            if ok:
                group_ema_medium.append(
                    f"{emoji}{symbol} 限價 {price:.2f} 距離 {diff*100:.2f}%"
                )
                notified_symbols.append(symbol)

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

    # ========= 傳送 4 個月日 K 圖 =========
    for symbol in dict.fromkeys(notified_symbols):
        try:
            df_chart = yf.download(symbol, period="3y", interval="1d", progress=False)
            if df_chart.empty:
                continue
            chart_path = plot_last_1y_chart(df_chart, symbol)
            if chart_path:
                send_telegram_photo(chart_path, caption=f"{symbol} 近 1 年日 K（含均線）")
        except Exception as e:
            print(f"{symbol} 圖表生成/推送錯誤：{e}")

# ========= 執行 =========
if __name__ == "__main__":
    detect_and_notify(STOCK_LIST)