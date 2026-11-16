"""
ماژول اخبار و تحلیل Sentiment
News Sentiment Analyzer Module

دریافت اخبار از RSS feeds رایگان:
- CoinDesk
- Cointelegraph
- The Block (Decrypt)

تحلیل sentiment بر اساس کلمات کلیدی:
- منفی: crash, plunge, hack, exploit, lawsuit, ban, sell-off, liquidation, dump, collapse
- مثبت: rally, surge, breakout, adoption, partnership, upgrade, bull, pump, gain, ETF approval
"""
import requests
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class NewsAnalyzer:
    """تحلیل اخبار کریپتو از RSS feeds رایگان"""

    # RSS feeds رایگان
    RSS_FEEDS = {
        'CoinDesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
        'Cointelegraph': 'https://cointelegraph.com/rss',
        'Decrypt': 'https://decrypt.co/feed',
    }

    # کلمات کلیدی منفی
    NEGATIVE_KEYWORDS = [
        'crash', 'plunge', 'plunges', 'dump', 'dumps', 'collapse', 'collapses',
        'hack', 'hacked', 'exploit', 'breach', 'lawsuit', 'sued', 'ban', 'banned',
        'sell-off', 'selloff', 'liquidation', 'liquidated', 'bear', 'bearish',
        'down', 'drops', 'dropped', 'falls', 'fell', 'decline', 'declines',
        'warning', 'warns', 'risk', 'danger', 'fear', 'panic', 'capitulation',
        'outflow', 'outflows', 'red', 'loss', 'losses', 'delist', 'delisted',
        'fraud', 'scam', 'ponzi', 'sec', 'enforcement', 'investigation',
        'death cross', 'resistance', 'rejection', 'failed', 'failure',
    ]

    # کلمات کلیدی مثبت
    POSITIVE_KEYWORDS = [
        'rally', 'rallies', 'surge', 'surges', 'surging', 'breakout', 'breaks out',
        'adoption', 'adopts', 'partnership', 'partners', 'collaboration',
        'upgrade', 'upgrades', 'launch', 'launches', 'bull', 'bullish',
        'pump', 'pumps', 'gain', 'gains', 'up', 'rises', 'rose', 'rise',
        'approval', 'approved', 'etf', 'inflow', 'inflows', 'green',
        'support', 'holds', 'recovery', 'recovers', 'rebound', 'rebounds',
        'milestone', 'record', 'ath', 'all-time high', 'accumulation',
        'buy', 'buys', 'long', 'upgrade', 'boost', 'boosts', 'surge',
    ]

    # کش اخبار (برای جلوگیری از درخواست مکرر)
    _news_cache = {}
    _cache_time = None

    @classmethod
    def fetch_all_news(cls, max_per_source: int = 30) -> List[Dict]:
        """
        دریافت اخبار از همه RSS feeds
        """
        # اگر کش تازه است (کمتر از 10 دقیقه)، از کش استفاده کن
        now = datetime.now()
        if cls._cache_time and (now - cls._cache_time).seconds < 600:
            return cls._news_cache.get('all', [])

        all_news = []

        for source, url in cls.RSS_FEEDS.items():
            try:
                news = cls._fetch_rss(url, source, max_per_source)
                all_news.extend(news)
                logger.info(f"اخبار {source}: {len(news)} مورد")
            except Exception as e:
                logger.warning(f"خطا در دریافت اخبار {source}: {e}")

        # مرتب‌سازی بر اساس زمان (جدیدترین اول)
        all_news.sort(key=lambda x: x.get('published_dt', datetime.min), reverse=True)

        cls._news_cache['all'] = all_news
        cls._cache_time = now

        return all_news

    @classmethod
    def _fetch_rss(cls, url: str, source: str, max_items: int) -> List[Dict]:
        """دریافت و parse یک RSS feed"""
        resp = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; CryptoScanner/1.0)'
        })
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        news_items = []

        # RSS 2.0 format
        items = root.findall('.//item')[:max_items]

        for item in items:
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            pub_date_str = item.findtext('pubDate', '').strip()

            # parse تاریخ
            pub_dt = cls._parse_date(pub_date_str)

            # تحلیل sentiment عنوان
            sentiment = cls._analyze_sentiment(title)

            news_items.append({
                'source': source,
                'title': title,
                'link': link,
                'published_at': pub_date_str,
                'published_dt': pub_dt,
                'sentiment': sentiment['sentiment'],
                'sentiment_score': sentiment['score'],
                'matched_keywords': sentiment['keywords'],
            })

        return news_items

    @classmethod
    def _analyze_sentiment(cls, text: str) -> Dict:
        """تحلیل sentiment یک متن بر اساس کلمات کلیدی"""
        text_lower = text.lower()
        positive_count = 0
        negative_count = 0
        matched = []

        for kw in cls.POSITIVE_KEYWORDS:
            if kw in text_lower:
                positive_count += 1
                matched.append(f"+{kw}")

        for kw in cls.NEGATIVE_KEYWORDS:
            if kw in text_lower:
                negative_count += 1
                matched.append(f"-{kw}")

        # محاسبه sentiment
        if positive_count > negative_count:
            sentiment = 'positive'
            score = positive_count - negative_count
        elif negative_count > positive_count:
            sentiment = 'negative'
            score = -(negative_count - positive_count)
        else:
            sentiment = 'neutral'
            score = 0

        return {
            'sentiment': sentiment,
            'score': score,
            'keywords': matched,
        }

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """parse فرمت‌های مختلف تاریخ RSS"""
        if not date_str:
            return datetime.min

        formats = [
            '%a, %d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S GMT',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return datetime.min

    @classmethod
    def get_news_for_coin(cls, coin_symbol: str, coin_name: str, hours: int = 48) -> Dict:
        """
        دریافت و تحلیل اخبار مرتبط با یک کوین
        """
        all_news = cls.fetch_all_news()

        # فیلتر اخبار مرتبط با این کوین
        symbol_lower = coin_symbol.lower()
        name_lower = coin_name.lower() if coin_name else ''

        related_news = []
        for news in all_news:
            title_lower = news['title'].lower()
            # بررسی تطابق سیمبل یا نام کوین در عنوان
            if (symbol_lower in title_lower or
                (name_lower and len(name_lower) > 2 and name_lower in title_lower)):
                related_news.append(news)

        # محاسبه sentiment کلی
        positive_count = sum(1 for n in related_news if n['sentiment'] == 'positive')
        negative_count = sum(1 for n in related_news if n['sentiment'] == 'negative')
        neutral_count = sum(1 for n in related_news if n['sentiment'] == 'neutral')

        # امتیاز sentiment (-100 تا +100)
        total = len(related_news) if related_news else 1
        sentiment_score = ((positive_count - negative_count) / total) * 100

        # جهت sentiment
        if sentiment_score > 30:
            overall_sentiment = 'مثبت قوی'
            news_score = 2  # برای لانگ
        elif sentiment_score > 10:
            overall_sentiment = 'مثبت ملایم'
            news_score = 1
        elif sentiment_score < -30:
            overall_sentiment = 'منفی قوی'
            news_score = -2  # برای شورت
        elif sentiment_score < -10:
            overall_sentiment = 'منفی ملایم'
            news_score = -1
        else:
            overall_sentiment = 'خنثی'
            news_score = 0

        return {
            'coin': coin_symbol,
            'total_news': len(related_news),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'sentiment_score': round(sentiment_score, 1),
            'overall_sentiment': overall_sentiment,
            'news_score': news_score,
            'top_news': related_news[:5],  # 5 خبر اخیر
        }
