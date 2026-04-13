# Portfolio Council AI

6명의 전문가 AI 에이전트가 **구조화된 토론**을 거쳐 포트폴리오 투자 의견을 도출하는 멀티에이전트 시스템.

## 에이전트 구성

| 에이전트 | 역할 | 분석 관점 |
|---------|------|----------|
| 🔢 퀀트 | 기술적 지표·팩터·리스크 | RSI, Sharpe, 팩터 노출 |
| 🌍 매크로 | 거시경제·금리·환율 | 경기사이클, 금리 방향 |
| 🏭 섹터 | 섹터 로테이션·업종 | 섹터별 상대강도 |
| 🔄 사이클 | 시장 타이밍·심리 | Fear & Greed, VIX |
| ₿ 크립토 | 암호화폐·DeFi | BTC 사이클, 도미넌스 |
| 📚 가치투자자 | 밸류에이션·안전마진 | PER, PBR, DCF |

## 토론 프로토콜

1. **Phase 1** — 6개 에이전트 독립 분석
2. **Phase 2** — 교차 반론 (퀀트↔가치투자자, 매크로↔섹터, 사이클↔크립토)
3. **Phase 3** — Moderator 종합 (근거 품질 가중 합의)

## Quick Start

```bash
# 1. 환경 설정
cp .env.example .env
# .env에 ANTHROPIC_API_KEY 입력

# 2. 의존성 설치
pip install -e .

# 3. 포트폴리오 설정
# data/portfolio.json 편집

# 4. 분석 실행
python scripts/run_pipeline.py
```

## 아키텍처

```
src/
├── core/           # Domain Layer (외부 의존성 ZERO)
├── agents/         # 6개 전문가 에이전트
├── infrastructure/ # LLM, 데이터, 저장소, 알림
├── application/    # 파이프라인 오케스트레이션
├── prompts/        # 에이전트 시스템 프롬프트
└── utils/          # 로깅, 면책조항
```

## 면책 조항

본 시스템은 AI 기반 투자 참고 정보를 제공하며, 투자자문업에 해당하지 않습니다. 모든 투자 결정은 사용자 본인의 판단과 책임 하에 이루어져야 합니다.
