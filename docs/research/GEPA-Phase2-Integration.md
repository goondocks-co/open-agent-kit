# GEPA Phase 2 Integration Plan

> **Status**: Research / Future Work
> **Depends On**: Codebase Intelligence feature (Phase 1)
> **Target**: Evolutionary optimization of retrieval and prompts

## Overview

Phase 2 extends the Codebase Intelligence feature with GEPA (Genetic Evolutionary Prompt Augmentation) to automatically improve retrieval quality and prompt effectiveness over time based on implicit feedback signals.

## Why GEPA?

| Capability | Phase 1 (Current) | Phase 2 (GEPA) |
|------------|-------------------|----------------|
| Retrieval | Static thresholds | Evolving thresholds based on feedback |
| Query processing | Fixed rewrite prompt | Optimized query expansion |
| Context synthesis | Static template | Evolved context assembly |
| Performance | Manual tuning | Automatic improvement |

## GEPA RAG Adapter Fit Analysis

### Out-of-Box Capabilities

| Capability | GEPA RAG Adapter | OAK Needs | Fit |
|------------|------------------|-----------|-----|
| ChromaDB support | Native | Using ChromaDB | Perfect |
| Ollama embeddings | `nomic-embed-text` | Same default | Perfect |
| Prompt optimization | Generation prompts | Query rewriting, synthesis | Good fit |
| Retrieval quality metrics | Built-in | Need this | Perfect |
| Local LLM support | Ollama models | Want local-first | Perfect |
| Training/validation split | Configurable | From feedback | Perfect |

### Required Customizations

| OAK Requirement | GEPA RAG Default | Our Customization |
|-----------------|------------------|-------------------|
| **Code-specific retrieval** | Generic document RAG | Add code-aware metrics (function match, file match) |
| **Multi-collection search** | Single collection | Search both `oak_code` and `oak_memory` |
| **Progressive disclosure** | Standard RAG (retrieve→generate) | Optimize Layer 1→2→3 thresholds |
| **Feedback sources** | Manual examples | Implicit signals from tool logs |
| **Domain vocabulary** | General | Code/programming terminology |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PHASE 2: GEPA INTEGRATION                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  LEVERAGE: GEPA Generic RAG Adapter                                     │
│  ─────────────────────────────────                                      │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    gepa.examples.rag_adapter                    │    │
│  │                                                                  │    │
│  │  • ChromaDB integration (we use this directly)                  │    │
│  │  • Ollama embedding support (same as our default)               │    │
│  │  • Retrieval quality scoring                                    │    │
│  │  • Evolutionary prompt optimization                             │    │
│  │  • Training/validation framework                                │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              │ Extend/Configure                         │
│                              ▼                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    OAK GEPA Configuration                       │    │
│  │                                                                  │    │
│  │  oak/optimization/config.py                                     │    │
│  │  ─────────────────────────                                      │    │
│  │  • Point to OAK's ChromaDB collections (oak_code, oak_memory)  │    │
│  │  • Configure code-specific evaluation metrics                   │    │
│  │  • Set up feedback → training task pipeline                    │    │
│  │  • Define optimization targets (query prompts, thresholds)     │    │
│  │                                                                  │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              │ Custom Layer                             │
│                              ▼                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    OAK-Specific Extensions                      │    │
│  │                                                                  │    │
│  │  oak/optimization/metrics.py                                    │    │
│  │  ───────────────────────────                                    │    │
│  │  • CodeRetrievalMetric: file_match, function_match scores      │    │
│  │  • MemoryRelevanceMetric: observation type appropriateness     │    │
│  │  • TokenEfficiencyMetric: tokens used vs quality               │    │
│  │                                                                  │    │
│  │  oak/optimization/training.py                                   │    │
│  │  ────────────────────────────                                   │    │
│  │  • Convert tool logs → training examples                       │    │
│  │  • Extract implicit signals (search→fetch patterns)            │    │
│  │  • Generate validation set from positive feedback              │    │
│  │                                                                  │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Implementation Milestones

### Milestone 5.1: Feedback Infrastructure

| Task | Description | Location |
|------|-------------|----------|
| 5.1.1 | Track search→fetch patterns | Daemon tool logs |
| 5.1.2 | Record context acceptance signals | PostToolUse hook |
| 5.1.3 | Store feedback in SQLite | `.oak/ci/feedback.db` |

### Milestone 5.2: GEPA Configuration

| Task | Description | Approach |
|------|-------------|----------|
| 5.2.1 | Install GEPA with RAG adapter | `pip install gepa` + rag requirements |
| 5.2.2 | Configure ChromaDB connection | Point to `.oak/ci/chroma/` |
| 5.2.3 | Define optimization targets | Query rewrite prompt, relevance threshold |
| 5.2.4 | Create OAK-specific metrics | Extend GEPA's scoring for code |

### Milestone 5.3: Training Pipeline

| Task | Description | Integration Point |
|------|-------------|-------------------|
| 5.3.1 | Build feedback → training converter | `oak/optimization/training.py` |
| 5.3.2 | Extract search→fetch success patterns | From tool logs |
| 5.3.3 | Generate validation set | Hold-out recent sessions |
| 5.3.4 | Create synthetic examples for cold start | Bootstrap with common queries |

