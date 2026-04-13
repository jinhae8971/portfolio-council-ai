"""OpenAI API LLM Provider — Stage 2 fallback용

Claude API 장애 시 자동 전환되는 백업 LLM.
MultiLLMProvider와 함께 사용.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAILLMProvider(LLMProvider):
    """OpenAI API를 통한 LLM 호출.

    Claude와 동일한 LLMProvider 인터페이스를 구현하므로
    에이전트 코드 변경 없이 교체 가능.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        max_retries: int = 3,
        timeout: float = 60.0,
    ):
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key, timeout=timeout)
        except ImportError:
            raise ImportError("openai 패키지가 필요합니다: pip install openai")
        self.model = model
        self.max_retries = max_retries

    def complete(self, system: str, messages: list, max_tokens: int = 2048) -> str:
        """OpenAI Chat Completions API 호출."""
        import openai

        # Anthropic messages 형식 → OpenAI 형식 변환
        oai_messages = [{"role": "system", "content": system}]
        for m in messages:
            oai_messages.append({"role": m["role"], "content": m["content"]})

        last_error = None
        for attempt in range(self.max_retries):
            start = time.time()
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=oai_messages,
                    max_tokens=max_tokens,
                    temperature=0.7,
                )
                duration_ms = int((time.time() - start) * 1000)

                usage = resp.usage
                logger.info(
                    f"[OpenAI] model={self.model} "
                    f"input_tokens={usage.prompt_tokens} "
                    f"output_tokens={usage.completion_tokens} "
                    f"duration={duration_ms}ms "
                    f"attempt={attempt + 1}"
                )

                return resp.choices[0].message.content

            except openai.RateLimitError as e:
                wait = 2 ** attempt
                logger.warning(f"[OpenAI] Rate limit, retry in {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
                last_error = e

            except openai.APITimeoutError as e:
                logger.warning(f"[OpenAI] Timeout (attempt {attempt + 1})")
                last_error = e

            except openai.APIError as e:
                duration_ms = int((time.time() - start) * 1000)
                logger.error(f"[OpenAI] API error: {e} ({duration_ms}ms)")
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(1)

        raise last_error or RuntimeError("OpenAI 호출 실패 (최대 재시도 초과)")
