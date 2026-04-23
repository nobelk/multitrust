"""Render evaluation results for CI summaries, release notes, and machine consumers.

Three output forms are provided:

- ``report_to_markdown`` — human-readable summary suitable for ``$GITHUB_STEP_SUMMARY``,
  Slack, or release notes.
- ``report_to_json`` — stable, schema-versioned JSON for archival and
  cross-release diffing.
- ``diff_reports`` — markdown diff highlighting newly failing / newly passing cases
  between two reports (typically previous release vs current branch).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from multitrust.evaluation.runner import CorpusReport, ScenarioResult

JSON_SCHEMA_VERSION = "1"


def _format_margin(margin: float) -> str:
    sign = "+" if margin >= 0 else ""
    return f"{sign}{margin:.4f}"


def _format_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def report_to_markdown(report: CorpusReport, *, include_passing: bool = False) -> str:
    """Render a CorpusReport as a markdown summary.

    The ``include_passing`` flag controls whether successful cases are listed
    individually (default: only failing cases get per-expectation detail, with
    a one-line passing summary). CI summaries usually want the default; release
    notes occasionally want the full listing.
    """
    lines: list[str] = []
    lines.append(f"# {report.corpus_name} — evaluation report")
    lines.append("")
    lines.append(f"- **Corpus version:** `{report.corpus_version}`")
    lines.append(f"- **SDK version:** `{report.sdk_version}`")
    lines.append(f"- **Generated:** {_format_timestamp(report.timestamp)}")
    pct = report.pass_rate * 100
    status_word = "PASS" if report.failed == 0 else "FAIL"
    lines.append(
        f"- **Result:** {status_word} — {report.passed}/{report.total} cases passed ({pct:.1f}%)"
    )
    lines.append("")

    failures = report.failures
    if failures:
        lines.append(f"## Failures ({len(failures)})")
        lines.append("")
        for result in failures:
            lines.extend(_render_case(result, failed_only=True))
            lines.append("")

    if include_passing:
        passing = tuple(r for r in report.results if r.passed)
        if passing:
            lines.append(f"## Passing cases ({len(passing)})")
            lines.append("")
            for result in passing:
                lines.extend(_render_case(result, failed_only=False))
                lines.append("")
    elif report.failed == 0:
        lines.append("All cases passed.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_case(result: ScenarioResult, *, failed_only: bool) -> list[str]:
    case = result.case
    badge = "PASS" if result.passed else "FAIL"
    lines: list[str] = [f"### `{case.case_id}` — **{badge}**"]
    if case.description:
        lines.append("")
        lines.append(case.description)
    if case.tags:
        lines.append("")
        lines.append(f"_Tags:_ {', '.join(f'`{t}`' for t in case.tags)}")
    lines.append("")
    for er in result.expectations:
        if failed_only and er.passed:
            continue
        marker = "PASS" if er.passed else "FAIL"
        label = f" ({er.expectation.label})" if er.expectation.label else ""
        lines.append(
            f"- **{marker}** at t={er.expectation.at_seconds:g}s,"
            f" threshold={er.expectation.threshold:.4f}{label}: "
            f"trust={er.trust_score:.4f} margin={_format_margin(er.margin)} "
            f"expected=`{er.expectation.expected}` actual=`{er.actual}`"
        )
    return lines


def report_to_json(report: CorpusReport) -> str:
    """Serialize a CorpusReport as schema-versioned JSON.

    The schema is stable: ``schema_version`` will be bumped on any breaking
    change. Numeric fields are emitted as floats so downstream diffing tools
    can compare margins quantitatively.
    """
    payload: dict[str, Any] = {
        "schema_version": JSON_SCHEMA_VERSION,
        "corpus_name": report.corpus_name,
        "corpus_version": report.corpus_version,
        "sdk_version": report.sdk_version,
        "timestamp": report.timestamp,
        "summary": {
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "pass_rate": report.pass_rate,
        },
        "cases": [
            {
                "case_id": r.case.case_id,
                "passed": r.passed,
                "tags": list(r.case.tags),
                "final_opinion": r.final_opinion.to_dict(),
                "expectations": [
                    {
                        "at_seconds": er.expectation.at_seconds,
                        "threshold": er.expectation.threshold,
                        "label": er.expectation.label,
                        "expected": er.expectation.expected,
                        "actual": er.actual,
                        "trust_score": er.trust_score,
                        "margin": er.margin,
                        "passed": er.passed,
                    }
                    for er in r.expectations
                ],
            }
            for r in report.results
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def diff_reports(old: CorpusReport, new: CorpusReport, *, drift_epsilon: float = 0.01) -> str:
    """Render a markdown diff between two reports.

    Highlights:

    - **Regressions** — cases that passed in ``old`` but fail in ``new`` (the
      load-bearing failure mode for release-note review).
    - **Fixes** — cases that failed in ``old`` but pass in ``new``.
    - **New / removed cases** — only present in one of the reports.
    - **Margin drift** — passing cases whose trust margin moved by more than
      ``drift_epsilon`` between releases (a soft signal of math changes).
    """
    old_by_id = {r.case.case_id: r for r in old.results}
    new_by_id = {r.case.case_id: r for r in new.results}

    regressions = sorted(
        cid
        for cid in old_by_id.keys() & new_by_id.keys()
        if old_by_id[cid].passed and not new_by_id[cid].passed
    )
    fixes = sorted(
        cid
        for cid in old_by_id.keys() & new_by_id.keys()
        if not old_by_id[cid].passed and new_by_id[cid].passed
    )
    added = sorted(new_by_id.keys() - old_by_id.keys())
    removed = sorted(old_by_id.keys() - new_by_id.keys())
    drift: list[tuple[str, float, float, float]] = []
    for cid in sorted(old_by_id.keys() & new_by_id.keys()):
        old_r = old_by_id[cid]
        new_r = new_by_id[cid]
        if not (old_r.passed and new_r.passed):
            continue
        for old_er, new_er in zip(old_r.expectations, new_r.expectations, strict=False):
            delta = new_er.trust_score - old_er.trust_score
            if abs(delta) > drift_epsilon:
                drift.append((cid, old_er.trust_score, new_er.trust_score, delta))
                break

    lines: list[str] = []
    lines.append(
        f"# Evaluation diff — {old.sdk_version} → {new.sdk_version} "
        f"({old.corpus_name} v{new.corpus_version})"
    )
    lines.append("")
    lines.append(
        f"- Old: **{old.passed}/{old.total}** passed  →  New: **{new.passed}/{new.total}** passed"
    )
    lines.append(
        f"- Regressions: **{len(regressions)}**  "
        f"Fixes: **{len(fixes)}**  Added: **{len(added)}**  Removed: **{len(removed)}**  "
        f"Margin drift (>{drift_epsilon:g}): **{len(drift)}**"
    )
    lines.append("")

    if regressions:
        lines.append("## Regressions")
        lines.append("")
        for cid in regressions:
            lines.append(f"- `{cid}` — passed previously, **fails now**")
        lines.append("")

    if fixes:
        lines.append("## Fixes")
        lines.append("")
        for cid in fixes:
            lines.append(f"- `{cid}` — failed previously, **passes now**")
        lines.append("")

    if added:
        lines.append("## New cases")
        lines.append("")
        for cid in added:
            badge = "passes" if new_by_id[cid].passed else "**FAILS**"
            lines.append(f"- `{cid}` — {badge}")
        lines.append("")

    if removed:
        lines.append("## Removed cases")
        lines.append("")
        for cid in removed:
            lines.append(f"- `{cid}`")
        lines.append("")

    if drift:
        lines.append(f"## Margin drift (>|{drift_epsilon:g}| in trust score)")
        lines.append("")
        for cid, old_score, new_score, delta in drift:
            lines.append(
                f"- `{cid}` — first-expectation trust {old_score:.4f} → "
                f"{new_score:.4f} ({_format_margin(delta)})"
            )
        lines.append("")

    if not (regressions or fixes or added or removed or drift):
        lines.append("No changes detected between reports.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
