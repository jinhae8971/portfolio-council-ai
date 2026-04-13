"""합의 도출 알고리즘 — 근거 품질 가중 투표

규칙 기반 선행 집계를 수행하여 LLM Moderator의 fallback으로도 사용한다.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .schemas import ConsensusType, PortfolioStance


def weighted_vote(
    reports: List[dict],
    agent_weights: Dict[str, float] | None = None,
) -> Tuple[float, float]:
    """에이전트 보고서의 confidence 가중 stance 투표.

    Args:
        reports: Phase 1 보고서 목록
        agent_weights: 사용자 커스텀 가중치 (예: {"퀀트": 1.5, "크립토": 0.5})
                       None이면 모든 에이전트 동일 가중치(1.0)

    Returns:
        (weighted_score, avg_confidence)
        weighted_score: -2.0 ~ +2.0 범위
    """
    agent_weights = agent_weights or {}
    total_weight = 0.0
    weighted_sum = 0.0
    conf_sum = 0.0
    valid_count = 0

    for r in reports:
        conf = r.get("confidence_score", 0)
        stance_str = r.get("overall_stance", "MAINTAIN")
        agent_name = r.get("agent_name", "unknown")

        # 사용자 가중치 적용 (기본 1.0)
        user_weight = agent_weights.get(agent_name, 1.0)

        try:
            stance = PortfolioStance(stance_str)
        except ValueError:
            stance = PortfolioStance.MAINTAIN

        score = stance.score
        effective_weight = conf * user_weight
        weighted_sum += score * effective_weight
        total_weight += effective_weight
        conf_sum += conf
        valid_count += 1

    if total_weight == 0:
        return 0.0, 50.0

    return weighted_sum / total_weight, conf_sum / max(valid_count, 1)


def score_to_stance(score: float) -> PortfolioStance:
    """가중 점수를 PortfolioStance로 변환."""
    if score >= 1.5:
        return PortfolioStance.STRONG_OVERWEIGHT
    elif score >= 0.5:
        return PortfolioStance.OVERWEIGHT
    elif score <= -1.5:
        return PortfolioStance.STRONG_UNDERWEIGHT
    elif score <= -0.5:
        return PortfolioStance.UNDERWEIGHT
    else:
        return PortfolioStance.MAINTAIN


def determine_consensus_type(reports: List[dict]) -> ConsensusType:
    """에이전트 투표 분포에서 합의 유형 판정."""
    stances = []
    for r in reports:
        try:
            s = PortfolioStance(r.get("overall_stance", "MAINTAIN"))
        except ValueError:
            s = PortfolioStance.MAINTAIN
        stances.append(s)

    if not stances:
        return ConsensusType.NO_CONSENSUS

    # 가장 많은 stance 카운트
    from collections import Counter
    counter = Counter(stances)
    most_common_count = counter.most_common(1)[0][1]
    total = len(stances)

    if most_common_count >= total - 1:  # 5-6 동의
        return ConsensusType.STRONG_CONSENSUS
    elif most_common_count >= total // 2 + 1:  # 과반수
        return ConsensusType.MAJORITY_VIEW
    elif most_common_count == total // 2:  # 반반
        return ConsensusType.SPLIT_DECISION
    else:
        return ConsensusType.NO_CONSENSUS


def rule_based_verdict(
    reports: List[dict],
    agent_weights: Dict[str, float] | None = None,
) -> dict:
    """규칙 기반 가중 투표 결과 — LLM 실패 시 fallback.

    Args:
        reports: Phase 1 보고서 목록
        agent_weights: 사용자 커스텀 가중치

    Returns:
        Verdict 호환 dict
    """
    score, avg_conf = weighted_vote(reports, agent_weights)
    stance = score_to_stance(score)
    consensus = determine_consensus_type(reports)

    stance_votes = {}
    for r in reports:
        stance_votes[r.get("agent_name", "unknown")] = r.get("overall_stance", "MAINTAIN")

    return {
        "consensus_type": consensus.value,
        "confidence_score": int(avg_conf),
        "summary": f"규칙 기반 집계 결과: 가중 점수 {score:.2f}, 종합 판단 {stance.value}",
        "portfolio_changes": [],
        "risk_warnings": [],
        "stance_votes": stance_votes,
        "key_insights": [f"에이전트 {len(reports)}명 투표 완료"],
        "action_items": [],
    }
