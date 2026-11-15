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

        current_price = state_15m.get('close', 0)
        atr_15m = state_15m.get('atr', current_price * 0.02)
        atr_1h = state_1h.get('atr', current_price * 0.03)

        # ---------- نقطه ورود ----------
        # سه سناریو برای ورود لانگ
        nearest_support = sr_1h.get('nearest_support', current_price * 0.98)
        nearest_resistance = sr_1h.get('nearest_resistance', current_price * 1.02)

        # سناریو 1: ورود در قیمت فعلی (اگر روند صعودی تأیید شده)
        entry_now = current_price

        # سناریو 2: ورود در پولبک به حمایت
        entry_pullback = nearest_support * 1.005  # کمی بالاتر از حمایت

        # سناریو 3: ورود در شکست مقاومت
        entry_breakout = nearest_resistance * 1.005

        # انتخاب بهترین نقطه ورود
        # اگر قیمت نزدیک حمایت باشد → پولبک
        # اگر قیمت نزدیک شکست مقاومت باشد → شکست
        # در غیر این صورت → ورود فعلی
        dist_to_support = (current_price - nearest_support) / current_price * 100
        dist_to_resistance = (nearest_resistance - current_price) / current_price * 100

        if dist_to_support < 2:
            recommended_entry = entry_pullback
            entry_strategy = "ورود در پولبک به حمایت (نزدیک نقطه حمایت هستیم)"
        elif dist_to_resistance < 1.5:
            recommended_entry = entry_breakout
            entry_strategy = "ورود بعد از شکست مقاومت (نزدیک نقطه شکست هستیم)"
        else:
            recommended_entry = entry_now
            entry_strategy = "ورود در قیمت فعلی (تأیید روند صعودی)"

        # ---------- استاپ لاس ----------
        # روش 1: ATR-based
        atr_stop = recommended_entry - (atr_1h * config.ATR_STOP_MULTIPLIER)

        # روش 2: زیر حمایت نزدیک
        sr_stop = nearest_support * 0.995

        # روش 3: دیوار خرید Order Book (اگر موجود باشد)
        ob_stop = None
        if order_book and order_book.get('nearest_bid_wall', 0) > 0:
            ob_stop = order_book['nearest_bid_wall'] * 0.998

        # انتخاب بهترین استاپ لاس (بالاترین سطح زیر قیمت ورود)
        stops = [s for s in [atr_stop, sr_stop, ob_stop] if s is not None and s < recommended_entry]
        recommended_stop = max(stops) if stops else atr_stop

        # ---------- هدف سود ----------
        risk = recommended_entry - recommended_stop
        target_1 = recommended_entry + (risk * 1.5)   # RR 1:1.5
        target_2 = recommended_entry + (risk * 2.0)   # RR 1:2
        target_3 = recommended_entry + (risk * config.ATR_TARGET_MULTIPLIER)  # RR 1:3

        # فاصله‌ها به درصد
        stop_pct = (recommended_entry - recommended_stop) / recommended_entry * 100
        target_2_pct = (target_2 - recommended_entry) / recommended_entry * 100
        rr = (target_2 - recommended_entry) / risk if risk > 0 else 0

        return {
            'direction': 'LONG',
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

        current_price = state_15m.get('close', 0)
        atr_15m = state_15m.get('atr', current_price * 0.02)
        atr_1h = state_1h.get('atr', current_price * 0.03)

        # ---------- نقطه ورود ----------
        nearest_support = sr_1h.get('nearest_support', current_price * 0.98)
        nearest_resistance = sr_1h.get('nearest_resistance', current_price * 1.02)

        entry_now = current_price
        entry_pullback = nearest_resistance * 0.995  # کمی پایین‌تر از مقاومت
        entry_breakdown = nearest_support * 0.995    # کمی پایین‌تر از شکست حمایت

        dist_to_support = (current_price - nearest_support) / current_price * 100
        dist_to_resistance = (nearest_resistance - current_price) / current_price * 100

        if dist_to_resistance < 2:
            recommended_entry = entry_pullback
            entry_strategy = "ورود در پولبک به مقاومت (نزدیک نقطه مقاومت هستیم)"
        elif dist_to_support < 1.5:
            recommended_entry = entry_breakdown
            entry_strategy = "ورود بعد از شکست حمایت (نزدیک نقطه شکست هستیم)"
        else:
            recommended_entry = entry_now
            entry_strategy = "ورود در قیمت فعلی (تأیید روند نزولی)"

        # ---------- استاپ لاس ----------
        atr_stop = recommended_entry + (atr_1h * config.ATR_STOP_MULTIPLIER)
        sr_stop = nearest_resistance * 1.005

        ob_stop = None
        if order_book and order_book.get('nearest_ask_wall', 0) > 0:
            ob_stop = order_book['nearest_ask_wall'] * 1.002

        stops = [s for s in [atr_stop, sr_stop, ob_stop] if s is not None and s > recommended_entry]
        recommended_stop = min(stops) if stops else atr_stop

        # ---------- هدف سود ----------
        risk = recommended_stop - recommended_entry
        target_1 = recommended_entry - (risk * 1.5)
        target_2 = recommended_entry - (risk * 2.0)
        target_3 = recommended_entry - (risk * config.ATR_TARGET_MULTIPLIER)

        stop_pct = (recommended_stop - recommended_entry) / recommended_entry * 100
        target_2_pct = (recommended_entry - target_2) / recommended_entry * 100
        rr = (recommended_entry - target_2) / risk if risk > 0 else 0

        return {
            'direction': 'SHORT',
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
