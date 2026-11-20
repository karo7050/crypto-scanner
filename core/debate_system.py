"""
سیستم مناظره بین تحلیلگر صعودی و نزولی
Debate System - Bullish vs Bearish

الهام گرفته از TradingAgents (github.com/tauricresearch/tradingagents)

جریان:
1. هر تحلیلگر مستقل تحلیل می‌کند
2. تحلیلگر صعودی تحلیل نزولی را رد می‌کند (با LLM)
3. تحلیلگر نزولی تحلیل صعودی را رد می‌کند (با LLM)
4. چند راند مناظره
5. مغز مرکزی نتیجه نهایی را می‌گیرد
"""
import sys, os, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Tuple
from llm_service import get_llm
from core.data_models import AgentReport
import config

logger = logging.getLogger(__name__)


class DebateSystem:
    """سیستم مناظره بین Bullish و Bearish با LLM"""

    def __init__(self, max_rounds: int = 2):
        self.llm = get_llm()
        self.max_rounds = max_rounds

    def debate(self, coin: Dict, bullish_report: AgentReport,
               bearish_report: AgentReport) -> Tuple[AgentReport, AgentReport, Dict]:
        """
        اجرای مناظره بین تحلیلگر صعودی و نزولی

        برمی‌گرداند:
        - bullish_report به‌روزرسانی شده
        - bearish_report به‌روزرسانی شده
        - debate_summary خلاصه مناظره
        """
        symbol = coin['symbol']
        base = coin['base']

        debate_history = []
        bull_score_original = bullish_report.score
        bear_score_original = bearish_report.score

        for round_num in range(self.max_rounds):
            logger.info(f"  💬 مناظره راند {round_num + 1}/{self.max_rounds} برای {base}...")

            bull_adj = 0
            bear_adj = 0

            # راند 1: Bullish به Bearish حمله می‌کند
            try:
                bull_rebuttal = self._bullish_rebuts_bearish(
                    coin, bullish_report, bearish_report, debate_history
                )

                if bull_rebuttal and bull_rebuttal.get('argument'):
                    debate_history.append({
                        'round': round_num + 1,
                        'speaker': 'bullish',
                        'argument': bull_rebuttal.get('argument', ''),
                    })

                    bear_adj = bull_rebuttal.get('bearish_score_adjustment', 0)
                    if isinstance(bear_adj, (int, float)):
                        bearish_report.score = max(0, bearish_report.score + bear_adj)
                        if bear_adj < 0:
                            bearish_report.reasons_con.append(f"رد مناظره: {bull_rebuttal.get('argument', '')[:60]}")
            except Exception as e:
                logger.debug(f"مناظره bullish ناموفق: {e}")

            # راند 2: Bearish به Bullish حمله می‌کند
            try:
                bear_rebuttal = self._bearish_rebuts_bullish(
                    coin, bearish_report, bullish_report, debate_history
                )

                if bear_rebuttal and bear_rebuttal.get('argument'):
                    debate_history.append({
                        'round': round_num + 1,
                        'speaker': 'bearish',
                        'argument': bear_rebuttal.get('argument', ''),
                    })

                    bull_adj = bear_rebuttal.get('bullish_score_adjustment', 0)
                    if isinstance(bull_adj, (int, float)):
                        bullish_report.score = max(0, bullish_report.score + bull_adj)
                        if bull_adj < 0:
                            bullish_report.reasons_con.append(f"رد مناظره: {bear_rebuttal.get('argument', '')[:60]}")
            except Exception as e:
                logger.debug(f"مناظره bearish ناموفق: {e}")

            # اگر LLM کار نکرد یا تغییر کم است، قطع کن
            if abs(bull_adj) < 2 and abs(bear_adj) < 2:
                logger.info(f"  💬 مناظره پایان یافت")
                break

        # خلاصه مناظره
        debate_summary = self._summarize_debate(
            coin, debate_history, bull_score_original, bear_score_original,
            bullish_report.score, bearish_report.score
        )

        return bullish_report, bearish_report, debate_summary

    def _bullish_rebuts_bearish(self, coin: Dict, bull: AgentReport,
                                bear: AgentReport, history: list) -> Dict:
        """تحلیلگر صعودی تحلیل نزولی را رد می‌کند"""
        prompt = f"""تو یک تحلیلگر صعودی (Bullish) هستی. تحلیلگر نزولی این استدلال‌ها را برای ارز {coin['base']} آورده:

تحلیل نزولی (امتیاز: {bear.score:.0f}/100):
دلایل نزولی: {json.dumps(bear.reasons_pro, ensure_ascii=False)}
دلایل ضد نزولی: {json.dumps(bear.reasons_con, ensure_ascii=False)}

تحلیل صعودی تو (امتیاز: {bull.score:.0f}/100):
دلایل صعودی: {json.dumps(bull.reasons_pro, ensure_ascii=False)}

وظیفه تو: استدلال‌های نزولی را رد کن یا ضعیفشان نشان بده.

پاسخ در JSON:
{{
  "argument": "استدلال رد اصلی",
  "bearish_score_adjustment": -5 تا 0 (چقدر امتیاز نزولی کاهش یابد),
  "confidence": 0 تا 1
}}"""

        system = "تو یک تحلیلگر صعودی حرفه‌ای هستی. با دلیل و منطق استدلال‌های نزولی را رد کن."

        return self.llm.chat_json(prompt, system) or {}

    def _bearish_rebuts_bullish(self, coin: Dict, bear: AgentReport,
                                bull: AgentReport, history: list) -> Dict:
        """تحلیلگر نزولی تحلیل صعودی را رد می‌کند"""
        prompt = f"""تو یک تحلیلگر نزولی (Bearish) هستی. تحلیلگر صعودی این استدلال‌ها را برای ارز {coin['base']} آورده:

تحلیل صعودی (امتیاز: {bull.score:.0f}/100):
دلایل صعودی: {json.dumps(bull.reasons_pro, ensure_ascii=False)}
دلایل ضد صعودی: {json.dumps(bull.reasons_con, ensure_ascii=False)}

تحلیل نزولی تو (امتیاز: {bear.score:.0f}/100):
دلایل نزولی: {json.dumps(bear.reasons_pro, ensure_ascii=False)}

وظیفه تو: استدلال‌های صعودی را رد کن یا ضعیفشان نشان بده.

پاسخ در JSON:
{{
  "argument": "استدلال رد اصلی",
  "bullish_score_adjustment": -5 تا 0 (چقدر امتیاز صعودی کاهش یابد),
  "confidence": 0 تا 1
}}"""

        system = "تو یک تحلیلگر نزولی حرفه‌ای هستی. با دلیل و منطق استدلال‌های صعودی را رد کن."

        return self.llm.chat_json(prompt, system) or {}

    def _summarize_debate(self, coin: Dict, history: list,
                          bull_orig: float, bear_orig: float,
                          bull_final: float, bear_final: float) -> Dict:
        """خلاصه مناظره"""
        winner = 'bullish' if bull_final > bear_final else 'bearish' if bear_final > bull_final else 'tie'
        score_change_bull = bull_final - bull_orig
        score_change_bear = bear_final - bear_orig

        return {
            'symbol': coin['symbol'],
            'rounds': len(history),
            'history': history,
            'bullish_score_before': bull_orig,
            'bullish_score_after': bull_final,
            'bearish_score_before': bear_orig,
            'bearish_score_after': bear_final,
            'winner': winner,
            'score_change_bull': score_change_bull,
            'score_change_bear': score_change_bear,
            'summary': f"مناظره {len(history)} راند | برنده: {winner} | تغییر صعودی: {score_change_bull:+.0f} | تغییر نزولی: {score_change_bear:+.0f}",
        }
