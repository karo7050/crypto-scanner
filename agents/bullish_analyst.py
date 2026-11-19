"""
Agent 3: تحلیلگر خوش‌بین (Bullish Analyst)
- شناسایی فرصت‌های صعودی
- بررسی ساختار صعودی
- شکست مقاومت‌ها
- ورود نقدینگی
- سناریوی صعودی با Entry/Stop/Targets
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict
from multi_tf import MultiTimeframeAnalyzer
from entry_exit import EntryExitCalculator
from indicators import Indicators
from core.data_models import BullishResult, AgentReport
import config
import logging

logger = logging.getLogger(__name__)


class BullishAnalystAgent:
    """Agent 3: تحلیلگر خوش‌بین"""

    def analyze(self, coin: Dict, analysis: Dict, order_book: Dict = None, smc_data: Dict = None) -> AgentReport:
        """
        تحلیل صعودی یک ارز
        """
        symbol = coin['symbol']
        report = AgentReport(
            agent_name="Bullish Analyst",
            coin_symbol=symbol,
            timestamp=config.tehran_now_str(),
        )

        result = BullishResult(symbol=symbol)

        try:
            # 1. بررسی روند چند تایم فریم
            trend = MultiTimeframeAnalyzer.check_trend_alignment(analysis)

            # فقط اگر روند صعودی یا خنثی-صعودی است
            if trend['alignment_score'] > 0:
                result.is_bullish = True
                result.confirmations.append(f"روند صعودی در چند تایم فریم ({trend['alignment_pct']:.0f}%)")
                report.reasons_pro.append(f"هماهنگی روند صعودی: {trend['overall_bias']}")
            elif trend['alignment_score'] < -5:
                result.is_bullish = False
                report.reasons_con.append(f"روند نزولی -不适合 لانگ")
                result.confidence = 0.1
                report.score = 10
                report.data['bullish_result'] = result.__dict__
                report.recommendation = "NOT_BULLISH"
                return report

            # 2. SMC ساختار صعودی
            if smc_data and smc_data.get('available'):
                combined_dir = smc_data.get('combined_direction', 'neutral')
                if combined_dir == 'bullish':
                    result.confirmations.append("SMC: ساختار صعودی تأیید شده")
                    report.reasons_pro.append("SMC BOS/CHoCH صعودی")

                # Order Block صعودی
                smc_1h = smc_data.get('1h', {})
                if smc_1h.get('in_bull_ob'):
                    result.confirmations.append("قیمت در Order Block صعودی")
                    report.reasons_pro.append("Order Block صعودی فعال")
                elif smc_1h.get('near_bull_ob'):
                    result.confirmations.append("نزدیک Order Block صعودی")
                    report.reasons_pro.append("نزدیک OB صعودی - نقطه ورود احتمالی")

                # FVG صعودی
                if smc_1h.get('last_fvg') and 'BULLISH' in smc_1h.get('last_fvg', ''):
                    result.confirmations.append("Fair Value Gap صعودی")
                    report.reasons_pro.append("FVG صعودی (حمایت)")

            # 3. محاسبه Entry/Stop/Targets
            setup = EntryExitCalculator.calculate_long_setup(analysis, order_book)
            if setup:
                result.entry_price = setup.get('entry_price', 0)
                result.stop_loss = setup.get('stop_loss', 0)
                result.targets = [
                    setup.get('target_1', 0),
                    setup.get('target_2', 0),
                    setup.get('target_3', 0),
                ]
                result.risk_reward = setup.get('risk_reward', 0)
                result.structure = setup.get('entry_strategy', '')

                # بررسی RR
                if result.risk_reward >= 2.0:
                    result.confirmations.append(f"RR قابل قبول: 1:{result.risk_reward:.1f}")
                    report.reasons_pro.append(f"RR 1:{result.risk_reward:.1f}")
                else:
                    report.reasons_con.append(f"RR پایین: 1:{result.risk_reward:.1f}")

            # 4. بررسی حجم ورود
            vol_entry = MultiTimeframeAnalyzer.analyze_volume_entry(analysis)
            if vol_entry:
                if 'ورود قوی' in vol_entry.get('entry_signal', ''):
                    result.confirmations.append("حجم تایید ورود")
                    report.reasons_pro.append("حجم ورود قوی")
                elif 'هشدار' in vol_entry.get('entry_signal', ''):
                    report.reasons_con.append("حجم ضعیف - هشدار")

            # 5. امتیازدهی
            result.bullish_score = self._calculate_score(result, trend)
            result.confidence = min(result.bullish_score / 100, 1.0)

            report.score = result.bullish_score
            report.confidence = result.confidence
            report.data['bullish_result'] = result.__dict__
            report.data['setup'] = setup
            report.recommendation = "LONG_CANDIDATE" if result.is_bullish else "NOT_BULLISH"

        except Exception as e:
            logger.error(f"خطا در تحلیل صعودی {symbol}: {e}")
            report.errors.append(str(e))

        return report

    def _calculate_score(self, result: BullishResult, trend: Dict) -> float:
        """امتیاز صعودی 0-100"""
        score = 0.0

        # روند (30%)
        score += min(abs(trend.get('alignment_pct', 0)) * 0.3, 30)

        # SMC تأییدها (30%)
        score += min(len(result.confirmations) * 10, 30)

        # RR (20%)
        if result.risk_reward >= 3:
            score += 20
        elif result.risk_reward >= 2:
            score += 15
        elif result.risk_reward >= 1.5:
            score += 5

        # تعداد تأییدها (20%)
        score += min(len(result.confirmations) * 5, 20)

        return min(score, 100)