### Milestone 5.4: CLI & Scheduling

| Task | Description | Integration Point |
|------|-------------|-------------------|
| 5.4.1 | Create `oak optimize run` wrapper | Calls GEPA with OAK config |
| 5.4.2 | Add `oak optimize status` | Shows last run, improvements |
| 5.4.3 | Schedule periodic optimization | Daemon background task |

## Code Example: OAK GEPA Optimizer

```python
# oak/optimization/runner.py
"""
OAK GEPA optimization runner.
Leverages GEPA's generic RAG adapter with OAK-specific configuration.
"""
from pathlib import Path
import json

class OAKOptimizer:
    """
    Runs GEPA RAG optimization for OAK.

    Uses GEPA's unified rag_optimization.py with OAK's ChromaDB.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.chroma_path = project_root / ".oak" / "ci" / "chroma"
        self.config_path = project_root / ".oak" / "gepa_config.json"

    def prepare_training_data(self) -> tuple[list, list]:
        """
        Convert OAK feedback logs to GEPA training format.

        GEPA expects:
        - Training examples: (query, relevant_docs, expected_answer)
        - Validation examples: Same format, held out
        """
        from oak.optimization.training import FeedbackToTraining

        converter = FeedbackToTraining(self.project_root)
        all_examples = converter.generate_examples()

        # 70/30 split
        split_idx = int(len(all_examples) * 0.7)
        return all_examples[:split_idx], all_examples[split_idx:]

    def generate_gepa_config(self, train_data: list, val_data: list) -> dict:
        """Generate GEPA RAG adapter configuration."""
        return {
            "vector_store": "chromadb",
            "chroma_persist_directory": str(self.chroma_path),
            "collection_name": "oak_code",
            "embedding_model": "ollama/nomic-embed-text:latest",
            "model": "ollama/qwen2.5-coder:7b",  # Local code model
            "max_iterations": 10,
            "training_examples": train_data,
            "validation_examples": val_data,

            # OAK-specific optimization targets
            "optimize_prompts": [
                "query_rewrite",
                "context_synthesis",
            ],
            "optimize_parameters": [
                "relevance_threshold",
                "top_k",
            ],
        }

    def run(self, max_iterations: int = 10) -> dict:
        """Run GEPA optimization."""
        train_data, val_data = self.prepare_training_data()

        if len(train_data) < 3:
            return {"status": "insufficient_data", "examples": len(train_data)}

        config = self.generate_gepa_config(train_data, val_data)
        config["max_iterations"] = max_iterations

        self.config_path.write_text(json.dumps(config, indent=2))

        result = self._run_gepa_optimization(config)

        if result.get("improved"):
            self._apply_optimized_config(result["best_config"])

        return result

    def _run_gepa_optimization(self, config: dict) -> dict:
        """Execute GEPA optimization."""
        from gepa.examples.rag_adapter.generic_rag_adapter import GenericRAGAdapter
        from gepa import optimize

        adapter = GenericRAGAdapter(
            vector_store="chromadb",
            chroma_persist_directory=str(self.chroma_path),
            collection_name="oak_code",
            embedding_model=config["embedding_model"],
        )

        result = optimize(
            adapter=adapter,
            trainset=config["training_examples"],
            valset=config["validation_examples"],
            max_iterations=config["max_iterations"],
            model=config["model"],
        )

        return {
            "improved": result.best_score > result.initial_score,
            "initial_score": result.initial_score,
            "best_score": result.best_score,
            "iterations": result.iterations,
            "best_config": result.best_candidate,
        }

    def _apply_optimized_config(self, best_config: dict):
        """Apply optimized configuration to OAK."""
        optimized_path = self.project_root / ".oak" / "optimized_prompts.json"
        optimized_path.write_text(json.dumps(best_config, indent=2))
```

## Dependencies

```toml
# Add to pyproject.toml for Phase 2
[project.optional-dependencies]
optimization = [
    "gepa>=0.1.0",
    "litellm>=1.0.0",  # GEPA's LLM abstraction
]
```

## Effort Estimate

| Component | Original Custom Build | With GEPA Adapter | Reduction |
|-----------|----------------------|-------------------|-----------|
| Custom GEPA adapter | 2-3 weeks | Use existing | -60% |
| Evaluation framework | 1-2 weeks | Extend GEPA metrics | -40% |
| Optimization loop | 2 weeks | Use GEPA's evolutionary search | -80% |
| **Total Phase 2** | 5-7 weeks | **2-3 weeks** | ~60% |

## Success Criteria

1. **Retrieval quality improves** - Measured by file_match and function_match scores
2. **Token efficiency increases** - Same quality with fewer tokens
3. **Automatic operation** - No manual tuning required after setup
4. **Local-first** - All optimization runs locally with Ollama

## References

- [GEPA GitHub](https://github.com/your-org/gepa) - Genetic Evolutionary Prompt Augmentation
- [Claude-Mem](https://github.com/thedotmack/claude-mem) - Inspiration for feedback patterns
- [DSPy](https://github.com/stanfordnlp/dspy) - Related prompt optimization research
