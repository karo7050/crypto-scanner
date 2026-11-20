"""
ماژول معامله خودکار Bybit (Demo/Testnet)
Bybit Auto-Trader for Demo Account

اتصال به Bybit testnet برای:
- باز کردن خودکار پوزیشن LONG/SHORT
- تنظیم استاپ لاس و تارگت
- بستن پوزیشن‌ها
- بک‌تست با معامله واقعی (دمو)

استفاده:
1. در Bybit حساب testnet بسازید: https://testnet.bybit.com
2. API key از testnet دریافت کنید
3. تنظیم متغیرهای محیطی:
   BYBIT_TESTNET_API_KEY=your_key
   BYBIT_TESTNET_API_SECRET=your_secret
"""
import ccxt
import os
import logging
from typing import Dict, Optional
import config

logger = logging.getLogger(__name__)


class BybitAutoTrader:
    """معامله خودکار در Bybit Testnet (Demo)"""

    def __init__(self):
        self.api_key = os.environ.get('BYBIT_TESTNET_API_KEY', '')
        self.api_secret = os.environ.get('BYBIT_TESTNET_API_SECRET', '')
        self.is_testnet = True
        self.exchange = None

        if self.api_key and self.api_secret:
            self._connect()
        else:
            logger.warning("Bybit testnet API keys تنظیم نشده")
            logger.info("برای فعال‌سازی:")
            logger.info("1. به https://testnet.bybit.com بروید")
            logger.info("2. حساب demo بسازید")
            logger.info("3. API key دریافت کنید")
            logger.info("4. export BYBIT_TESTNET_API_KEY='your_key'")
            logger.info("5. export BYBIT_TESTNET_API_SECRET='your_secret'")

    def _connect(self):
        """اتصال به Bybit testnet"""
        try:
            self.exchange = ccxt.bybit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'linear',  # فیوچرز USDT
                },
            })
            # تنظیم testnet
            self.exchange.set_sandbox_mode(True)
            self.exchange.load_markets()
            logger.info("✓ متصل به Bybit Testnet (Demo)")
        except Exception as e:
            logger.error(f"خطا در اتصال به Bybit testnet: {e}")
            self.exchange = None

    def is_ready(self) -> bool:
        """آیا آماده معامله است؟"""
        return self.exchange is not None

    def open_position(self, symbol: str, direction: str, entry_price: float,
                      stop_loss: float, take_profit: float, size_usd: float = 100) -> Dict:
        """
        باز کردن پوزیشن در Bybit testnet

        direction: 'LONG' یا 'SHORT'
        size_usd: حجم به USD
        """
        if not self.is_ready():
            return {'success': False, 'error': 'Bybit testnet متصل نیست'}

        try:
            # تبدیل سیمبل: BTC/USDT → BTCUSDT
            ticker = symbol.replace('/USDT', '') + 'USDT'

            # محاسبه حجم
            price = entry_price
            amount = size_usd / price

            # تنظیم side
            side = 'Buy' if direction == 'LONG' else 'Sell'

            # ایجاد سفارش market
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side.lower() if hasattr(self.exchange, 'lower') else side,
                amount=amount,
                params={
                    'stopLoss': stop_loss,
                    'takeProfit': take_profit,
                    'category': 'linear',
                }
            )

            logger.info(f"✓ پوزیشن {direction} باز شد: {symbol}")
            logger.info(f"  حجم: {amount} | ورود: ~{price}")
            logger.info(f"  استاپ: {stop_loss} | تارگت: {take_profit}")

            return {
                'success': True,
                'order_id': order.get('id', ''),
                'symbol': symbol,
                'direction': direction,
                'size': amount,
                'entry_price': price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
            }

        except Exception as e:
            logger.error(f"خطا در باز کردن پوزیشن: {e}")
            return {'success': False, 'error': str(e)}

    def close_position(self, symbol: str) -> Dict:
        """بستن پوزیشن"""
        if not self.is_ready():
            return {'success': False, 'error': 'Bybit testnet متصل نیست'}

        try:
            # دریافت پوزیشن فعلی
            positions = self.exchange.fetch_positions([symbol])
            for pos in positions:
                if pos.get('contracts', 0) > 0:
                    side = 'Sell' if pos['side'] == 'long' else 'Buy'
                    order = self.exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=side.lower(),
                        amount=pos['contracts'],
                        params={'reduceOnly': True, 'category': 'linear'}
                    )
                    logger.info(f"✓ پوزیشن {symbol} بسته شد")
                    return {'success': True, 'order_id': order.get('id', '')}

            return {'success': False, 'error': 'پوزیشن فعال یافت نشد'}

        except Exception as e:
            logger.error(f"خطا در بستن پوزیشن: {e}")
            return {'success': False, 'error': str(e)}

    def get_balance(self) -> Dict:
        """دریافت موجودی حساب دمو"""
        if not self.is_ready():
            return {'success': False}

        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {})
            return {
                'success': True,
                'free': usdt.get('free', 0),
                'used': usdt.get('used', 0),
                'total': usdt.get('total', 0),
            }
        except Exception as e:
            logger.error(f"خطا در دریافت موجودی: {e}")
            return {'success': False, 'error': str(e)}

    def get_open_positions(self) -> list:
        """دریافت همه پوزیشن‌های باز"""
        if not self.is_ready():
            return []

        try:
            positions = self.exchange.fetch_positions()
            active = []
            for pos in positions:
                if pos.get('contracts', 0) > 0:
                    active.append({
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': pos['contracts'],
                        'entry': pos['entryPrice'],
                        'pnl': pos.get('unrealizedPnl', 0),
                        'liq': pos.get('liquidationPrice', 0),
                    })
            return active
        except Exception as e:
            logger.error(f"خطا در دریافت پوزیشن‌ها: {e}")
            return []

    def execute_decision(self, decision) -> Dict:
        """
        اجرای تصمیم مغز مرکزی به‌طور خودکار

        decision: FinalDecision object
        """
        if not self.is_ready():
            return {'success': False, 'error': 'Bybit testnet متصل نیست'}

        from core.data_models import Decision

        if decision.decision not in [Decision.LONG, Decision.SHORT]:
            return {'success': False, 'error': f'تصمیم {decision.decision.value} قابل اجرا نیست'}

        if decision.entry_price <= 0:
            return {'success': False, 'error': 'نقطه ورود نامعتبر'}

        # محاسبه حجم بر اساس اعتماد
        base_size = 100  # $100 پایه
        size = base_size * decision.confidence  # بیشتر اعتماد = حجم بیشتر

        return self.open_position(
            symbol=decision.symbol,
            direction=decision.decision.value,
            entry_price=decision.entry_price,
            stop_loss=decision.stop_loss,
            take_profit=decision.target_2,  # تارگت اصلی
            size_usd=size,
        )
