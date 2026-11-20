"""
Agent 5: مدیر ریسک (Risk Manager) - با Portfolio Context
- بررسی ریسک معاملات پیشنهادی
- Risk/Reward واقعی
- حجم پوزیشن
- همبستگی معاملات با پوزیشن‌های فعلی
- شرایط بازار
- تأیید یا رد معاملات

الهام از TradingAgents - Portfolio-aware risk management
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Optional
from core.data_models import RiskAssessment, AgentReport
import config
import logging

logger = logging.getLogger(__name__)

# همبستگی تقریبی ارزها با یکدیگر (0-1)
CORRELATION_MATRIX = {
    'BTC': {'ETH': 0.85, 'SOL': 0.75, 'BNB': 0.70, 'XRP': 0.65, 'ADA': 0.60},
    'ETH': {'BTC': 0.85, 'SOL': 0.70, 'AVAX': 0.75, 'LINK': 0.65},
    'SOL': {'BTC': 0.75, 'ETH': 0.70, 'AVAX': 0.65},
}


class RiskManagerAgent:
    """Agent 5: مدیر ریسک با Portfolio Context"""

    def __init__(self):
        self.active_positions = []  # پوزیشن‌های فعال
        self.max_risk_per_trade = 2.0
        self.min_rr = 2.0
        self.max_stop_pct = 15.0
        self.max_concurrent_same_direction = 3
        self.max_portfolio_risk = 6.0  # حداکثر ریسک کل سبد %
        self.max_correlated_positions = 2  # حداکثر پوزیشن همبسته

    def set_portfolio(self, positions: List[Dict]):
        """
        تنظیم پوزیشن‌های فعلی سبد

        positions = [
            {'symbol': 'BTC/USDT', 'direction': 'LONG', 'size_pct': 2.0, 'entry': 65000},
            {'symbol': 'ETH/USDT', 'direction': 'LONG', 'size_pct': 1.5, 'entry': 1800},
        ]
        """
        self.active_positions = positions
        logger.info(f"Portfolio تنظیم شد: {len(positions)} پوزیشن فعال")

    def assess(self, coin: Dict, direction: str, entry: float, stop: float,
               targets: List[float], bullish_report: AgentReport = None,
               bearish_report: AgentReport = None, market_report: AgentReport = None) -> AgentReport:
        """
        ارزیابی ریسک یک معامله با در نظر گرفتن portfolio
        """
        symbol = coin['symbol']
        base = coin['base']
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

            # 3. بررسی استاپ وسیع
            if assessment.stop_distance_pct > self.max_stop_pct:
                assessment.rejection_reasons.append(
                    f"استاپ وسیع: {assessment.stop_distance_pct:.1f}% (حداکثر {self.max_stop_pct}%)"
                )
                report.reasons_con.append(f"استاپ وسیع: {assessment.stop_distance_pct:.1f}%")

            # 4. محاسبه حجم پوزیشن
            if assessment.stop_distance_pct > 0:
                assessment.position_size_recommendation = min(
                    self.max_risk_per_trade / assessment.stop_distance_pct, 100
                )

            # 5. بررسی همبستگی با portfolio فعلی
            portfolio_risk = 0
            same_direction_count = 0
            correlated_count = 0

            for pos in self.active_positions:
                pos_risk = pos.get('size_pct', 0)
                portfolio_risk += pos_risk

                if pos.get('direction') == direction:
                    same_direction_count += 1

                # بررسی همبستگی
                pos_base = pos.get('symbol', '').replace('/USDT', '')
                correlation = self._get_correlation(base, pos_base)
                if correlation > 0.6:
                    correlated_count += 1
                    if correlated_count >= self.max_correlated_positions:
                        assessment.correlation_warning = True
                        assessment.warnings.append(
                            f"همبستگی بالا با {pos_base} ({correlation:.0%})"
                        )
                        report.reasons_con.append(f"همبستگی بالا با {pos_base}")

            # 6. بررسی ریسک کل سبد
            if portfolio_risk + assessment.position_size_recommendation > self.max_portfolio_risk:
                assessment.warnings.append(
                    f"ریسک سبد بالا: {portfolio_risk:.1f}% + {assessment.position_size_recommendation:.1f}% = {portfolio_risk + assessment.position_size_recommendation:.1f}%"
                )
                report.reasons_con.append(f"ریسک سبد زیاد: {portfolio_risk:.1f}%")

            # 7. بررسی تعداد معاملات هم‌جهت
            if same_direction_count >= self.max_concurrent_same_direction:
                assessment.correlation_warning = True
                assessment.warnings.append(
                    f"تعداد معاملات {direction} زیاد: {same_direction_count}"
                )
                report.reasons_con.append(f"معاملات {direction} زیاد: {same_direction_count}")

            # 8. شرایط بازار
            market_condition = self._assess_market_condition(market_report)
            assessment.market_condition = market_condition
            if market_condition == "HIGH_VOLATILITY":
                assessment.warnings.append("نوسان بالا")
                report.reasons_con.append("نوسان بازار بالا")

            # 9. بررسی تناقض تحلیل‌ها
            if bullish_report and bearish_report:
                score_diff = abs(bullish_report.score - bearish_report.score)
                if score_diff < 10:
                    assessment.warnings.append("تناقض تحلیل صعودی و نزولی")
                    report.reasons_con.append("تناقض تحلیل‌ها")

            # 10. محاسبه ریسک کلی
            assessment.risk_score = self._calculate_risk_score(assessment, portfolio_risk)

            # 11. تصمیم نهایی
            if len(assessment.rejection_reasons) == 0 and assessment.risk_score < 70:
                assessment.approved = True
                report.reasons_pro.append("تأیید شد - ریسک قابل قبول")
                if portfolio_risk > 0:
                    report.reasons_pro.append(f"ریسک سبد: {portfolio_risk:.1f}%")
            else:
                assessment.approved = False
                report.reasons_con.extend(assessment.rejection_reasons)

            report.score = 100 - assessment.risk_score
            report.confidence = 0.8 if assessment.approved else 0.3
            report.data['risk_assessment'] = assessment.__dict__
            report.recommendation = "APPROVED" if assessment.approved else "REJECTED"

        except Exception as e:
            logger.error(f"خطا در ارزیابی ریسک {symbol}: {e}")
            report.errors.append(str(e))

        return report

    def _get_correlation(self, base1: str, base2: str) -> float:
        """دریافت همبستگی بین دو ارز"""
        if base1 == base2:
            return 1.0
        correlations = CORRELATION_MATRIX.get(base1, {})
        return correlations.get(base2, 0.5)  # پیش‌فرض 0.5

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
        return "QUIET"

    def _calculate_risk_score(self, assessment: RiskAssessment, portfolio_risk: float) -> float:
        """محاسبه ریسک 0-100"""
        risk = 0.0

        # RR
        if assessment.risk_reward >= 3:
            risk += 5
        elif assessment.risk_reward >= 2:
            risk += 15
        elif assessment.risk_reward >= 1.5:
            risk += 30
        else:
            risk += 50

        # استاپ
        if assessment.stop_distance_pct < 3:
            risk += 5
        elif assessment.stop_distance_pct < 7:
            risk += 15
        elif assessment.stop_distance_pct < 12:
            risk += 30
        else:
            risk += 50

        # همبستگی
        if assessment.correlation_warning:
            risk += 20

        # شرایط بازار
        if assessment.market_condition == "HIGH_VOLATILITY":
            risk += 20
        elif assessment.market_condition == "QUIET":
            risk += 10

        # ریسک سبد
        if portfolio_risk > 4:
            risk += 15
        elif portfolio_risk > 2:
            risk += 8

        return min(risk, 100)
