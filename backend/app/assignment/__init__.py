"""순수 배정 알고리즘 패키지 (UI/IO 의존 없음)."""

from .scoring import (
    Assignment,
    Breakdown,
    Person,
    ScoringContext,
    Violation,
    Weights,
    collect_violations,
    collect_warnings,
    score,
    table_balance_summary,
)
from .solver import (
    SolveError,
    SolveResult,
    compute_table_sizes,
    evaluate_tables,
    resolve_num_tables,
    solve,
)

__all__ = [
    "Assignment",
    "Breakdown",
    "Person",
    "ScoringContext",
    "Violation",
    "Weights",
    "collect_violations",
    "collect_warnings",
    "score",
    "table_balance_summary",
    "SolveError",
    "SolveResult",
    "compute_table_sizes",
    "evaluate_tables",
    "resolve_num_tables",
    "solve",
]
