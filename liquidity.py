"""
ماژول تحلیل نقدینگی و جریان پول
Liquidity & Money Flow Analysis Module
- MFI (Money Flow Index)
- OBV (On Balance Volume)
- CMF (Chaikin Money Flow)
- تشخیص انباشت، شکست و خروج پول
"""
import pandas as pd
import numpy as np
import ta
from typing import Dict
import config


class LiquidityAnalyzer:
    """تحلیل نقدینگی، انباشت و خروج پول"""

    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or len(df) < 30:
            return df

        df = df.copy()

        # MFI - شاخص جریان پول (شامل حجم)
        df['mfi'] = ta.volume.MFIIndicator(
            df['high'], df['low'], df['close'], df['volume'], window=14
        ).money_flow_index()

        # OBV - حجم تعادل
        df['obv'] = ta.volume.OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
        df['obv_ma'] = df['obv'].rolling(window=20).mean()

        # CMF - جریان پول چایکین
        df['cmf'] = ta.volume.ChaikinMoneyFlowIndicator(
            df['high'], df['low'], df['close'], df['volume'], window=20
        ).chaikin_money_flow()

        # Volume Price Trend
        df['vpt'] = ta.volume.VolumePriceTrendIndicator(
            df['close'], df['volume']
        ).volume_price_trend()
        df['vpt_ma'] = df['vpt'].rolling(window=20).mean()

        # Accumulation/Distribution Line
        df['adl'] = ta.volume.AccDistIndexIndicator(
            df['high'], df['low'], df['close'], df['volume']
        ).acc_dist_index()
        df['adl_ma'] = df['adl'].rolling(window=20).mean()

        # Force Index
        df['force_index'] = ta.volume.ForceIndexIndicator(df['close'], df['volume'], window=13).force_index()

        # شناسایی انباشت/توزیع
        df['accumulation'] = (
            (df['close'] > df['close'].shift(1)) &
            (df['volume'] > df['volume_ma']) &
            (df['cmf'] > 0)
        )
        df['distribution'] = (
            (df['close'] < df['close'].shift(1)) &
            (df['volume'] > df['volume_ma']) &
            (df['cmf'] < 0)
        )

        return df

    # ----------------- تحلیل وضعیت نقدینگی -----------------
    @staticmethod
    def analyze(df: pd.DataFrame) -> Dict:
        """
        تحلیل وضعیت نقدینگی و جریان پول
        """
        if df is None or len(df) < 30:
            return {}

        last = df.iloc[-1]
        recent = df.tail(20)

        # وضعیت MFI
        mfi = float(last['mfi']) if not np.isnan(last['mfi']) else 50
        mfi_state = (
            'اشباع خرید' if mfi > 80 else
            'اشباع فروش' if mfi < 20 else
            'خنثی'
        )

        # روند OBV
        obv = float(last['obv']) if not np.isnan(last['obv']) else 0
        obv_ma = float(last['obv_ma']) if not np.isnan(last['obv_ma']) else 0
        obv_trend = 'صعودی' if obv > obv_ma else 'نزولی'

        # CMF
        cmf = float(last['cmf']) if not np.isnan(last['cmf']) else 0
        cmf_state = 'ورود پول' if cmf > 0.05 else 'خروج پول' if cmf < -0.05 else 'خنثی'

        # تشخیص فاز بازار
        accumulation_count = int(recent['accumulation'].sum())
        distribution_count = int(recent['distribution'].sum())

        if accumulation_count > distribution_count * 1.5 and accumulation_count >= 3:
            phase = 'انباشت (Accumulation)'
            phase_score = 2  # مثبت برای لانگ
        elif distribution_count > accumulation_count * 1.5 and distribution_count >= 3:
            phase = 'توزیع (Distribution)'
            phase_score = -2  # منفی برای شورت
        else:
            phase = 'خنثی'
            phase_score = 0

        # تشخیص شکست حجمی
        last_volume = float(last['volume'])
        avg_volume = float(recent['volume'].mean())
        volume_breakout = last_volume > avg_volume * 1.8
        volume_breakdown = last_volume > avg_volume * 1.5 and float(last['close']) < float(recent['close'].mean())

        return {
            'mfi': mfi,
            'mfi_state': mfi_state,
            'obv': obv,
            'obv_ma': obv_ma,
            'obv_trend': obv_trend,
            'cmf': cmf,
            'cmf_state': cmf_state,
            'phase': phase,
            'phase_score': phase_score,
            'accumulation_count': accumulation_count,
            'distribution_count': distribution_count,
            'volume_breakout': volume_breakout,
            'volume_breakdown': volume_breakdown,
            'last_volume': last_volume,
            'avg_volume': avg_volume,
            'volume_change_pct': ((last_volume - avg_volume) / avg_volume * 100) if avg_volume > 0 else 0,
        }

    # ----------------- تحلیل Order Book -----------------
    @staticmethod
    def analyze_order_book(order_book: Dict) -> Dict:
        """
        تحلیل Order Book برای سنجش فشار خرید/فروش و دیوارها
        """
        if order_book is None:
            return {}

        imbalance = order_book['imbalance']
        if imbalance > 0.15:
            pressure = 'فشار خرید قوی'
            pressure_score = 2
        elif imbalance > 0.05:
            pressure = 'فشار خرید ملایم'
            pressure_score = 1
        elif imbalance < -0.15:
            pressure = 'فشار فروش قوی'
            pressure_score = -2
        elif imbalance < -0.05:
            pressure = 'فشار فروش ملایم'
            pressure_score = -1
        else:
            pressure = 'متعادل'
            pressure_score = 0

        # نزدیک‌ترین دیوارهای خرید و فروش به قیمت فعلی
        best_bid = order_book['best_bid']
        best_ask = order_book['best_ask']
        mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0

        bid_walls = order_book['bid_walls']
        ask_walls = order_book['ask_walls']

        # نزدیک‌ترین دیوار خرید (حمایت) و فروش (مقاومت)
        nearest_bid_wall_price = float(bid_walls['price'].max()) if len(bid_walls) else best_bid
        nearest_ask_wall_price = float(ask_walls['price'].min()) if len(ask_walls) else best_ask

        return {
            'imbalance': imbalance,
            'pressure': pressure,
            'pressure_score': pressure_score,
            'bid_volume': float(order_book['bid_volume']),
            'ask_volume': float(order_book['ask_volume']),
            'spread': float(order_book['spread']),
            'spread_pct': (float(order_book['spread']) / mid_price * 100) if mid_price else 0,
            'nearest_bid_wall': nearest_bid_wall_price,
            'nearest_ask_wall': nearest_ask_wall_price,
            'bid_wall_distance_pct': ((mid_price - nearest_bid_wall_price) / mid_price * 100) if mid_price else 0,
            'ask_wall_distance_pct': ((nearest_ask_wall_price - mid_price) / mid_price * 100) if mid_price else 0,
        }
