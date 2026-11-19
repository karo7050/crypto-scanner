"""
Agent 1: اسکنر بازار (Market Scanner)
- شناسایی ورود پول واقعی
- افزایش حجم غیرعادی
- تغییرات Open Interest
- Funding Rate
- Long/Short Ratio
- Volume Delta و CVD
- نقدینگی و Order Book
- رتبه‌بندی فرصت‌ها

بسته‌بندی تحلیل‌های موجود در یک ایجنت یکپارچه
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List
from data_fetcher import DataFetcher
from oi_funding import OIFundingAnalyzer
from volume_flow import VolumeFlowAnalyzer
from liquidity import LiquidityAnalyzer
from smc_analyzer import SMCAnalyzer
from btc_benchmark import BTCBenchmarkAnalyzer
from core.data_models import MarketScanResult, AgentReport
import config
import logging

logger = logging.getLogger(__name__)


class MarketScannerAgent:
    """Agent 1: اسکنر بازار"""

    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher

    def scan_coin(self, coin: Dict, timeframes_data: Dict) -> AgentReport:
        """
        اسکن کامل یک ارز برای شناسایی فرصت
        """
        symbol = coin['symbol']
        base = coin['base']
        report = AgentReport(
            agent_name="Market Scanner",
            coin_symbol=symbol,
            timestamp=config.tehran_now_str(),
        )

        scan = MarketScanResult(symbol=symbol)

        try:
            # 1. Open Interest و Funding Rate
            oi_data = OIFundingAnalyzer.fetch_oi_and_funding(symbol)
            if oi_data:
                scan.funding_rate = oi_data.get('funding_rate')
                scan.oi_change = oi_data.get('oi_usd')  # snapshot فعلی
                if oi_data.get('funding_score', 0) != 0:
                    scan.reasons.append(f"Funding: {oi_data.get('funding_analysis', '')}")
                report.data['oi_funding'] = oi_data

            # 2. Volume Flow (ورود/خروج پول)
            tf_1h = timeframes_data.get('1h')
            if tf_1h is not None:
                flow_data = VolumeFlowAnalyzer.compute_flow(tf_1h)
                if flow_data:
                    scan.volume_delta = flow_data.get('net_flow_24h_usd')
                    scan.cvd = flow_data.get('cvd_24h')
                    scan.volume_anomaly = abs(flow_data.get('flow_intensity', 0)) > 10
                    if flow_data.get('flow_score', 0) != 0:
                        scan.reasons.append(f"Volume Flow: {flow_data.get('flow_signal', '')}")
                    report.data['volume_flow'] = flow_data

            # 3. Order Book و نقدینگی
            order_book = self.fetcher.fetch_order_book(symbol)
            if order_book:
                ob_analysis = LiquidityAnalyzer.analyze_order_book(order_book)
                if ob_analysis:
                    scan.order_book_imbalance = ob_analysis.get('imbalance')
                    scan.liquidity_score = abs(ob_analysis.get('pressure_score', 0))
                    if ob_analysis.get('pressure_score', 0) != 0:
                        scan.reasons.append(f"Order Book: {ob_analysis.get('pressure', '')}")
                    report.data['order_book'] = ob_analysis

            # 4. SMC تحلیل ساختار
            smc_data = SMCAnalyzer.analyze_multi_tf(timeframes_data)
            if smc_data.get('available'):
                scan.signal_strength = smc_data.get('combined_score', 0)
                scan.reasons.append(f"SMC: {smc_data.get('combined_direction', 'neutral')}")
                report.data['smc'] = smc_data

            # 5. BTC benchmark
            btc_pair_data = timeframes_data.get('_btc_pair')
            if btc_pair_data:
                btc_data = BTCBenchmarkAnalyzer.analyze_btc_pair(btc_pair_data)
                if btc_data.get('available'):
                    scan.reasons.append(f"vs BTC: {btc_data.get('btc_strength', '')}")
                    report.data['btc_benchmark'] = btc_data

            # محاسبه امتیاز کلی
            scan.signal_strength = self._calculate_signal_strength(scan, report)
            report.data['scan_result'] = scan.__dict__
            report.score = scan.signal_strength
            report.confidence = min(scan.signal_strength / 100, 1.0)
            report.reasons_pro = [r for r in scan.reasons if 'قوی' in r or 'تایید' in r or 'INFLOW' in r or 'قوی‌تر' in r]
            report.reasons_con = [r for r in scan.reasons if 'ضعیف' in r or 'هشدار' in r or 'OUTFLOW' in r or 'ضعیف‌تر' in r]
            report.recommendation = "SCAN_COMPLETE"

        except Exception as e:
            logger.error(f"خطا در اسکن {symbol}: {e}")
            report.errors.append(str(e))

        return report

    def _calculate_signal_strength(self, scan: MarketScanResult, report: AgentReport) -> float:
        """
        محاسبه قدرت سیگنال بر اساس همه داده‌ها
        خروجی: 0-100
        """
        score = 0.0

        # SMC (بالاترین وزن - 40%)
        smc_data = report.data.get('smc', {})
        if smc_data.get('available'):
            smc_combined = abs(smc_data.get('combined_score', 0))
            score += min(smc_combined * 10, 40)

        # Volume Flow (20%)
        flow_data = report.data.get('volume_flow', {})
        if flow_data:
            flow_intensity = abs(flow_data.get('flow_intensity', 0))
            score += min(flow_intensity, 20)

        # OI/Funding (15%)
        oi_data = report.data.get('oi_funding', {})
        if oi_data:
            funding_score = abs(oi_data.get('funding_score', 0))
            score += min(funding_score * 5, 15)

        # Order Book (15%)
        ob_data = report.data.get('order_book', {})
        if ob_data:
            ob_pressure = abs(ob_data.get('pressure_score', 0))
            score += min(ob_pressure * 5, 15)

        # BTC benchmark (10%)
        btc_data = report.data.get('btc_benchmark', {})
        if btc_data.get('available'):
            btc_score = abs(btc_data.get('btc_score', 0))
            score += min(btc_score * 5, 10)

        return min(score, 100)
