"""Claude API LLM Provider — Resilient 패턴 (재시도 + 타임아웃 + 메트릭)"""

from __future__ import annotations

import logging
import time
from typing import Optional

import anthropic

from .base import LLMProvider

logger = logging.getLogger(__name__)


class ClaudeLLMProvider(LLMProvider):
    """Anthropic Claude API를 통한 LLM 호출.

    - Exponential backoff 재시도
    - 구조화 로깅 (토큰 사용량, 응답 시간)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_retries: int = 3,
        timeout: float = 60.0,
    ):
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self.model = model
        self.max_retries = max_retries

    def complete(self, system: str, messages: list, max_tokens: int = 2048) -> str:
        """Claude API 호출 (재시도 포함)."""
        last_error = None

        for attempt in range(self.max_retries):
            start = time.time()
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                )
                duration_ms = int((time.time() - start) * 1000)

                # 토큰 사용량 로깅
                usage = resp.usage
                logger.info(
                    f"[Claude] model={self.model} "
                    f"input_tokens={usage.input_tokens} "
                    f"output_tokens={usage.output_tokens} "
                    f"duration={duration_ms}ms "
                    f"attempt={attempt + 1}"
                )

                return resp.content[0].text

            except anthropic.RateLimitError as e:
                wait = 2 ** attempt
                logger.warning(f"[Claude] Rate limit, retry in {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
                last_error = e

            except anthropic.APITimeoutError as e:
                logger.warning(f"[Claude] Timeout (attempt {attempt + 1})")
                last_error = e

            except anthropic.APIError as e:
                duration_ms = int((time.time() - start) * 1000)
                logger.error(f"[Claude] API error: {e} ({duration_ms}ms, attempt {attempt + 1})")
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(1)

        raise last_error or RuntimeError("LLM 호출 실패 (최대 재시도 초과)")
