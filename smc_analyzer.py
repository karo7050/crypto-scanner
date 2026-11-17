"""
ماژول تحلیل Smart Money Concepts
SMC Analyzer Module

استخراج شده از کتابخانه smartmoneyconcepts (github.com/joshyattridge/smart-money-concepts)
تطبیق با ساختار اسکنر ما

مفاهیم تحلیل شده:
- Order Blocks (OB)
- Fair Value Gap (FVG)
- Break of Structure (BOS) / Change of Character (CHoCH)
- Liquidity zones
- Swing Highs/Lows
- Retracements

این ماژول جایگزین تحلیل سطحی EMA/RSI می‌شود و ساختار واقعی بازار را بررسی می‌کند.
"""
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

try:
    from smartmoneyconcepts import smc
    SMC_AVAILABLE = True
except ImportError:
    SMC_AVAILABLE = False
    logger.warning("smartmoneyconcepts نصب نیست. pip install smartmoneyconcepts")


class SMCAnalyzer:
    """تحلیل Smart Money Concepts برای یک DataFrame"""

    @staticmethod
    def is_available() -> bool:
        return SMC_AVAILABLE

    @staticmethod
    def analyze(df: pd.DataFrame) -> Dict:
        """
        تحلیل کامل SMC برای یک تایم فریم
        """
        if not SMC_AVAILABLE or df is None or len(df) < 60:
            return {'available': False}

        try:
            # آماده‌سازی داده - SMC نیاز به lowercase columns دارد
            ohlc = df[['open', 'high', 'low', 'close', 'volume']].copy()
            ohlc.columns = ['open', 'high', 'low', 'close', 'volume']

            result = {'available': True}

            # 1. Swing Highs and Lows
            swing_hl = smc.swing_highs_lows(ohlc, swing_length=10)
            result['swing_highs_lows'] = swing_hl

            # نزدیک‌ترین swing high و low
            if swing_hl is not None and len(swing_hl) > 0:
                last_close = float(ohlc['close'].iloc[-1])
                recent_swing_highs = swing_hl[swing_hl['HighLow'] == 1].tail(5)
                recent_swing_lows = swing_hl[swing_hl['HighLow'] == -1].tail(5)

                if len(recent_swing_highs) > 0:
                    nearest_swing_high = float(recent_swing_highs['Level'].iloc[-1])
                    result['nearest_swing_high'] = nearest_swing_high
                    result['dist_to_swing_high_pct'] = ((nearest_swing_high - last_close) / last_close) * 100
                if len(recent_swing_lows) > 0:
                    nearest_swing_low = float(recent_swing_lows['Level'].iloc[-1])
                    result['nearest_swing_low'] = nearest_swing_low
                    result['dist_to_swing_low_pct'] = ((last_close - nearest_swing_low) / last_close) * 100

            # 2. BOS and CHoCH
            bos_choch = smc.bos_choch(ohlc, swing_hl, close_break=True)
            result['bos_choch'] = bos_choch

            # تحلیل آخرین BOS/CHoCH
            if bos_choch is not None and len(bos_choch) > 0:
                last_bos = bos_choch.iloc[-1]
                bos_val = last_bos.get('BOS', 0)
                choch_val = last_bos.get('CHOCH', 0)

                if bos_val == 1:
                    result['structure'] = 'BULLISH BOS - روند صعودی تأیید شده'
                    result['structure_dir'] = 'bullish'
                    result['structure_score'] = 2
                elif bos_val == -1:
                    result['structure'] = 'BEARISH BOS - روند نزولی تأیید شده'
                    result['structure_dir'] = 'bearish'
                    result['structure_score'] = -2
                elif choch_val == 1:
                    result['structure'] = 'BULLISH CHoCH - احتمال تغییر جهت به صعودی'
                    result['structure_dir'] = 'bullish_reversal'
                    result['structure_score'] = 1
                elif choch_val == -1:
                    result['structure'] = 'BEARISH CHoCH - احتمال تغییر جهت به نزولی'
                    result['structure_dir'] = 'bearish_reversal'
                    result['structure_score'] = -1
                else:
                    result['structure'] = 'بدون شکست ساختار - رنج'
                    result['structure_dir'] = 'neutral'
                    result['structure_score'] = 0

            # 3. Order Blocks
            ob = smc.ob(ohlc, swing_hl, close_mitigation=False)
            result['order_blocks'] = ob

            # پیدا کردن OB نزدیک به قیمت فعلی
            if ob is not None and len(ob) > 0:
                last_close = float(ohlc['close'].iloc[-1])
                # OBهای اخیر (آخرین 10)
                recent_obs = ob.tail(10)
                # OB صعودی (1) و نزولی (-1)
                bull_obs = recent_obs[recent_obs['OB'] == 1]
                bear_obs = recent_obs[recent_obs['OB'] == -1]

                if len(bull_obs) > 0:
                    # نزدیک‌ترین OB صعودی به قیمت فعلی
                    for _, row in bull_obs.iterrows():
                        ob_top = float(row['Top'])
                        ob_bottom = float(row['Bottom'])
                        # آیا قیمت در OB هست یا نزدیک آن؟
                        if ob_bottom <= last_close <= ob_top:
                            result['in_bull_ob'] = True
                            result['bull_ob_top'] = ob_top
                            result['bull_ob_bottom'] = ob_bottom
                            result['bull_ob_strength'] = float(row.get('Percentage', 0))
                            break
                        elif abs(last_close - ob_top) / last_close < 0.02:  # نزدیک OB
                            result['near_bull_ob'] = True
                            result['bull_ob_top'] = ob_top
                            result['bull_ob_bottom'] = ob_bottom
                            break

                if len(bear_obs) > 0:
                    for _, row in bear_obs.iterrows():
                        ob_top = float(row['Top'])
                        ob_bottom = float(row['Bottom'])
                        if ob_bottom <= last_close <= ob_top:
                            result['in_bear_ob'] = True
                            result['bear_ob_top'] = ob_top
                            result['bear_ob_bottom'] = ob_bottom
                            result['bear_ob_strength'] = float(row.get('Percentage', 0))
                            break
                        elif abs(last_close - ob_bottom) / last_close < 0.02:
                            result['near_bear_ob'] = True
                            result['bear_ob_top'] = ob_top
                            result['bear_ob_bottom'] = ob_bottom
                            break

            # 4. Fair Value Gap (FVG)
            fvg = smc.fvg(ohlc, join_consecutive=False)
            result['fvg'] = fvg

            # آخرین FVG
            if fvg is not None and len(fvg) > 0:
                recent_fvgs = fvg.tail(5)
                last_fvg = recent_fvgs.iloc[-1]
                fvg_val = last_fvg.get('FVG', 0)
                if fvg_val == 1:
                    result['last_fvg'] = 'BULLISH FVG - شکاف صعودی (حمایت احتمالی)'
                    result['fvg_top'] = float(last_fvg.get('Top', 0))
                    result['fvg_bottom'] = float(last_fvg.get('Bottom', 0))
                elif fvg_val == -1:
                    result['last_fvg'] = 'BEARISH FVG - شکاف نزولی (مقاومت احتمالی)'
                    result['fvg_top'] = float(last_fvg.get('Top', 0))
                    result['fvg_bottom'] = float(last_fvg.get('Bottom', 0))

            # 5. Liquidity
            liquidity = smc.liquidity(ohlc, swing_hl, range_percent=0.01)
            result['liquidity'] = liquidity

            if liquidity is not None and len(liquidity) > 0:
                recent_liq = liquidity.tail(5)
                last_liq = recent_liq.iloc[-1]
                liq_val = last_liq.get('Liquidity', 0)
                if liq_val == 1:
                    result['liquidity_above'] = True
                    result['liquidity_level'] = float(last_liq.get('Level', 0))
                    result['liquidity_type'] = 'BUY_SIDE LIQUIDITY (بالای قیمت - هدف احتمالی)'
                elif liq_val == -1:
                    result['liquidity_below'] = True
                    result['liquidity_level'] = float(last_liq.get('Level', 0))
                    result['liquidity_type'] = 'SELL_SIDE LIQUIDITY (پایین قیمت - هدف احتمالی)'

            # 6. Retracements
            retracements = smc.retracements(ohlc, swing_hl)
            if retracements is not None and len(retracements) > 0:
                last_retr = retracements.iloc[-1]
                result['retracement_dir'] = int(last_retr.get('Direction', 0))
                result['retracement_current'] = float(last_retr.get('CurrentRetracement%', 0))
                result['retracement_deepest'] = float(last_retr.get('DeepestRetracement%', 0))

            return result

        except Exception as e:
            logger.debug(f"خطا در SMC analysis: {e}")
            return {'available': False, 'error': str(e)}

    # ============ تحلیل چند تایم فریم SMC ============
    @staticmethod
    def analyze_multi_tf(timeframes_data: Dict) -> Dict:
        """
        تحلیل SMC در تایم فریم‌های 4h و 1h و 15m
        و ترکیب نتایج
        """
        result = {
            '4h': {},
            '1h': {},
            '15m': {},
            'combined_score': 0,
            'combined_direction': 'neutral',
            'setup_quality': 0,
        }

        for tf in ['4h', '1h', '15m']:
            df = timeframes_data.get(tf)
            if df is not None:
                result[tf] = SMCAnalyzer.analyze(df)

        # ترکیب امتیازها
        scores = []
        directions = []
        for tf in ['4h', '1h', '15m']:
            tf_data = result.get(tf, {})
            if tf_data.get('available'):
                score = tf_data.get('structure_score', 0)
                direction = tf_data.get('structure_dir', 'neutral')
                scores.append(score)
                directions.append(direction)

        if scores:
            # وزن: 4h (3x), 1h (2x), 15m (1x)
            weights = [3, 2, 1]
            weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

            result['combined_score'] = weighted_score

            if weighted_score > 1.0:
                result['combined_direction'] = 'bullish'
            elif weighted_score < -1.0:
                result['combined_direction'] = 'bearish'
            else:
                result['combined_direction'] = 'neutral'

        # کیفیت setup بر اساس تأییدهای همزمان
        confirmations = 0
        if result.get('4h', {}).get('structure_score', 0) != 0:
            confirmations += 1
        if result.get('1h', {}).get('structure_score', 0) != 0:
            confirmations += 1
        if result.get('15m', {}).get('structure_score', 0) != 0:
            confirmations += 1
        # OB یا FVG
        if result.get('1h', {}).get('in_bull_ob') or result.get('1h', {}).get('in_bear_ob'):
            confirmations += 1
        if result.get('1h', {}).get('last_fvg'):
            confirmations += 1

        result['setup_quality'] = confirmations

        return result

    # ============ تولید دلایل SMC ============
    @staticmethod
    def generate_reasons(smc_data: Dict, is_long: bool) -> List[str]:
        """تولید دلایل بر اساس SMC"""
        reasons = []

        if not smc_data or not smc_data.get('available'):
            return reasons

        # ساختار بازار
        structure = smc_data.get('structure', '')
        if structure:
            if is_long and 'BULLISH' in structure:
                reasons.append(f"ساختار بازار: {structure}")
            elif not is_long and 'BEARISH' in structure:
                reasons.append(f"ساختار بازار: {structure}")

        # Order Block
        if is_long and smc_data.get('in_bull_ob'):
            reasons.append(f"قیمت در Order Block صعودی ({smc_data.get('bull_ob_bottom', 0):.6f} - {smc_data.get('bull_ob_top', 0):.6f})")
        elif is_long and smc_data.get('near_bull_ob'):
            reasons.append(f"نزدیک Order Block صعودی - نقطه ورود احتمالی")
        elif not is_long and smc_data.get('in_bear_ob'):
            reasons.append(f"قیمت در Order Block نزولی ({smc_data.get('bear_ob_bottom', 0):.6f} - {smc_data.get('bear_ob_top', 0):.6f})")
        elif not is_long and smc_data.get('near_bear_ob'):
            reasons.append(f"نزدیک Order Block نزولی - نقطه ورود احتمالی")

        # FVG
        fvg = smc_data.get('last_fvg', '')
        if fvg:
            if is_long and 'BULLISH FVG' in fvg:
                reasons.append(f"FVG: {fvg}")
            elif not is_long and 'BEARISH FVG' in fvg:
                reasons.append(f"FVG: {fvg}")

        # Liquidity
        liq_type = smc_data.get('liquidity_type', '')
        if liq_type:
            if is_long and 'SELL_SIDE' in liq_type:
                reasons.append(f"نقدینگی پایین شکار شده - احتمال بازگشت صعودی")
            elif not is_long and 'BUY_SIDE' in liq_type:
                reasons.append(f"نقدینگی بالا شکار شده - احتمال بازگشت نزولی")

        return reasons
