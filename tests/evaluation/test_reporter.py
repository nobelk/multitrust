from __future__ import annotations

import json

from multitrust.evaluation import (
    DecisionExpectation,
    EvaluationCorpus,
    EvidenceStep,
    ScenarioCase,
    diff_reports,
    evaluate_corpus,
    report_to_json,
    report_to_markdown,
)


def _two_case_corpus() -> EvaluationCorpus:
    pass_case = ScenarioCase(
        case_id="passes",
        description="trivial pass",
        evidence=(EvidenceStep(at_seconds=0, positive=10, negative=0),),
        expectations=(DecisionExpectation(0, 0.7, "allow"),),
        tags=("smoke",),
    )
    fail_case = ScenarioCase(
        case_id="fails",
        description="trivial fail",
        expectations=(DecisionExpectation(0, 0.5, "block"),),
    )
    return EvaluationCorpus(name="t", version="1", cases=(pass_case, fail_case))


class TestMarkdown:
    def test_markdown_contains_summary_and_failures(self):
        corpus = _two_case_corpus()
        report = evaluate_corpus(corpus, sdk_version="t", timestamp=0.0)
        md = report_to_markdown(report)
        assert "evaluation report" in md
        assert "FAIL" in md
        assert "1/2" in md
        # Failing case is detailed; passing case is not (default mode)
        assert "fails" in md
        assert "Failures (1)" in md
        assert "passes" not in md

    def test_include_passing_lists_passing_cases(self):
        corpus = _two_case_corpus()
        report = evaluate_corpus(corpus, sdk_version="t", timestamp=0.0)
        md = report_to_markdown(report, include_passing=True)
        assert "Passing cases" in md
        assert "passes" in md

    def test_all_pass_emits_clean_summary(self):
        case = ScenarioCase(
            case_id="ok",
            description="ok",
            evidence=(EvidenceStep(at_seconds=0, positive=10, negative=0),),
            expectations=(DecisionExpectation(0, 0.7, "allow"),),
        )
        corpus = EvaluationCorpus(name="t", version="1", cases=(case,))
        report = evaluate_corpus(corpus, sdk_version="t", timestamp=0.0)
        md = report_to_markdown(report)
        assert "PASS" in md
        assert "All cases passed" in md
        assert "Failures" not in md


class TestJSON:
    def test_json_round_trip_preserves_summary(self):
        corpus = _two_case_corpus()
        report = evaluate_corpus(corpus, sdk_version="t", timestamp=42.0)
        payload = json.loads(report_to_json(report))
        assert payload["schema_version"] == "1"
        assert payload["sdk_version"] == "t"
        assert payload["timestamp"] == 42.0
        assert payload["summary"] == {
            "total": 2,
            "passed": 1,
            "failed": 1,
            "pass_rate": 0.5,
        }
        assert {c["case_id"] for c in payload["cases"]} == {"passes", "fails"}

    def test_json_includes_per_expectation_detail(self):
        corpus = _two_case_corpus()
        report = evaluate_corpus(corpus, sdk_version="t", timestamp=0.0)
        payload = json.loads(report_to_json(report))
        fails_case = next(c for c in payload["cases"] if c["case_id"] == "fails")
        assert len(fails_case["expectations"]) == 1
        er = fails_case["expectations"][0]
        assert er["expected"] == "block"
        assert er["actual"] == "allow"
        assert er["passed"] is False
        assert "trust_score" in er
        assert "margin" in er


class TestDiffReports:
    def _baseline_report(self):
        case = ScenarioCase(
            case_id="x",
            description="d",
            evidence=(EvidenceStep(at_seconds=0, positive=10, negative=0),),
            expectations=(DecisionExpectation(0, 0.7, "allow"),),
        )
        corpus = EvaluationCorpus(name="t", version="1", cases=(case,))
        return evaluate_corpus(corpus, sdk_version="0.0.1", timestamp=0.0)

    def test_no_changes_reports_clean(self):
        old = self._baseline_report()
        new = self._baseline_report()
        diff = diff_reports(old, new)
        assert "No changes detected" in diff

    def test_regression_is_highlighted(self):
        old = self._baseline_report()
        # New report with a tightened expectation that the same trust score cannot meet.
        case = ScenarioCase(
            case_id="x",
            description="d",
            evidence=(EvidenceStep(at_seconds=0, positive=10, negative=0),),
            expectations=(DecisionExpectation(0, 0.99, "allow"),),
        )
        corpus = EvaluationCorpus(name="t", version="1", cases=(case,))
        new = evaluate_corpus(corpus, sdk_version="0.0.2", timestamp=0.0)
        diff = diff_reports(old, new)
        assert "Regressions" in diff
        assert "`x`" in diff

    def test_added_case_listed(self):
        old = self._baseline_report()
        case_a = ScenarioCase(
            case_id="x",
            description="d",
            evidence=(EvidenceStep(at_seconds=0, positive=10, negative=0),),
            expectations=(DecisionExpectation(0, 0.7, "allow"),),
        )
        case_b = ScenarioCase(
            case_id="newly_added",
            description="d",
            evidence=(EvidenceStep(at_seconds=0, positive=5, negative=0),),
            expectations=(DecisionExpectation(0, 0.5, "allow"),),
        )
        corpus = EvaluationCorpus(name="t", version="1", cases=(case_a, case_b))
        new = evaluate_corpus(corpus, sdk_version="0.0.2", timestamp=0.0)
        diff = diff_reports(old, new)
        assert "New cases" in diff
        assert "newly_added" in diff
