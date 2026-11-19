"""
Agent 4: تحلیلگر بدبین (Bearish Analyst)
- شناسایی فرصت‌های نزولی
- ضعف روند و توزیع
- شکست حمایت‌ها
- خروج نقدینگی
- سناریوی نزولی با Entry/Stop/Targets
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict
from multi_tf import MultiTimeframeAnalyzer
from entry_exit import EntryExitCalculator
from core.data_models import BearishResult, AgentReport
import config
import logging

logger = logging.getLogger(__name__)


class BearishAnalystAgent:
    """Agent 4: تحلیلگر بدبین"""

    def analyze(self, coin: Dict, analysis: Dict, order_book: Dict = None, smc_data: Dict = None) -> AgentReport:
        """
        تحلیل نزولی یک ارز
        """
        symbol = coin['symbol']
        report = AgentReport(
            agent_name="Bearish Analyst",
            coin_symbol=symbol,
            timestamp=config.tehran_now_str(),
        )

        result = BearishResult(symbol=symbol)

        try:
            # 1. بررسی روند
            trend = MultiTimeframeAnalyzer.check_trend_alignment(analysis)

            if trend['alignment_score'] < 0:
                result.is_bearish = True
                result.confirmations.append(f"روند نزولی در چند تایم فریم ({abs(trend['alignment_pct']):.0f}%)")
                report.reasons_pro.append(f"هماهنگی روند نزولی: {trend['overall_bias']}")
            elif trend['alignment_score'] > 5:
                result.is_bearish = False
                report.reasons_con.append("روند صعودی -不适合 شورت")
                result.confidence = 0.1
                report.score = 10
                report.data['bearish_result'] = result.__dict__
                report.recommendation = "NOT_BEARISH"
                return report

            # 2. SMC ساختار نزولی
            if smc_data and smc_data.get('available'):
                combined_dir = smc_data.get('combined_direction', 'neutral')
                if combined_dir == 'bearish':
                    result.confirmations.append("SMC: ساختار نزولی تأیید شده")
                    report.reasons_pro.append("SMC BOS/CHoCH نزولی")

                smc_1h = smc_data.get('1h', {})
                if smc_1h.get('in_bear_ob'):
                    result.confirmations.append("قیمت در Order Block نزولی")
                    report.reasons_pro.append("Order Block نزولی فعال")
                elif smc_1h.get('near_bear_ob'):
                    result.confirmations.append("نزدیک Order Block نزولی")
                    report.reasons_pro.append("نزدیک OB نزولی")

                if smc_1h.get('last_fvg') and 'BEARISH' in smc_1h.get('last_fvg', ''):
                    result.confirmations.append("Fair Value Gap نزولی")
                    report.reasons_pro.append("FVG نزولی (مقاومت)")

            # 3. محاسبه Entry/Stop/Targets
            setup = EntryExitCalculator.calculate_short_setup(analysis, order_book)
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

                if result.risk_reward >= 2.0:
                    result.confirmations.append(f"RR قابل قبول: 1:{result.risk_reward:.1f}")
                    report.reasons_pro.append(f"RR 1:{result.risk_reward:.1f}")
                else:
                    report.reasons_con.append(f"RR پایین: 1:{result.risk_reward:.1f}")

            # 4. ساختار قیمت - توزیع
            structure = MultiTimeframeAnalyzer.analyze_structure(analysis)
            if structure.get('total_phase_score', 0) < -2:
                result.confirmations.append("فاز توزیع قوی")
                report.reasons_pro.append("توزیع قوی - آماده شکست نزولی")
            elif structure.get('total_phase_score', 0) < -1:
                result.confirmations.append("فاز توزیع ملایم")
                report.reasons_pro.append("توزیع ملایم")

            # 5. امتیازدهی
            result.bearish_score = self._calculate_score(result, trend)
            result.confidence = min(result.bearish_score / 100, 1.0)

            report.score = result.bearish_score
            report.confidence = result.confidence
            report.data['bearish_result'] = result.__dict__
            report.data['setup'] = setup
            report.recommendation = "SHORT_CANDIDATE" if result.is_bearish else "NOT_BEARISH"

        except Exception as e:
            logger.error(f"خطا در تحلیل نزولی {symbol}: {e}")
            report.errors.append(str(e))

        return report

    def _calculate_score(self, result: BearishResult, trend: Dict) -> float:
        """امتیاز نزولی 0-100"""
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

        # تأییدها (20%)
        score += min(len(result.confirmations) * 5, 20)

        return min(score, 100)
