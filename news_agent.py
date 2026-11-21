"""
ایجنت اخبار مستقل - پایش مداوم
Independent News Agent

منابع اخبار:
- Google News (شامل Bloomberg, Reuters, AP, CNBC, WSJ)
- X/Twitter (از طریق Google News)
- CoinDesk, Cointelegraph, Decrypt
- The Block

ویژگی‌ها:
- اجرای مستقل هر 15-30 دقیقه
- تشخیص اخبار فوری (breaking news)
- ارسال فوری به تلگرام
- دسته‌بندی: قانونی، صرافی، هک، شراکت، اقتصاد کلان
- ارزیابی تأثیر: بالا/متوسط/پایین
- فقط اخبار مهم و تأثیرگذار ارسال می‌شوند
"""
import feedparser
import requests
import os
import sys
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from telegram_sender import TelegramSender

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# منابع RSS
NEWS_SOURCES = {
    # Google News - پوشش همه منابع بزرگ
    'Google Crypto': 'https://news.google.com/rss/search?q=bitcoin+OR+crypto+OR+cryptocurrency+OR+ethereum&hl=en-US&gl=US&ceid=US:en',
    'Google Bloomberg Crypto': 'https://news.google.com/rss/search?q=bloomberg+crypto+OR+bitcoin&hl=en-US&gl=US&ceid=US:en',
    'Google Fed/Economy': 'https://news.google.com/rss/search?q=federal+reserve+OR+FOMC+OR+rate+cut+OR+interest+rate&hl=en-US&gl=US&ceid=US:en',
    'Google SEC/Crypto': 'https://news.google.com/rss/search?q=SEC+crypto+OR+bitcoin+lawsuit+OR+ETF&hl=en-US&gl=US&ceid=US:en',
    # کریپتویی
    'CoinDesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
    'Cointelegraph': 'https://cointelegraph.com/rss',
    'Decrypt': 'https://decrypt.co/feed',
    'The Block': 'https://www.theblock.co/rss.xml',
    # X/Twitter از طریق Nitter (اگر در دسترس باشد)
    'Twitter Crypto': 'https://nitter.net/search/rss?f=tweets&q=bitcoin+OR+crypto+OR+eth&since=1d',
}

# کلمات کلیدی اخبار فوری (high impact)
BREAKING_KEYWORDS = {
    # هک و امنیت
    'hack': 'high', 'hacked': 'high', 'exploit': 'high', 'breach': 'high',
    'stolen': 'high', 'drained': 'high', 'vulnerability': 'medium',
    # قانونی
    'sec': 'high', 'lawsuit': 'high', 'ban': 'high', 'banned': 'high',
    'regulation': 'medium', 'regulatory': 'medium', 'compliance': 'low',
    'approve': 'high', 'approved': 'high', 'approval': 'high',
    'reject': 'high', 'rejected': 'high', 'denied': 'high',
    # ETF
    'etf': 'high', 'spot etf': 'high', 'etf approval': 'high',
    # اقتصاد کلان
    'federal reserve': 'high', 'fed': 'high', 'fomc': 'high',
    'rate cut': 'high', 'rate hike': 'high', 'interest rate': 'high',
    'powell': 'high', 'jerome powell': 'high',
    'inflation': 'medium', 'cpi': 'medium', 'jobs report': 'medium',
    'nonfarm': 'medium', 'gdp': 'medium',
    # صرافی
    'binance': 'medium', 'coinbase': 'medium', 'ftx': 'medium',
    'delist': 'high', 'delisting': 'high', 'bankruptcy': 'high',
    'liquidation': 'medium', 'liquidations': 'medium',
    # حرکت بازار
    'crash': 'high', 'plunge': 'high', 'surge': 'medium',
    'pump': 'medium', 'dump': 'high', 'rally': 'medium',
    'all-time high': 'high', 'ath': 'medium',
    'bear market': 'medium', 'bull market': 'medium',
    # پروژه
    'mainnet': 'medium', 'airdrop': 'medium', 'launch': 'medium',
    'partnership': 'low', 'upgrade': 'low', 'fork': 'medium',
}

