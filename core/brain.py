"""
مغز مرکزی (Central Brain) - نسخه LLM
- دریافت خروجی همه ایجنت‌ها
- استدلال با GLM-4
- تشخیص تناقض
- تصمیم نهایی: LONG / SHORT / WAIT / NO_TRADE

نسخه 2: استفاده واقعی از LLM به‌جای if/else
"""
import sys, os, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List
from core.data_models import (
    AgentReport, FinalDecision, Decision,
    BullishResult, BearishResult, RiskAssessment, BacktestResult
)
from llm_service import get_llm
import config

logger = logging.getLogger(__name__)


class CentralBrain:
    """مغز مرکزی با LLM (GLM-4)"""

    def __init__(self):
        self.llm = get_llm()
        self.system_prompt = """تو یک تحلیلگر ارشد بازار ارزهای دیجیتال هستی با تخصص در:
- تحلیل تکنیکال (SMC, Order Block, BOS/CHoCH)
- تحلیل بنیادی (اخبار, رویدادها)
- تحلیل جریان نقدینگی (Volume Flow, OI, Funding)
- مدیریت ریسک

وظیفه تو: جمع‌بندی تحلیل‌های 6 ایجنت تخصصی و تصمیم‌گیری نهایی.

قواعد تصمیم‌گیری:
1. LONG: فقط اگر تحلیل صعودی قوی‌تر از نزولی، ریسک تأیید شده، بک‌تست مثبت
2. SHORT: فقط اگر تحلیل نزولی قوی‌تر از صعودی، ریسک تأیید شده، بک‌تست مثبت
3. WAIT: اگر تأییدهای کافی نیست اما پتانسیل وجود دارد
4. NO_TRADE: اگر تناقض اساسی، ریسک بالا، یا داده ضعیف

مهم:
- اگر تحلیل صعودی و نزولی تناقض دارند، WAIT یا NO_TRADE
- اگر ریسک رد شده، NO_TRADE
- اگر بک‌تست Win Rate زیر 40%، WAIT
- کیفیت داده را ارزیابی کن
- تناقض بین ایجنت‌ها را تشخیص بده

پاسخ را در فرمت JSON با ساختار زیر بده:
{
  "decision": "LONG" یا "SHORT" یا "WAIT" یا "NO_TRADE",
  "confidence": 0.0 تا 1.0,
  "reasoning": "استدلال کامل به فارسی",
  "contradictions": ["تناقض‌های شناسایی شده"],
  "data_quality": "good" یا "moderate" یا "poor",
  "key_factors": ["فاکتورهای کلیدی تصمیم"],
  "warnings": ["هشدارهای مهم"]
}"""

    def decide(self, coin: Dict, market_report: AgentReport,
               fundamental_report: AgentReport, bullish_report: AgentReport,
               bearish_report: AgentReport, risk_report: AgentReport,
               backtest_report: AgentReport) -> FinalDecision:
        """
        تصمیم‌گیری نهایی با LLM
        """
        symbol = coin['symbol']
        decision = FinalDecision(symbol=symbol)

        try:
            # ساخت prompt با همه داده‌ها
            prompt = self._build_prompt(
                coin, market_report, fundamental_report,
                bullish_report, bearish_report, risk_report, backtest_report
            )

            # درخواست از LLM
            logger.info(f"  🧠 مغز مرکزی در حال استدلال برای {symbol}...")
            llm_response = self.llm.chat_json(prompt, self.system_prompt)

            if llm_response and 'decision' in llm_response:
                # parse پاسخ LLM
                decision_str = llm_response.get('decision', 'WAIT').upper()
                try:
                    decision.decision = Decision(decision_str)
                except ValueError:
                    decision.decision = Decision.WAIT

                decision.confidence = float(llm_response.get('confidence', 0.3))
                decision.brain_reasoning = llm_response.get('reasoning', '')
                decision.final_analysis = decision.brain_reasoning

                # تنظیم پارامترهای معامله
                if decision.decision == Decision.LONG:
                    self._set_trade_params(decision, bullish_report, 'LONG')
                elif decision.decision == Decision.SHORT:
                    self._set_trade_params(decision, bearish_report, 'SHORT')

                # قدرت سیگنال
                market_score = market_report.score
                dir_score = bullish_report.score if decision.decision == Decision.LONG else bearish_report.score
                decision.signal_strength = self._determine_strength(market_score, dir_score)

                logger.info(f"  🧠 تصمیم: {decision.decision.value} ({decision.confidence:.0%})")
            else:
                # fallback به rule-based اگر LLM کار نکرد
                logger.warning(f"  ⚠ LLM پاسخ نداد، استفاده از fallback")
                decision = self._fallback_decide(
                    coin, market_report, fundamental_report,
                    bullish_report, bearish_report, risk_report, backtest_report
                )

            # خلاصه‌ها
            decision.market_scan_summary = self._summarize_market(market_report)
            decision.fundamental_summary = self._summarize_fundamental(fundamental_report)
            decision.bullish_summary = self._summarize_bullish(bullish_report)
            decision.bearish_summary = self._summarize_bearish(bearish_report)
            decision.risk_summary = self._summarize_risk(risk_report)
            decision.backtest_summary = self._summarize_backtest(backtest_report)

            # دلایل
            decision.reasons_pro = self._collect_pro_reasons([
                market_report, fundamental_report, bullish_report
            ])
            decision.reasons_con = self._collect_con_reasons([
                market_report, fundamental_report, bearish_report, risk_report
            ])

        except Exception as e:
            logger.error(f"خطا در تصمیم‌گیری LLM {symbol}: {e}")
            decision = self._fallback_decide(
                coin, market_report, fundamental_report,
                bullish_report, bearish_report, risk_report, backtest_report
            )

        return decision

    def _build_prompt(self, coin: Dict, market_report: AgentReport,
                      fundamental_report: AgentReport, bullish_report: AgentReport,
                      bearish_report: AgentReport, risk_report: AgentReport,
                      backtest_report: AgentReport) -> str:
        """ساخت prompt با همه داده‌های ایجنت‌ها"""

        prompt = f"""تحلیل کامل ارز {coin.get('base', '')} ({coin.get('name', '')})

=== داده‌های بازار ===
قیمت فعلی: {coin.get('current_price', 'N/A')}
مارکت کپ: ${coin.get('market_cap', 0)/1e6:.0f}M
تغییر 24h: {coin.get('price_change_24h', 0):.1f}%

=== Agent 1: Market Scanner ===
امتیاز: {market_report.score:.0f}/100
دلایل: {json.dumps(market_report.reasons_pro + market_report.reasons_con, ensure_ascii=False)}

=== Agent 2: Fundamental Analyst ===
امتیاز: {fundamental_report.score:.0f}/100
اخبار: {fundamental_report.data.get('fundamental_result', {}).get('news_count', 0)} مورد
Sentiment: {fundamental_report.data.get('fundamental_result', {}).get('news_sentiment', 0):.2f}
رویدادها: {fundamental_report.data.get('fundamental_result', {}).get('events_impact', 'low')}

=== Agent 3: Bullish Analyst ===
امتیاز: {bullish_report.score:.0f}/100
توصیه: {bullish_report.recommendation}
تأییدها: {json.dumps(bullish_report.reasons_pro, ensure_ascii=False)}
Entry: {bullish_report.data.get('bullish_result', {}).get('entry_price', 0)}
Stop: {bullish_report.data.get('bullish_result', {}).get('stop_loss', 0)}
RR: 1:{bullish_report.data.get('bullish_result', {}).get('risk_reward', 0):.1f}

=== Agent 4: Bearish Analyst ===
امتیاز: {bearish_report.score:.0f}/100
توصیه: {bearish_report.recommendation}
تأییدها: {json.dumps(bearish_report.reasons_pro, ensure_ascii=False)}
Entry: {bearish_report.data.get('bearish_result', {}).get('entry_price', 0)}
Stop: {bearish_report.data.get('bearish_result', {}).get('stop_loss', 0)}
RR: 1:{bearish_report.data.get('bearish_result', {}).get('risk_reward', 0):.1f}

=== Agent 5: Risk Manager ===
تأیید: {risk_report.data.get('risk_assessment', {}).get('approved', False)}
ریسک: {risk_report.data.get('risk_assessment', {}).get('risk_score', 0):.0f}/100
RR: 1:{risk_report.data.get('risk_assessment', {}).get('risk_reward', 0):.1f}
استاپ: {risk_report.data.get('risk_assessment', {}).get('stop_distance_pct', 0):.1f}%

=== Agent 6: Backtester ===
Win Rate: {backtest_report.data.get('backtest_result', {}).get('win_rate', 0):.1f}%
Profit Factor: {backtest_report.data.get('backtest_result', {}).get('profit_factor', 0):.2f}
تأیید: {backtest_report.data.get('backtest_result', {}).get('backtest_approved', False)}

بر اساس این داده‌ها، تصمیم نهایی را با استدلال کامل ارائه بده."""

        return prompt

    def _fallback_decide(self, coin, market, fund, bull, bear, risk, bt) -> FinalDecision:
        """تصمیم‌گیری fallback (rule-based) در صورت خطای LLM"""
        decision = FinalDecision(symbol=coin['symbol'])

        bull_score = bull.score
        bear_score = bear.score
        risk_approved = risk.data.get('risk_assessment', {}).get('approved', False)
        bt_approved = bt.data.get('backtest_result', {}).get('backtest_approved', False)
        bt_wr = bt.data.get('backtest_result', {}).get('win_rate', 0)

        if abs(bull_score - bear_score) < 10:
            decision.decision = Decision.WAIT
            decision.confidence = 0.3
        elif bull_score > bear_score:
            if risk_approved and bt_approved and bt_wr >= 40:
                decision.decision = Decision.LONG
                decision.confidence = min(bull_score / 100, 1.0)
            else:
                decision.decision = Decision.WAIT if bt_wr >= 40 else Decision.NO_TRADE
                decision.confidence = 0.4
        else:
            if risk_approved and bt_approved and bt_wr >= 40:
                decision.decision = Decision.SHORT
                decision.confidence = min(bear_score / 100, 1.0)
            else:
                decision.decision = Decision.WAIT if bt_wr >= 40 else Decision.NO_TRADE
                decision.confidence = 0.4

        decision.brain_reasoning = f"تصمیم fallback: {decision.decision.value} (LLM در دسترس نبود)"
        decision.final_analysis = decision.brain_reasoning

        if decision.decision == Decision.LONG:
            self._set_trade_params(decision, bull, 'LONG')
        elif decision.decision == Decision.SHORT:
            self._set_trade_params(decision, bear, 'SHORT')

        return decision

    def _set_trade_params(self, decision: FinalDecision, report: AgentReport, direction: str):
        """تنظیم پارامترهای معامله"""
        result_key = 'bullish_result' if direction == 'LONG' else 'bearish_result'
        result_data = report.data.get(result_key, {})

        decision.entry_price = result_data.get('entry_price', 0)
        decision.stop_loss = result_data.get('stop_loss', 0)
        targets = result_data.get('targets', [])
        decision.target_1 = targets[0] if len(targets) > 0 else 0
        decision.target_2 = targets[1] if len(targets) > 1 else 0
        decision.target_3 = targets[2] if len(targets) > 2 else 0
        decision.risk_reward = result_data.get('risk_reward', 0)

    def _determine_strength(self, market_score: float, direction_score: float) -> str:
        combined = (market_score + direction_score) / 2
        if combined >= 70:
            return "قوی"
        elif combined >= 50:
            return "متوسط"
        elif combined >= 30:
            return "ضعیف"
        else:
            return "خنثی"

    def _summarize_market(self, report: AgentReport) -> str:
        scan = report.data.get('scan_result', {})
        reasons = scan.get('reasons', [])
        return f"امتیاز: {report.score:.0f}/100 | {' | '.join(reasons[:3])}"

    def _summarize_fundamental(self, report: AgentReport) -> str:
        fund = report.data.get('fundamental_result', {})
        return f"امتیاز: {report.score:.0f}/100 | اخبار: {fund.get('news_count', 0)} | رویداد: {fund.get('events_impact', 'low')}"

    def _summarize_bullish(self, report: AgentReport) -> str:
        bull = report.data.get('bullish_result', {})
        return f"امتیاز: {report.score:.0f}/100 | RR: 1:{bull.get('risk_reward', 0):.1f}"

    def _summarize_bearish(self, report: AgentReport) -> str:
        bear = report.data.get('bearish_result', {})
        return f"امتیاز: {report.score:.0f}/100 | RR: 1:{bear.get('risk_reward', 0):.1f}"

    def _summarize_risk(self, report: AgentReport) -> str:
        risk = report.data.get('risk_assessment', {})
        return f"{'✅' if risk.get('approved') else '❌'} | ریسک: {risk.get('risk_score', 0):.0f}/100"

    def _summarize_backtest(self, report: AgentReport) -> str:
        bt = report.data.get('backtest_result', {})
        return f"WR: {bt.get('win_rate', 0):.1f}% | PF: {bt.get('profit_factor', 0):.2f}"

    def _collect_pro_reasons(self, reports: List[AgentReport]) -> List[str]:
        all_pros = []
        for r in reports:
            all_pros.extend(r.reasons_pro[:3])
        return all_pros[:10]

    def _collect_con_reasons(self, reports: List[AgentReport]) -> List[str]:
        all_cons = []
        for r in reports:
            all_cons.extend(r.reasons_con[:3])
        return all_cons[:10]
