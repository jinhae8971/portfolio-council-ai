"""Multi LLM Provider — Primary + Fallback 자동 전환

Claude가 다운되면 자동으로 OpenAI로 전환.
전환 시 로깅하여 운영자가 알 수 있도록 함.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .base import LLMProvider

logger = logging.getLogger(__name__)


class MultiLLMProvider(LLMProvider):
    """Primary LLM 실패 시 Fallback으로 자동 전환.

    사용 예:
        llm = MultiLLMProvider(
            primary=ClaudeLLMProvider(model="claude-sonnet-4-6"),
            fallback=OpenAILLMProvider(model="gpt-4o"),
        )
    """

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        primary_name: str = "Claude",
        fallback_name: str = "OpenAI",
    ):
        self.primary = primary
        self.fallback = fallback
        self.primary_name = primary_name
        self.fallback_name = fallback_name

        # 통계
        self._primary_calls = 0
        self._fallback_calls = 0
        self._primary_failures = 0

    def complete(self, system: str, messages: list, max_tokens: int = 2048) -> str:
        """Primary 시도 → 실패 시 Fallback으로 전환."""

        # 1) Primary 시도
        try:
            result = self.primary.complete(system, messages, max_tokens)
            self._primary_calls += 1
            return result

        except Exception as primary_error:
            self._primary_failures += 1
            logger.warning(
                f"[MultiLLM] {self.primary_name} 실패: {primary_error}. "
                f"{self.fallback_name}으로 전환 "
                f"(실패 누적: {self._primary_failures}회)"
            )

            # 2) Fallback 시도
            try:
                result = self.fallback.complete(system, messages, max_tokens)
                self._fallback_calls += 1
                logger.info(f"[MultiLLM] {self.fallback_name} 성공 (fallback)")
                return result

            except Exception as fallback_error:
                logger.error(
                    f"[MultiLLM] 양쪽 모두 실패! "
                    f"{self.primary_name}: {primary_error}, "
                    f"{self.fallback_name}: {fallback_error}"
                )
                # Primary 에러를 올림 (원래 의도한 LLM의 에러가 더 의미있음)
                raise primary_error

    @property
    def stats(self) -> dict:
        """호출 통계."""
        total = self._primary_calls + self._fallback_calls
        return {
            "primary_calls": self._primary_calls,
            "fallback_calls": self._fallback_calls,
            "primary_failures": self._primary_failures,
            "total_calls": total,
            "fallback_rate": (
                round(self._fallback_calls / total * 100, 1) if total > 0 else 0
            ),
        }
