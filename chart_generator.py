"""
ماژول تولید نمودار تحلیلی
Chart Generator - Visual Analysis

تولید تصویر نمودار با:
- کندل‌ها یا خط قیمت
- EMA 20/50/200
- سطوح حمایت/مقاومت (Swing)
- نقطه ورود، استاپ، تارگت
- Order Block (SMC)
- RSI در پایین
- حجم معاملات

استفاده از matplotlib (رایگان)
"""
import os
import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional
import matplotlib
matplotlib.use('Agg')  # بدون GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import config

logger = logging.getLogger(__name__)

# تنظیمات فونت
plt.rcParams['font.size'] = 9
plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.bbox'] = 'tight'


class ChartGenerator:
    """تولید نمودار تحلیلی برای هر ارز"""

    @staticmethod
    def generate_chart(coin: Dict, decision, df_1h: pd.DataFrame = None,
                       df_4h: pd.DataFrame = None, coinalyze_data: Dict = None) -> Optional[str]:
        """
        تولید تصویر نمودار تحلیلی

        برمی‌گرداند: مسیر فایل PNG یا None
        """
        if df_1h is None or len(df_1h) < 30:
            return None

        base = coin.get('base', 'UNKNOWN')
        direction = decision.decision.value if hasattr(decision, 'decision') else 'WAIT'
        entry = decision.entry_price if hasattr(decision, 'entry_price') else 0
        stop = decision.stop_loss if hasattr(decision, 'stop_loss') else 0
        tp1 = decision.target_1 if hasattr(decision, 'target_1') else 0
        tp2 = decision.target_2 if hasattr(decision, 'target_2') else 0
        tp3 = decision.target_3 if hasattr(decision, 'target_3') else 0
        confidence = decision.confidence if hasattr(decision, 'confidence') else 0

        # رنگ بر اساس جهت
        if direction == 'LONG':
            color_main = '#00ff88'
            color_stop = '#ff4444'
            color_target = '#00aaff'
            bg_color = '#0a0a0a'
        elif direction == 'SHORT':
            color_main = '#ff4477'
            color_stop = '#ff4444'
            color_target = '#00aaff'
            bg_color = '#0a0a0a'
        else:
            color_main = '#888888'
            color_stop = '#888888'
            color_target = '#888888'
            bg_color = '#0a0a0a'

        # آخرین 50 کندل
        df = df_1h.tail(50).copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        opens = df['open'].values
        volumes = df['volume'].values
        dates = df.index

        # EMA
        if 'ema_fast' in df.columns:
            ema20 = df['ema_fast'].tail(50).values
            ema50 = df['ema_slow'].tail(50).values
        else:
            ema20 = pd.Series(closes).rolling(20).mean().values
            ema50 = pd.Series(closes).rolling(50).mean().values

        # RSI
        if 'rsi' in df.columns:
            rsi = df['rsi'].tail(50).values
        else:
            rsi = np.full(50, 50)

        # ساخت figure
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, gridspec_kw={'height_ratios': [3, 1, 1]},
                                            figsize=(12, 8), facecolor=bg_color)

        # ===== پنل 1: قیمت + EMA + سطوح =====
        ax1.set_facecolor(bg_color)

        # کندل‌ها به‌صورت خط + shadow
        for i in range(len(dates)):
            ax1.vlines(dates[i], lows[i], highs[i], color='#444444', linewidth=0.5)
            if closes[i] >= opens[i]:
                ax1.plot(dates[i], closes[i], 'o', color=color_main, markersize=2)
            else:
                ax1.plot(dates[i], closes[i], 'o', color='#ff4444', markersize=2)

        # خط قیمت
        ax1.plot(dates, closes, color=color_main, linewidth=1.5, label='Price')

        # EMA
        if not np.all(np.isnan(ema20)):
            ax1.plot(dates, ema20, color='#ffaa00', linewidth=1, label='EMA20', alpha=0.7)
        if not np.all(np.isnan(ema50)):
            ax1.plot(dates, ema50, color='#aa00ff', linewidth=1, label='EMA50', alpha=0.7)

        # خطوط Entry/Stop/Target
        current_price = closes[-1]
        if entry > 0:
            ax1.axhline(y=entry, color='#00ff00', linewidth=1.5, linestyle='--', label=f'Entry: {entry:.6g}', alpha=0.8)
        if stop > 0:
            ax1.axhline(y=stop, color=color_stop, linewidth=1.5, linestyle='--', label=f'Stop: {stop:.6g}', alpha=0.8)
            # منطقه استاپ ( shaded)
            ax1.axhspan(stop, entry if direction == 'LONG' else entry,
                       alpha=0.1, color=color_stop)
        if tp1 > 0:
            ax1.axhline(y=tp1, color=color_target, linewidth=1, linestyle=':', label=f'TP1: {tp1:.6g}', alpha=0.6)
        if tp2 > 0:
            ax1.axhline(y=tp2, color=color_target, linewidth=1.2, linestyle=':', label=f'TP2: {tp2:.6g}', alpha=0.7)
        if tp3 > 0:
            ax1.axhline(y=tp3, color=color_target, linewidth=1, linestyle=':', label=f'TP3: {tp3:.6g}', alpha=0.5)

        # عنوان
        title = f"{base}/USDT | {direction} | Confidence: {confidence:.0%}"
        if hasattr(decision, 'signal_strength'):
            title += f" | {decision.signal_strength}"
        ax1.set_title(title, color='white', fontsize=12, fontweight='bold')

        # Coinalyze data در عنوان
        if coinalyze_data and coinalyze_data.get('available'):
            ls = coinalyze_data.get('long_ratio', 0)
            ss = coinalyze_data.get('short_ratio', 0)
            oi_chg = coinalyze_data.get('oi_change_pct', 0)
            fr = coinalyze_data.get('funding_rate', 0)
            ax1.text(0.02, 0.95, f"L/S: {ls:.0f}/{ss:.0f} | OI: {oi_chg:+.1f}% | FR: {fr*100:.4f}%",
                    transform=ax1.transAxes, color='#00aaff', fontsize=8, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='#222', alpha=0.8))

        ax1.legend(loc='upper right', fontsize=7, facecolor='#222', labelcolor='white')
        ax1.tick_params(colors='#888888')
        ax1.spines['bottom'].set_color('#333')
        ax1.spines['top'].set_color('#333')
        ax1.spines['left'].set_color('#333')
        ax1.spines['right'].set_color('#333')

        # ===== پنل 2: RSI =====
        ax2.set_facecolor(bg_color)
        ax2.plot(dates, rsi, color='#ffaa00', linewidth=1.5)
        ax2.axhline(y=70, color='#ff4444', linewidth=0.5, linestyle='--', alpha=0.5)
        ax2.axhline(y=30, color='#00ff88', linewidth=0.5, linestyle='--', alpha=0.5)
        ax2.axhline(y=50, color='#888888', linewidth=0.3, linestyle='-', alpha=0.3)
        ax2.fill_between(dates, 70, 100, alpha=0.1, color='#ff4444')
        ax2.fill_between(dates, 0, 30, alpha=0.1, color='#00ff88')
        ax2.set_ylim(0, 100)
        ax2.set_ylabel('RSI', color='white', fontsize=8)
        last_rsi = rsi[-1] if not np.isnan(rsi[-1]) else 50
        rsi_color = '#ff4444' if last_rsi > 70 else '#00ff88' if last_rsi < 30 else '#ffaa00'
        ax2.text(0.98, 0.9, f'RSI: {last_rsi:.0f}', transform=ax2.transAxes,
                color=rsi_color, fontsize=9, fontweight='bold', ha='right',
                bbox=dict(boxstyle='round', facecolor='#222', alpha=0.8))
        ax2.tick_params(colors='#888888')
        for spine in ax2.spines.values():
            spine.set_color('#333')

        # ===== پنل 3: Volume =====
        ax3.set_facecolor(bg_color)
        colors_vol = ['#00ff88' if closes[i] >= opens[i] else '#ff4444' for i in range(len(dates))]
        ax3.bar(dates, volumes, color=colors_vol, alpha=0.6, width=0.8)
        # میانگین حجم
        vol_ma = pd.Series(volumes).rolling(20).mean().values
        ax3.plot(dates, vol_ma, color='#ffaa00', linewidth=1, label='Vol MA20')
        ax3.set_ylabel('Volume', color='white', fontsize=8)
        ax3.legend(loc='upper right', fontsize=7, facecolor='#222', labelcolor='white')
        ax3.tick_params(colors='#888888')
        for spine in ax3.spines.values():
            spine.set_color('#333')

        # تاریخ
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right', color='#888888')

        # دلایل در پایین
        if hasattr(decision, 'reasons_pro') and decision.reasons_pro:
            reasons_text = " | ".join(decision.reasons_pro[:3])
            fig.text(0.5, 0.01, reasons_text[:120], ha='center', color='#00aaff', fontsize=7,
                    bbox=dict(boxstyle='round', facecolor='#222', alpha=0.8))

        # ذخیره
        filepath = os.path.join(config.OUTPUT_DIR, f'chart_{base}_{config.tehran_now().strftime("%Y%m%d_%H%M")}.png')
        plt.savefig(filepath, facecolor=bg_color, dpi=150)
        plt.close()

        logger.info(f"  📊 نمودار {base} تولید شد: {filepath}")
        return filepath
