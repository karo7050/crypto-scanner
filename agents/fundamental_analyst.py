"""
Agent 2: تحلیلگر بنیادی (Fundamental Analyst) - نسخه LLM
- اخبار با تحلیل NLP واقعی (GLM-4)
- رویدادهای اقتصادی
- سلامت پروژه
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict
from news_analyzer import NewsAnalyzer
from events_calendar import EconomicEventsCalendar
from core.data_models import FundamentalResult, AgentReport
from llm_service import get_llm
import config
import logging

logger = logging.getLogger(__name__)


class FundamentalAnalystAgent:
    """Agent 2: تحلیلگر بنیادی با LLM"""

    def __init__(self):
        self.calendar = EconomicEventsCalendar()
        self.llm = get_llm()
        # کش اخبار یک بار fetch می‌شود
        NewsAnalyzer.fetch_all_news(max_per_source=30)

    def analyze(self, coin: Dict) -> AgentReport:
        """
        تحلیل بنیادی یک ارز با LLM
        """
        symbol = coin['symbol']
        base = coin['base']
        name = coin.get('name', base)

        report = AgentReport(
            agent_name="Fundamental Analyst",
            coin_symbol=symbol,
            timestamp=config.tehran_now_str(),
        )

        result = FundamentalResult(symbol=symbol)

        try:
            # 1. دریافت اخبار
            news_data = NewsAnalyzer.get_news_for_coin(base, name)

            # 2. تحلیل اخبار با LLM (به‌جای keyword matching)
            if news_data:
                result.news_count = news_data.get('total_news', 0)
                result.positive_news = news_data.get('positive_count', 0)
                result.negative_news = news_data.get('negative_count', 0)
                result.news_sentiment = news_data.get('sentiment_score', 0) / 100

                # همیشه اخبار در گزارش نمایش داده شود
                top_news = news_data.get('top_news', [])
                if top_news:
                    result.key_factors.append(f"اخبار اخیر: {len(top_news)} مورد")
                    for news in top_news[:3]:
                        title = news.get('title', '')[:60]
                        source = news.get('source', '')
                        sentiment = news.get('sentiment', '')
                        result.key_factors.append(f"[{source}] {title} ({sentiment})")

                # تلاش با LLM برای تحلیل عمیق‌تر
                if top_news:
                    llm_analysis = self._analyze_news_with_llm(base, top_news)
                    if llm_analysis:
                        result.news_sentiment = llm_analysis.get('sentiment', result.news_sentiment)
                        result.positive_news = llm_analysis.get('positive_count', result.positive_news)
                        result.negative_news = llm_analysis.get('negative_count', result.negative_news)
                        report.data['llm_news_analysis'] = llm_analysis

                if result.news_sentiment > 0.3:
                    report.reasons_pro.append(f"اخبار مثبت (sentiment: {result.news_sentiment:.2f})")
                elif result.news_sentiment < -0.3:
                    report.reasons_con.append(f"اخبار منفی (sentiment: {result.news_sentiment:.2f})")

                report.data['news'] = news_data

            # 3. رویدادهای اقتصادی
            events = self.calendar.get_upcoming_events(hours_ahead=24)
            guidance = self.calendar.get_event_guidance(events)

            result.events_impact = guidance.get('risk_level', 'low')
            if guidance.get('has_events'):
                nearest = guidance.get('nearest_event', {})
                result.warnings.append(f"رویداد: {nearest.get('name', '')}")
                if result.events_impact in ['critical', 'high']:
                    report.reasons_con.append(f"رویداد پرریسک: {nearest.get('name', '')}")

            report.data['events'] = guidance

            # 4. اطلاعات بازار
            market_cap = coin.get('market_cap', 0)
            if market_cap > 1_000_000_000:
                result.key_factors.append("مارکت کپ بالا (>$1B)")
                result.project_health = "good"
            elif market_cap > 100_000_000:
                result.project_health = "moderate"

            # 5. محاسبه امتیاز
            result.fundamental_score = self._calculate_score(result)
            report.score = result.fundamental_score
            report.confidence = min(result.fundamental_score / 100, 1.0)
            report.data['fundamental_result'] = result.__dict__
            report.recommendation = "FUNDAMENTAL_COMPLETE"

        except Exception as e:
            logger.error(f"خطا در تحلیل بنیادی {symbol}: {e}")
            report.errors.append(str(e))

        return report

    def _analyze_news_with_llm(self, coin_name: str, news_list: list) -> Dict:
        """
        تحلیل اخبار با GLM-4 - NLP واقعی به‌جای keyword matching
        """
        if not news_list:
            return None

        # ساخت خلاصه اخبار برای LLM
        news_summaries = []
        for news in news_list[:8]:  # 8 خبر اخیر
            title = news.get('title', '')
            source = news.get('source', '')
            news_summaries.append(f"- [{source}] {title}")

        news_text = '\n'.join(news_summaries)

        prompt = f"""اخبار اخیر ارز {coin_name} را تحلیل کن و sentiment بازار را ارزیابی کن:

اخبار:
{news_text}

تحلیل کن:
1. sentiment کلی مثبت، منفی یا خنثی است؟ (-1 تا +1)
2. چند خبر مثبت و چند خبر منفی؟
3. فاکتورهای کلیدی مؤثر بر قیمت چیست؟
4. هشدارهای مهم چیست؟

پاسخ در فرمت JSON:
{{
  "sentiment": -1 تا +1,
  "positive_count": عدد,
  "negative_count": عدد,
  "key_factors": ["فاکتور1", "فاکتور2"],
  "warnings": ["هشدار1"],
  "summary": "خلاصه کوتاه"
}}"""

        system = "تو یک تحلیلگر ارشد اخبار بازار کریپتو هستی. تحلیل دقیق و واقعی ارائه بده."

        response = self.llm.chat_json(prompt, system)

        if response:
            # نرمال‌سازی sentiment
            sentiment = response.get('sentiment', 0)
            if isinstance(sentiment, str):
                try:
                    sentiment = float(sentiment)
                except ValueError:
                    sentiment = 0
            response['sentiment'] = max(-1, min(1, sentiment))
            return response

        return None

    def _calculate_score(self, result: FundamentalResult) -> float:
        """محاسبه امتیاز بنیادی 0-100"""
        score = 50

        # sentiment (40%)
        score += result.news_sentiment * 20

        # رویدادها (20%)
        if result.events_impact == 'critical':
            score -= 15
        elif result.events_impact == 'high':
            score -= 10
        elif result.events_impact == 'low':
            score += 5

        # مارکت کپ (20%)
        if result.project_health == 'good':
            score += 10
        elif result.project_health == 'moderate':
            score += 5

        # اکوسیستم (20%)
        score += result.ecosystem_score

        return max(0, min(100, score))
