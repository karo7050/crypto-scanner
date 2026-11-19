"""
Agent 5: مدیر ریسک (Risk Manager)
- بررسی ریسک معاملات پیشنهادی
- Risk/Reward واقعی
- حجم پوزیشن
- همبستگی معاملات
- شرایط بازار
- تأیید یا رد معاملات
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List
from core.data_models import RiskAssessment, AgentReport
import config
import logging

logger = logging.getLogger(__name__)


class RiskManagerAgent:
    """Agent 5: مدیر ریسک"""

    def __init__(self):
        self.active_positions = []  # پوزیشن‌های فعال (برای همبستگی)
        self.max_risk_per_trade = 2.0  # حداکثر ریسک 2% سرمایه
        self.min_rr = 2.0  # حداقل RR 1:2
        self.max_stop_pct = 15.0  # حداکثر استاپ 15%
        self.max_concurrent_same_direction = 3  # حداکثر 3 معامله هم‌جهت

    def assess(self, coin: Dict, direction: str, entry: float, stop: float,
               targets: List[float], bullish_report: AgentReport = None,
               bearish_report: AgentReport = None, market_report: AgentReport = None) -> AgentReport:
        """
        ارزیابی ریسک یک معامله پیشنهادی
        """
        symbol = coin['symbol']
        report = AgentReport(
            agent_name="Risk Manager",
            coin_symbol=symbol,
            timestamp=config.tehran_now_str(),
        )

        assessment = RiskAssessment(symbol=symbol)

        try:
            # 1. محاسبه RR واقعی
            if entry > 0 and stop > 0 and targets:
                risk = abs(entry - stop)
                reward = abs(targets[1] - entry) if len(targets) > 1 else abs(targets[0] - entry)
                assessment.risk_reward = reward / risk if risk > 0 else 0
                assessment.stop_distance_pct = (risk / entry) * 100

            # 2. بررسی حداقل RR
            if assessment.risk_reward < self.min_rr:
                assessment.rejection_reasons.append(
                    f"RR پایین: 1:{assessment.risk_reward:.1f} (حداقل 1:{self.min_rr})"
                )
                report.reasons_con.append(f"RR رد شده: 1:{assessment.risk_reward:.1f}")

            # 3. بررسی استاپ بیش از حد وسیع
            if assessment.stop_distance_pct > self.max_stop_pct:
                assessment.rejection_reasons.append(
                    f"استاپ بیش از حد وسیع: {assessment.stop_distance_pct:.1f}% (حداکثر {self.max_stop_pct}%)"
                )
                report.reasons_con.append(f"استاپ وسیع: {assessment.stop_distance_pct:.1f}%")

            # 4. محاسبه حجم پوزیشن
            # فرمول: position_size = (max_risk% * capital) / stop_distance
            if assessment.stop_distance_pct > 0:
                assessment.position_size_recommendation = (
                    self.max_risk_per_trade / assessment.stop_distance_pct
                )
                assessment.position_size_recommendation = min(assessment.position_size_recommendation, 100)

            # 5. بررسی همبستگی
            same_direction_count = sum(1 for p in self.active_positions if p['direction'] == direction)
            if same_direction_count >= self.max_concurrent_same_direction:
                assessment.correlation_warning = True
                assessment.warnings.append(
                    f"تعداد معاملات {direction} فعال زیاد: {same_direction_count}"
                )
                report.reasons_con.append(f"همبستگی: {same_direction_count} معامله {direction} فعال")

            # 6. شرایط بازار
            market_condition = self._assess_market_condition(market_report)
            assessment.market_condition = market_condition

            if market_condition == "HIGH_VOLATILITY":
                assessment.warnings.append("نوسان بالا - احتیاط")
                report.reasons_con.append("نوسان بازار بالا")

            # 7. بررسی تناقض تحلیل‌ها
            if bullish_report and bearish_report:
                bull_score = bullish_report.score
                bear_score = bearish_report.score
                score_diff = abs(bull_score - bear_score)

                if score_diff < 10:
                    assessment.warnings.append("تناقض تحلیل صعودی و نزولی")
                    report.reasons_con.append("تناقض تحلیل‌ها - جهت نامشخص")

            # 8. محاسبه ریسک کلی (0-100, بالاتر = پرریسک)
            assessment.risk_score = self._calculate_risk_score(assessment)

            # 9. تصمیم نهایی
            if len(assessment.rejection_reasons) == 0 and assessment.risk_score < 70:
                assessment.approved = True
                report.reasons_pro.append("معامله تأیید شد - ریسک قابل قبول")
            else:
                assessment.approved = False
                report.reasons_con.extend(assessment.rejection_reasons)

            report.score = 100 - assessment.risk_score  # امتیاز معکوس (100 = کم ریسک)
            report.confidence = 0.8 if assessment.approved else 0.3
            report.data['risk_assessment'] = assessment.__dict__
            report.recommendation = "APPROVED" if assessment.approved else "REJECTED"

        except Exception as e:
            logger.error(f"خطا در ارزیابی ریسک {symbol}: {e}")
            report.errors.append(str(e))

        return report

    def _assess_market_condition(self, market_report: AgentReport) -> str:
        """ارزیابی شرایط بازار"""
        if not market_report:
            return "UNKNOWN"

        scan_data = market_report.data.get('scan_result', {})
        signal_strength = scan_data.get('signal_strength', 0)

        if signal_strength > 70:
            return "HIGH_VOLATILITY"
        elif signal_strength > 40:
            return "ACTIVE"
        elif signal_strength > 20:
            return "NORMAL"
        else:
            return "QUIET"

    def _calculate_risk_score(self, assessment: RiskAssessment) -> float:
        """محاسبه ریسک 0-100"""
        risk = 0.0

        # RR (30%)
        if assessment.risk_reward >= 3:
            risk += 5
        elif assessment.risk_reward >= 2:
            risk += 15
        elif assessment.risk_reward >= 1.5:
            risk += 30
        else:
            risk += 50

        # استاپ (30%)
        if assessment.stop_distance_pct < 3:
            risk += 5
        elif assessment.stop_distance_pct < 7:
            risk += 15
        elif assessment.stop_distance_pct < 12:
            risk += 30
        else:
            risk += 50

        # همبستگی (20%)
        if assessment.correlation_warning:
            risk += 20

        # شرایط بازار (20%)
        if assessment.market_condition == "HIGH_VOLATILITY":
            risk += 20
        elif assessment.market_condition == "QUIET":
            risk += 10

        return min(risk, 100)
