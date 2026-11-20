"""
ماژول دریافت داده‌ها
Data Fetcher Module
- دریافت لیست کوین‌های با مارکت کپ > 100M از CoinGecko
- دریافت OHLCV چند تایم فریم از Binance
- دریافت Order Book و وضعیت صرافی
"""
import ccxt
import pandas as pd
import requests
import time
import os
import logging
from typing import Dict, List, Optional, Tuple
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataFetcher:
    def __init__(self):
        # تلاش برای اتصال به صرافی‌های مختلف تا یافتن یکی که کار می‌کند
        self.exchange = None
        self.exchange_id = None
        self._connect_to_exchange()

    def _connect_to_exchange(self):
        """اتصال به اولین صرافی در دسترس از لیست اولویت"""
        for ex_id in config.EXCHANGE_PRIORITY:
            try:
                logger.info(f"تلاش برای اتصال به {ex_id.title()}...")
                exchange_class = getattr(ccxt, ex_id)
                ex = exchange_class({
                    'apiKey': config.EXCHANGE_API_KEY,
                    'secret': config.EXCHANGE_API_SECRET,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })
                ex.load_markets()
                # تست با دریافت یک OHLCV ساده
                test_ohlcv = ex.fetch_ohlcv('BTC/USDT', '1h', limit=2)
                if test_ohlcv:
                    self.exchange = ex
                    self.exchange_id = ex_id
                    logger.info(f"✓ متصل به {ex_id.title()} - {len(ex.symbols)} سیمبل")
                    return
            except Exception as e:
                logger.warning(f"✗ {ex_id.title()} در دسترس نیست: {str(e)[:100]}")
                continue

        if self.exchange is None:
            raise RuntimeError("هیچ صرافی در دسترس نیست! بررسی اتصال اینترنت.")

    # ----------------- دریافت لیست کوین‌ها با مارکت کپ -----------------
    def fetch_top_market_cap_coins(self) -> List[Dict]:
        """
        دریافت لیست کوین‌های با مارکت کپ حداقل 100 میلیون دلار از CoinGecko
        و تطبیق با سیمبل‌های موجود در صرافی
        دارای retry و fallback در صورت محدودیت نرخ CoinGecko
        """
        logger.info(f"در حال دریافت لیست کوین‌ها از CoinGecko (حداقل مارکت کپ: ${config.MIN_MARKET_CAP_USD:,.0f})")

        coins = []
        max_retries = 2  # کاهش retry برای جلوگیری از اتلاف وقت

        try:
            # دریافت صفحه به صفحه با retry
            for page in range(1, 6):  # تا 500 کوین
                success = False
                for attempt in range(max_retries):
                    try:
                        url = f"{config.COINGECKO_BASE_URL}/coins/markets"
                        params = {
                            'vs_currency': 'usd',
                            'order': 'market_cap_desc',
                            'per_page': 100,
                            'page': page,
                            'sparkline': False,
                            'price_change_percentage': '24h'
                        }
                        # هدر Demo API برای افزایش محدودیت نرخ (در صورت وجود)
                        headers = {}
                        demo_key = os.environ.get('COINGECKO_API_KEY', '')
                        if demo_key:
                            headers['x-cg-demo-api-key'] = demo_key

                        resp = requests.get(url, params=params, headers=headers, timeout=15)
                        if resp.status_code == 200:
                            data = resp.json()
                            if not data:
                                success = True
                                break
                            coins.extend(data)
                            logger.info(f"صفحه {page}: {len(data)} کوین دریافت شد")
                            time.sleep(2.0)  # احترام به محدودیت API
                            success = True
                            break
                        elif resp.status_code == 429:
                            wait_time = 5 * (attempt + 1)
                            logger.warning(f"CoinGecko 429 - تلاش مجدد در {wait_time}s (تلاش {attempt+1}/{max_retries})")
                            time.sleep(wait_time)
                        else:
                            logger.warning(f"خطای CoinGecko صفحه {page}: {resp.status_code}")
                            break
                    except Exception as e:
                        logger.warning(f"خطا در صفحه {page}: {e}")
                        time.sleep(3)

                if not success:
                    # اگر صفحه اول شکست خورد، مستقیماً به fallback برو
                    if page == 1:
                        logger.warning("CoinGecko در دسترس نیست. استفاده از fallback.")
                        break
                    else:
                        break

        except Exception as e:
            logger.error(f"خطا در دریافت داده CoinGecko: {e}")

        # اگر CoinGecko کار نکرد → fallback به استفاده از پرحجم‌ترین کوین‌های صرافی
        if not coins:
            logger.warning("CoinGecko در دسترس نیست. استفاده از fallback: پرحجم‌ترین کوین‌های صرافی")
            coins = self._fallback_top_volume_coins()

        # فیلتر مارکت کپ
        filtered = [c for c in coins if c.get('market_cap', 0) >= config.MIN_MARKET_CAP_USD]
        logger.info(f"کوین‌های با مارکت کپ >= ${config.MIN_MARKET_CAP_USD:,.0f}: {len(filtered)}")

        # اگر فیلتر مارکت کپ همه را حذف کرد (در حالت fallback)، همه را نگه دار
        if not filtered and coins:
            logger.warning("هیچ کوینی شرط مارکت کپ را نداشت. استفاده از همه کوین‌های پرحجم.")
            filtered = coins

        # فیلتر استیبل‌کوین‌ها و توکن‌های هم‌ارز
        before_stable_filter = len(filtered)
        filtered = [c for c in filtered if c.get('symbol', '').upper() not in config.STABLECOINS_BLACKLIST]
        logger.info(f"حذف استیبل‌کوین‌ها: {before_stable_filter - len(filtered)} مورد حذف شد، {len(filtered)} مورد باقی ماند")

        # تطبیق با سیمبل‌های صرافی (USDT pairs)
        # symbols می‌تواند dict یا list باشد بسته به نسخه ccxt
        symbols_obj = self.exchange.symbols
        if isinstance(symbols_obj, dict):
            exchange_symbols = set(symbols_obj.keys())
        else:
            exchange_symbols = set(symbols_obj)

        matched = []
        for coin in filtered:
            symbol = coin.get('symbol', '').upper()
            # سعی با USDT
            exchange_symbol = f"{symbol}/USDT"
            if exchange_symbol in exchange_symbols:
                matched.append({
                    'symbol': exchange_symbol,
                    'base': symbol,
                    'name': coin.get('name', ''),
                    'market_cap': coin.get('market_cap', 0),
                    'coingecko_id': coin.get('id', ''),
                    'price_change_24h': coin.get('price_change_percentage_24h', 0),
                    'current_price': coin.get('current_price', 0),
                    'total_volume': coin.get('total_volume', 0),
                })

        logger.info(f"کوین‌های قابل معامله در {self.exchange_id.title()}: {len(matched)}")

        # اضافه کردن ارزهای طلا/نقره از config
        for extra_coin in config.EXTRA_SCAN_COINS:
            exchange_symbol = f"{extra_coin['base']}/USDT"
            if exchange_symbol in exchange_symbols and extra_coin['base'] not in [c['base'] for c in matched]:
                # دریافت قیمت فعلی
                try:
                    ticker = self.fetch_ticker(exchange_symbol)
                    if ticker:
                        extra_coin['current_price'] = ticker.get('last', 0)
                        extra_coin['price_change_24h'] = ticker.get('percentage', 0)
                        extra_coin['total_volume'] = ticker.get('quoteVolume', 0)
                        extra_coin['symbol'] = exchange_symbol
                        matched.append(extra_coin)
                        logger.info(f"ارز اضافی اضافه شد: {extra_coin['base']}")
                except Exception as e:
                    logger.debug(f"خطا در دریافت {extra_coin['base']}: {e}")

        return matched[:config.MAX_COINS_TO_SCAN]

    def _fallback_top_volume_coins(self) -> List[Dict]:
        """
        Fallback: استفاده از پرحجم‌ترین کوین‌های صرافی به جای CoinGecko
        در حالت fallback، مارکت کپ دقیق در دسترس نیست، پس از volume استفاده می‌کنیم
        استیبل‌کوین‌ها حذف می‌شوند
        """
        try:
            tickers = self.exchange.fetch_tickers()
            # فیلتر USDT pairs
            usdt_tickers = []
            for symbol, t in tickers.items():
                if symbol.endswith('/USDT') and t.get('quoteVolume', 0) > 0:
                    base = symbol.replace('/USDT', '')
                    # حذف استیبل‌کوین‌ها و توکن‌های هم‌ارز با استفاده از لیست سیاه
                    if base in config.STABLECOINS_BLACKLIST:
                        continue
                    usdt_tickers.append({
                        'symbol': base,
                        'name': base,
                        'market_cap': t.get('quoteVolume', 0) * 10,  # تخمین تقریبی
                        'current_price': t.get('last', 0),
                        'total_volume': t.get('quoteVolume', 0),
                        'price_change_percentage_24h': t.get('percentage', 0),
                        'id': '',
                    })

            # مرتب‌سازی بر اساس حجم نقدی نزولی
            usdt_tickers.sort(key=lambda x: x['total_volume'], reverse=True)
            logger.info(f"fallback: {len(usdt_tickers)} کوین USDT از صرافی (بعد از حذف استیبل‌کوین‌ها)")
            return usdt_tickers
        except Exception as e:
            logger.error(f"خطا در fallback: {e}")
            return []

    # ----------------- دریافت OHLCV -----------------
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """
        دریافت داده OHLCV برای یک سیمبل و تایم فریم مشخص
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logger.debug(f"خطا در دریافت OHLCV {symbol} {timeframe}: {e}")
            return None

    # ----------------- دریافت Order Book -----------------
    def fetch_order_book(self, symbol: str, limit: int = 50) -> Optional[Dict]:
        """
        دریافت Order Book برای تحلیل نقدینگی و سطوح حمایت/مقاومت
        """
        try:
            ob = self.exchange.fetch_order_book(symbol, limit=limit)
            bids = pd.DataFrame(ob['bids'], columns=['price', 'amount'])
            asks = pd.DataFrame(ob['asks'], columns=['price', 'amount'])

            # محاسبه دیوارهای خرید و فروش
            bid_walls = bids.nlargest(5, 'amount')
            ask_walls = asks.nlargest(5, 'amount')

            # نسبت خرید به فروش (Bid/Ask Imbalance)
            bid_volume = bids['amount'].sum()
            ask_volume = asks['amount'].sum()
            imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0

            return {
                'bids': bids,
                'asks': asks,
                'bid_walls': bid_walls,
                'ask_walls': ask_walls,
                'bid_volume': bid_volume,
                'ask_volume': ask_volume,
                'imbalance': imbalance,  # > 0 یعنی فشار خرید بیشتر
                'spread': asks['price'].iloc[0] - bids['price'].iloc[0] if len(bids) and len(asks) else 0,
                'best_bid': bids['price'].iloc[0] if len(bids) else 0,
                'best_ask': asks['price'].iloc[0] if len(asks) else 0,
            }
        except Exception as e:
            logger.debug(f"خطا در دریافت Order Book {symbol}: {e}")
            return None

    # ----------------- دریافت اطلاعات تکرر -----------------
    def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """
        دریافت اطلاعات لحظه‌ای تکرر: قیمت، حجم 24 ساعت، تغییر قیمت
        """
        try:
            t = self.exchange.fetch_ticker(symbol)
            return {
                'last': t.get('last', 0),
                'high_24h': t.get('high', 0),
                'low_24h': t.get('low', 0),
                'volume_24h': t.get('baseVolume', 0),
                'quote_volume_24h': t.get('quoteVolume', 0),  # حجم به دلار
                'change_24h': t.get('change', 0),
                'percentage_24h': t.get('percentage', 0),
            }
        except Exception as e:
            logger.debug(f"خطا در دریافت تکرر {symbol}: {e}")
            return None

    # ----------------- دریافت همه تایم فریم‌ها + BTC pair -----------------
    def fetch_all_timeframes(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """
        دریافت OHLCV برای همه تایم فریم‌های تعریف شده
        + دریافت BTC pair برای مقایسه نسبت به بیت‌کوین
        """
        result = {}
        for tf in config.TIMEFRAMES:
            limit = config.CANDLE_LIMITS.get(tf, 100)
            df = self.fetch_ohlcv(symbol, tf, limit)
            if df is not None and len(df) >= 50:
                result[tf] = df
            time.sleep(0.15)  # احترام به Rate Limit

        # دریافت BTC pair برای مقایسه (مثلا ETH/BTC)
        if symbol != 'BTC/USDT':
            base = symbol.replace('/USDT', '')
            btc_symbol = f"{base}/BTC"
            btc_pair_data = {}
            for tf in config.TIMEFRAMES:
                try:
                    df_btc = self.fetch_ohlcv(btc_symbol, tf, limit=100)
                    if df_btc is not None and len(df_btc) >= 50:
                        btc_pair_data[tf] = df_btc
                    time.sleep(0.1)
                except Exception:
                    continue
            if btc_pair_data:
                result['_btc_pair'] = btc_pair_data
                logger.debug(f"BTC pair برای {base} دریافت شد")

        return result
