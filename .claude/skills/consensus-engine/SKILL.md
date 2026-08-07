---
name: consensus-engine
description: Domain-agnostic Multi-LLM consensus engine with weighted voting, confidence scoring, and disagreement handling. Use for any agent system requiring multi-model decision consensus across trading, content generation, code review, or other domains.
---

# Consensus Engine

Universal Multi-LLM consensus system for reliable AI-driven decisions.

## Overview

**Domain-agnostic** consensus engine that combines multiple LLM responses using weighted voting and confidence thresholds.

**Core principle:** Multiple perspectives reduce bias, weighted consensus ensures quality.

## When to Use

Use for any system requiring multi-LLM consensus:
- Trading decisions (crypto, stocks, forex)
- Content moderation and review
- Code review and analysis
- Medical diagnosis support
- Risk assessment
- Strategic planning

## Architecture

### Core Components

```python
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class ConsensusResult:
    """Universal consensus result."""
    decision: Optional[str]
    confidence: float
    status: str  # CONSENSUS_REACHED, LOW_CONFIDENCE, DISAGREEMENT
    votes: Dict[str, float]
    reasoning: List[str]

class ConsensusEngine:
    """Domain-agnostic Multi-LLM consensus engine."""

    def __init__(
        self,
        providers: List[str],
        weights: Dict[str, float],
        confidence_threshold: float = 0.75
    ):
        self.providers = providers
        self.weights = weights
        self.confidence_threshold = confidence_threshold

    async def get_consensus(
        self,
        prompt: str,
        context: Optional[Dict] = None
    ) -> ConsensusResult:
        """Get consensus from multiple LLMs."""
        # 1. Gather responses from all providers
        responses = await self._gather_responses(prompt, context)

        # 2. Calculate weighted votes
        votes = self._calculate_votes(responses)

        # 3. Determine winner
        decision = max(votes.items(), key=lambda x: x[1])

        # 4. Calculate confidence
        confidence = self._calculate_confidence(votes, responses)

        # 5. Check threshold
        if confidence < self.confidence_threshold:
            return ConsensusResult(
                decision=None,
                confidence=confidence,
                status="LOW_CONFIDENCE",
                votes=votes,
                reasoning=[r.reasoning for r in responses]
            )

        return ConsensusResult(
            decision=decision[0],
            confidence=confidence,
            status="CONSENSUS_REACHED",
            votes=votes,
            reasoning=[r.reasoning for r in responses]
        )

    def _calculate_votes(self, responses: List[Response]) -> Dict[str, float]:
        """Calculate weighted votes."""
        votes = {}
        for response in responses:
            provider = response.provider
            decision = response.decision
            weight = self.weights.get(provider, 1.0)

            votes[decision] = votes.get(decision, 0) + weight

        return votes

    def _calculate_confidence(
        self,
        votes: Dict[str, float],
        responses: List[Response]
    ) -> float:
        """Calculate consensus confidence score."""
        total_weight = sum(self.weights.values())
        winning_weight = max(votes.values())

        # Base confidence from vote distribution
        vote_confidence = winning_weight / total_weight

        # Penalty for high disagreement
        disagreement_penalty = self._calculate_disagreement(responses)

        # Adjust for individual response confidence
        avg_response_confidence = sum(r.confidence for r in responses) / len(responses)

        return (vote_confidence * 0.5 +
                avg_response_confidence * 0.3 -
                disagreement_penalty * 0.2)
```

## Configuration Patterns

### 1. Equal Weight (Democracy)
```python
engine = ConsensusEngine(
    providers=["openai", "claude", "gemini"],
    weights={"openai": 1.0, "claude": 1.0, "gemini": 1.0},
    confidence_threshold=0.75
)
```

### 2. Expert Weight (Meritocracy)
```python
engine = ConsensusEngine(
    providers=["openai", "claude", "gemini"],
    weights={"openai": 0.5, "claude": 0.3, "gemini": 0.2},
    confidence_threshold=0.80  # Higher threshold for expert system
)
```

### 3. Quorum System
```python
engine = ConsensusEngine(
    providers=["openai", "claude", "gemini", "llama", "mistral"],
    weights={p: 1.0 for p in ["openai", "claude", "gemini", "llama", "mistral"]},
    confidence_threshold=0.60  # 3/5 majority = 60%
)
```

## Disagreement Handling

### Types of Disagreement

```python
class DisagreementAnalyzer:
    """Analyze LLM disagreements."""

    def analyze(self, responses: List[Response]) -> DisagreementReport:
        """Analyze disagreement patterns."""
        decisions = [r.decision for r in responses]
        unique_decisions = set(decisions)

        if len(unique_decisions) == 1:
            return DisagreementReport(
                type="UNANIMOUS",
                severity=0.0,
                pattern="All LLMs agree"
            )

        if len(unique_decisions) == len(responses):
            return DisagreementReport(
                type="COMPLETE_DISAGREEMENT",
                severity=1.0,
                pattern="Every LLM disagrees"
            )

        # Majority vs minority
        majority_count = max(decisions.count(d) for d in unique_decisions)
        if majority_count >= len(responses) * 0.66:
            return DisagreementReport(
                type="WEAK_DISAGREEMENT",
                severity=0.3,
                pattern="Strong majority with outliers"
            )

        return DisagreementReport(
            type="SPLIT_DECISION",
            severity=0.7,
            pattern="No clear majority"
        )
```

