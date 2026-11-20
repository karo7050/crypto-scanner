"""
سرویس LLM با استفاده از z-ai CLI (GLM-4)
LLM Service - Free GLM-4 via z-ai-web-dev-sdk CLI

استفاده از subprocess برای فراخوانی z-ai chat
رایگان - بدون نیاز به API key
"""
import subprocess
import json
import os
import tempfile
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """سرویس LLM رایگان با GLM-4"""

    def __init__(self):
        self.cli_path = 'z-ai'
        self.model = 'glm-4-plus'
        self.max_retries = 3
        self.timeout = 60
        self.last_call_time = 0
        self.min_delay = 3  # حداقل 3 ثانیه بین فراخوانی‌ها

    def chat(self, prompt: str, system: str = "") -> Optional[str]:
        """ارسال درخواست chat به GLM-4 با تأخیر"""
        import time as _time

        # تأخیر بین فراخوانی‌ها
        elapsed = _time.time() - self.last_call_time
        if elapsed < self.min_delay:
            _time.sleep(self.min_delay - elapsed)

        for attempt in range(self.max_retries):
            try:
                self.last_call_time = _time.time()

                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    output_path = f.name

                cmd = [self.cli_path, 'chat']
                cmd.extend(['-p', prompt[:8000]])  # محدودیت طول prompt
                if system:
                    cmd.extend(['-s', system[:2000]])
                cmd.extend(['-o', output_path])

                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=self.timeout, env={**os.environ}
                )

                if os.path.exists(output_path):
                    with open(output_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    os.unlink(output_path)

                    choices = data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                        if content:
                            return content

                logger.warning(f"LLM تلاش {attempt+1} ناموفق - خروجی خالی")
                _time.sleep(2)  # تأخیر اضافی قبل از retry

            except subprocess.TimeoutExpired:
                logger.warning(f"LLM تایم‌اوت تلاش {attempt+1}")
                _time.sleep(3)
            except Exception as e:
                logger.warning(f"LLM خطا تلاش {attempt+1}: {e}")
                _time.sleep(2)

            if 'output_path' in locals() and os.path.exists(output_path):
                try:
                    os.unlink(output_path)
                except Exception:
                    pass

        return None

    def chat_json(self, prompt: str, system: str = "") -> Optional[Dict]:
        """
        ارسال درخواست و دریافت پاسخ JSON
        """
        # اضافه کردن دستور JSON به system prompt
        json_system = system + "\n\nپاسخ را فقط در فرمت JSON معتبر ارائه بده. بدون متن اضافی."
        response = self.chat(prompt, json_system)

        if response:
            try:
                # تلاش برای parse JSON
                # حذف markdown code blocks اگر وجود دارد
                clean = response.strip()
                if clean.startswith('```'):
                    clean = clean.split('\n', 1)[1] if '\n' in clean else clean[3:]
                if clean.endswith('```'):
                    clean = clean[:-3]
                clean = clean.strip()

                return json.loads(clean)
            except json.JSONDecodeError:
                # اگر parse نشد، متن خام را برگردان
                logger.warning("پاسخ JSON معتبر نیست، متن خام برگردانده شد")
                return {'raw_response': response}

        return None


# نمونه singleton
_llm_service = None

def get_llm() -> LLMService:
    """دریافت نمونه LLM Service"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
