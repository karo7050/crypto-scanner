"""
ماژول محاسبه نقطه ورود، استاپ لاس و هدف سود
Entry & Exit Calculation Module
- نقطه ورود بهینه (بر اساس حمایت/مقاومت و قیمت فعلی)
- استاپ لاس بر اساس ATR و سطح حمایت
- هدف سود (Risk/Reward = 1:2)
- نسبت ریسک به ریوارد
"""
import numpy as np
from typing import Dict
import config


class EntryExitCalculator:
    """محاسبه نقطه ورود، استاپ لاس و هدف سود"""

    @staticmethod
    def calculate_long_setup(analysis: Dict, order_book: Dict = None) -> Dict:
        """
        محاسبه نقطه ورود و استاپ لاس برای پوزیشن LONG
        استراتژی: ورود نزدیک حمایت یا بعد از تأیید شکست
        """
        tf_15m = analysis.get('15m', {})
        tf_1h = analysis.get('1h', {})

        if not tf_15m or not tf_1h:
            return {}

        state_15m = tf_15m.get('state', {})
        state_1h = tf_1h.get('state', {})
        sr_1h = tf_1h.get('sr', {})

        # برای Swing: استفاده از داده‌های 4h و روزانه
        tf_4h = analysis.get('4h', {})
        tf_1d = analysis.get('1d', {})
        state_4h = tf_4h.get('state', {}) if tf_4h else {}
        state_1d = tf_1d.get('state', {}) if tf_1d else {}
        sr_4h = tf_4h.get('sr', {}) if tf_4h else {}
        sr_1d = tf_1d.get('sr', {}) if tf_1d else {}

        current_price = state_15m.get('close', 0)
        atr_15m = state_15m.get('atr', current_price * 0.02)
        atr_1h = state_1h.get('atr', current_price * 0.03)
        # Swing: ATR 4h (وسیع‌تر برای استاپ‌های Swing)
        atr_4h = state_4h.get('atr', atr_1h * 1.5) if state_4h else atr_1h * 1.5
        atr_1d = state_1d.get('atr', atr_4h * 1.5) if state_1d else atr_4h * 1.5

        # ---------- نقطه ورود ----------
        # Swing: استفاده از سطوح 4h و روزانه برای حمایت/مقاومت
        if config.SWING_USE_DAILY_LEVELS and sr_1d:
            nearest_support = sr_1d.get('nearest_support', sr_4h.get('nearest_support', current_price * 0.95))
            nearest_resistance = sr_1d.get('nearest_resistance', sr_4h.get('nearest_resistance', current_price * 1.05))
        elif sr_4h:
            nearest_support = sr_4h.get('nearest_support', sr_1h.get('nearest_support', current_price * 0.97))
            nearest_resistance = sr_4h.get('nearest_resistance', sr_1h.get('nearest_resistance', current_price * 1.03))
        else:
            nearest_support = sr_1h.get('nearest_support', current_price * 0.98)
            nearest_resistance = sr_1h.get('nearest_resistance', current_price * 1.02)

        # سناریو 1: ورود در قیمت فعلی (اگر روند صعودی تأیید شده)
        entry_now = current_price

        # سناریو 2: ورود در پولبک به حمایت (Swing - پولبک عمیق‌تر)
        entry_pullback = nearest_support * 1.01  # کمی بالاتر از حمایت روزانه/4h

        # سناریو 3: ورود در شکست مقاومت
        entry_breakout = nearest_resistance * 1.005

        # انتخاب بهترین نقطه ورود (Swing: تلورانس بیشتر برای پولبک)
        dist_to_support = (current_price - nearest_support) / current_price * 100
        dist_to_resistance = (nearest_resistance - current_price) / current_price * 100

        if dist_to_support < 5:  # Swing: پولبک تا 5% از قیمت فعلی
            recommended_entry = entry_pullback
            entry_strategy = "Swing: ورود در پولبک به حمایت ساختاری (4h/روزانه)"
        elif dist_to_resistance < 2:
            recommended_entry = entry_breakout
            entry_strategy = "Swing: ورود بعد از شکست مقاومت ساختاری"
        else:
            recommended_entry = entry_now
            entry_strategy = "Swing: ورود در قیمت فعلی (تأیید روند صعودی 4h)"

        # ---------- استاپ لاس (Swing) ----------
        # Swing: استفاده از ATR 4h (وسیع‌تر) به جای 1h
        atr_for_stop = atr_4h if config.SWING_USE_4H_ATR else atr_1h

        # روش 1: ATR-based (Swing - وسیع‌تر)
        atr_stop = recommended_entry - (atr_for_stop * config.ATR_STOP_MULTIPLIER)

        # روش 2: زیر حمایت ساختاری (Swing - با حاشیه بیشتر)
        sr_stop = nearest_support * 0.99  # 1% زیر حمایت (Swing)

        # روش 3: دیوار خرید Order Book (اگر موجود باشد)
        ob_stop = None
        if order_book and order_book.get('nearest_bid_wall', 0) > 0:
            ob_stop = order_book['nearest_bid_wall'] * 0.998

        # انتخاب بهترین استاپ لاس (بالاترین سطح زیر قیمت ورود)
        stops = [s for s in [atr_stop, sr_stop, ob_stop] if s is not None and s < recommended_entry]
        recommended_stop = max(stops) if stops else atr_stop

        # ---------- هدف سود (Swing) ----------
        # Swing: اهداف بزرگ‌تر برای حرکت‌های قوی‌تر
        risk = recommended_entry - recommended_stop
        target_1 = recommended_entry + (risk * 2.0)   # Swing: RR 1:2 (حداقل)
        target_2 = recommended_entry + (risk * 3.0)   # Swing: RR 1:3 (اصلی)
        target_3 = recommended_entry + (risk * config.ATR_TARGET_MULTIPLIER)  # Swing: RR 1:5 (حداکثر)

        # فاصله‌ها به درصد
        stop_pct = (recommended_entry - recommended_stop) / recommended_entry * 100
        target_2_pct = (target_2 - recommended_entry) / recommended_entry * 100
        rr = (target_2 - recommended_entry) / risk if risk > 0 else 0

        return {
            'direction': 'LONG',
            'style': 'Swing',
            'current_price': round(current_price, 6),
            'entry_price': round(recommended_entry, 6),
            'entry_strategy': entry_strategy,
            'stop_loss': round(recommended_stop, 6),
            'stop_pct': round(stop_pct, 2),
            'target_1': round(target_1, 6),
            'target_2': round(target_2, 6),
            'target_3': round(target_3, 6),
            'target_2_pct': round(target_2_pct, 2),
            'risk_reward': round(rr, 2),
            'atr_15m': round(atr_15m, 6),
            'atr_1h': round(atr_1h, 6),
            'atr_4h': round(atr_4h, 6),
            'atr_1d': round(atr_1d, 6),
            'nearest_support': round(nearest_support, 6),
            'nearest_resistance': round(nearest_resistance, 6),
            'alt_entries': {
                'pullback': round(entry_pullback, 6),
                'breakout': round(entry_breakout, 6),
                'current': round(entry_now, 6),
            },
            'alt_stops': {
                'atr_based': round(atr_stop, 6),
                'support_based': round(sr_stop, 6),
                'order_book_based': round(ob_stop, 6) if ob_stop else None,
            },
        }

    # ----------------- محاسبه SETUP شورت -----------------
    @staticmethod
    def calculate_short_setup(analysis: Dict, order_book: Dict = None) -> Dict:
        """
        محاسبه نقطه ورود و استاپ لاس برای پوزیشن SHORT
        استراتژی: ورود نزدیک مقاومت یا بعد از تأیید شکست نزولی
        """
        tf_15m = analysis.get('15m', {})
        tf_1h = analysis.get('1h', {})

        if not tf_15m or not tf_1h:
            return {}

        state_15m = tf_15m.get('state', {})
        state_1h = tf_1h.get('state', {})
        sr_1h = tf_1h.get('sr', {})

        # برای Swing: استفاده از داده‌های 4h و روزانه
        tf_4h = analysis.get('4h', {})
        tf_1d = analysis.get('1d', {})
        state_4h = tf_4h.get('state', {}) if tf_4h else {}
        state_1d = tf_1d.get('state', {}) if tf_1d else {}
        sr_4h = tf_4h.get('sr', {}) if tf_4h else {}
        sr_1d = tf_1d.get('sr', {}) if tf_1d else {}

        current_price = state_15m.get('close', 0)
        atr_15m = state_15m.get('atr', current_price * 0.02)
        atr_1h = state_1h.get('atr', current_price * 0.03)
        # Swing: ATR 4h (وسیع‌تر)
        atr_4h = state_4h.get('atr', atr_1h * 1.5) if state_4h else atr_1h * 1.5
        atr_1d = state_1d.get('atr', atr_4h * 1.5) if state_1d else atr_4h * 1.5

        # ---------- نقطه ورود (Swing) ----------
        if config.SWING_USE_DAILY_LEVELS and sr_1d:
            nearest_support = sr_1d.get('nearest_support', sr_4h.get('nearest_support', current_price * 0.95))
            nearest_resistance = sr_1d.get('nearest_resistance', sr_4h.get('nearest_resistance', current_price * 1.05))
        elif sr_4h:
            nearest_support = sr_4h.get('nearest_support', sr_1h.get('nearest_support', current_price * 0.97))
            nearest_resistance = sr_4h.get('nearest_resistance', sr_1h.get('nearest_resistance', current_price * 1.03))
        else:
            nearest_support = sr_1h.get('nearest_support', current_price * 0.98)
            nearest_resistance = sr_1h.get('nearest_resistance', current_price * 1.02)

        entry_now = current_price
        entry_pullback = nearest_resistance * 0.99  # Swing: کمی پایین‌تر از مقاومت ساختاری
        entry_breakdown = nearest_support * 0.99    # Swing: شکست حمایت ساختاری

        dist_to_support = (current_price - nearest_support) / current_price * 100
        dist_to_resistance = (nearest_resistance - current_price) / current_price * 100

        if dist_to_resistance < 5:  # Swing: پولبک تا 5%
            recommended_entry = entry_pullback
            entry_strategy = "Swing: ورود در پولبک به مقاومت ساختاری (4h/روزانه)"
        elif dist_to_support < 2:
            recommended_entry = entry_breakdown
            entry_strategy = "Swing: ورود بعد از شکست حمایت ساختاری"
        else:
            recommended_entry = entry_now
            entry_strategy = "Swing: ورود در قیمت فعلی (تأیید روند نزولی 4h)"

        # ---------- استاپ لاس (Swing) ----------
        atr_for_stop = atr_4h if config.SWING_USE_4H_ATR else atr_1h
        atr_stop = recommended_entry + (atr_for_stop * config.ATR_STOP_MULTIPLIER)
        sr_stop = nearest_resistance * 1.01  # Swing: 1% بالای مقاومت

        ob_stop = None
        if order_book and order_book.get('nearest_ask_wall', 0) > 0:
            ob_stop = order_book['nearest_ask_wall'] * 1.002

        stops = [s for s in [atr_stop, sr_stop, ob_stop] if s is not None and s > recommended_entry]
        recommended_stop = min(stops) if stops else atr_stop

        # ---------- هدف سود (Swing) ----------
        risk = recommended_stop - recommended_entry
        target_1 = recommended_entry - (risk * 2.0)   # Swing: RR 1:2
        target_2 = recommended_entry - (risk * 3.0)   # Swing: RR 1:3
        target_3 = recommended_entry - (risk * config.ATR_TARGET_MULTIPLIER)  # Swing: RR 1:5

        stop_pct = (recommended_stop - recommended_entry) / recommended_entry * 100
        target_2_pct = (recommended_entry - target_2) / recommended_entry * 100
        rr = (recommended_entry - target_2) / risk if risk > 0 else 0

        return {
            'direction': 'SHORT',
            'style': 'Swing',
            'current_price': round(current_price, 6),
            'entry_price': round(recommended_entry, 6),
            'entry_strategy': entry_strategy,
            'stop_loss': round(recommended_stop, 6),
            'stop_pct': round(stop_pct, 2),
            'target_1': round(target_1, 6),
            'target_2': round(target_2, 6),
            'target_3': round(target_3, 6),
            'target_2_pct': round(target_2_pct, 2),
            'risk_reward': round(rr, 2),
            'atr_15m': round(atr_15m, 6),
            'atr_1h': round(atr_1h, 6),
            'atr_4h': round(atr_4h, 6),
            'atr_1d': round(atr_1d, 6),
            'nearest_support': round(nearest_support, 6),
            'nearest_resistance': round(nearest_resistance, 6),
            'alt_entries': {
                'pullback': round(entry_pullback, 6),
                'breakdown': round(entry_breakdown, 6),
                'current': round(entry_now, 6),
            },
            'alt_stops': {
                'atr_based': round(atr_stop, 6),
                'resistance_based': round(sr_stop, 6),
                'order_book_based': round(ob_stop, 6) if ob_stop else None,
            },
        }