# کلمات کلیدی منفی (تأثیر نزولی)
BEARISH_KEYWORDS = ['hack', 'ban', 'lawsuit', 'sec', 'reject', 'crash', 'plunge', 'dump', 'delist', 'bankruptcy', 'drained', 'stolen']
# کلمات کلیدی مثبت (تأثیر صعودی)
BULLISH_KEYWORDS = ['approve', 'approved', 'etf', 'surge', 'rally', 'partnership', 'upgrade', 'rate cut', 'adoption']


class NewsAgent:
    """ایجنت اخبار مستقل"""

    def __init__(self):
        self.tg = TelegramSender()
        self.seen_hashes = set()
        self.last_scan = None
        # بارگذاری هش‌های قبلی
        self._load_seen()

    def _load_seen(self):
        """بارگذاری هش‌های اخبار قبلی"""
        hash_file = os.path.join(config.OUTPUT_DIR, 'news_seen.txt')
        if os.path.exists(hash_file):
            with open(hash_file, 'r') as f:
                self.seen_hashes = set(line.strip() for line in f)

    def _save_seen(self):
        """ذخیره هش‌های اخبار"""
        hash_file = os.path.join(config.OUTPUT_DIR, 'news_seen.txt')
        # فقط 500 هش اخیر را نگه دار
        recent = list(self.seen_hashes)[-500:]
        with open(hash_file, 'w') as f:
            for h in recent:
                f.write(h + '\n')

    def _get_hash(self, title: str, source: str) -> str:
        """هش یکتا برای هر خبر"""
        return hashlib.md5(f"{title}{source}".encode()).hexdigest()

    def scan_all_sources(self) -> List[Dict]:
        """اسکن همه منابع اخبار"""
        all_news = []

        for source_name, url in NEWS_SOURCES.items():
            try:
                news = self._fetch_rss(url, source_name)
                all_news.extend(news)
                logger.info(f"  {source_name}: {len(news)} خبر")
            except Exception as e:
                logger.debug(f"خطا در {source_name}: {e}")

        # حذف تکراری‌ها
        unique = []
        seen_titles = set()
        for news in all_news:
            title_lower = news['title'].lower().strip()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique.append(news)

        return unique

    def _fetch_rss(self, url: str, source: str) -> List[Dict]:
        """دریافت و parse RSS"""
        try:
            resp = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; CryptoNewsBot/1.0)'
            })
            if resp.status_code != 200:
                return []

            feed = feedparser.parse(resp.content)
            news_items = []

            for entry in feed.entries[:20]:  # 20 خبر اخیر
                title = entry.get('title', '').strip()
                link = entry.get('link', '')
                published = entry.get('published', '')
                summary = entry.get('summary', '')

                if not title:
                    continue

                news = {
                    'title': title,
                    'link': link,
                    'source': source,
                    'published': published,
                    'summary': summary[:200],
                }

                # تحلیل تأثیر
                news.update(self._analyze_impact(title, summary))
                news['hash'] = self._get_hash(title, source)

                news_items.append(news)

            return news_items

        except Exception as e:
            logger.debug(f"خطا در RSS {source}: {e}")
            return []

    def _analyze_impact(self, title: str, summary: str) -> Dict:
        """تحلیل تأثیر خبر"""
        text = (title + ' ' + summary).lower()

        impact = 'low'
        impact_keywords = []

        for keyword, level in BREAKING_KEYWORDS.items():
            if keyword in text:
                impact_keywords.append(keyword)
                if level == 'high':
                    impact = 'high'
                elif level == 'medium' and impact != 'high':
                    impact = 'medium'

        # جهت تأثیر
        bearish_count = sum(1 for k in BEARISH_KEYWORDS if k in text)
        bullish_count = sum(1 for k in BULLISH_KEYWORDS if k in text)

        if bearish_count > bullish_count:
            direction = 'bearish'
        elif bullish_count > bearish_count:
            direction = 'bullish'
        else:
            direction = 'neutral'

        return {
            'impact': impact,
            'direction': direction,
            'keywords': impact_keywords[:5],
            'bearish_count': bearish_count,
            'bullish_count': bullish_count,
        }

    def filter_important(self, news_list: List[Dict]) -> List[Dict]:
        """فیلتر فقط اخبار مهم (high + medium)"""
        important = [n for n in news_list if n['impact'] in ['high', 'medium']]

        # مرتب‌سازی بر اساس تأثیر
        impact_order = {'high': 0, 'medium': 1, 'low': 2}
        important.sort(key=lambda x: impact_order.get(x['impact'], 3))

        return important

    def send_alerts(self, news_list: List[Dict]):
        """ارسال اخبار - هر خبر مهم جداگانه + بقیه در فایل خلاصه"""
        if not self.tg.is_configured():
            return

        # دسته‌بندی
        high_new = [n for n in news_list if n['impact'] == 'high' and n['hash'] not in self.seen_hashes]
        medium_new = [n for n in news_list if n['impact'] == 'medium' and n['hash'] not in self.seen_hashes]

        # 1. اخبار HIGH را جداگانه و فوری بفرست (بدون لینک)
        for news in high_new[:5]:
            self.seen_hashes.add(news['hash'])
            msg = self._format_breaking_news(news)
            self.tg.send_message(msg)
            time.sleep(2)  # جلوگیری از rate limit

        # 2. اخبار MEDIUM را ذخیره کن برای فایل 4 ساعته
        for news in medium_new:
            self.seen_hashes.add(news['hash'])

        # ذخیره اخبار برای فایل خلاصه
        self._save_for_summary(high_new + medium_new)

        if high_new:
            logger.info(f"✓ {len(high_new)} خبر فوری ارسال شد")
        else:
            logger.info("خبر فوری جدیدی نیست")

    def _format_breaking_news(self, news: Dict) -> str:
        """فرمت خبر فوری - بدون لینک، سریع و خلاصه"""
        dir_emoji = {'bearish': '🔴', 'bullish': '🟢', 'neutral': '⚪'}.get(news['direction'], '⚪')

        msg = []
        msg.append(f"🚨 <b>خبر فوری</b> {dir_emoji}")
        msg.append(f"━━━━━━━━━━━━━━━━━━━━")
        msg.append(f"<b>{news['title']}</b>")
        msg.append(f"")
        msg.append(f"📰 {news['source']}")
        msg.append(f"📊 جهت: {news['direction']} | تأثیر: بالا")
        if news['keywords']:
            msg.append(f"🔑 {', '.join(news['keywords'][:3])}")
        msg.append(f"⏰ {config.tehran_now_str('%H:%M')}")

        return '\n'.join(msg)

    def _save_for_summary(self, news_list: List[Dict]):
        """ذخیره اخبار برای فایل خلاصه 4 ساعته"""
        summary_file = os.path.join(config.OUTPUT_DIR, 'news_summary.json')
        existing = []
        if os.path.exists(summary_file):
            try:
                import json
                with open(summary_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        for news in news_list:
            existing.append({
                'title': news['title'],
                'source': news['source'],
                'link': news['link'],
                'direction': news['direction'],
                'impact': news['impact'],
                'time': config.tehran_now_str(),
            })

        # فقط 100 خبر اخیر
        existing = existing[-100:]

        import json
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def send_summary_report(self):
        """ارسال فایل خلاصه اخبار (هر 4 ساعت)"""
        summary_file = os.path.join(config.OUTPUT_DIR, 'news_summary.json')
        if not os.path.exists(summary_file):
            logger.info("فایل خلاصه اخبار وجود ندارد")
            return

        import json
        with open(summary_file, 'r', encoding='utf-8') as f:
            news_list = json.load(f)

        if not news_list:
            return

        # ساخت فایل متنی با سرتیتر + لینک
        lines = []
        lines.append("📋 خلاصه اخبار بازار کریپتو")
        lines.append(f"🕐 {config.tehran_now_str()}")
        lines.append(f"📊 تعداد: {len(news_list)} خبر")
        lines.append("=" * 60)
        lines.append("")

        for i, news in enumerate(news_list, 1):
            dir_emoji = {'bearish': '🔴', 'bullish': '🟢', 'neutral': '⚪'}.get(news.get('direction', ''), '⚪')
            lines.append(f"{i}. {dir_emoji} {news['title']}")
            lines.append(f"   📰 {news['source']} | {news.get('time', '')}")
            if news.get('link'):
                lines.append(f"   🔗 {news['link']}")
            lines.append("")

        lines.append("=" * 60)

        # ذخیره فایل
        report_file = os.path.join(config.OUTPUT_DIR, f'news_summary_{config.tehran_now().strftime("%Y%m%d_%H%M")}.txt')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        # ارسال فایل به تلگرام
        if self.tg.is_configured():
            caption = f"📋 خلاصه اخبار - {len(news_list)} خبر\n🕐 {config.tehran_now_str()}"
            self.tg.send_document(report_file, caption)

        # پاک کردن فایل خلاصه
        os.remove(summary_file)
        logger.info(f"✓ فایل خلاصه اخبار ارسال شد: {len(news_list)} خبر")

    def _format_news_message(self, news: Dict) -> Optional[str]:
        """فرمت پیام خبر"""
        if news['impact'] == 'low':
            return None  # اخبار کم‌تأثیر ارسال نمی‌شوند

        impact_emoji = {'high': '🚨', 'medium': '⚠'}
        direction_emoji = {'bearish': '🔴', 'bullish': '🟢', 'neutral': '⚪'}

        emoji = impact_emoji.get(news['impact'], 'ℹ')
        dir_emoji = direction_emoji.get(news['direction'], '⚪')

        msg = []
        msg.append(f"{emoji} <b>خبر مهم بازار</b> {dir_emoji}")
        msg.append(f"━━━━━━━━━━━━━━━━━━━━")
        msg.append(f"<b>{news['title']}</b>")
        msg.append(f"")
        msg.append(f"📰 منبع: {news['source']}")
        msg.append(f"⚡ تأثیر: {news['impact'].upper()}")
        msg.append(f"📊 جهت: {news['direction']}")
        if news['keywords']:
            msg.append(f"🔑 کلمات کلیدی: {', '.join(news['keywords'])}")
        msg.append(f"⏰ {config.tehran_now_str()}")
        if news['link']:
            msg.append(f"🔗 {news['link']}")

        return '\n'.join(msg)

    def run(self, send_summary=False):
        """اجرای کامل اسکن اخبار
        send_summary=True: فایل خلاصه 4 ساعته را هم بفرست
        """
        start = time.time()
        logger.info("=" * 50)
        logger.info(f"ایجنت اخبار - {config.tehran_now_str()}")
        logger.info("=" * 50)

        # اسکن همه منابع
        all_news = self.scan_all_sources()
        logger.info(f"کل اخبار: {len(all_news)}")

        # فیلتر اخبار مهم
        important = self.filter_important(all_news)
        logger.info(f"اخبار مهم: {len(important)}")

        # ارسال هشدارها
        self.send_alerts(important)

        # ارسال فایل خلاصه (هر 4 ساعت)
        if send_summary:
            self.send_summary_report()

        duration = time.time() - start
        logger.info(f"اتمام - {duration:.1f}s")
        return True


if __name__ == '__main__':
    import sys
    send_summary = '--summary' in sys.argv
    try:
        agent = NewsAgent()
        agent.run(send_summary=send_summary)
    except KeyboardInterrupt:
        logger.info("متوقف شد")
        sys.exit(0)
    except Exception as e:
        logger.error(f"خطا: {e}", exc_info=True)
        sys.exit(1)
