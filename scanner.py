"""
اسکنر یکپارچه بازار - معماری جدید
Unified Market Scanner

تمام تحلیل‌های تکنیکال در یک ماژول:
- روند چند تایم فریم (1d/4h/1h/15m)
- SMC (Order Block, BOS, CHoCH, FVG)
- پرایس اکشن (الگوهای کندلی)
- روند عکس vs BTC
- حجم و جریان پول (Volume Flow)
- OI + Funding Rate
- تشخیص اشباع فروش/خرید

خروجی: LONG/SHORT/WAIT با Entry/Stop/Targets

قواعد RSI:
- RSI < 25 = اشباع فروش = نباید شورت (احتمال بازگشت)
- RSI > 75 = اشباع خرید = نباید لانگ (احتمال ریزش)
- RSI 25-50 = نزولی (می‌توان شورت)
- RSI 50-75 = صعودی (می‌توان لانگ)
"""
import sys, os, json, logging, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, List

import config
from data_fetcher import DataFetcher
from multi_tf import MultiTimeframeAnalyzer
from indicators import Indicators
from liquidity import LiquidityAnalyzer
from smc_analyzer import SMCAnalyzer
from price_action import PriceActionAnalyzer, InverseTrendDetector
from volume_flow import VolumeFlowAnalyzer
from oi_funding import OIFundingAnalyzer
from btc_benchmark import BTCBenchmarkAnalyzer
from coinalyze_data import CoinalyzeData
from entry_exit import EntryExitCalculator
from core.data_models import FinalDecision, Decision
from core.watchlist_manager import WatchlistManager
from core.memory_log import MemoryLog
from telegram_sender import TelegramSender
from events_calendar import EconomicEventsCalendar

logger = logging.getLogger(__name__)


