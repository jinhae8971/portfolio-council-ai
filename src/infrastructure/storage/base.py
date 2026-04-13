"""결과 저장소 추상 인터페이스"""

from abc import ABC, abstractmethod
from typing import List, Optional


class ResultStorage(ABC):
    @abstractmethod
    def save_report(self, report: dict, user_id: str = "default") -> str:
        """보고서 저장. 저장된 report_id 반환."""
        raise NotImplementedError

    @abstractmethod
    def load_report(self, report_id: str) -> Optional[dict]:
        """보고서 로드."""
        raise NotImplementedError

    @abstractmethod
    def list_reports(self, user_id: str = "default", limit: int = 10) -> List[dict]:
        """보고서 목록 (최신순)."""
        raise NotImplementedError

    @abstractmethod
    def save_latest(self, report: dict, user_id: str = "default") -> None:
        """최신 보고서를 대시보드용으로 저장."""
        raise NotImplementedError
