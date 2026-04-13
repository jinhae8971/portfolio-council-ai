"""데이터 수집 추상 인터페이스"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class DataFetcher(ABC):
    """시장 데이터 수집 추상 인터페이스."""

    @abstractmethod
    def fetch(self, tickers: List[str]) -> Dict[str, Any]:
        """티커 목록에 대한 시장 데이터를 수집하여 반환."""
        raise NotImplementedError


class MacroFetcher(ABC):
    """매크로 경제 데이터 수집 인터페이스."""

    @abstractmethod
    def fetch(self) -> Dict[str, Any]:
        raise NotImplementedError


class CryptoFetcher(ABC):
    """암호화폐 데이터 수집 인터페이스."""

    @abstractmethod
    def fetch(self, coins: List[str]) -> Dict[str, Any]:
        raise NotImplementedError
