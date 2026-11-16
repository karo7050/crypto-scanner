"""
ماژول تحلیل Volume Flow - جریان ورود/خروج پول
Volume Flow / Inflow-Outflow Analyzer Module

این ماژول جریان خالص پول (Net Money Flow) را محاسبه می‌کند -
شبیه به چیزی که Cryptometer.io در بخش Volume Flow نمایش می‌دهد.

روش محاسبه (رایگان، از داده OHLCV موجود):
- برای هر کندل، حجم خرید و فروش را بر اساس موقعیت قیمت تخمین می‌زنیم
- buy_volume = volume * (close - low) / (high - low)
- sell_volume = volume - buy_volume
- جریان خالص = buy_volume - sell_volume (به USD)

همچنین شامل:
- Cumulative Volume Delta (CVD) 
- شتاب جریان پول (Flow Momentum)
- درصد خرید به فروش (Buy/Sell Ratio)
"""
import pandas as pd
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class VolumeFlowAnalyzer:
    """تحلیل جریان ورود/خروج پول - رایگان از داده OHLCV"""

    @staticmethod
    def compute_flow(df: pd.DataFrame, current_price: float = None) -> Dict:
        """
        محاسبه جریان پول برای یک DataFrame OHLCV
        """
        if df is None or len(df) < 20:
            return {}

        df = df.copy()

        # محاسبه حجم خرید و فروش برای هر کندل
        # روش: buy_volume = volume * (close - low) / (high - low)
        # این روش استاندارد Chaikin Money Flow است
        high = df['high']
        low = df['low']
        close = df['close']
        volume = df['volume']

        # جلوگیری از تقسیم بر صفر
        range_hl = (high - low).replace(0, np.nan)

        # نسبت خرید (0 تا 1)
        buy_ratio = ((close - low) / range_hl).fillna(0.5)
        buy_ratio = buy_ratio.clip(0, 1)  # محدود به 0-1

        # حجم خرید و فروش
        df['buy_volume'] = volume * buy_ratio
        df['sell_volume'] = volume * (1 - buy_ratio)

        # محاسبه برای بازه‌های مختلف
        # 24 ساعت (کندل‌های 1h)
        last_24 = df.tail(24) if len(df) >= 24 else df
        # 4 ساعت
        last_4 = df.tail(4) if len(df) >= 4 else df
        # 1 ساعت اخیر
        last_1 = df.tail(1)

        # محاسبه به USD (ضرب در قیمت close)
        def calc_flow(data):
            buy_vol = data['buy_volume'].sum()
            sell_vol = data['sell_volume'].sum()
            avg_price = data['close'].mean()
            buy_usd = buy_vol * avg_price
            sell_usd = sell_vol * avg_price
            net_usd = buy_usd - sell_usd
            total_usd = buy_usd + sell_usd
            buy_pct = (buy_usd / total_usd * 100) if total_usd > 0 else 50
            return {
                'buy_volume': float(buy_vol),
                'sell_volume': float(sell_vol),
                'buy_usd': float(buy_usd),
                'sell_usd': float(sell_usd),
                'net_flow_usd': float(net_usd),
                'total_volume_usd': float(total_usd),
                'buy_pct': float(buy_pct),
                'sell_pct': float(100 - buy_pct),
                'buy_sell_ratio': float(buy_usd / sell_usd) if sell_usd > 0 else 1.0,
            }

        flow_24h = calc_flow(last_24)
        flow_4h = calc_flow(last_4)
        flow_1h = calc_flow(last_1)

        # CVD (Cumulative Volume Delta) - مجموع خالص حجم
        cvd_24h = float(last_24['buy_volume'].sum() - last_24['sell_volume'].sum())
        cvd_4h = float(last_4['buy_volume'].sum() - last_4['sell_volume'].sum())

        # شتاب جریان (مقایسه 4h اخیر با 4h قبلی)
        if len(df) >= 8:
            prev_4 = df.iloc[-8:-4]
            current_net = last_4['buy_volume'].sum() - last_4['sell_volume'].sum()
            prev_net = prev_4['buy_volume'].sum() - prev_4['sell_volume'].sum()
            if prev_net != 0:
                flow_momentum = ((current_net - prev_net) / abs(prev_net)) * 100
            else:
                flow_momentum = 0
        else:
            flow_momentum = 0

        # تعیین جهت جریان
        net_24h = flow_24h['net_flow_usd']
        if net_24h > 0:
            direction = 'ورود پول (Inflow)'
            direction_en = 'INFLOW'
        elif net_24h < 0:
            direction = 'خروج پول (Outflow)'
            direction_en = 'OUTFLOW'
        else:
            direction = 'متعادل'
            direction_en = 'NEUTRAL'

        # شدت جریان
        total_24h = flow_24h['total_volume_usd']
        if total_24h > 0:
            flow_intensity = abs(net_24h) / total_24h * 100
        else:
            flow_intensity = 0

        # امتیاز جهت (برای لانگ/شورت)
        # ورود پول قوی = امتیاز لانگ
        # خروج پول قوی = امتیاز شورت
        if flow_intensity > 15:
            if net_24h > 0:
                flow_score = 2  # ورود قوی → لانگ
                flow_signal = 'ورود قوی پول - تایید لانگ'
            else:
                flow_score = -2  # خروج قوی → شورت
                flow_signal = 'خروج قوی پول - تایید شورت'
        elif flow_intensity > 5:
            if net_24h > 0:
                flow_score = 1
                flow_signal = 'ورود ملایم پول'
            else:
                flow_score = -1
                flow_signal = 'خروج ملایم پول'
        else:
            flow_score = 0
            flow_signal = 'جریان متعادل'

        return {
            'flow_24h': flow_24h,
            'flow_4h': flow_4h,
            'flow_1h': flow_1h,
            'cvd_24h': cvd_24h,
            'cvd_4h': cvd_4h,
            'flow_momentum': float(flow_momentum),
            'direction': direction,
            'direction_en': direction_en,
            'flow_intensity': float(flow_intensity),
            'flow_score': flow_score,
            'flow_signal': flow_signal,
            'net_flow_24h_usd': net_24h,
            'buy_pct_24h': flow_24h['buy_pct'],
            'buy_sell_ratio_24h': flow_24h['buy_sell_ratio'],
        }

    @staticmethod
    def format_flow_summary(flow_data: Dict) -> str:
        """فرمت‌بندی خلاصه جریان برای نمایش"""
        if not flow_data:
            return 'داده جریان موجود نیست'

        direction = flow_data.get('direction', '')
        net = flow_data.get('net_flow_24h_usd', 0)
        buy_pct = flow_data.get('buy_pct_24h', 50)
        signal = flow_data.get('flow_signal', '')
        momentum = flow_data.get('flow_momentum', 0)

        # فرمت USD
        if abs(net) >= 1_000_000_000:
            net_str = f"${net/1e9:.2f}B"
        elif abs(net) >= 1_000_000:
            net_str = f"${net/1e6:.1f}M"
        elif abs(net) >= 1_000:
            net_str = f"${net/1e3:.1f}K"
        else:
            net_str = f"${net:.0f}"

        momentum_str = f"{'+' if momentum > 0 else ''}{momentum:.1f}%"

        return f"{direction} | خالص: {net_str} | خرید: {buy_pct:.1f}% | شتاب: {momentum_str} | {signal}"
