"""DI 컨테이너 — Stage별 다른 구성으로 앱 조립"""

from __future__ import annotations

import os
from typing import List

from ..agents import QuantAgent, MacroAgent, SectorAgent, CycleAgent, CryptoAgent, ValueAgent
from ..core.base_agent import BaseAgent
from ..infrastructure.llm.claude_provider import ClaudeLLMProvider
from ..infrastructure.storage.json_storage import JSONFileStorage


def create_agents(stage: str = "personal") -> tuple:
    """Stage별 구성 요소 생성.

    Returns:
        (agents, llm, storage) 튜플
    """
    if stage == "personal":
        llm = ClaudeLLMProvider(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            model=os.environ.get("LLM_MODEL", "claude-sonnet-4-6"),
        )
        storage = JSONFileStorage(base_dir="data")

        agents: List[BaseAgent] = [
            QuantAgent(llm),
            MacroAgent(llm),
            SectorAgent(llm),
            CycleAgent(llm),
            CryptoAgent(llm),
            ValueAgent(llm),
        ]

        return agents, llm, storage

    elif stage == "beta":
        from ..infrastructure.llm.openai_provider import OpenAILLMProvider
        from ..infrastructure.llm.multi_provider import MultiLLMProvider
        from ..infrastructure.storage.supabase_storage import SupabaseStorage

        llm = MultiLLMProvider(
            primary=ClaudeLLMProvider(
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                model=os.environ.get("LLM_MODEL", "claude-sonnet-4-6"),
            ),
            fallback=OpenAILLMProvider(
                api_key=os.environ.get("OPENAI_API_KEY"),
                model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            ),
        )
        storage = SupabaseStorage(
            url=os.environ["SUPABASE_URL"],
            key=os.environ["SUPABASE_KEY"],
            service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        )

        agents: List[BaseAgent] = [
            QuantAgent(llm),
            MacroAgent(llm),
            SectorAgent(llm),
            CycleAgent(llm),
            CryptoAgent(llm),
            ValueAgent(llm),
        ]

        return agents, llm, storage

    raise ValueError(f"Unknown stage: {stage}")
