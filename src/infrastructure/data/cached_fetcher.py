"""캐싱 래퍼 — API 실패 시 stale 캐시 fallback"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from .base import DataFetcher

logger = logging.getLogger(__name__)


class CachedDataFetcher(DataFetcher):
    """DataFetcher를 감싸 캐싱 + stale fallback 제공."""

    def __init__(
        self,
        fetcher: DataFetcher,
        cache_dir: str = "data/cache",
        max_age_hours: int = 24,
    ):
        self.fetcher = fetcher
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_hours = max_age_hours

    def fetch(self, tickers: List[str]) -> Dict[str, Any]:
        cache_key = self._make_key(tickers)
        cached = self._read_cache(cache_key)

        # 캐시 유효 → 바로 반환
        if cached and not self._is_stale(cached):
            logger.info(f"[Cache] HIT (fresh) — {cache_key}")
            return cached["data"]

        # 새 데이터 수집 시도
        try:
            fresh = self.fetcher.fetch(tickers)
            self._write_cache(cache_key, fresh)
            logger.info(f"[Cache] MISS — 새 데이터 수집 완료 — {cache_key}")
            return fresh
        except Exception as e:
            logger.warning(f"[Cache] 수집 실패: {e}")

            # stale 캐시라도 있으면 사용
            if cached:
                logger.info(f"[Cache] STALE fallback 사용 — {cache_key}")
                data = cached["data"]
                data["_stale"] = True
                data["_cached_at"] = cached["cached_at"]
                return data

            raise  # 캐시도 없으면 에러 전파

    def _make_key(self, tickers: List[str]) -> str:
        return "_".join(sorted(t.replace("/", "_") for t in tickers))[:100]

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> dict | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_cache(self, key: str, data: dict) -> None:
        cache_entry = {
            "cached_at": datetime.now().isoformat(),
            "data": data,
        }
        path = self._cache_path(key)
        path.write_text(json.dumps(cache_entry, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def _is_stale(self, cached: dict) -> bool:
        try:
            cached_at = datetime.fromisoformat(cached["cached_at"])
            return datetime.now() - cached_at > timedelta(hours=self.max_age_hours)
        except Exception:
            return True
