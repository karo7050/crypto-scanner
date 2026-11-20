"""
حافظه تصمیمات (Memory Log)
الهام از TradingAgents

ذخیره تصمیمات قبلی، ارزیابی نتایج، یادگیری
هر تصمیم در فایل memory_log.json ذخیره می‌شود
و در تحلیل بعدی به مغز مرکزی داده می‌شود
"""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import config
import logging

logger = logging.getLogger(__name__)

MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'memory_log.json')


class MemoryLog:
    """حافظه تصمیمات سیستم"""

    def __init__(self):
        self.log = self._load()

    def _load(self) -> Dict:
        """بارگذاری حافظه"""
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"خطا در بارگذاری memory: {e}")
        return {'decisions': [], 'lessons': []}

    def _save(self):
        """ذخیره حافظه"""
        try:
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.log, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطا در ذخیره memory: {e}")

    def add_decision(self, symbol: str, direction: str, entry: float,
                     stop: float, targets: List[float], confidence: float,
                     reasoning: str):
        """افزودن تصمیم جدید به حافظه"""
        decision = {
            'id': f"{symbol}_{config.tehran_now().strftime('%Y%m%d_%H%M')}",
            'symbol': symbol,
            'direction': direction,
            'entry': entry,
            'stop': stop,
            'targets': targets,
            'confidence': confidence,
            'reasoning': reasoning,
            'created_at': config.tehran_now_str(),
            'status': 'ACTIVE',
            'result': None,
            'return_pct': None,
            'lesson': None,
        }
        self.log['decisions'].append(decision)
        # نگهداری فقط 100 تصمیم اخیر
        if len(self.log['decisions']) > 100:
            self.log['decisions'] = self.log['decisions'][-100:]
        self._save()
        logger.info(f"تصمیم {symbol} {direction} به حافظه اضافه شد")

    def settle_decision(self, decision_id: str, current_price: float):
        """ارزیابی نتیجه یک تصمیم"""
        for d in self.log['decisions']:
            if d['id'] == decision_id and d['status'] == 'ACTIVE':
                entry = d['entry']
                stop = d['stop']
                targets = d.get('targets', [])

                if d['direction'] == 'LONG':
                    if current_price <= stop:
                        d['status'] = 'LOSS'
                        d['result'] = 'STOP_HIT'
                        d['return_pct'] = ((stop - entry) / entry) * 100
                    elif any(current_price >= t for t in targets):
                        d['status'] = 'WIN'
                        d['result'] = 'TARGET_HIT'
                        hit_target = [t for t in targets if current_price >= t][0]
                        d['return_pct'] = ((hit_target - entry) / entry) * 100
                    else:
                        d['return_pct'] = ((current_price - entry) / entry) * 100

                elif d['direction'] == 'SHORT':
                    if current_price >= stop:
                        d['status'] = 'LOSS'
                        d['result'] = 'STOP_HIT'
                        d['return_pct'] = ((entry - stop) / entry) * 100
                    elif any(current_price <= t for t in targets):
                        d['status'] = 'WIN'
                        d['result'] = 'TARGET_HIT'
                        hit_target = [t for t in targets if current_price <= t][0]
                        d['return_pct'] = ((entry - hit_target) / entry) * 100
                    else:
                        d['return_pct'] = ((entry - current_price) / entry) * 100

                # تولید درس
                d['lesson'] = self._generate_lesson(d)
                self._save()
                return d
        return None

    def _generate_lesson(self, decision: Dict) -> str:
        """تولید درس از نتیجه تصمیم"""
        if decision['status'] == 'WIN':
            return f"موفق: {decision['symbol']} {decision['direction']} با RR خوب کار کرد"
        elif decision['status'] == 'LOSS':
            return f"ناموفق: {decision['symbol']} {decision['direction']} استاپ خورد - شاید ورود زود بود"
        return ""

    def settle_all_pending(self, current_prices: Dict[str, float]):
        """ارزیابی همه تصمیمات فعال"""
        settled = 0
        for d in self.log['decisions']:
            if d['status'] == 'ACTIVE' and d['symbol'] in current_prices:
                self.settle_decision(d['id'], current_prices[d['symbol']])
                settled += 1

        # انتقال درس‌ها به لیست lessons
        for d in self.log['decisions']:
            if d.get('lesson') and d['lesson'] not in self.log['lessons']:
                self.log['lessons'].append(d['lesson'])
                if len(self.log['lessons']) > 20:
                    self.log['lessons'] = self.log['lessons'][-20:]

        if settled:
            self._save()
            logger.info(f"{settled} تصمیم ارزیابی شد")

    def get_recent_decisions(self, symbol: str = None, limit: int = 5) -> List[Dict]:
        """دریافت تصمیمات اخیر"""
        decisions = self.log['decisions']
        if symbol:
            decisions = [d for d in decisions if d['symbol'] == symbol]
        return decisions[-limit:]

    def get_lessons(self) -> List[str]:
        """دریافت درس‌های آموخته شده"""
        return self.log.get('lessons', [])

    def get_stats(self) -> Dict:
        """آمار عملکرد"""
        decisions = self.log['decisions']
        settled = [d for d in decisions if d['status'] in ['WIN', 'LOSS']]
        wins = [d for d in settled if d['status'] == 'WIN']
        losses = [d for d in settled if d['status'] == 'LOSS']

        win_rate = (len(wins) / len(settled) * 100) if settled else 0
        avg_win = sum(d.get('return_pct', 0) for d in wins) / len(wins) if wins else 0
        avg_loss = sum(d.get('return_pct', 0) for d in losses) / len(losses) if losses else 0

        return {
            'total_decisions': len(decisions),
            'settled': len(settled),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'active': len([d for d in decisions if d['status'] == 'ACTIVE']),
        }

    def get_memory_context(self, symbol: str = None) -> str:
        """دریافت context حافظه برای LLM"""
        recent = self.get_recent_decisions(symbol, limit=3)
        lessons = self.get_lessons()[-5:]
        stats = self.get_stats()

        context = f"آمار عملکرد: Win Rate: {stats['win_rate']:.1f}% | {stats['wins']}W/{stats['losses']}L"
        if recent:
            context += f"\nتصمیمات اخیر: " + " | ".join(
                f"{d['symbol']} {d['direction']} → {d['status']}" for d in recent
            )
        if lessons:
            context += f"\nدرس‌ها: " + " | ".join(lessons[:3])

        return context
