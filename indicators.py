"""
ماژول محاسبه اندیکاتورهای تکنیکال
Technical Indicators Module
- RSI, EMA, MACD, ATR, Bollinger Bands
- Volume MA, ADX (قدرت روند)
"""
import pandas as pd
import numpy as np
import ta
from typing import Dict
import config


class Indicators:
    """محاسبه همه اندیکاتورهای تکنیکال روی یک DataFrame"""

    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        """افزودن همه اندیکاتورها به DataFrame"""
        if df is None or len(df) < 50:
            return df

        df = df.copy()

        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=config.RSI_PERIOD).rsi()

        # EMA ها
        df['ema_fast'] = ta.trend.EMAIndicator(df['close'], window=config.EMA_FAST).ema_indicator()
        df['ema_slow'] = ta.trend.EMAIndicator(df['close'], window=config.EMA_SLOW).ema_indicator()
        df['ema_trend'] = ta.trend.EMAIndicator(df['close'], window=config.EMA_TREND).ema_indicator()

        # MACD
        macd = ta.trend.MACD(
            df['close'],
            window_slow=config.MACD_SLOW,
            window_fast=config.MACD_FAST,
            window_sign=config.MACD_SIGNAL
        )
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()

        # ATR (نوسانات برای استاپ لاس)
        df['atr'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=config.ATR_PERIOD
        ).average_true_range()

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

        # Volume MA
        df['volume_ma'] = df['volume'].rolling(window=config.VOLUME_MA_PERIOD).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        # ADX (قدرت روند)
        df['adx'] = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()

        # Stochastic
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=14, smooth_window=3)
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()

        # روند صعودی/نزولی
        df['trend_bullish'] = (df['ema_fast'] > df['ema_slow']) & (df['close'] > df['ema_trend'])
        df['trend_bearish'] = (df['ema_fast'] < df['ema_slow']) & (df['close'] < df['ema_trend'])

        # روند مومنتوم (RSI + MACD) - حتی اگر EMA خنثی باشد
        # اگر RSI < 35 و MACD منفی → روند نزولی مومنتوم
        df['momentum_bearish'] = (df['rsi'] < 35) & (df['macd_diff'] < 0)
        # اگر RSI > 65 و MACD مثبت → روند صعودی مومنتوم
        df['momentum_bullish'] = (df['rsi'] > 65) & (df['macd_diff'] > 0)

        # روند ترکیبی: EMA یا مومنتوم
        df['trend_bullish'] = df['trend_bullish'] | df['momentum_bullish']
        df['trend_bearish'] = df['trend_bearish'] | df['momentum_bearish']

        return df

    # ----------------- خلاصه وضعیت فعلی -----------------
    @staticmethod
    def get_current_state(df: pd.DataFrame) -> Dict:
        """استخراج وضعیت فعلی از آخرین کندل"""
        if df is None or len(df) < 50:
            return {}

        last = df.iloc[-1]
        prev = df.iloc[-2]

        state = {
            'close': float(last['close']),
            'rsi': float(last['rsi']) if not np.isnan(last['rsi']) else 50,
            'ema_fast': float(last['ema_fast']) if not np.isnan(last['ema_fast']) else 0,
            'ema_slow': float(last['ema_slow']) if not np.isnan(last['ema_slow']) else 0,
            'ema_trend': float(last['ema_trend']) if not np.isnan(last['ema_trend']) else 0,
            'macd': float(last['macd']) if not np.isnan(last['macd']) else 0,
            'macd_signal': float(last['macd_signal']) if not np.isnan(last['macd_signal']) else 0,
            'macd_diff': float(last['macd_diff']) if not np.isnan(last['macd_diff']) else 0,
            'atr': float(last['atr']) if not np.isnan(last['atr']) else 0,
            'adx': float(last['adx']) if not np.isnan(last['adx']) else 0,
            'volume_ratio': float(last['volume_ratio']) if not np.isnan(last['volume_ratio']) else 1,
            'bb_width': float(last['bb_width']) if not np.isnan(last['bb_width']) else 0,
            'stoch_k': float(last['stoch_k']) if not np.isnan(last['stoch_k']) else 50,
            'trend_bullish': bool(last['trend_bullish']),
            'trend_bearish': bool(last['trend_bearish']),
            # تقاطع EMA
            'ema_cross_up': bool(prev['ema_fast'] <= prev['ema_slow'] and last['ema_fast'] > last['ema_slow']),
            'ema_cross_down': bool(prev['ema_fast'] >= prev['ema_slow'] and last['ema_fast'] < last['ema_slow']),
            # تقاطع MACD
            'macd_cross_up': bool(prev['macd_diff'] < 0 and last['macd_diff'] > 0),
            'macd_cross_down': bool(prev['macd_diff'] > 0 and last['macd_diff'] < 0),
        }

        # تعیین جهت روند
        if state['trend_bullish']:
            state['trend_dir'] = 'صعودی'
        elif state['trend_bearish']:
            state['trend_dir'] = 'نزولی'
        else:
            state['trend_dir'] = 'رنج/خنثی'

        # قدرت روند
        if state['adx'] > 25:
            state['trend_strength'] = 'قوی'
        elif state['adx'] > 20:
            state['trend_strength'] = 'متوسط'
        else:
            state['trend_strength'] = 'ضعیف'

        return state

    # ----------------- سطوح حمایت و مقاومت -----------------
    @staticmethod
    def find_support_resistance(df: pd.DataFrame, lookback: int = 50) -> Dict:
        """
        یافتن سطوح حمایت و مقاومت بر اساس Swing High/Low
        """
        if df is None or len(df) < lookback:
            return {}

        recent = df.tail(lookback)
        highs = recent['high'].values
        lows = recent['low'].values
        current = recent['close'].iloc[-1]

        # پیدا کردن Swing Points
        resistance_levels = []
        support_levels = []
        window = 5

        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i - window:i + window + 1]):
                resistance_levels.append(highs[i])
            if lows[i] == min(lows[i - window:i + window + 1]):
                support_levels.append(lows[i])

        # نزدیک‌ترین حمایت و مقاومت به قیمت فعلی
        nearest_resistance = min([r for r in resistance_levels if r > current], default=current * 1.05)
        nearest_support = max([s for s in support_levels if s < current], default=current * 0.95)

        return {
            'nearest_support': float(nearest_support),
            'nearest_resistance': float(nearest_resistance),
            'all_supports': support_levels[-5:],
            'all_resistances': resistance_levels[-5:],
        }
