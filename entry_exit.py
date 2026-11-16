"""
ماژول محاسبه نقطه ورود، استاپ لاس و هدف سود (Swing)
Entry & Exit Calculator - Swing Style v2

معماری:
- روند از 1d و 4h (جهت بازار)
- ساختار از 1h (سطوح حمایت/مقاومت)
- ورود از 15m (نقطه دقیق)

ویژگی‌ها:
- پرهیز از ورود نزدیک دیوار فروش (برای لانگ) یا دیوار خرید (برای شورت)
- هر استاپ لاس دلیل مشخص دارد
- هر تی‌پی دلیل مشخص دارد
- Swing highs/lows از چند تایم فریم
"""
import numpy as np
from typing import Dict, List
import config


class EntryExitCalculator:
    """محاسبه Swing Setup با دلایل کامل"""

    # ============ تشخیص swing points از DataFrame ============
    @staticmethod
    def _find_swing_levels(df, lookback=50, window=3):
        """
        یافتن swing highs و lows
        window: تعداد کندل‌های هر طرف برای تایید swing
        """
        if df is None or len(df) < lookback:
            return {'highs': [], 'lows': []}

        recent = df.tail(lookback)
        highs_data = recent['high'].values
        lows_data = recent['low'].values
        closes = recent['close'].values
        timestamps = recent.index

        swing_highs = []
        swing_lows = []

        for i in range(window, len(highs_data) - window):
            # Swing High: این کندل بالاترین در پنجره است
            if highs_data[i] == max(highs_data[i - window:i + window + 1]):
                swing_highs.append({
                    'price': float(highs_data[i]),
                    'index': i,
                    'time': str(timestamps[i]),
                    'candles_ago': len(highs_data) - i,
                })
            # Swing Low
            if lows_data[i] == min(lows_data[i - window:i + window + 1]):
                swing_lows.append({
                    'price': float(lows_data[i]),
                    'index': i,
                    'time': str(timestamps[i]),
                    'candles_ago': len(lows_data) - i,
                })

        return {'highs': swing_highs, 'lows': swing_lows}

    # ============ تشخیص نزدیکی به دیوار ============
    @staticmethod
    def _check_wall_proximity(current_price, order_book, is_long=True):
        """
        بررسی نزدیکی قیمت به دیوار خرید/فروش
        برمی‌گرداند: نزدیک است؟ کدام دیوار؟ فاصله چند درصد؟
        """
        if not order_book:
            return {'near_wall': False}

        bid_walls = order_book.get('bid_walls', [])
        ask_walls = order_book.get('ask_walls', [])

        # برای لانگ: نگران دیوار فروش (resistance) در بالا هستیم
        # برای شورت: نگران دیوار خرید (support) در پایین هستیم

        nearest_ask_wall = float(ask_walls['price'].min()) if len(ask_walls) else None
        nearest_bid_wall = float(bid_walls['price'].max()) if len(bid_walls) else None

        result = {'near_wall': False, 'wall_type': '', 'wall_price': 0, 'wall_distance_pct': 0}

        if is_long and nearest_ask_wall:
            dist = (nearest_ask_wall - current_price) / current_price * 100
            if 0 < dist < 1.5:  # دیوار فروش در فاصله کمتر از 1.5%
                result = {
                    'near_wall': True,
                    'wall_type': 'sell_wall_above',
                    'wall_price': nearest_ask_wall,
                    'wall_distance_pct': dist,
                    'advice': f'نزدیک دیوار فروش ({dist:.1f}% بالاتر) - ورود بعد از شکست دیوار توصیه می‌شود'
                }
        elif not is_long and nearest_bid_wall:
            dist = (current_price - nearest_bid_wall) / current_price * 100
            if 0 < dist < 1.5:
                result = {
                    'near_wall': True,
                    'wall_type': 'buy_wall_below',
                    'wall_price': nearest_bid_wall,
                    'wall_distance_pct': dist,
                    'advice': f'نزدیک دیوار خرید ({dist:.1f}% پایین‌تر) - ورود بعد از شکست دیوار توصیه می‌شود'
                }

        return result

    # ============ محاسبه SETUP لانگ ============
    @staticmethod
    def calculate_long_setup(analysis: Dict, order_book: Dict = None) -> Dict:
        """
        Swing Long Setup:
        - روند از 1d/4h
        - سطوح از 1h/4h
        - ورود از 15m
        - پرهیز از دیوار فروش
        - هر استاپ و تی‌پی دلیل دارد
        """
        tf_15m = analysis.get('15m', {})
        tf_1h = analysis.get('1h', {})
        tf_4h = analysis.get('4h', {})
        tf_1d = analysis.get('1d', {})

        if not tf_15m or not tf_1h:
            return {}

        state_15m = tf_15m.get('state', {})
        state_1h = tf_1h.get('state', {})
        state_4h = tf_4h.get('state', {}) if tf_4h else {}
        state_1d = tf_1d.get('state', {}) if tf_1d else {}

        current_price = state_15m.get('close', 0)
        atr_1h = state_1h.get('atr', current_price * 0.03)
        atr_4h = state_4h.get('atr', atr_1h * 1.5) if state_4h else atr_1h * 1.5
        atr_1d = state_1d.get('atr', atr_4h * 1.5) if state_1d else atr_4h * 1.5

        # ============ یافتن سطوح از چند تایم فریم ============
        df_1h = tf_1h.get('dataframe')
        df_4h = tf_4h.get('dataframe') if tf_4h else None
        df_1d = tf_1d.get('dataframe') if tf_1d else None

        # Swing levels از 1h (50 کندل اخیر)
        swings_1h = EntryExitCalculator._find_swing_levels(df_1h, lookback=50, window=3)
        # Swing levels از 4h (30 کندل اخیر)
        swings_4h = EntryExitCalculator._find_swing_levels(df_4h, lookback=30, window=3) if df_4h is not None else {'highs': [], 'lows': []}
        # Swing levels از روزانه (20 کندل اخیر)
        swings_1d = EntryExitCalculator._find_swing_levels(df_1d, lookback=20, window=3) if df_1d is not None else {'highs': [], 'lows': []}

        # حمایت‌ها و مقاومت‌ها
        all_lows = [s['price'] for s in swings_1h['lows']] + [s['price'] for s in swings_4h['lows']] + [s['price'] for s in swings_1d['lows']]
        all_highs = [s['price'] for s in swings_1h['highs']] + [s['price'] for s in swings_4h['highs']] + [s['price'] for s in swings_1d['highs']]

        # نزدیک‌ترین حمایت (زیر قیمت فعلی)
        supports_below = sorted([s for s in all_lows if s < current_price and s > current_price * 0.85], reverse=True)
        nearest_support = supports_below[0] if supports_below else current_price * 0.95

        # نزدیک‌ترین مقاومت (بالای قیمت فعلی)
        resistances_above = sorted([r for r in all_highs if r > current_price and r < current_price * 1.15])
        nearest_resistance = resistances_above[0] if resistances_above else current_price * 1.05

        # ============ بررسی نزدیکی به دیوار فروش ============
        wall_check = EntryExitCalculator._check_wall_proximity(current_price, order_book, is_long=True)

        # ============ تعیین نقطه ورود ============
        entry_reasons = []
        dist_to_resistance = (nearest_resistance - current_price) / current_price * 100
        dist_to_support = (current_price - nearest_support) / current_price * 100

        if wall_check.get('near_wall') and wall_check['wall_type'] == 'sell_wall_above':
            # نزدیک دیوار فروش → ورود بعد از شکست دیوار
            recommended_entry = wall_check['wall_price'] * 1.003  # کمی بالاتر از دیوار شکسته شده
            entry_strategy = f"ورود بعد از شکست دیوار فروش ({wall_check['wall_distance_pct']:.1f}% بالاتر)"
            entry_reasons.append(f"دیوار فروش قوی در {wall_check['wall_price']:.6f} شناسایی شد")
            entry_reasons.append(f"ورود بعد از شکست دیوار برای جلوگیری از استاپ زدن")
        elif dist_to_resistance < 1.0:
            # نزدیک مقاومت → ورود بعد از شکست
            recommended_entry = nearest_resistance * 1.003
            entry_strategy = "ورود بعد از شکست مقاومت نزدیک"
            entry_reasons.append(f"نزدیک مقاومت swing در {nearest_resistance:.6f} هستیم")
            entry_reasons.append("ورود بعد از شکست مقاومت برای تایید روند صعودی")
        elif dist_to_support < 3.0:
            # نزدیک حمایت → ورود در پولبک
            recommended_entry = nearest_support * 1.005
            entry_strategy = "ورود در پولبک به حمایت"
            entry_reasons.append(f"نزدیک حمایت swing در {nearest_support:.6f} هستیم")
            entry_reasons.append("ورود در پولبک به حمایت با ریسک کم")
        else:
            # ورود در قیمت فعلی
            recommended_entry = current_price
            entry_strategy = "ورود در قیمت فعلی (تایید روند صعودی)"
            entry_reasons.append("قیمت در فاصله مناسب از حمایت و مقاومت است")
            entry_reasons.append(f"حمایت در {dist_to_support:.1f}% پایین‌تر، مقاومت در {dist_to_resistance:.1f}% بالاتر")

        # ============ محاسبه استاپ لاس با دلیل ============
        stop_options = []

        # گزینه 1: زیر حمایت swing
        if nearest_support < recommended_entry:
            atr_buffer = atr_1h * 0.3  # 30% ATR زیر حمایت
            stop_at_support = nearest_support - atr_buffer
            if stop_at_support < recommended_entry:
                # پیدا کردن کندل swing
                swing_info = None
                for s in swings_1h['lows']:
                    if abs(s['price'] - nearest_support) / nearest_support < 0.001:
                        swing_info = s
                        break
                tf_label = '1h'
                if not swing_info:
                    for s in swings_4h['lows']:
                        if abs(s['price'] - nearest_support) / nearest_support < 0.001:
                            swing_info = s
                            tf_label = '4h'
                            break
                if not swing_info:
                    for s in swings_1d['lows']:
                        if abs(s['price'] - nearest_support) / nearest_support < 0.001:
                            swing_info = s
                            tf_label = 'روزانه'
                            break

                reason = f"زیر حمایت swing ({tf_label}) در {nearest_support:.6f}"
                if swing_info:
                    reason += f" از {swing_info['candles_ago']} کندل قبل"
                reason += f" + بافر {atr_buffer:.6f} (0.3x ATR 1h)"
                stop_options.append({
                    'price': stop_at_support,
                    'reason': reason,
                    'type': 'support_based',
                })

        # گزینه 2: ATR-based (2.5x ATR 4h)
        atr_stop = recommended_entry - (atr_4h * config.ATR_STOP_MULTIPLIER)
        stop_options.append({
            'price': atr_stop,
            'reason': f"{config.ATR_STOP_MULTIPLIER}x ATR(4h) زیر قیمت ورود = نوسانات 4 ساعته",
            'type': 'atr_based',
        })

        # گزینه 3: دیوار خرید Order Book
        if order_book:
            bid_walls = order_book.get('bid_walls', [])
            if len(bid_walls):
                wall_price = float(bid_walls['price'].max())
                if wall_price < recommended_entry:
                    stop_options.append({
                        'price': wall_price * 0.998,
                        'reason': f"پشت دیوار خرید Order Book در {wall_price:.6f} (حمایت نقدینگی)",
                        'type': 'order_book_wall',
                    })

        # انتخاب بهترین استاپ: بالاترین سطح زیر ورود (محافظه‌کارانه‌ترین)
        valid_stops = [s for s in stop_options if s['price'] < recommended_entry]
        if valid_stops:
            recommended_stop_data = max(valid_stops, key=lambda x: x['price'])
            recommended_stop = recommended_stop_data['price']
            stop_reason = recommended_stop_data['reason']
        else:
            recommended_stop = atr_stop
            stop_reason = stop_options[1]['reason'] if len(stop_options) > 1 else "ATR-based"

        # ============ محاسبه تی‌پی‌ها با دلیل ============
        risk = recommended_entry - recommended_stop
        targets = []

        # تی‌پی 1: نزدیک‌ترین مقاومت یا RR 1:2 (کدام زودتر)
        tp1_by_rr = recommended_entry + (risk * 2.0)
        tp1_reason = ""
        if nearest_resistance > recommended_entry and nearest_resistance < tp1_by_rr:
            # مقاومت قبل از RR 1:2 است
            tp1_price = nearest_resistance * 0.995  # کمی قبل از مقاومت
            tp1_reason = f"نزدیک مقاومت swing در {nearest_resistance:.6f}"
            # پیدا کردن اطلاعات swing
            for s in swings_1h['highs'] + swings_4h['highs'] + swings_1d['highs']:
                if abs(s['price'] - nearest_resistance) / nearest_resistance < 0.001:
                    tp1_reason += f" (از {s['candles_ago']} کندل قبل)"
                    break
        else:
            tp1_price = tp1_by_rr
            tp1_reason = f"RR 1:2 (دو برابر ریسک) = {risk:.6f} سود"

        targets.append({'price': tp1_price, 'reason': tp1_reason, 'rr': 2.0})

        # تی‌پی 2: RR 1:3 یا مقاومت بعدی
        tp2_by_rr = recommended_entry + (risk * 3.0)
        # مقاومت بعدی
        next_resistances = [r for r in resistances_above if r > tp1_price]
        if next_resistances and next_resistances[0] < tp2_by_rr:
            tp2_price = next_resistances[0] * 0.995
            tp2_reason = f"مقاومت بعدی swing در {next_resistances[0]:.6f}"
        else:
            tp2_price = tp2_by_rr
            tp2_reason = f"RR 1:3 (سه برابر ریسک) - هدف اصلی Swing"
        targets.append({'price': tp2_price, 'reason': tp2_reason, 'rr': 3.0})

        # تی‌پی 3: RR 1:5 یا مقاومت بالاتر
        tp3_by_rr = recommended_entry + (risk * config.ATR_TARGET_MULTIPLIER)
        if len(next_resistances) > 1 and next_resistances[1] < tp3_by_rr:
            tp3_price = next_resistances[1] * 0.995
            tp3_reason = f"مقاومت بالاتر swing در {next_resistances[1]:.6f}"
        else:
            tp3_price = tp3_by_rr
            tp3_reason = f"RR 1:{config.ATR_TARGET_MULTIPLIER:.0f} - هدف حداکثری Swing"
        targets.append({'price': tp3_price, 'reason': tp3_reason, 'rr': config.ATR_TARGET_MULTIPLIER})

        # ============ فاصله‌ها ============
        stop_pct = (recommended_entry - recommended_stop) / recommended_entry * 100
        tp2_pct = (tp2_price - recommended_entry) / recommended_entry * 100
        rr = (tp2_price - recommended_entry) / risk if risk > 0 else 0

        return {
            'direction': 'LONG',
            'style': 'Swing',
            'current_price': round(current_price, 6),
            'entry_price': round(recommended_entry, 6),
            'entry_strategy': entry_strategy,
            'entry_reasons': entry_reasons,
            'stop_loss': round(recommended_stop, 6),
            'stop_pct': round(stop_pct, 2),
            'stop_reason': stop_reason,
            'stop_options': [{'price': round(s['price'], 6), 'reason': s['reason'], 'type': s['type']} for s in stop_options],
            'target_1': round(tp1_price, 6),
            'target_1_reason': tp1_reason,
            'target_2': round(tp2_price, 6),
            'target_2_reason': tp2_reason,
            'target_3': round(tp3_price, 6),
            'target_3_reason': tp3_reason,
            'targets': [{'price': round(t['price'], 6), 'reason': t['reason'], 'rr': t['rr']} for t in targets],
            'target_2_pct': round(tp2_pct, 2),
            'risk_reward': round(rr, 2),
            'atr_1h': round(atr_1h, 6),
            'atr_4h': round(atr_4h, 6),
            'atr_1d': round(atr_1d, 6),
            'nearest_support': round(nearest_support, 6),
            'nearest_resistance': round(nearest_resistance, 6),
            'support_distance_pct': round(dist_to_support, 2),
            'resistance_distance_pct': round(dist_to_resistance, 2),
            'wall_check': wall_check,
        }

    # ============ محاسبه SETUP شورت ============
    @staticmethod
    def calculate_short_setup(analysis: Dict, order_book: Dict = None) -> Dict:
        """
        Swing Short Setup:
        - روند از 1d/4h
        - سطوح از 1h/4h
        - ورود از 15m
        - پرهیز از دیوار خرید
        - هر استاپ و تی‌پی دلیل دارد
        """
        tf_15m = analysis.get('15m', {})
        tf_1h = analysis.get('1h', {})
        tf_4h = analysis.get('4h', {})
        tf_1d = analysis.get('1d', {})

        if not tf_15m or not tf_1h:
            return {}

        state_15m = tf_15m.get('state', {})
        state_1h = tf_1h.get('state', {})
        state_4h = tf_4h.get('state', {}) if tf_4h else {}
        state_1d = tf_1d.get('state', {}) if tf_1d else {}

        current_price = state_15m.get('close', 0)
        atr_1h = state_1h.get('atr', current_price * 0.03)
        atr_4h = state_4h.get('atr', atr_1h * 1.5) if state_4h else atr_1h * 1.5
        atr_1d = state_1d.get('atr', atr_4h * 1.5) if state_1d else atr_4h * 1.5

        # ============ یافتن سطوح ============
        df_1h = tf_1h.get('dataframe')
        df_4h = tf_4h.get('dataframe') if tf_4h else None
        df_1d = tf_1d.get('dataframe') if tf_1d else None

        swings_1h = EntryExitCalculator._find_swing_levels(df_1h, lookback=50, window=3)
        swings_4h = EntryExitCalculator._find_swing_levels(df_4h, lookback=30, window=3) if df_4h is not None else {'highs': [], 'lows': []}
        swings_1d = EntryExitCalculator._find_swing_levels(df_1d, lookback=20, window=3) if df_1d is not None else {'highs': [], 'lows': []}

        all_lows = [s['price'] for s in swings_1h['lows']] + [s['price'] for s in swings_4h['lows']] + [s['price'] for s in swings_1d['lows']]
        all_highs = [s['price'] for s in swings_1h['highs']] + [s['price'] for s in swings_4h['highs']] + [s['price'] for s in swings_1d['highs']]

        # برای شورت: حمایت زیر قیمت (هدف)، مقاومت بالای قیمت (استاپ)
        supports_below = sorted([s for s in all_lows if s < current_price and s > current_price * 0.85], reverse=True)
        nearest_support = supports_below[0] if supports_below else current_price * 0.95

        resistances_above = sorted([r for r in all_highs if r > current_price and r < current_price * 1.15])
        nearest_resistance = resistances_above[0] if resistances_above else current_price * 1.05

        # ============ بررسی نزدیکی به دیوار خرید ============
        wall_check = EntryExitCalculator._check_wall_proximity(current_price, order_book, is_long=False)

        # ============ تعیین نقطه ورود ============
        entry_reasons = []
        dist_to_resistance = (nearest_resistance - current_price) / current_price * 100
        dist_to_support = (current_price - nearest_support) / current_price * 100

        if wall_check.get('near_wall') and wall_check['wall_type'] == 'buy_wall_below':
            # نزدیک دیوار خرید → ورود بعد از شکست دیوار (شکست نزولی)
            recommended_entry = wall_check['wall_price'] * 0.997
            entry_strategy = f"ورود بعد از شکست دیوار خرید ({wall_check['wall_distance_pct']:.1f}% پایین‌تر)"
            entry_reasons.append(f"دیوار خرید قوی در {wall_check['wall_price']:.6f} شناسایی شد")
            entry_reasons.append(f"ورود بعد از شکست دیوار برای جلوگیری از استاپ زدن")
        elif dist_to_support < 1.0:
            # نزدیک حمایت → ورود بعد از شکست حمایت
            recommended_entry = nearest_support * 0.997
            entry_strategy = "ورود بعد از شکست حمایت نزدیک"
            entry_reasons.append(f"نزدیک حمایت swing در {nearest_support:.6f} هستیم")
            entry_reasons.append("ورود بعد از شکست حمایت برای تایید روند نزولی")
        elif dist_to_resistance < 3.0:
            # نزدیک مقاومت → ورود در پولبک
            recommended_entry = nearest_resistance * 0.995
            entry_strategy = "ورود در پولبک به مقاومت"
            entry_reasons.append(f"نزدیک مقاومت swing در {nearest_resistance:.6f} هستیم")
            entry_reasons.append("ورود در پولبک به مقاومت با ریسک کم")
        else:
            recommended_entry = current_price
            entry_strategy = "ورود در قیمت فعلی (تایید روند نزولی)"
            entry_reasons.append("قیمت در فاصله مناسب از حمایت و مقاومت است")
            entry_reasons.append(f"مقاومت در {dist_to_resistance:.1f}% بالاتر، حمایت در {dist_to_support:.1f}% پایین‌تر")

        # ============ محاسبه استاپ لاس با دلیل ============
        stop_options = []

        # گزینه 1: بالای مقاومت swing
        if nearest_resistance > recommended_entry:
            atr_buffer = atr_1h * 0.3
            stop_at_resistance = nearest_resistance + atr_buffer
            if stop_at_resistance > recommended_entry:
                swing_info = None
                for s in swings_1h['highs']:
                    if abs(s['price'] - nearest_resistance) / nearest_resistance < 0.001:
                        swing_info = s
                        break
                tf_label = '1h'
                if not swing_info:
                    for s in swings_4h['highs']:
                        if abs(s['price'] - nearest_resistance) / nearest_resistance < 0.001:
                            swing_info = s
                            tf_label = '4h'
                            break
                if not swing_info:
                    for s in swings_1d['highs']:
                        if abs(s['price'] - nearest_resistance) / nearest_resistance < 0.001:
                            swing_info = s
                            tf_label = 'روزانه'
                            break

                reason = f"بالای مقاومت swing ({tf_label}) در {nearest_resistance:.6f}"
                if swing_info:
                    reason += f" از {swing_info['candles_ago']} کندل قبل"
                reason += f" + بافر {atr_buffer:.6f} (0.3x ATR 1h)"
                stop_options.append({
                    'price': stop_at_resistance,
                    'reason': reason,
                    'type': 'resistance_based',
                })

        # گزینه 2: ATR-based
        atr_stop = recommended_entry + (atr_4h * config.ATR_STOP_MULTIPLIER)
        stop_options.append({
            'price': atr_stop,
            'reason': f"{config.ATR_STOP_MULTIPLIER}x ATR(4h) بالای قیمت ورود = نوسانات 4 ساعته",
            'type': 'atr_based',
        })

        # گزینه 3: دیوار فروش Order Book
        if order_book:
            ask_walls = order_book.get('ask_walls', [])
            if len(ask_walls):
                wall_price = float(ask_walls['price'].min())
                if wall_price > recommended_entry:
                    stop_options.append({
                        'price': wall_price * 1.002,
                        'reason': f"پشت دیوار فروش Order Book در {wall_price:.6f} (مقاومت نقدینگی)",
                        'type': 'order_book_wall',
                    })

        # انتخاب بهترین استاپ: پایین‌ترین سطح بالای ورود (محافظه‌کارانه‌ترین)
        valid_stops = [s for s in stop_options if s['price'] > recommended_entry]
        if valid_stops:
            recommended_stop_data = min(valid_stops, key=lambda x: x['price'])
            recommended_stop = recommended_stop_data['price']
            stop_reason = recommended_stop_data['reason']
        else:
            recommended_stop = atr_stop
            stop_reason = stop_options[1]['reason'] if len(stop_options) > 1 else "ATR-based"

        # ============ محاسبه تی‌پی‌ها با دلیل ============
        risk = recommended_stop - recommended_entry
        targets = []

        # تی‌پی 1: نزدیک‌ترین حمایت یا RR 1:2
        tp1_by_rr = recommended_entry - (risk * 2.0)
        tp1_reason = ""
        if nearest_support < recommended_entry and nearest_support > tp1_by_rr:
            tp1_price = nearest_support * 1.005  # کمی قبل از حمایت
            tp1_reason = f"نزدیک حمایت swing در {nearest_support:.6f}"
            for s in swings_1h['lows'] + swings_4h['lows'] + swings_1d['lows']:
                if abs(s['price'] - nearest_support) / nearest_support < 0.001:
                    tp1_reason += f" (از {s['candles_ago']} کندل قبل)"
                    break
        else:
            tp1_price = tp1_by_rr
            tp1_reason = f"RR 1:2 (دو برابر ریسک) = {risk:.6f} سود"

        targets.append({'price': tp1_price, 'reason': tp1_reason, 'rr': 2.0})

        # تی‌پی 2: RR 1:3 یا حمایت بعدی
        tp2_by_rr = recommended_entry - (risk * 3.0)
        next_supports = [s for s in supports_below if s < tp1_price]
        if next_supports and next_supports[0] > tp2_by_rr:
            tp2_price = next_supports[0] * 1.005
            tp2_reason = f"حمایت بعدی swing در {next_supports[0]:.6f}"
        else:
            tp2_price = tp2_by_rr
            tp2_reason = f"RR 1:3 (سه برابر ریسک) - هدف اصلی Swing"
        targets.append({'price': tp2_price, 'reason': tp2_reason, 'rr': 3.0})

        # تی‌پی 3: RR 1:5 یا حمایت پایین‌تر
        tp3_by_rr = recommended_entry - (risk * config.ATR_TARGET_MULTIPLIER)
        if len(next_supports) > 1 and next_supports[1] > tp3_by_rr:
            tp3_price = next_supports[1] * 1.005
            tp3_reason = f"حمایت پایین‌تر swing در {next_supports[1]:.6f}"
        else:
            tp3_price = tp3_by_rr
            tp3_reason = f"RR 1:{config.ATR_TARGET_MULTIPLIER:.0f} - هدف حداکثری Swing"
        targets.append({'price': tp3_price, 'reason': tp3_reason, 'rr': config.ATR_TARGET_MULTIPLIER})

        # ============ فاصله‌ها ============
        stop_pct = (recommended_stop - recommended_entry) / recommended_entry * 100
        tp2_pct = (recommended_entry - tp2_price) / recommended_entry * 100
        rr = (recommended_entry - tp2_price) / risk if risk > 0 else 0

        return {
            'direction': 'SHORT',
            'style': 'Swing',
            'current_price': round(current_price, 6),
            'entry_price': round(recommended_entry, 6),
            'entry_strategy': entry_strategy,
            'entry_reasons': entry_reasons,
            'stop_loss': round(recommended_stop, 6),
            'stop_pct': round(stop_pct, 2),
            'stop_reason': stop_reason,
            'stop_options': [{'price': round(s['price'], 6), 'reason': s['reason'], 'type': s['type']} for s in stop_options],
            'target_1': round(tp1_price, 6),
            'target_1_reason': tp1_reason,
            'target_2': round(tp2_price, 6),
            'target_2_reason': tp2_reason,
            'target_3': round(tp3_price, 6),
            'target_3_reason': tp3_reason,
            'targets': [{'price': round(t['price'], 6), 'reason': t['reason'], 'rr': t['rr']} for t in targets],
            'target_2_pct': round(tp2_pct, 2),
            'risk_reward': round(rr, 2),
            'atr_1h': round(atr_1h, 6),
            'atr_4h': round(atr_4h, 6),
            'atr_1d': round(atr_1d, 6),
            'nearest_support': round(nearest_support, 6),
            'nearest_resistance': round(nearest_resistance, 6),
            'support_distance_pct': round(dist_to_support, 2),
            'resistance_distance_pct': round(dist_to_resistance, 2),
            'wall_check': wall_check,
        }
