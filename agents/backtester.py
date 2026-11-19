"""
Agent 6: بک‌تستر (Backtester)
- آزمایش استراتژی روی داده تاریخی
- Win Rate, Profit Factor, Drawdown
- بررسی عملکرد در شرایط مختلف
- جلوگیری از استراتژی‌های ضعیف

این ایجنت از داده OHLCV موجود برای بک‌تست استفاده می‌کند.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from typing import Dict, List
from core.data_models import BacktestResult, AgentReport
import config
import logging

logger = logging.getLogger(__name__)


class BacktesterAgent:
    """Agent 6: بک‌تستر"""

    def backtest(self, coin: Dict, analysis: Dict, direction: str,
                 entry: float, stop: float, targets: List[float]) -> AgentReport:
        """
        بک‌تست استراتژی روی داده تاریخی
        """
        symbol = coin['symbol']
        report = AgentReport(
            agent_name="Backtester",
            coin_symbol=symbol,
            timestamp=config.tehran_now_str(),
        )

        result = BacktestResult(
            symbol=symbol,
            strategy_name=f"{direction}_SWING_SMC",
        )

        try:
            # استفاده از داده 1h برای بک‌تست
            tf_data = analysis.get('1h', {})
            df = tf_data.get('dataframe')

            if df is None or len(df) < 100:
                report.errors.append("داده کافی برای بک‌تست نیست")
                report.score = 0
                report.confidence = 0
                result.backtest_approved = False
                result.notes = "داده ناکافی"
                report.data['backtest_result'] = result.__dict__
                report.recommendation = "INSUFFICIENT_DATA"
                return report

            # شبیه‌سازی استراتژی روی 100 کندل اخیر
            trades = self._simulate_strategy(df, direction, entry, stop, targets)

            if not trades:
                report.errors.append("هیچ معامله‌ای در بک‌تست انجام نشد")
                result.backtest_approved = False
                report.recommendation = "NO_TRADES"
                report.data['backtest_result'] = result.__dict__
                return report

            # محاسبه آمار
            result.total_trades = len(trades)
            result.profitable_trades = sum(1 for t in trades if t['pnl'] > 0)
            result.win_rate = (result.profitable_trades / result.total_trades) * 100

            wins = [t['pnl'] for t in trades if t['pnl'] > 0]
            losses = [abs(t['pnl']) for t in trades if t['pnl'] < 0]

            result.avg_win = np.mean(wins) if wins else 0
            result.avg_loss = np.mean(losses) if losses else 0

            # Profit Factor
            gross_profit = sum(wins) if wins else 0
            gross_loss = sum(losses) if losses else 0
            result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

            # Max Drawdown
            cumulative = np.cumsum([t['pnl'] for t in trades])
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = running_max - cumulative
            result.max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0

            # تصمیم
            if result.win_rate >= 50 and result.profit_factor >= 1.5:
                result.backtest_approved = True
                report.reasons_pro.append(f"Win Rate: {result.win_rate:.1f}%")
                report.reasons_pro.append(f"Profit Factor: {result.profit_factor:.2f}")
            else:
                result.backtest_approved = False
                report.reasons_con.append(f"Win Rate پایین: {result.win_rate:.1f}%")
                report.reasons_con.append(f"Profit Factor پایین: {result.profit_factor:.2f}")

            report.score = result.win_rate
            report.confidence = result.win_rate / 100
            report.data['backtest_result'] = result.__dict__
            report.recommendation = "BACKTEST_PASSED" if result.backtest_approved else "BACKTEST_FAILED"

        except Exception as e:
            logger.error(f"خطا در بک‌تست {symbol}: {e}")
            report.errors.append(str(e))

        return report

    def _simulate_strategy(self, df: pd.DataFrame, direction: str,
                           current_entry: float, current_stop: float,
                           targets: List[float]) -> List[Dict]:
        """
        شبیه‌سازی استراتژی روی داده تاریخی

        استراتژی: ورود وقتی قیمت به entry می‌رسد
        خروج وقتی stop یا target خورده شود
        """
        trades = []
        in_position = False
        entry_price = 0
        stop_price = 0
        target_price = targets[1] if len(targets) > 1 else targets[0] if targets else current_entry * 1.03

        # نرمال‌سازی entry/stop بر اساس نسبت فعلی
        if current_entry > 0:
            entry_ratio = current_entry / df['close'].iloc[-1]
            stop_ratio = current_stop / df['close'].iloc[-1] if current_stop > 0 else entry_ratio * 0.95
            target_ratio = target_price / df['close'].iloc[-1]
        else:
            return trades

        # شبیه‌سازی روی 100 کندل اخیر
        recent = df.tail(100)

        for i in range(len(recent)):
            row = recent.iloc[i]

            # تعیین entry/stop/target برای این کندل (بر اساس نسبت)
            dynamic_entry = row['close'] * entry_ratio
            dynamic_stop = row['close'] * stop_ratio
            dynamic_target = row['close'] * target_ratio

            if direction == 'LONG':
                if not in_position:
                    # ورود وقتی قیمت به entry می‌رسد
                    if row['low'] <= dynamic_entry:
                        in_position = True
                        entry_price = dynamic_entry
                        stop_price = dynamic_stop
                        target_price_dyn = dynamic_target
                else:
                    # بررسی stop یا target
                    if row['low'] <= stop_price:
                        pnl = (stop_price - entry_price) / entry_price * 100
                        trades.append({'pnl': pnl, 'type': 'stop'})
                        in_position = False
                    elif row['high'] >= target_price_dyn:
                        pnl = (target_price_dyn - entry_price) / entry_price * 100
                        trades.append({'pnl': pnl, 'type': 'target'})
                        in_position = False

            elif direction == 'SHORT':
                if not in_position:
                    if row['high'] >= dynamic_entry:
                        in_position = True
                        entry_price = dynamic_entry
                        stop_price = dynamic_stop
                        target_price_dyn = dynamic_target
                else:
                    if row['high'] >= stop_price:
                        pnl = (entry_price - stop_price) / entry_price * 100
                        trades.append({'pnl': pnl, 'type': 'stop'})
                        in_position = False
                    elif row['low'] <= target_price_dyn:
                        pnl = (entry_price - target_price_dyn) / entry_price * 100
                        trades.append({'pnl': pnl, 'type': 'target'})
                        in_position = False

        return trades
