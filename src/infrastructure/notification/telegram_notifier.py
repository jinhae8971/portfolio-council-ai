"""Telegram 알림 발송"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.environ.get("TELEGRAM_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    def send(self, verdict: dict, date_str: str, dashboard_url: str = "") -> bool:
        if not self.token or not self.chat_id:
            logger.warning("[Telegram] 토큰/채팅ID 미설정 — 알림 건너뜀")
            return False

        consensus = verdict.get("consensus_type", "unknown")
        confidence = verdict.get("confidence_score", 0)
        summary = verdict.get("summary", "")[:300]
        risks = ", ".join(verdict.get("risk_warnings", [])[:3])
        changes = verdict.get("portfolio_changes", [])

        emoji = {"strong_consensus": "🟢", "majority_view": "🟡",
                 "split_decision": "🟠", "no_consensus": "🔴"}.get(consensus, "⚪")

        changes_text = ""
        for c in changes[:5]:
            action_emoji = {"increase": "📈", "reduce": "📉", "add_new": "🆕", "remove": "❌"}.get(
                c.get("action", ""), "🔄"
            )
            changes_text += (
                f"\n  {action_emoji} {c.get('ticker', '?')}: "
                f"{c.get('from_weight', 0)}% → {c.get('to_weight', 0)}%"
            )

        msg = (
            f"📊 <b>Portfolio Council — {date_str}</b>\n\n"
            f"{emoji} 합의: <b>{consensus}</b> (확신도 {confidence}%)\n\n"
            f"📌 <b>요약</b>\n{summary}\n"
        )
        if changes_text:
            msg += f"\n📋 <b>변경 제안</b>{changes_text}\n"
        if risks:
            msg += f"\n⚠️ 리스크: {risks}"
        if dashboard_url:
            msg += f"\n\n📎 <a href='{dashboard_url}'>대시보드 보기</a>"

        try:
            import requests
            resp = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=15,
            )
            ok = resp.status_code == 200
            if ok:
                logger.info("[Telegram] 알림 전송 성공")
            else:
                logger.warning(f"[Telegram] HTTP {resp.status_code}: {resp.text[:200]}")
            return ok
        except Exception as e:
            logger.error(f"[Telegram] 전송 실패: {e}")
            return False
