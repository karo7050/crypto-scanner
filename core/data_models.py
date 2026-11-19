"""
مدل‌های داده مشترک بین ایجنت‌ها
Shared Data Models for Multi-Agent System

هر ایجنت خروجی خود را در این ساختارها قرار می‌دهد
تا مغز مرکزی بتواند همه را جمع‌بندی کند.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class Decision(Enum):
    """تصمیم نهایی سیستم"""
    LONG = "LONG"
    SHORT = "SHORT"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"


class SignalStrength(Enum):
    """قدرت سیگنال"""
    STRONG = "قوی"
    MODERATE = "متوسط"
    WEAK = "ضعیف"
    NONE = "خنثی"


@dataclass
class AgentReport:
    """ساختار استاندارد گزارش هر ایجنت"""
    agent_name: str
    coin_symbol: str
    timestamp: str
    data: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0  # امتیاز 0-100
    confidence: float = 0.0  # اعتماد 0-1
    reasons_pro: List[str] = field(default_factory=list)  # دلایل موافق
    reasons_con: List[str] = field(default_factory=list)  # دلایل مخالف
    recommendation: str = ""  # توصیه
    errors: List[str] = field(default_factory=list)


@dataclass
class MarketScanResult:
    """خروجی Agent 1: اسکنر بازار"""
    symbol: str
    # جریان نقدینگی
    volume_delta: Optional[float] = None
    cvd: Optional[float] = None
    volume_anomaly: bool = False
    # مشتقات
    oi_change: Optional[float] = None
    funding_rate: Optional[float] = None
    long_short_ratio: Optional[float] = None
    # نقدینگی
    order_book_imbalance: Optional[float] = None
    liquidity_score: float = 0.0
    # قدرت سیگنال
    signal_strength: float = 0.0
    # رتبه
    rank: int = 0
    # دلایل
    reasons: List[str] = field(default_factory=list)


@dataclass
class FundamentalResult:
    """خروجی Agent 2: تحلیلگر بنیادی"""
    symbol: str
    news_sentiment: float = 0.0  # -1 to 1
    news_count: int = 0
    positive_news: int = 0
    negative_news: int = 0
    events_impact: str = "low"
    project_health: str = "unknown"
    ecosystem_score: float = 0.0
    fundamental_score: float = 0.0
    key_factors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class BullishResult:
    """خروجی Agent 3: تحلیلگر خوش‌بین"""
    symbol: str
    is_bullish: bool = False
    bullish_score: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)
    risk_reward: float = 0.0
    structure: str = ""
    confirmations: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class BearishResult:
    """خروجی Agent 4: تحلیلگر بدبین"""
    symbol: str
    is_bearish: bool = False
    bearish_score: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)
    risk_reward: float = 0.0
    structure: str = ""
    confirmations: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class RiskAssessment:
    """خروجی Agent 5: مدیر ریسک"""
    symbol: str
    approved: bool = False
    risk_score: float = 0.0  # 0-100 (higher = more risky)
    risk_reward: float = 0.0
    position_size_recommendation: float = 0.0  # % of portfolio
    stop_distance_pct: float = 0.0
    correlation_warning: bool = False
    market_condition: str = ""
    rejection_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class BacktestResult:
    """خروجی Agent 6: بک‌تستر"""
    symbol: str
    strategy_name: str
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    profitable_trades: int = 0
    backtest_approved: bool = False
    notes: str = ""


@dataclass
class FinalDecision:
    """تصمیم نهایی مغز مرکزی"""
    symbol: str
    decision: Decision = Decision.NO_TRADE
    confidence: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    target_3: float = 0.0
    risk_reward: float = 0.0
    signal_strength: str = ""
    # خلاصه تحلیل‌ها
    market_scan_summary: str = ""
    fundamental_summary: str = ""
    bullish_summary: str = ""
    bearish_summary: str = ""
    risk_summary: str = ""
    backtest_summary: str = ""
    # دلایل
    reasons_pro: List[str] = field(default_factory=list)
    reasons_con: List[str] = field(default_factory=list)
    # توضیح نهایی
    final_analysis: str = ""
    brain_reasoning: str = ""
