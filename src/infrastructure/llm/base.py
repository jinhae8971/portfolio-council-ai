"""LLM Provider 추상 인터페이스

Stage 1: ClaudeLLMProvider
Stage 2+: OpenAILLMProvider, MultiLLMProvider (fallback)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class LLMProvider(ABC):
    """LLM 호출 추상 인터페이스. 모든 에이전트와 Moderator가 이 인터페이스를 사용."""

    @abstractmethod
    def complete(self, system: str, messages: list, max_tokens: int = 2048) -> str:
        """LLM에 메시지를 보내고 응답 텍스트를 반환.

        Args:
            system: 시스템 프롬프트
            messages: [{"role": "user", "content": "..."}] 형식
            max_tokens: 최대 응답 토큰 수

        Returns:
            LLM 응답 텍스트

        Raises:
            Exception: API 호출 실패 시
        """
        raise NotImplementedError
