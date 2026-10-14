"""Metrics, thresholds and the printed scorecard shared by every eval suite."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

REPORTS = Path(__file__).with_name("reports")


@dataclass(frozen=True, slots=True)
class Metric:
    suite: str
    name: str
    value: float
    threshold: float
    higher_is_better: bool = True
    detail: str = ""

    @property
    def passed(self) -> bool:
        return (
            self.value >= self.threshold if self.higher_is_better else self.value <= self.threshold
        )


def ratio(hits: int, total: int) -> float:
    return hits / total if total else 1.0


def print_scorecard(metrics: list[Metric]) -> None:
    width = max((len(m.name) for m in metrics), default=10)
    suite = ""
    for metric in metrics:
        if metric.suite != suite:
            suite = metric.suite
            print(f"\n== {suite} ==")
        sign = ">=" if metric.higher_is_better else "<="
        status = "PASS" if metric.passed else "FAIL"
        print(
            f"{status}  {metric.name:<{width}}  {metric.value:7.3f}  "
            f"(target {sign} {metric.threshold:g})  {metric.detail}"
        )
    failed = sum(not m.passed for m in metrics)
    print(f"\n{len(metrics) - failed}/{len(metrics)} metrics on target")


def save_report(metrics: list[Metric]) -> Path:
    """Write the run as JSON under ``evals/reports/`` (git-ignored) to compare runs over time."""
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    rows = [asdict(m) | {"passed": m.passed} for m in metrics]
    path.write_text(json.dumps(rows, indent=2))
    return path
