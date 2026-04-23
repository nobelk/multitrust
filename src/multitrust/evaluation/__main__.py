"""CLI entry point: ``python -m multitrust.evaluation``.

Examples
--------

Run the canonical corpus and emit a markdown summary suitable for ``$GITHUB_STEP_SUMMARY``::

    python -m multitrust.evaluation > summary.md

Emit JSON for archival / cross-release diffing::

    python -m multitrust.evaluation --format json > report.json

Diff a previous JSON report against a fresh run::

    python -m multitrust.evaluation --baseline prev_report.json > diff.md
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from multitrust.evaluation.corpus import canonical_corpus
from multitrust.evaluation.reporter import (
    diff_reports,
    report_to_json,
    report_to_markdown,
)
from multitrust.evaluation.runner import (
    CorpusReport,
    ExpectationResult,
    ScenarioResult,
    evaluate_corpus,
)
from multitrust.evaluation.scenario import (
    DecisionExpectation,
    EvaluationCorpus,
    ScenarioCase,
)


def _load_baseline(path: Path) -> CorpusReport:
    """Reconstitute a CorpusReport from its JSON serialization for diffing."""
    from multitrust.core.opinion import Opinion

    payload = json.loads(path.read_text())
    cases = []
    for case_data in payload["cases"]:
        # Synthesize a minimal ScenarioCase placeholder to carry case_id + tags.
        case = ScenarioCase(
            case_id=case_data["case_id"],
            description="(baseline)",
            tags=tuple(case_data.get("tags", [])),
            expectations=(DecisionExpectation(at_seconds=0, threshold=0.5, expected="allow"),),
        )
        # Reconstruct expectation results for trust-score drift analysis.
        expectation_results = tuple(
            ExpectationResult(
                expectation=DecisionExpectation(
                    at_seconds=float(er["at_seconds"]),
                    threshold=float(er["threshold"]),
                    expected=er["expected"],
                    label=er.get("label", ""),
                ),
                trust_score=float(er["trust_score"]),
                margin=float(er["margin"]),
                actual=er["actual"],
                passed=bool(er["passed"]),
            )
            for er in case_data["expectations"]
        )
        cases.append(
            ScenarioResult(
                case=case,
                expectations=expectation_results,
                final_opinion=Opinion.from_dict(case_data["final_opinion"]),
                passed=bool(case_data["passed"]),
            )
        )
    return CorpusReport(
        corpus_name=payload["corpus_name"],
        corpus_version=payload["corpus_version"],
        sdk_version=payload["sdk_version"],
        timestamp=float(payload["timestamp"]),
        results=tuple(cases),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m multitrust.evaluation")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format for the fresh evaluation (ignored when --baseline is supplied).",
    )
    parser.add_argument(
        "--tag",
        help="Run only cases carrying this tag (e.g. 'decay', 'allow_block').",
    )
    parser.add_argument(
        "--include-passing",
        action="store_true",
        help="Include passing cases in the markdown output (default: failures only).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Path to a previous JSON report; output a markdown diff instead of a fresh report.",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero when any case fails (or when diffing, when regressions are present).",
    )
    args = parser.parse_args(argv)

    corpus: EvaluationCorpus = canonical_corpus()
    if args.tag:
        corpus = corpus.filter(tag=args.tag)
    fresh = evaluate_corpus(corpus)

    if args.baseline is not None:
        baseline = _load_baseline(args.baseline)
        # Pin the timestamp so diff output is reproducible across CI runs.
        fresh = replace(fresh, timestamp=baseline.timestamp)
        sys.stdout.write(diff_reports(baseline, fresh))
        if args.fail_on_regression:
            old_by_id = {r.case.case_id: r for r in baseline.results}
            new_by_id = {r.case.case_id: r for r in fresh.results}
            regressions = [
                cid
                for cid in old_by_id.keys() & new_by_id.keys()
                if old_by_id[cid].passed and not new_by_id[cid].passed
            ]
            return 1 if regressions else 0
        return 0

    if args.format == "json":
        sys.stdout.write(report_to_json(fresh) + "\n")
    else:
        sys.stdout.write(report_to_markdown(fresh, include_passing=args.include_passing))

    return 1 if (args.fail_on_regression and fresh.failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
