"""
ماژول Open Interest و Funding Rate
Open Interest & Funding Rate Module

دریافت داده‌های:
- Open Interest (موقعیت‌های باز) از Bybit API
- Funding Rate (نرخ تامین مالی)

این داده‌ها برای تشخیص:
- Long/Short squeeze
- فشار خرید/فروش در فیوچرز
- تغییرات OI + قیمت = جهت حرکت هوشمند پول
"""
import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class OIFundingAnalyzer:
    """تحلیل Open Interest و Funding Rate از Bybit"""

    # Bybit V5 API endpoints (رایگان، نیاز به کلید ندارد)
    BYBIT_OI_URL = "https://api.bybit.com/v5/market/open-interest"
    BYBIT_FUNDING_URL = "https://api.bybit.com/v5/market/tickers"

    @staticmethod
    def fetch_oi_and_funding(symbol: str) -> Dict:
        """
        دریافت Open Interest و Funding Rate برای یک سیمبل
        symbol: فرمت BTC/USDT → تبدیل به BTCUSDT
        """
        # تبدیل BTC/USDT → BTCUSDT
        base = symbol.replace('/USDT', '').replace('/usdt', '')
        ticker = f"{base}USDT"

        result = {
            'oi_usd': None,
            'oi_token': None,
            'funding_rate': None,
            'next_funding_time': None,
            'oi_analysis': '',
            'funding_analysis': '',
            'oi_score': 0,
            'funding_score': 0,
        }

        try:
            # دریافت Open Interest
            oi_resp = requests.get(
                OIFundingAnalyzer.BYBIT_OI_URL,
                params={'category': 'linear', 'symbol': ticker, 'interval': '1h'},
                timeout=10
            )
            if oi_resp.status_code == 200:
                oi_data = oi_resp.json()
                if oi_data.get('retCode') == 0 and oi_data.get('result', {}).get('list'):
                    oi_list = oi_data['result']['list']
                    if oi_list:
                        oi_token = float(oi_list[0].get('openInterest', 0))
                        # دریافت قیمت برای تبدیل به USD
                        price = OIFundingAnalyzer._get_current_price(ticker)
                        if price and oi_token:
                            oi_usd = oi_token * price
                            result['oi_token'] = oi_token
                            result['oi_usd'] = oi_usd

                            # تحلیل OI
                            if oi_usd > 500_000_000:
                                result['oi_analysis'] = 'OI بسیار بالا (نقدینگی قوی فیوچرز)'
                                result['oi_score'] = 2
                            elif oi_usd > 100_000_000:
                                result['oi_analysis'] = 'OI بالا (نقدینگی مناسب)'
                                result['oi_score'] = 1
                            elif oi_usd > 10_000_000:
                                result['oi_analysis'] = 'OI متوسط'
                                result['oi_score'] = 0
                            else:
                                result['oi_analysis'] = 'OI پایین (ریسک نقدینگی)'
                                result['oi_score'] = -1
        except Exception as e:
            logger.debug(f"خطا در دریافت OI برای {symbol}: {e}")

        try:
            # دریافت Funding Rate از ticker
            funding_resp = requests.get(
                OIFundingAnalyzer.BYBIT_FUNDING_URL,
                params={'category': 'linear', 'symbol': ticker},
                timeout=10
            )
            if funding_resp.status_code == 200:
                funding_data = funding_resp.json()
                if funding_data.get('retCode') == 0:
                    tickers = funding_data.get('result', {}).get('list', [])
                    if tickers:
                        t = tickers[0]
                        funding_rate = float(t.get('fundingRate', 0))
                        next_funding = t.get('nextFundingTime')

                        result['funding_rate'] = funding_rate
                        result['next_funding_time'] = next_funding

                        # تحلیل Funding Rate
                        # Funding منفی = شورت‌ها به لانگ‌ها پرداخت می‌کنند (احتمال کف)
                        # Funding مثبت = لانگ‌ها به شورت‌ها پرداخت می‌کنند (احتمال سقف)
                        if funding_rate < -0.0005:
                            result['funding_analysis'] = f'Funding منفی قوی ({funding_rate*100:.4f}%) - احتمال فشار شورت زیاد، کف محتمل'
                            result['funding_score'] = 2  # برای لانگ
                        elif funding_rate < -0.0001:
                            result['funding_analysis'] = f'Funding منفی ملایم ({funding_rate*100:.4f}%) - ترجیح轻度 شورت'
                            result['funding_score'] = 1
                        elif funding_rate > 0.001:
                            result['funding_analysis'] = f'Funding مثبت قوی ({funding_rate*100:.4f}%) - احتمال فشار لانگ زیاد، سقف محتمل'
                            result['funding_score'] = -2  # برای شورت
                        elif funding_rate > 0.0003:
                            result['funding_analysis'] = f'Funding مثبت ملایم ({funding_rate*100:.4f}%) - ترجیح轻度 لانگ'
                            result['funding_score'] = -1
                        else:
                            result['funding_analysis'] = f'Funding نزدیک صفر ({funding_rate*100:.4f}%) - متعادل'
                            result['funding_score'] = 0
        except Exception as e:
            logger.debug(f"خطا در دریافت Funding برای {symbol}: {e}")

        return result

    @staticmethod
    def _get_current_price(ticker: str) -> Optional[float]:
        """دریافت قیمت فعلی برای تبدیل OI به USD"""
        try:
            resp = requests.get(
                "https://api.bybit.com/v5/market/tickers",
                params={'category': 'linear', 'symbol': ticker},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get('retCode') == 0:
                    tickers = data.get('result', {}).get('list', [])
                    if tickers:
                        return float(tickers[0].get('lastPrice', 0))
        except Exception:
            pass
        return None

    @staticmethod
    def analyze(oi_data: Dict, price_change_24h: float) -> Dict:
        """
        تحلیل ترکیبی OI + Funding + تغییر قیمت
        - OI بالا + قیمت صعودی = روند صعودی قوی (پول هوشمند وارد می‌شود)
        - OI بالا + قیمت نزولی = روند نزولی قوی (پول هوشمند شورت می‌کند)
        - OI پایین + قیمت صعودی = رالی بدون پشتوانان (خطرناک)
        - OI در حال کاهش + قیمت تغییر = بسته شدن پوزیشن‌ها (خروج پول)
        """
        oi_usd = oi_data.get('oi_usd', 0)
        funding_rate = oi_data.get('funding_rate', 0)
        oi_score = oi_data.get('oi_score', 0)
        funding_score = oi_data.get('funding_score', 0)

        # تحلیل ترکیبی
        long_bias = 0
        short_bias = 0
        insights = []

        # Funding منفی = احتمال کف (لانگ)
        if funding_score > 0:
            long_bias += funding_score * 5
            insights.append(f"Funding منفی حمایت لانگ (Score: +{funding_score*5})")
        elif funding_score < 0:
            short_bias += abs(funding_score) * 5
            insights.append(f"Funding مثبت حمایت شورت (Score: +{abs(funding_score)*5})")

        # OI + تغییر قیمت
        if oi_usd and oi_usd > 50_000_000:
            if price_change_24h > 2:
                long_bias += 3
                insights.append("OI بالا + قیمت صعودی = پول هوشمند وارد می‌شود")
            elif price_change_24h < -2:
                short_bias += 3
                insights.append("OI بالا + قیمت نزولی = پول هوشمند شورت می‌کند")
        elif oi_usd and oi_usd < 10_000_000:
            insights.append("⚠ OI پایین - ریسک نقدینگی")

        return {
            'oi_data': oi_data,
            'long_bias': long_bias,
            'short_bias': short_bias,
            'insights': insights,
            'oi_usd': oi_usd,
            'funding_rate': funding_rate,
        }
