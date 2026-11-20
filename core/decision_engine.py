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
from core.debate_system import DebateSystem
from core.memory_log import MemoryLog
from core.data_models import FinalDecision, Decision, AgentReport
from data_fetcher import DataFetcher
from multi_tf import MultiTimeframeAnalyzer
from liquidity import LiquidityAnalyzer
from smc_analyzer import SMCAnalyzer
from price_action import PriceActionAnalyzer, InverseTrendDetector
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
        self.debate = DebateSystem(max_rounds=2)
        self.memory = MemoryLog()

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

        # 🔥 سیستم مناظره (Debate) - از TradingAgents الهام گرفته
        logger.info(f"  💬 شروع مناظره Bullish vs Bearish...")
        bull_report, bear_report, debate_summary = self.debate.debate(
            coin, bull_report, bear_report
        )
        logger.info(f"  💬 مناظره پایان یافت: {debate_summary.get('summary', '')}")

        # تعیین جهت برتر پس از مناظره
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

        # Central Brain: تصمیم نهایی (با context حافظه)
        memory_context = self.memory.get_memory_context(symbol)
        decision = self.brain.decide(
            coin, market_report, fund_report, bull_report,
            bear_report, risk_report, bt_report
        )

        # اضافه کردن debate summary و memory context به تصمیم
        decision.data = {
            'market_report': market_report,
            'fundamental_report': fund_report,
            'bullish_report': bull_report,
            'bearish_report': bear_report,
            'risk_report': risk_report,
            'backtest_report': bt_report,
            'debate_summary': debate_summary,
            'memory_context': memory_context,
            'analysis': analysis,
            'smc_data': smc_data,
            'oi_data': market_report.data.get('oi_funding'),
            'flow_data': market_report.data.get('volume_flow'),
            'order_book': ob_analysis,
            'btc_data': market_report.data.get('btc_benchmark'),
        }

        # ثبت تصمیم در حافظه (فقط LONG/SHORT)
        if decision.decision in [Decision.LONG, Decision.SHORT] and decision.entry_price > 0:
            self.memory.add_decision(
                symbol=symbol,
                direction=decision.decision.value,
                entry=decision.entry_price,
                stop=decision.stop_loss,
                targets=[decision.target_1, decision.target_2, decision.target_3],
                confidence=decision.confidence,
                reasoning=decision.brain_reasoning,
            )

        return decision

    def analyze_market(self, coins: List[Dict]) -> List[FinalDecision]:
        """
        تحلیل بازار با پیش‌فیلتر:
        1. همه کوین‌ها با Rule-Based سریع اسکن شوند
        2. فقط 15 کوین برتر → LLM (مناظره + مغز)
        3. کاهش فراخوانی LLM از 200 به 45
        """
        decisions = []
        pre_filtered = []
        total = len(coins)

        # مرحله 1: پیش‌فیلتر سریع (بدون LLM)
        logger.info(f"مرحله 1: پیش‌فیلتر {total} کوین (بدون LLM)...")
        for i, coin in enumerate(coins, 1):
            try:
                quick_score = self._quick_scan(coin)
                if quick_score > 15:  # فقط امیدوارترین‌ها
                    pre_filtered.append((coin, quick_score))
                    logger.info(f"  [{i}/{total}] {coin['base']}: امتیاز اولیه {quick_score:.0f} → منتقل به LLM")
                else:
                    # رد سریع
                    decision = FinalDecision(symbol=coin['symbol'], decision=Decision.NO_TRADE)
                    decision.final_analysis = f"امتیاز اولیه پایین ({quick_score:.0f})"
                    decisions.append(decision)
            except Exception as e:
                logger.warning(f"خطا در پیش‌فیلتر {coin['symbol']}: {e}")

        # مرتب‌سازی بر اساس امتیاز
        pre_filtered.sort(key=lambda x: x[1], reverse=True)
        pre_filtered = pre_filtered[:15]  # فقط 15 کوین برتر

        logger.info(f"مرحله 2: تحلیل LLM برای {len(pre_filtered)} کوین برتر...")

        # مرحله 2: تحلیل کامل با LLM فقط برای کوین‌های منتخب
        for i, (coin, quick_score) in enumerate(pre_filtered, 1):
            try:
                logger.info(f"  [{i}/{len(pre_filtered)}] {coin['base']} (امتیاز: {quick_score:.0f})")
                decision = self.analyze_coin(coin)
                decisions.append(decision)

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

        return self._filter_and_rank(decisions)

    def _quick_scan(self, coin: Dict) -> float:
        """
        اسکن سریع - شامل:
        - روند چند تایم فریم
        - SMC
        - پرایس اکشن
        - روند عکس نسبت به BTC
        - حجم
        """
        symbol = coin['symbol']
        score = 0

        try:
            timeframes_data = self.fetcher.fetch_all_timeframes(symbol)
            if len(timeframes_data) < 3:
                return 0

            analysis = MultiTimeframeAnalyzer.analyze_all(timeframes_data)

            # 1. روند
            trend = MultiTimeframeAnalyzer.check_trend_alignment(analysis)
            score += abs(trend.get('alignment_score', 0)) * 3

            # 2. SMC
            smc_data = SMCAnalyzer.analyze_multi_tf(timeframes_data)
            if smc_data.get('available'):
                score += abs(smc_data.get('combined_score', 0)) * 5

            # 3. پرایس اکشن (الگوهای کندلی)
            df_1h = timeframes_data.get('1h')
            df_15m = timeframes_data.get('15m')

            if df_1h is not None:
                pa_1h = PriceActionAnalyzer.analyze(df_1h)
                if pa_1h.get('available'):
                    score += abs(pa_1h.get('score', 0)) * 3
                    # الگوهای قوی امتیاز بیشتر
                    for pattern in pa_1h.get('patterns', []):
                        if pattern.get('strength') == 'strong':
                            score += 5

            if df_15m is not None:
                pa_15m = PriceActionAnalyzer.analyze(df_15m)
                if pa_15m.get('available'):
                    score += abs(pa_15m.get('score', 0)) * 2

            # 4. روند عکس نسبت به BTC
            btc_pair_data = timeframes_data.get('_btc_pair')
            if btc_pair_data:
                from btc_benchmark import BTCBenchmarkAnalyzer
                btc_data = BTCBenchmarkAnalyzer.analyze_btc_pair(btc_pair_data)
                if btc_data.get('available'):
                    btc_score = btc_data.get('btc_score', 0)
                    # ارز قوی‌تر از BTC در بازار نزولی = امتیاز بالا
                    if btc_score > 0:
                        score += btc_score * 8  # وزن بالا برای روند عکس

                    # تشخیص روند عکس
                    inverse = InverseTrendDetector.detect(coin, btc_data, market_bearish=True)
                    if inverse.get('is_inverse'):
                        score += inverse.get('strength', 0) * 5
                        logger.info(f"    ⚡ {coin['base']}: روند عکس! {inverse.get('reason', '')}")

            # 5. حجم
            vol_entry = MultiTimeframeAnalyzer.analyze_volume_entry(analysis)
            if vol_entry:
                score += vol_entry.get('entry_score', 0) * 2

            # 6. تغییر قیمت
            price_change = coin.get('price_change_24h', 0)
            score += min(abs(price_change), 10)

            # 7. ساختار
            structure = MultiTimeframeAnalyzer.analyze_structure(analysis)
            score += abs(structure.get('total_phase_score', 0)) * 3

        except Exception as e:
            logger.debug(f"خطا در quick scan {symbol}: {e}")
            return 0

        return score

    def _filter_and_rank(self, decisions: List[FinalDecision]) -> List[FinalDecision]:
        """
        فیلتر و رتبه‌بندی - حداقل 5 لانگ + 5 شورت
        """
        longs = [d for d in decisions if d.decision == Decision.LONG]
        shorts = [d for d in decisions if d.decision == Decision.SHORT]
        waits = [d for d in decisions if d.decision == Decision.WAIT]
        rejects = [d for d in decisions if d.decision == Decision.NO_TRADE]

        longs.sort(key=lambda x: x.confidence, reverse=True)
        shorts.sort(key=lambda x: x.confidence, reverse=True)

        top_longs = longs[:config.TOP_LONG_COUNT]
        top_shorts = shorts[:config.TOP_SHORT_COUNT]

        # اگر کمتر از 5 سیگنال داریم، WAIT‌های با اعتماد بالا را اضافه کن
        if len(top_longs) < 5:
            wait_long_candidates = [d for d in waits if 'bullish' in d.brain_reasoning.lower() or 'long' in d.brain_reasoning.lower()]
            wait_long_candidates.sort(key=lambda x: x.confidence, reverse=True)
            top_longs.extend(wait_long_candidates[:5 - len(top_longs)])

        if len(top_shorts) < 5:
            wait_short_candidates = [d for d in waits if 'bearish' in d.brain_reasoning.lower() or 'short' in d.brain_reasoning.lower()]
            wait_short_candidates.sort(key=lambda x: x.confidence, reverse=True)
            top_shorts.extend(wait_short_candidates[:5 - len(top_shorts)])

        logger.info(f"نتایج: {len(top_longs)} LONG, {len(top_shorts)} SHORT, {len(waits)} WAIT, {len(rejects)} REJECT")

        return top_longs + top_shorts + waits[:3]
