"""
مغز مرکزی - بررسی و استدلال نهایی
Central Brain - Review Only

می‌تواند:
- پیشنهاد اسکنر را بررسی کند
- به WAIT تغییر دهد اگر مشکلی ببیند
- استدلال فارسی تولید کند
- اخبار را در نظر بگیرد

نمی‌تواند:
- سیگنال جدید بسازد
- NO_TRADE را به LONG/SHORT تغییر دهد
"""
import sys, os, json, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict
from llm_service import get_llm
from core.data_models import FinalDecision, Decision
import config

logger = logging.getLogger(__name__)


class ReviewBrain:
    """مغز بررسی - فقط review، نه تصمیم‌گیری"""

    def __init__(self):
        self.llm = get_llm()

    def review(self, decision: FinalDecision) -> FinalDecision:
        """
        بررسی تصمیم اسکنر با LLM
        - اگر مشکلی ببیند → WAIT
        - اگر تأیید کند → همان تصمیم
        - استدلال فارسی اضافه می‌کند
        """
        if decision.decision in [Decision.NO_TRADE, Decision.WAIT]:
            # برای WAIT/NO_TRADE فقط استدلال اضافه کن
            return decision

        try:
            prompt = self._build_prompt(decision)
            logger.info(f"  🧠 بررسی {decision.symbol}...")

            response = self.llm.chat_json(prompt, self._system_prompt())

            if response and 'review' in response:
                review_result = response.get('review', 'confirm')
                reasoning = response.get('reasoning', '')
                concerns = response.get('concerns', [])

                if review_result == 'reject':
                    # مغز رد کرد → WAIT
                    old_decision = decision.decision.value
                    decision.decision = Decision.WAIT
                    decision.confidence = 0.4
                    decision.brain_reasoning = f"مغز: WAIT - {reasoning[:200]}"
                    if concerns:
                        decision.reasons_con.extend(concerns[:3])
                    logger.info(f"  🧠 مغز رد کرد: {old_decision} → WAIT")
                else:
                    # تأیید شد
                    decision.brain_reasoning = f"تأیید مغز: {decision.decision.value} - {reasoning[:200]}"
                    if concerns:
                        decision.reasons_con.extend(concerns[:2])
                    logger.info(f"  🧠 مغز تأیید کرد: {decision.decision.value}")
            else:
                # LLM پاسخ نداد → تصمیم اسکنر باقی می‌ماند
                decision.brain_reasoning = f"اسکنر: {decision.decision.value} (مغز در دسترس نبود)"

        except Exception as e:
            logger.warning(f"  ⚠ خطای مغز: {e}")
            decision.brain_reasoning = f"اسکنر: {decision.decision.value} (مغز خطا)"

        decision.final_analysis = decision.brain_reasoning
        return decision

    def _system_prompt(self) -> str:
        return """تو یک تحلیلگر ارشد بازار کریپتو هستی. وظیفه تو بررسی تصمیم اسکنر است.

قواعد:
1. اگر تصمیم درست است → "confirm"
2. اگر مشکلی هست → "reject" (تبدیل به WAIT)
3. اگر RSI اشباع فروش/خرید است و جهت مخالف پیشنهاد شده → "reject"
4. اگر روند 4H با جهت پیشنهاد متناقض است → "reject"
5. اگر تناقض واضح هست → "reject"

پاسخ در JSON:
{
  "review": "confirm" یا "reject",
  "reasoning": "استدلال کوتاه به فارسی",
  "concerns": ["نگرانی‌ها"]
}"""

    def _build_prompt(self, d: FinalDecision) -> str:
        data = d.data if hasattr(d, 'data') else {}
        return f"""بررسی تصمیم برای {d.symbol}:

تصمیم اسکنر: {d.decision.value}
اعتماد: {d.confidence:.0%}
قدرت: {d.signal_strength}

امتیازها: لانگ={data.get('long_score', 0):.0f} / شورت={data.get('short_score', 0):.0f}
RSI: 1H={data.get('rsi_1h', 0):.0f} / 4H={data.get('rsi_4h', 0):.0f}

دلایل موافق: {json.dumps(d.reasons_pro[:5], ensure_ascii=False)}
دلایل مخالف: {json.dumps(d.reasons_con[:3], ensure_ascii=False)}

Entry: {d.entry_price} | Stop: {d.stop_loss} | RR: 1:{d.risk_reward:.1f}

آیا این تصمیم درست است؟"""