### Resolution Strategies

```python
class ConsensusResolver:
    """Resolve low-confidence consensus."""

    async def resolve(self, result: ConsensusResult) -> Resolution:
        """Resolve low confidence or disagreement."""
        if result.status == "LOW_CONFIDENCE":
            # Strategy 1: Request human review
            if result.confidence < 0.5:
                return Resolution(
                    action="HUMAN_REVIEW",
                    reason="Confidence too low"
                )

            # Strategy 2: Request more detail from LLMs
            if self._has_vague_reasoning(result):
                return Resolution(
                    action="REQUEST_DETAIL",
                    reason="Need more specific reasoning"
                )

            # Strategy 3: Add more LLM providers
            if len(result.votes) <= 3:
                return Resolution(
                    action="EXPAND_CONSENSUS",
                    reason="Need more perspectives"
                )

        return Resolution(action="ACCEPT", reason="Within threshold")
```

## Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_consensus_with_unanimous_agreement():
    """Test unanimous consensus."""
    engine = ConsensusEngine(
        providers=["a", "b", "c"],
        weights={"a": 1.0, "b": 1.0, "c": 1.0}
    )

    responses = [
        Response(provider="a", decision="YES", confidence=0.9),
        Response(provider="b", decision="YES", confidence=0.85),
        Response(provider="c", decision="YES", confidence=0.8)
    ]

    result = engine._calculate_consensus(responses)

    assert result.status == "CONSENSUS_REACHED"
    assert result.decision == "YES"
    assert result.confidence >= 0.85

@pytest.mark.asyncio
async def test_consensus_with_complete_disagreement():
    """Test complete disagreement."""
    engine = ConsensusEngine(
        providers=["a", "b", "c"],
        weights={"a": 1.0, "b": 1.0, "c": 1.0},
        confidence_threshold=0.75
    )

    responses = [
        Response(provider="a", decision="YES", confidence=0.9),
        Response(provider="b", decision="NO", confidence=0.9),
        Response(provider="c", decision="MAYBE", confidence=0.9)
    ]

    result = engine._calculate_consensus(responses)

    assert result.status == "LOW_CONFIDENCE"
    assert result.decision is None
    assert result.confidence < 0.75
```

## Domain Integration Examples

### Trading Domain
```python
# crypto-agent uses consensus-engine
from consensus_engine import ConsensusEngine

engine = ConsensusEngine(
    providers=["openai", "claude", "gemini"],
    weights={"openai": 0.4, "claude": 0.3, "gemini": 0.3}
)

result = await engine.get_consensus(
    prompt="Should I buy BTC at $50k?",
    context={"market_data": market_data, "portfolio": portfolio}
)
```

### Content Moderation
```python
# content-moderator uses consensus-engine
engine = ConsensusEngine(
    providers=["openai", "claude", "perspective-api"],
    weights={"openai": 0.3, "claude": 0.3, "perspective-api": 0.4}
)

result = await engine.get_consensus(
    prompt="Is this content appropriate?",
    context={"content": user_content}
)
```

### Code Review
```python
# code-reviewer uses consensus-engine
engine = ConsensusEngine(
    providers=["openai", "claude", "codex"],
    weights={"openai": 0.3, "claude": 0.3, "codex": 0.4}
)

result = await engine.get_consensus(
    prompt="Should this code be approved?",
    context={"diff": git_diff, "tests": test_results}
)
```

## Performance Optimization

### Parallel Execution
```python
async def _gather_responses(self, prompt: str, context: dict) -> List[Response]:
    """Gather responses in parallel."""
    tasks = [
        provider.query(prompt, context)
        for provider in self.providers
    ]
    return await asyncio.gather(*tasks)
```

### Caching
```python
class CachedConsensusEngine(ConsensusEngine):
    """Consensus engine with response caching."""

    def __init__(self, *args, cache_ttl=300, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = TTLCache(maxsize=1000, ttl=cache_ttl)

    async def get_consensus(self, prompt: str, context: dict) -> ConsensusResult:
        cache_key = self._make_cache_key(prompt, context)

        if cache_key in self.cache:
            return self.cache[cache_key]

        result = await super().get_consensus(prompt, context)
        self.cache[cache_key] = result
        return result
```

## Best Practices

1. **Provider Selection**: Choose 3-5 providers for balance of cost/speed/quality
2. **Weight Tuning**: Start equal, adjust based on domain performance
3. **Threshold Setting**: 0.75 for general, 0.80+ for critical decisions
4. **Timeout Handling**: Set per-provider timeouts (5-10s)
5. **Cost Management**: Cache frequent queries, use cheaper models for non-critical
6. **Monitoring**: Track consensus rates, disagreement patterns, confidence distribution

## Red Flags

- Confidence consistently below 0.6
- One provider always dominates votes
- High disagreement on simple queries
- Providers returning similar wording (plagiarism detection needed)

## Integration

**Used by:**
- crypto-agent-architect (trading decisions)
- content-moderator (moderation decisions)
- code-reviewer (code approval)

**Requires:**
- test-driven-development (TDD for reliability)
- systematic-debugging (debug consensus issues)

## Resources

- Weighted Voting Algorithm
- Confidence Scoring Methods
- Disagreement Analysis Patterns
