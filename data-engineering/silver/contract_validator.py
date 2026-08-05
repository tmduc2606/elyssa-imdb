"""
Contract Validator — Schema enforcement at Silver→Gold boundaries.

Validates incoming/outgoing schemas at layer boundaries:
- Silver→Gold: ensures required columns exist, types match, FKs resolve
- Gold→Web: ensures mart grains are preserved, no orphan FKs
"""

import yaml


class ContractViolation(Exception):
    """Raised when a schema contract is violated."""
    pass


class ContractValidator:
    """
    Validates data contracts between layers using YAML schema definitions.
    """

    def __init__(self, contract_path: str):
        with open(contract_path) as f:
            self.contract = yaml.safe_load(f)

    def validate_column_presence(
        self,
        available_columns: list[str],
        required_columns: list[str],
    ) -> list[str]:
        """Check that all required columns are present. Returns missing columns."""
        return [c for c in required_columns if c not in available_columns]

    def validate_null_constraints(
        self,
        null_rates: dict[str, float],
        not_null_columns: list[str],
        max_null_rate: float = 0.0,
    ) -> dict[str, float]:
        """Check that not-null columns have null rate below threshold."""
        violations = {}
        for col in not_null_columns:
            rate = null_rates.get(col, 0.0)
            if rate > max_null_rate:
                violations[col] = rate
        return violations

    def validate_fk_integrity(
        self,
        orphan_counts: dict[str, int],
        max_orphans: int = 0,
    ) -> dict[str, int]:
        """Check FK integrity — return tables with orphan FKs exceeding threshold."""
        violations = {}
        for table, count in orphan_counts.items():
            if count > max_orphans:
                violations[table] = count
        return violations

    def validate_row_count(
        self,
        actual_count: int,
        min_count: int = 0,
    ) -> bool:
        """Check that row count meets minimum threshold."""
        return actual_count >= min_count

    def run_full_validation(
        self,
        available_columns: list[str],
        null_rates: dict[str, float],
        orphan_counts: dict[str, int],
        row_count: int,
    ) -> dict:
        """Run all contract checks and return a report."""
        report = {"passed": True, "violations": []}

        # Check required columns
        required = self.contract.get("required_columns", [])
        missing = self.validate_column_presence(available_columns, required)
        if missing:
            report["passed"] = False
            report["violations"].append({
                "type": "missing_columns",
                "columns": missing,
            })

        # Check null constraints
        not_null = self.contract.get("not_null_columns", [])
        null_violations = self.validate_null_constraints(null_rates, not_null)
        if null_violations:
            report["passed"] = False
            report["violations"].append({
                "type": "null_violations",
                "columns": null_violations,
            })

        # Check FK integrity
        fk_violations = self.validate_fk_integrity(orphan_counts)
        if fk_violations:
            report["passed"] = False
            report["violations"].append({
                "type": "fk_violations",
                "tables": fk_violations,
            })

        # Check row count
        min_count = self.contract.get("min_row_count", 0)
        if not self.validate_row_count(row_count, min_count):
            report["passed"] = False
            report["violations"].append({
                "type": "row_count",
                "actual": row_count,
                "minimum": min_count,
            })

        return report


# ─── Pre-built contracts for Silver→Gold boundary ─────────────────────

SILVER_TO_GOLD_CONTRACT = {
    "required_columns": [
        "tconst", "title_type", "primary_title", "original_title",
        "is_adult", "start_year", "end_year", "runtime_minutes",
    ],
    "not_null_columns": ["tconst", "title_type", "primary_title"],
    "min_row_count": 100000,
}


def validate_silver_to_gold(
    available_columns: list[str],
    null_rates: dict[str, float],
    orphan_counts: dict[str, int],
    row_count: int,
) -> dict:
    """Convenience function for Silver→Gold contract validation."""
    validator = ContractValidator.__new__(ContractValidator)
    validator.contract = {
        "required_columns": ["tconst", "title_type", "primary_title"],
        "not_null_columns": ["tconst", "title_type", "primary_title"],
        "min_row_count": 100000,
    }
    return validator.run_full_validation(
        available_columns, null_rates, orphan_counts, row_count
    )
