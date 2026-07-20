from typing import Optional


def sample_clause(
    development_mode: bool = True,
    sample_percent: int = 5,
    random_seed: int = 42,
    alias: Optional[str] = None,
) -> str:
    if not development_mode:
        return ""
    table_ref = alias if alias else ""
    return f"TABLESAMPLE SYSTEM ({sample_percent} PERCENT) REPEATABLE ({random_seed}) {table_ref}"