class UnifiedScanner:
    """اسکنر یکپارچه - تمام تحلیل‌ها در یک جا"""

    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher
        self.wl = WatchlistManager()
        self.memory = MemoryLog()

    def scan_coin(self, coin: Dict) -> FinalDecision:
        """
        اسکن کامل یک ارز - تمام تحلیل‌ها
        خروجی: FinalDecision با LONG/SHORT/WAIT
        """
        symbol = coin['symbol']
        base = coin['base']
        decision = FinalDecision(symbol=symbol)

        try:
            # 1. دریافت داده همه تایم فریم‌ها
            tf_data = self.fetcher.fetch_all_timeframes(symbol)
            if len(tf_data) < 3:
                decision.decision = Decision.NO_TRADE
                decision.final_analysis = "داده ناکافی"
                return decision

            # 2. تحلیل چند تایم فریم
            analysis = MultiTimeframeAnalyzer.analyze_all(tf_data)
            trend = MultiTimeframeAnalyzer.check_trend_alignment(analysis)
            structure = MultiTimeframeAnalyzer.analyze_structure(analysis)

            # 3. SMC
            smc_data = SMCAnalyzer.analyze_multi_tf(tf_data)

            # 4. پرایس اکشن
            df_1h = tf_data.get('1h')
            df_15m = tf_data.get('15m')
            pa_1h = PriceActionAnalyzer.analyze(df_1h) if df_1h is not None else {}
            pa_15m = PriceActionAnalyzer.analyze(df_15m) if df_15m is not None else {}

            # 5. حجم ورود
            vol_entry = MultiTimeframeAnalyzer.analyze_volume_entry(analysis)

            # 6. Volume Flow
            flow_data = VolumeFlowAnalyzer.compute_flow(df_1h) if df_1h is not None else {}

            # 7. OI + Funding + Long/Short از Coinalyze (داده واقعی)
            coinalyze_data = CoinalyzeData.get_current_data(base)
            oi_data = OIFundingAnalyzer.fetch_oi_and_funding(symbol)

            # 8. BTC benchmark
            btc_pair_data = tf_data.get('_btc_pair')
            btc_data = BTCBenchmarkAnalyzer.analyze_btc_pair(btc_pair_data) if btc_pair_data else {}

            # 9. Order Book
            order_book = self.fetcher.fetch_order_book(symbol)
            ob_analysis = LiquidityAnalyzer.analyze_order_book(order_book) if order_book else {}

            # 10. وضعیت RSI
            state_1h = analysis.get('1h', {}).get('state', {})
            state_4h = analysis.get('4h', {}).get('state', {})
            rsi_1h = state_1h.get('rsi', 50)
            rsi_4h = state_4h.get('rsi', 50)

            # ===== امتیازدهی =====
            long_score = 0
            short_score = 0
            reasons_pro = []
            reasons_con = []

            # --- روند (30 امتیاز) ---
            if trend['alignment_score'] > 0:
                long_score += min(abs(trend['alignment_pct']) * 0.3, 30)
                reasons_pro.append(f"روند صعودی ({trend['alignment_pct']:.0f}%)")
            elif trend['alignment_score'] < 0:
                short_score += min(abs(trend['alignment_pct']) * 0.3, 30)
                reasons_pro.append(f"روند نزولی ({abs(trend['alignment_pct']):.0f}%)")

            # --- SMC (20 امتیاز) ---
            if smc_data.get('available'):
                smc_dir = smc_data.get('combined_direction', 'neutral')
                smc_score = smc_data.get('combined_score', 0)
                if smc_dir == 'bullish':
                    long_score += min(abs(smc_score) * 10, 20)
                    reasons_pro.append(f"SMC صعودی")
                elif smc_dir == 'bearish':
                    short_score += min(abs(smc_score) * 10, 20)
                    reasons_pro.append(f"SMC نزولی")

                # Order Block
                smc_1h = smc_data.get('1h', {})
                if smc_1h.get('in_bull_ob'):
                    long_score += 10
                    reasons_pro.append("در Order Block صعودی")
                if smc_1h.get('in_bear_ob'):
                    short_score += 10
                    reasons_pro.append("در Order Block نزولی")

            # --- پرایس اکشن (15 امتیاز) ---
            if pa_1h.get('available'):
                pa_score = pa_1h.get('score', 0)
                if pa_score > 0:
                    long_score += min(pa_score, 15)
                    for p in pa_1h.get('patterns', []):
                        if p['direction'] == 'bullish' and p['strength'] == 'strong':
                            reasons_pro.append(f"الگو: {p['name']}")
                elif pa_score < 0:
                    short_score += min(abs(pa_score), 15)
                    for p in pa_1h.get('patterns', []):
                        if p['direction'] == 'bearish' and p['strength'] == 'strong':
                            reasons_pro.append(f"الگو: {p['name']}")

            # --- حجم (10 امتیاز) ---
            if vol_entry:
                vol_score = vol_entry.get('entry_score', 0)
                if vol_score > 0:
                    long_score += min(vol_score * 2, 10)
                elif vol_score < 0:
                    short_score += min(abs(vol_score) * 2, 10)

            # --- Volume Flow (10 امتیاز) ---
            if flow_data:
                flow_score = flow_data.get('flow_score', 0)
                if flow_score > 0:
                    long_score += min(flow_score * 5, 10)
                    reasons_pro.append(f"ورود پول ({flow_data.get('direction', '')})")
                elif flow_score < 0:
                    short_score += min(abs(flow_score) * 5, 10)
                    reasons_pro.append(f"خروج پول ({flow_data.get('direction', '')})")

            # --- OI + Funding + Long/Short از Coinalyze (15 امتیاز) ---
            if coinalyze_data.get('available'):
                funding_score = coinalyze_data.get('funding_score', 0)
                ls_score = coinalyze_data.get('ls_score', 0)
                oi_score = coinalyze_data.get('oi_score', 0)

                # Funding
                if funding_score > 0:
                    long_score += min(funding_score * 3, 5)
                    reasons_pro.append(f"Funding: {coinalyze_data.get('funding_signal', '')}")
                elif funding_score < 0:
                    short_score += min(abs(funding_score) * 3, 5)
                    reasons_pro.append(f"Funding: {coinalyze_data.get('funding_signal', '')}")

                # Long/Short Ratio (داده واقعی!)
                if ls_score > 0:
                    long_score += min(ls_score * 3, 5)
                    reasons_pro.append(f"L/S: {coinalyze_data.get('ls_signal', '')}")
                elif ls_score < 0:
                    short_score += min(abs(ls_score) * 3, 5)
                    reasons_pro.append(f"L/S: {coinalyze_data.get('ls_signal', '')}")

                # OI
                if oi_score > 0:
                    long_score += min(oi_score, 3)
                    short_score += min(oi_score, 3)  # OI بالا برای هر دو جهت خوب است
                    reasons_pro.append(f"OI: {coinalyze_data.get('oi_signal', '')}")

                # نمایش Long/Short در خلاصه
                if coinalyze_data.get('long_ratio', 0) > 0:
                    decision.risk_summary += f" | L/S: {coinalyze_data['long_ratio']:.0f}/{coinalyze_data['short_ratio']:.0f}"

            elif oi_data:
                funding_score = oi_data.get('funding_score', 0)
                if funding_score > 0:
                    long_score += min(funding_score * 5, 10)
                    reasons_pro.append(f"Funding منفی (حمایت لانگ)")
                elif funding_score < 0:
                    short_score += min(abs(funding_score) * 5, 10)
                    reasons_pro.append(f"Funding مثبت (حمایت شورت)")

            # --- BTC benchmark (15 امتیاز) ---
            if btc_data.get('available'):
                btc_score = btc_data.get('btc_score', 0)
                if btc_score > 0:
                    long_score += min(btc_score * 7, 15)
                    reasons_pro.append(f"قوی‌تر از BTC")
                elif btc_score < 0:
                    short_score += min(abs(btc_score) * 7, 15)
                    reasons_pro.append(f"ضعیف‌تر از BTC")

            # ===== فیلتر RSI (بحرانی) =====
            # اگر RSI اشباع فروش است، شورت نده
            if rsi_1h < 25 or rsi_4h < 25:
                short_score *= 0.2  # کاهش شدید امتیاز شورت
                reasons_con.append(f"⚠ RSI اشباع فروش ({rsi_1h:.0f}/{rsi_4h:.0f}) - احتمال بازگشت")
                # اگر اشباع شدید، شورت را صفر کن
                if rsi_1h < 20 or rsi_4h < 20:
                    short_score = 0
                    reasons_con.append("🚨 اشباع فروش شدید - شورت ممنوع!")

            # اگر RSI اشباع خرید است، لانگ نده
            if rsi_1h > 75 or rsi_4h > 75:
                long_score *= 0.2
                reasons_con.append(f"⚠ RSI اشباع خرید ({rsi_1h:.0f}/{rsi_4h:.0f}) - احتمال ریزش")
                if rsi_1h > 80 or rsi_4h > 80:
                    long_score = 0
                    reasons_con.append("🚨 اشباع خرید شدید - لانگ ممنوع!")

            # ===== تصمیم =====
            score_diff = abs(long_score - short_score)

            if score_diff < 10:
                decision.decision = Decision.WAIT
                decision.confidence = 0.3
                decision.brain_reasoning = "اختلاف امتیاز کم - صبر کنید"
            elif long_score > short_score:
                decision.decision = Decision.LONG
                decision.confidence = min(long_score / 100, 1.0)
                # محاسبه entry/stop/target
                setup = EntryExitCalculator.calculate_long_setup(analysis, ob_analysis)
                self._apply_setup(decision, setup)
            else:
                decision.decision = Decision.SHORT
                decision.confidence = min(short_score / 100, 1.0)
                setup = EntryExitCalculator.calculate_short_setup(analysis, ob_analysis)
                self._apply_setup(decision, setup)

            # قدرت سیگنال
            max_score = max(long_score, short_score)
            if max_score >= 70:
                decision.signal_strength = "قوی"
            elif max_score >= 50:
                decision.signal_strength = "متوسط"
            elif max_score >= 30:
                decision.signal_strength = "ضعیف"
            else:
                decision.signal_strength = "خنثی"

            # خلاصه‌ها
            decision.market_scan_summary = f"امتیاز: {max(long_score, short_score):.0f}/100 | RSI: {rsi_1h:.0f}"
            decision.fundamental_summary = f"روند: {trend.get('overall_bias', '')} | SMC: {smc_data.get('combined_direction', '')}"
            decision.bullish_summary = f"لانگ: {long_score:.0f} | شورت: {short_score:.0f}"
            decision.bearish_summary = f"اختلاف: {score_diff:.0f}"
            decision.risk_summary = f"RR: 1:{decision.risk_reward:.1f}" if decision.risk_reward > 0 else "نامشخص"

            decision.reasons_pro = reasons_pro[:8]
            decision.reasons_con = reasons_con[:5]
            decision.brain_reasoning = f"اسکنر: {decision.decision.value} (امتیاز لانگ: {long_score:.0f} / شورت: {short_score:.0f})"
            decision.final_analysis = decision.brain_reasoning

            # ذخیره داده‌ها
            decision.data = {
                'long_score': long_score,
                'short_score': short_score,
                'rsi_1h': rsi_1h,
                'rsi_4h': rsi_4h,
                'trend': trend,
                'smc': smc_data,
                'pa_1h': pa_1h,
                'flow': flow_data,
                'oi': oi_data,
                'btc': btc_data,
                'vol_entry': vol_entry,
            }

        except Exception as e:
            logger.error(f"خطا در اسکن {symbol}: {e}")
            decision.decision = Decision.NO_TRADE
            decision.final_analysis = f"خطا: {str(e)[:50]}"

        return decision

    def _apply_setup(self, decision: FinalDecision, setup: Dict):
        """اعمال entry/stop/targets"""
        if not setup:
            return
        decision.entry_price = setup.get('entry_price', 0)
        decision.stop_loss = setup.get('stop_loss', 0)
        decision.target_1 = setup.get('target_1', 0)
        decision.target_2 = setup.get('target_2', 0)
        decision.target_3 = setup.get('target_3', 0)
        decision.risk_reward = setup.get('risk_reward', 0)

    def scan_market(self, coins: List[Dict]) -> List[FinalDecision]:
        """اسکن کل بازار"""
        decisions = []
        total = len(coins)

        logger.info(f"اسکن {total} کوین...")

        for i, coin in enumerate(coins, 1):
            try:
                logger.info(f"  [{i}/{total}] {coin['base']}")
                decision = self.scan_coin(coin)

                emoji = {
                    Decision.LONG: '🟢', Decision.SHORT: '🔴',
                    Decision.WAIT: '🟡', Decision.NO_TRADE: '⚪'
                }.get(decision.decision, '⚪')
                logger.info(f"  {emoji} {decision.decision.value} ({decision.confidence:.0%})")

                decisions.append(decision)
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"خطا در {coin['symbol']}: {e}")

        return self._rank(decisions)

    def _rank(self, decisions: List[FinalDecision]) -> List[FinalDecision]:
        """رتبه‌بندی - حداقل 5 لانگ + 5 شورت"""
        longs = [d for d in decisions if d.decision == Decision.LONG]
        shorts = [d for d in decisions if d.decision == Decision.SHORT]
        waits = [d for d in decisions if d.decision == Decision.WAIT]

        longs.sort(key=lambda x: x.confidence, reverse=True)
        shorts.sort(key=lambda x: x.confidence, reverse=True)

        top_longs = longs[:config.TOP_LONG_COUNT]
        top_shorts = shorts[:config.TOP_SHORT_COUNT]

        # اگر کمتر از 5، WAIT‌های با اعتماد بالا را اضافه کن
        if len(top_longs) < 5:
            extra = sorted(waits, key=lambda x: x.confidence, reverse=True)
            top_longs.extend(extra[:5 - len(top_longs)])
        if len(top_shorts) < 5:
            extra = sorted(waits, key=lambda x: x.confidence, reverse=True)
            top_shorts.extend(extra[:5 - len(top_shorts)])

        logger.info(f"نتایج: {len(top_longs)} LONG, {len(top_shorts)} SHORT, {len(waits)} WAIT")
        return top_longs + top_shorts + waits[:3]
