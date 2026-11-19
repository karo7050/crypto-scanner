"""
سیستم تصمیم‌گیری نهایی (Decision Pipeline)

جریان تصمیم‌گیری:
1. اسکنر بازار → فرصت‌های احتمالی
2. تحلیلگر بنیادی → وضعیت پروژه و اخبار
3. تحلیلگر خوش‌بین → سناریوی صعودی
4. تحلیلگر بدبین → سناریوی نزولی
5. مدیر ریسک → ارزیابی ریسک
6. بک‌تستر → اعتبار استراتژی
7. مغز مرکزی → تصمیم نهایی
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List
from agents.market_scanner import MarketScannerAgent
from agents.fundamental_analyst import FundamentalAnalystAgent
from agents.bullish_analyst import BullishAnalystAgent
from agents.bearish_analyst import BearishAnalystAgent
from agents.risk_manager import RiskManagerAgent
from agents.backtester import BacktesterAgent
from core.brain import CentralBrain
from core.data_models import FinalDecision, Decision, AgentReport
from data_fetcher import DataFetcher
from multi_tf import MultiTimeframeAnalyzer
from liquidity import LiquidityAnalyzer
from smc_analyzer import SMCAnalyzer
import config
import logging
import time

logger = logging.getLogger(__name__)


class DecisionPipeline:
    """مدیر pipeline تصمیم‌گیری چند‌ایجنت"""

    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher
        self.market_scanner = MarketScannerAgent(fetcher)
        self.fundamental_analyst = FundamentalAnalystAgent()
        self.bullish_analyst = BullishAnalystAgent()
        self.bearish_analyst = BearishAnalystAgent()
        self.risk_manager = RiskManagerAgent()
        self.backtester = BacktesterAgent()
        self.brain = CentralBrain()

    def analyze_coin(self, coin: Dict) -> FinalDecision:
        """
        اجرای کامل pipeline برای یک ارز
        """
        symbol = coin['symbol']
        base = coin['base']

        logger.info(f"  🔍 تحلیل چند‌ایجنت {base}...")

        # دریافت داده
        timeframes_data = self.fetcher.fetch_all_timeframes(symbol)
        if len(timeframes_data) < 3:
            decision = FinalDecision(symbol=symbol, decision=Decision.NO_TRADE)
            decision.final_analysis = "داده ناکافی"
            return decision

        # تحلیل چند تایم فریم
        analysis = MultiTimeframeAnalyzer.analyze_all(timeframes_data)

        # SMC
        smc_data = SMCAnalyzer.analyze_multi_tf(timeframes_data)

        # Order Book
        order_book = self.fetcher.fetch_order_book(symbol)
        ob_analysis = LiquidityAnalyzer.analyze_order_book(order_book) if order_book else None

        # Agent 1: Market Scanner
        market_report = self.market_scanner.scan_coin(coin, timeframes_data)

        # Agent 2: Fundamental Analyst
        fund_report = self.fundamental_analyst.analyze(coin)

        # Agent 3: Bullish Analyst
        bull_report = self.bullish_analyst.analyze(coin, analysis, ob_analysis, smc_data)

        # Agent 4: Bearish Analyst
        bear_report = self.bearish_analyst.analyze(coin, analysis, ob_analysis, smc_data)

        # تعیین جهت برتر
        direction = 'LONG' if bull_report.score > bear_report.score else 'SHORT'
        bull_result = bull_report.data.get('bullish_result', {})
        bear_result = bear_report.data.get('bearish_result', {})

        if direction == 'LONG':
            entry = bull_result.get('entry_price', 0)
            stop = bull_result.get('stop_loss', 0)
            targets = bull_result.get('targets', [])
        else:
            entry = bear_result.get('entry_price', 0)
            stop = bear_result.get('stop_loss', 0)
            targets = bear_result.get('targets', [])

        # Agent 5: Risk Manager
        risk_report = self.risk_manager.assess(
            coin, direction, entry, stop, targets,
            bull_report, bear_report, market_report
        )

        # Agent 6: Backtester
        bt_report = self.backtester.backtest(coin, analysis, direction, entry, stop, targets)

        # Central Brain: تصمیم نهایی
        decision = self.brain.decide(
            coin, market_report, fund_report, bull_report,
            bear_report, risk_report, bt_report
        )

        # ذخیره گزارش‌های ایجنت‌ها در تصمیم
        decision.data = {
            'market_report': market_report,
            'fundamental_report': fund_report,
            'bullish_report': bull_report,
            'bearish_report': bear_report,
            'risk_report': risk_report,
            'backtest_report': bt_report,
            'analysis': analysis,
            'smc_data': smc_data,
            'oi_data': market_report.data.get('oi_funding'),
            'flow_data': market_report.data.get('volume_flow'),
            'order_book': ob_analysis,
            'btc_data': market_report.data.get('btc_benchmark'),
        }

        return decision

    def analyze_market(self, coins: List[Dict]) -> List[FinalDecision]:
        """
        تحلیل کل بازار و برگرداندن تصمیمات
        """
        decisions = []
        total = len(coins)

        for i, coin in enumerate(coins, 1):
            try:
                logger.info(f"[{i}/{total}] {coin['base']}")
                decision = self.analyze_coin(coin)
                decisions.append(decision)

                # نمایش تصمیم
                dir_emoji = {
                    Decision.LONG: '🟢',
                    Decision.SHORT: '🔴',
                    Decision.WAIT: '🟡',
                    Decision.NO_TRADE: '⚪'
                }.get(decision.decision, '⚪')
                logger.info(f"  {dir_emoji} {decision.decision.value} (اعتماد: {decision.confidence:.0%})")

                time.sleep(0.3)

            except Exception as e:
                logger.error(f"خطا در تحلیل {coin['symbol']}: {e}")
                continue

        return self._filter_and_rank(decisions)

    def _filter_and_rank(self, decisions: List[FinalDecision]) -> List[FinalDecision]:
        """
        فیلتر و رتبه‌بندی تصمیمات
        """
        # جدا کردن LONG و SHORT
        longs = [d for d in decisions if d.decision == Decision.LONG]
        shorts = [d for d in decisions if d.decision == Decision.SHORT]
        waits = [d for d in decisions if d.decision == Decision.WAIT]
        rejects = [d for d in decisions if d.decision == Decision.NO_TRADE]

        # مرتب‌سازی بر اساس اعتماد
        longs.sort(key=lambda x: x.confidence, reverse=True)
        shorts.sort(key=lambda x: x.confidence, reverse=True)

        # محدود کردن تعداد
        top_longs = longs[:config.TOP_LONG_COUNT]
        top_shorts = shorts[:config.TOP_SHORT_COUNT]

        logger.info(f"نتایج: {len(top_longs)} LONG, {len(top_shorts)} SHORT, {len(waits)} WAIT, {len(rejects)} REJECT")

        return top_longs + top_shorts + waits[:2]  # فقط 2 WAIT برای اطلاع
