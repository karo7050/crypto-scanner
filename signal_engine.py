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
                   oi_data: Dict = None, news_data: Dict = None, flow_data: Dict = None,
                   btc_data: Dict = None, smc_data: Dict = None) -> Dict:
        """
        امتیازدهی جامع با SMC (Smart Money Concepts)
        اولویت: SMC > Trend > Volume > Liquidity
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

        # ---------- امتیاز Volume Flow (Inflow/Outflow) ----------
        flow_long_bonus = 0
        flow_short_bonus = 0
        if flow_data:
            flow_score = flow_data.get('flow_score', 0)
            if flow_score > 0:
                flow_long_bonus = flow_score * 8  # ورود پول → لانگ
            elif flow_score < 0:
                flow_short_bonus = abs(flow_score) * 8  # خروج پول → شورت

        # ---------- امتیاز BTC pair (قدرت نسبت به بیت‌کوین) ----------
        btc_long_bonus = 0
        btc_short_bonus = 0
        btc_confirmation_long = ''
        btc_confirmation_short = ''
        if btc_data and btc_data.get('available'):
            btc_score = btc_data.get('btc_score', 0)
            btc_strength = btc_data.get('btc_strength', 'unknown')
            
            # تأیید لانگ: ارز قوی‌تر از BTC
            if btc_score > 0:
                btc_long_bonus = btc_score * 10
                btc_confirmation_long = f'✅ {btc_strength}'
            # تأیید شورت: ارز ضعیف‌تر از BTC
            elif btc_score < 0:
                btc_short_bonus = abs(btc_score) * 10
                btc_confirmation_short = f'✅ {btc_strength}'
            
            # هشدارهای مخالف
            if btc_score < 0:
                btc_confirmation_long = f'⚠ {btc_strength} - لانگ خطرناک'
            elif btc_score > 0:
                btc_confirmation_short = f'⚠ {btc_strength} - شورت خطرناک'

        # ---------- امتیاز SMC (Smart Money Concepts) - بالاترین اولویت ----------
        smc_long_bonus = 0
        smc_short_bonus = 0
        smc_reasons_long = []
        smc_reasons_short = []
        smc_quality = 0

        if smc_data and smc_data.get('available'):
            # تحلیل 4h
            smc_4h = smc_data.get('4h', {})
            smc_1h = smc_data.get('1h', {})
            smc_15m = smc_data.get('15m', {})

            # امتیاز ساختار (BOS/CHoCH)
            score_4h = smc_4h.get('structure_score', 0) if smc_4h.get('available') else 0
            score_1h = smc_1h.get('structure_score', 0) if smc_1h.get('available') else 0
            score_15m = smc_15m.get('structure_score', 0) if smc_15m.get('available') else 0

            # وزن: 4h (3x), 1h (2x), 15m (1x)
            smc_combined = (score_4h * 3 + score_1h * 2 + score_15m * 1) / 6

            if smc_combined > 0:
                smc_long_bonus = smc_combined * 15  # SMC بالاترین وزن
            elif smc_combined < 0:
                smc_short_bonus = abs(smc_combined) * 15

            # تأیید Order Block
            if smc_1h.get('in_bull_ob') or smc_1h.get('near_bull_ob'):
                smc_long_bonus += 10
                smc_reasons_long.append("✅ قیمت در/نزدیک Order Block صعودی")
            if smc_1h.get('in_bear_ob') or smc_1h.get('near_bear_ob'):
                smc_short_bonus += 10
                smc_reasons_short.append("✅ قیمت در/نزدیک Order Block نزولی")

            # تأیید FVG
            if smc_1h.get('last_fvg'):
                fvg = smc_1h.get('last_fvg', '')
                if 'BULLISH FVG' in fvg:
                    smc_long_bonus += 8
                    smc_reasons_long.append("✅ Fair Value Gap صعودی (حمایت)")
                elif 'BEARISH FVG' in fvg:
                    smc_short_bonus += 8
                    smc_reasons_short.append("✅ Fair Value Gap نزولی (مقاومت)")

            # کیفیت setup
            smc_quality = smc_data.get('setup_quality', 0)

            # در صورت تناقض SMC، امتیاز منفی
            if score_4h > 0 and score_1h < 0:
                smc_long_bonus *= 0.5  # کاهش امتیاز به دلیل conflict
                smc_reasons_long.append("⚠ تناقض 4H صعودی و 1H نزولی")
            if score_4h < 0 and score_1h > 0:
                smc_short_bonus *= 0.5
                smc_reasons_short.append("⚠ تناقض 4H نزولی و 1H صعودی")

        # ---------- فیلتر جهت SMC ----------
        # اگر SMC جهت مشخص دارد، فقط آن جهت سیگنال بده
        smc_direction = 'neutral'
        if smc_data and smc_data.get('available'):
            smc_direction = smc_data.get('combined_direction', 'neutral')

        # اگر SMC صعودی است → شورت را کاهش بده
        if smc_direction == 'bullish':
            smc_short_bonus *= 0.3
        # اگر SMC نزولی است → لانگ را کاهش بده
        elif smc_direction == 'bearish':
            smc_long_bonus *= 0.3

        # ---------- امتیاز نهایی ----------
        long_score = (
            trend_long_score * weights['trend_alignment'] / 100 +
            momentum_long * weights['momentum'] / 100 +
            liquidity_long * weights['liquidity'] / 100 +
            volume_score * weights['volume'] / 100 +
            ob_score_long * weights['structure'] / 100 +
            oi_long_bonus + news_long_bonus + flow_long_bonus + btc_long_bonus + smc_long_bonus
        )
        short_score = (
            trend_short_score * weights['trend_alignment'] / 100 +
            momentum_short * weights['momentum'] / 100 +
            liquidity_short * weights['liquidity'] / 100 +
            volume_score * weights['volume'] / 100 +
            ob_score_short * weights['structure'] / 100 +
            oi_short_bonus + news_short_bonus + flow_short_bonus + btc_short_bonus + smc_short_bonus
        )

        # ---------- تولید دلایل ----------
        long_reasons = SignalEngine._generate_long_reasons(
            trend, structure, state_1h, state_15m, order_book_analysis, oi_data, news_data, flow_data, btc_data
        )
        short_reasons = SignalEngine._generate_short_reasons(
            trend, structure, state_1h, state_15m, order_book_analysis, oi_data, news_data, flow_data, btc_data
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
    def _generate_long_reasons(trend, structure, state_1h, state_15m, ob, oi_data=None, news_data=None, flow_data=None, btc_data=None) -> List[str]:
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
        # دلایل Volume Flow
        if flow_data:
            if flow_data.get('flow_score', 0) > 0:
                net = flow_data.get('net_flow_24h_usd', 0)
                if abs(net) >= 1e6:
                    net_str = f"${net/1e6:.1f}M"
                else:
                    net_str = f"${net/1e3:.0f}K"
                reasons.append(f"ورود پول خالص 24h: {net_str} ({flow_data.get('flow_signal', '')})")
        # دلایل BTC pair
        if btc_data and btc_data.get('available'):
            btc_score = btc_data.get('btc_score', 0)
            if btc_score > 0:
                change_4h = btc_data.get('4h', {}).get('change_24h_vs_btc_pct', 0)
                reasons.append(f"قوی‌تر از BTC (24h: {change_4h:+.1f}% نسبت به BTC)")
            elif btc_score < 0:
                reasons.append(f"⚠ ضعیف‌تر از BTC - لانگ با احتیاط")
        return reasons

    # ----------------- تولید دلایل شورت -----------------
    @staticmethod
    def _generate_short_reasons(trend, structure, state_1h, state_15m, ob, oi_data=None, news_data=None, flow_data=None, btc_data=None) -> List[str]:
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
        # دلایل Volume Flow
        if flow_data:
            if flow_data.get('flow_score', 0) < 0:
                net = flow_data.get('net_flow_24h_usd', 0)
                if abs(net) >= 1e6:
                    net_str = f"${net/1e6:.1f}M"
                else:
                    net_str = f"${abs(net)/1e3:.0f}K"
                reasons.append(f"خروج پول خالص 24h: {net_str} ({flow_data.get('flow_signal', '')})")
        # دلایل BTC pair
        if btc_data and btc_data.get('available'):
            btc_score = btc_data.get('btc_score', 0)
            if btc_score < 0:
                change_4h = btc_data.get('4h', {}).get('change_24h_vs_btc_pct', 0)
                reasons.append(f"ضعیف‌تر از BTC (24h: {change_4h:+.1f}% نسبت به BTC)")
            elif btc_score > 0:
                reasons.append(f"⚠ قوی‌تر از BTC - شورت با احتیاط")
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
