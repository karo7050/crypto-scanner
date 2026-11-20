"""
ماژول معامله خودکار Toobit (Demo)
Toobit Auto-Trader

اتصال به Toobit برای:
- باز کردن خودکار پوزیشن LONG/SHORT
- تنظیم استاپ لاس و تارگت
- بستن پوزیشن‌ها
- بک‌تست با معامله واقعی (دمو)

استفاده:
1. در Toobit حساب دمو بسازید
2. API key دریافت کنید
3. export TOOBIT_API_KEY='your_key'
4. export TOOBIT_API_SECRET='your_secret'
"""
import ccxt
import os
import logging
from typing import Dict, Optional
import config

logger = logging.getLogger(__name__)


class ToobitAutoTrader:
    """معامله خودکار در Toobit"""

    def __init__(self):
        self.api_key = os.environ.get('TOOBIT_API_KEY', '')
        self.api_secret = os.environ.get('TOOBIT_API_SECRET', '')
        self.exchange = None

        if self.api_key and self.api_secret:
            self._connect()
        else:
            logger.warning("Toobit API keys تنظیم نشده")
            logger.info("برای فعال‌سازی:")
            logger.info("1. در Toobit حساب دمو بسازید")
            logger.info("2. API key دریافت کنید")
            logger.info("3. export TOOBIT_API_KEY='your_key'")
            logger.info("4. export TOOBIT_API_SECRET='your_secret'")

    def _connect(self):
        """اتصال به Toobit"""
        try:
            self.exchange = ccxt.toobit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'},  # فیوچرز
            })
            self.exchange.load_markets()
            logger.info(f"✓ متصل به Toobit - {len(self.exchange.symbols)} سیمبل")
        except Exception as e:
            logger.error(f"خطا در اتصال به Toobit: {e}")
            self.exchange = None

    def is_ready(self) -> bool:
        return self.exchange is not None

    def open_position(self, symbol: str, direction: str, entry_price: float,
                      stop_loss: float, take_profit: float, size_usd: float = 100) -> Dict:
        """باز کردن پوزیشن"""
        if not self.is_ready():
            return {'success': False, 'error': 'Toobit متصل نیست'}

        try:
            amount = size_usd / entry_price if entry_price > 0 else 0
            side = 'buy' if direction == 'LONG' else 'sell'

            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                params={
                    'stopLossPrice': stop_loss,
                    'takeProfitPrice': take_profit,
                }
            )

            logger.info(f"✓ پوزیشن {direction} باز شد: {symbol}")
            return {
                'success': True,
                'order_id': order.get('id', ''),
                'symbol': symbol,
                'direction': direction,
                'size': amount,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
            }

        except Exception as e:
            logger.error(f"خطا در باز کردن پوزیشن: {e}")
            return {'success': False, 'error': str(e)}

    def close_position(self, symbol: str) -> Dict:
        """بستن پوزیشن"""
        if not self.is_ready():
            return {'success': False, 'error': 'Toobit متصل نیست'}

        try:
            positions = self.exchange.fetch_positions([symbol])
            for pos in positions:
                if pos.get('contracts', 0) > 0:
                    side = 'sell' if pos['side'] == 'long' else 'buy'
                    self.exchange.create_order(
                        symbol=symbol, type='market', side=side,
                        amount=pos['contracts'], params={'reduceOnly': True}
                    )
                    logger.info(f"✓ پوزیشن {symbol} بسته شد")
                    return {'success': True}
            return {'success': False, 'error': 'پوزیشن یافت نشد'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_balance(self) -> Dict:
        """موجودی حساب"""
        if not self.is_ready():
            return {'success': False}
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {})
            return {'success': True, 'free': usdt.get('free', 0), 'total': usdt.get('total', 0)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def execute_decision(self, decision) -> Dict:
        """اجرای تصمیم مغز مرکزی"""
        from core.data_models import Decision

        if decision.decision not in [Decision.LONG, Decision.SHORT]:
            return {'success': False, 'error': f'تصمیم {decision.decision.value} قابل اجرا نیست'}

        if decision.entry_price <= 0:
            return {'success': False, 'error': 'نقطه ورود نامعتبر'}

        size = 100 * decision.confidence  # حجم بر اساس اعتماد
        return self.open_position(
            symbol=decision.symbol,
            direction=decision.decision.value,
            entry_price=decision.entry_price,
            stop_loss=decision.stop_loss,
            take_profit=decision.target_2,
            size_usd=size,
        )
