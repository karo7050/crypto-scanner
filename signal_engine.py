"""
موتور تولید سیگنال و امتیازدهی
Signal Engine Module
- امتیازدهی همه جانبه به هر کوین
- انتخاب 10 لانگ و 10 شورت برتر
- تولید دلایل انتخاب
"""
import pandas as pd
import numpy as np
from typing import Dict, List
import config
from multi_tf import MultiTimeframeAnalyzer
from liquidity import LiquidityAnalyzer


class SignalEngine:
    """موتور امتیازدهی و تولید سیگنال لانگ/شورت"""

    @staticmethod
    def score_coin(coin_info: Dict, analysis: Dict, order_book_analysis: Dict,
                   oi_data: Dict = None, news_data: Dict = None) -> Dict:
        """
        امتیازدهی جامع به یک کوین برای لانگ و شورت
        شامل: روند، مومنتوم، نقدینگی، حجم، ساختار، OI/Funding، اخبار
        """
        weights = config.SCORE_WEIGHTS

        # ---------- 1) امتیاز هماهنگی روند ----------
        trend = MultiTimeframeAnalyzer.check_trend_alignment(analysis)
        # برای لانگ: روند صعودی امتیاز مثبت
        trend_long_score = max(0, trend['alignment_score']) / trend['max_possible'] * 100
        # برای شورت: روند نزولی امتیاز مثبت
        trend_short_score = max(0, -trend['alignment_score']) / trend['max_possible'] * 100

        # ---------- 2) امتیاز مومنتوم ----------
        tf_1h = analysis.get('1h', {})
        tf_15m = analysis.get('15m', {})
        state_1h = tf_1h.get('state', {}) if tf_1h else {}
        state_15m = tf_15m.get('state', {}) if tf_15m else {}

        # مومنتوم لانگ: RSI بالا (نه اشباع)، MACD مثبت، تقاطع صعودی
        momentum_long = 0
        rsi_1h = state_1h.get('rsi', 50)
        if 50 < rsi_1h < 70:
            momentum_long += 30
        elif 40 < rsi_1h <= 50:
            momentum_long += 20  # بازگشت از RSI پایین
        elif rsi_1h >= 70:
            momentum_long += 10  # اشباع خرید

        if state_1h.get('macd_diff', 0) > 0:
            momentum_long += 20
        if state_15m.get('macd_cross_up'):
            momentum_long += 25
        if state_1h.get('ema_cross_up'):
            momentum_long += 25
        momentum_long = min(momentum_long, 100)

        # مومنتوم شورت: RSI پایین (نه اشباع فروش)، MACD منفی، تقاطع نزولی
        momentum_short = 0
        if 30 < rsi_1h < 50:
            momentum_short += 30
        elif 50 <= rsi_1h < 60:
            momentum_short += 20
        elif rsi_1h <= 30:
            momentum_short += 10  # اشباع فروش

        if state_1h.get('macd_diff', 0) < 0:
            momentum_short += 20
        if state_15m.get('macd_cross_down'):
            momentum_short += 25
        if state_1h.get('ema_cross_down'):
            momentum_short += 25
        momentum_short = min(momentum_short, 100)

        # ---------- 3) امتیاز نقدینگی و جریان پول ----------
        structure = MultiTimeframeAnalyzer.analyze_structure(analysis)
        phase_score = structure['total_phase_score']

        # برای لانگ: انباشت مثبت، برای شورت: توزیع مثبت
        liquidity_long = max(0, phase_score) / 6 * 100 if phase_score > 0 else 0
        liquidity_short = max(0, -phase_score) / 6 * 100 if phase_score < 0 else 0

        # CMF و OBV
        for tf_name in ['4h', '1h']:
            tf_data = analysis.get(tf_name, {})
            if tf_data:
                liq = tf_data.get('liquidity', {})
                cmf = liq.get('cmf', 0)
                if cmf > 0.05:
                    liquidity_long += 15
                elif cmf < -0.05:
                    liquidity_short += 15

                if liq.get('obv_trend') == 'صعودی':
                    liquidity_long += 10
                elif liq.get('obv_trend') == 'نزولی':
                    liquidity_short += 10

        liquidity_long = min(liquidity_long, 100)
        liquidity_short = min(liquidity_short, 100)

        # ---------- 4) امتیاز حجم ----------
        volume_score = 0
        for tf_name in ['1h', '15m']:
            tf_data = analysis.get(tf_name, {})
            if tf_data:
                state = tf_data.get('state', {})
                vol_ratio = state.get('volume_ratio', 1)
                if vol_ratio > 1.5:
                    volume_score += 30
                elif vol_ratio > 1.0:
                    volume_score += 15
        volume_score = min(volume_score, 100)

        # ---------- 5) امتیاز Order Book ----------
        ob_score_long = 0
        ob_score_short = 0
        if order_book_analysis:
            pressure_score = order_book_analysis.get('pressure_score', 0)
            if pressure_score > 0:
                ob_score_long = pressure_score * 25  # حداکثر 50
            else:
                ob_score_short = abs(pressure_score) * 25

            # فاصله دیوارها
            bid_dist = abs(order_book_analysis.get('bid_wall_distance_pct', 0))
            ask_dist = abs(order_book_analysis.get('ask_wall_distance_pct', 0))
            # اگر حمایت نزدیک‌تر از مقاومت باشد → بهتر برای لانگ
            if bid_dist < ask_dist and bid_dist < 2:
                ob_score_long += 15
            elif ask_dist < bid_dist and ask_dist < 2:
                ob_score_short += 15

        # ---------- امتیاز OI و Funding Rate ----------
        oi_long_bonus = 0
        oi_short_bonus = 0
        if oi_data:
            oi_analysis = oi_data.get('oi_analysis', '')
            funding_analysis = oi_data.get('funding_analysis', '')
            funding_score = oi_data.get('funding_score', 0)
            oi_score = oi_data.get('oi_score', 0)

            # Funding منفی → حمایت لانگ
            if funding_score > 0:
                oi_long_bonus = funding_score * 8
            elif funding_score < 0:
                oi_short_bonus = abs(funding_score) * 8

            # OI بالا → تایید حرکت (در جهت روند)
            if oi_score > 0:
                oi_long_bonus += oi_score * 2
                oi_short_bonus += oi_score * 2

        # ---------- امتیاز اخبار ----------
        news_long_bonus = 0
        news_short_bonus = 0
        if news_data:
            news_score = news_data.get('news_score', 0)
            if news_score > 0:
                news_long_bonus = news_score * 10
            elif news_score < 0:
                news_short_bonus = abs(news_score) * 10

        # ---------- امتیاز نهایی ----------
        long_score = (
            trend_long_score * weights['trend_alignment'] / 100 +
            momentum_long * weights['momentum'] / 100 +
            liquidity_long * weights['liquidity'] / 100 +
            volume_score * weights['volume'] / 100 +
            ob_score_long * weights['structure'] / 100 +
            oi_long_bonus + news_long_bonus
        )
        short_score = (
            trend_short_score * weights['trend_alignment'] / 100 +
            momentum_short * weights['momentum'] / 100 +
            liquidity_short * weights['liquidity'] / 100 +
            volume_score * weights['volume'] / 100 +
            ob_score_short * weights['structure'] / 100 +
            oi_short_bonus + news_short_bonus
        )

        # ---------- تولید دلایل ----------
        long_reasons = SignalEngine._generate_long_reasons(
            trend, structure, state_1h, state_15m, order_book_analysis, oi_data, news_data
        )
        short_reasons = SignalEngine._generate_short_reasons(
            trend, structure, state_1h, state_15m, order_book_analysis, oi_data, news_data
        )

        return {
            'coin': coin_info,
            'long_score': round(long_score, 2),
            'short_score': round(short_score, 2),
            'components': {
                'trend_long': round(trend_long_score, 2),
                'trend_short': round(trend_short_score, 2),
                'momentum_long': round(momentum_long, 2),
                'momentum_short': round(momentum_short, 2),
                'liquidity_long': round(liquidity_long, 2),
                'liquidity_short': round(liquidity_short, 2),
                'volume': round(volume_score, 2),
                'ob_long': round(ob_score_long, 2),
                'ob_short': round(ob_score_short, 2),
            },
            'trend_alignment': trend,
            'structure': structure,
            'state_1h': state_1h,
            'state_15m': state_15m,
            'order_book': order_book_analysis,
            'long_reasons': long_reasons,
            'short_reasons': short_reasons,
        }

    # ----------------- تولید دلایل لانگ -----------------
    @staticmethod
    def _generate_long_reasons(trend, structure, state_1h, state_15m, ob, oi_data=None, news_data=None) -> List[str]:
        reasons = []
        if trend['alignment_pct'] > 40:
            reasons.append(f"هماهنگی روند صعودی قوی در چند تایم فریم ({trend['alignment_pct']:.0f}%)")
        if structure['total_phase_score'] >= 2:
            reasons.append(f"فاز انباشت مثبت: {structure['overall_structure']}")
        if state_1h.get('macd_cross_up'):
            reasons.append("تقاطع صعودی MACD در تایم 1 ساعت")
        if state_15m.get('macd_cross_up'):
            reasons.append("تقاطع صعودی MACD در تایم 15 دقیقه (تأیید ورود)")
        if state_1h.get('ema_cross_up'):
            reasons.append("تقاطع صعودی EMA20 و EMA50 در 1 ساعت")
        if state_1h.get('rsi', 50) > 50 and state_1h.get('rsi', 50) < 70:
            reasons.append(f"RSI در محدوده سالم صعودی ({state_1h.get('rsi', 0):.1f})")
        if ob and ob.get('pressure_score', 0) > 0:
            reasons.append(f"فشار خرید در Order Book: {ob.get('pressure', '')}")
        if ob and ob.get('bid_wall_distance_pct', 100) < 2 and ob.get('bid_wall_distance_pct', 100) > 0:
            reasons.append(f"دیوار خرید قوی در فاصله {abs(ob['bid_wall_distance_pct']):.1f}% (حمایت نقدینگی)")
        if state_1h.get('volume_ratio', 1) > 1.5:
            reasons.append(f"افزایش حجم معاملات ({state_1h.get('volume_ratio', 0):.2f}x میانگین)")
        # دلایل OI و Funding
        if oi_data:
            if oi_data.get('funding_score', 0) > 0:
                reasons.append(f"Funding Rate منفی (حمایت لانگ): {oi_data.get('funding_analysis', '')}")
            if oi_data.get('oi_usd', 0) and oi_data.get('oi_usd', 0) > 100_000_000:
                reasons.append(f"OI بالا: ${oi_data['oi_usd']/1e6:.0f}M (نقدینگی فیوچرز قوی)")
        # دلایل اخبار
        if news_data:
            if news_data.get('news_score', 0) > 0:
                reasons.append(f"اخبار مثبت ({news_data.get('positive_count', 0)} مورد): {news_data.get('overall_sentiment', '')}")
        return reasons

    # ----------------- تولید دلایل شورت -----------------
    @staticmethod
    def _generate_short_reasons(trend, structure, state_1h, state_15m, ob, oi_data=None, news_data=None) -> List[str]:
        reasons = []
        if trend['alignment_pct'] < -40:
            reasons.append(f"هماهنگی روند نزولی قوی در چند تایم فریم ({abs(trend['alignment_pct']):.0f}%)")
        if structure['total_phase_score'] <= -2:
            reasons.append(f"فاز توزیع: {structure['overall_structure']}")
        if state_1h.get('macd_cross_down'):
            reasons.append("تقاطع نزولی MACD در تایم 1 ساعت")
        if state_15m.get('macd_cross_down'):
            reasons.append("تقاطع نزولی MACD در تایم 15 دقیقه (تأیید ورود)")
        if state_1h.get('ema_cross_down'):
            reasons.append("تقاطع نزولی EMA20 و EMA50 در 1 ساعت")
        if 30 < state_1h.get('rsi', 50) < 50:
            reasons.append(f"RSI در محدوده نزولی ({state_1h.get('rsi', 0):.1f})")
        if ob and ob.get('pressure_score', 0) < 0:
            reasons.append(f"فشار فروش در Order Book: {ob.get('pressure', '')}")
        if ob and ob.get('ask_wall_distance_pct', 100) < 2 and ob.get('ask_wall_distance_pct', 100) > 0:
            reasons.append(f"دیوار فروش قوی در فاصله {abs(ob['ask_wall_distance_pct']):.1f}% (مقاومت نقدینگی)")
        if state_1h.get('volume_ratio', 1) > 1.5 and state_1h.get('trend_bearish'):
            reasons.append(f"افزایش حجم همراه با روند نزولی ({state_1h.get('volume_ratio', 0):.2f}x میانگین)")
        # دلایل OI و Funding
        if oi_data:
            if oi_data.get('funding_score', 0) < 0:
                reasons.append(f"Funding Rate مثبت (حمایت شورت): {oi_data.get('funding_analysis', '')}")
            if oi_data.get('oi_usd', 0) and oi_data.get('oi_usd', 0) > 100_000_000:
                reasons.append(f"OI بالا: ${oi_data['oi_usd']/1e6:.0f}M (نقدینگی فیوچرز قوی)")
        # دلایل اخبار
        if news_data:
            if news_data.get('news_score', 0) < 0:
                reasons.append(f"اخبار منفی ({news_data.get('negative_count', 0)} مورد): {news_data.get('overall_sentiment', '')}")
        return reasons

    # ----------------- انتخاب نهایی -----------------
    @staticmethod
    def select_top_signals(scored_coins: List[Dict]) -> Dict:
        """
        انتخاب 10 لانگ و 10 شورت برتر
        """
        # فیلتر: حداقل امتیاز لازم
        long_candidates = [c for c in scored_coins if c['long_score'] > 30 and len(c['long_reasons']) >= 2]
        short_candidates = [c for c in scored_coins if c['short_score'] > 30 and len(c['short_reasons']) >= 2]

        # مرتب‌سازی نزولی
        long_candidates.sort(key=lambda x: x['long_score'], reverse=True)
        short_candidates.sort(key=lambda x: x['short_score'], reverse=True)

        return {
            'long': long_candidates[:config.TOP_LONG_COUNT],
            'short': short_candidates[:config.TOP_SHORT_COUNT],
        }
