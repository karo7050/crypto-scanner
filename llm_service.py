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
        self.max_retries = 2
        self.timeout = 60  # ثانیه

    def chat(self, prompt: str, system: str = "") -> Optional[str]:
        """
        ارسال درخواست chat به GLM-4
        برمی‌گرداند: متن پاسخ یا None در صورت خطا
        """
        for attempt in range(self.max_retries):
            try:
                # ایجاد فایل موقت برای خروجی
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    output_path = f.name

                # ساخت دستور
                cmd = [self.cli_path, 'chat']
                cmd.extend(['-p', prompt])
                if system:
                    cmd.extend(['-s', system])
                cmd.extend(['-o', output_path])

                # اجرای دستور
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    env={**os.environ}
                )

                # خواندن خروجی
                if os.path.exists(output_path):
                    with open(output_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # پاک کردن فایل موقت
                    os.unlink(output_path)

                    # استخراج متن پاسخ
                    choices = data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                        if content:
                            return content

                logger.warning(f"تلاش {attempt+1} ناموفق - خروجی خالی")
            except subprocess.TimeoutExpired:
                logger.warning(f"تایم‌اوت در تلاش {attempt+1}")
            except Exception as e:
                logger.warning(f"خطا در تلاش {attempt+1}: {e}")

            # پاک کردن فایل موقت در صورت خطا
            if 'output_path' in locals() and os.path.exists(output_path):
                try:
                    os.unlink(output_path)
                except Exception:
                    pass

        logger.error("همه تلاش‌ها ناموفق بود")
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
