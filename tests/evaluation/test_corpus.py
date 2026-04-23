"""Regression test: every case in the canonical corpus must pass on the current SDK.

This is the load-bearing assertion of the evaluation suite. If a future change
to operator math, threshold semantics, or decay behaviour breaks any case here,
this test fails — and the failure message tells the maintainer exactly which
allow/block contract was violated.
"""

from __future__ import annotations

from multitrust.evaluation import canonical_corpus, evaluate_corpus


def test_canonical_corpus_passes_on_current_sdk():
    corpus = canonical_corpus()
    report = evaluate_corpus(corpus, sdk_version="test", timestamp=0.0)
    if report.failed:
        details = "\n".join(
            f"  - {f.case.case_id}: "
            + ", ".join(
                f"t={er.expectation.at_seconds:g}s "
                f"threshold={er.expectation.threshold:.3f} "
                f"trust={er.trust_score:.4f} "
                f"expected={er.expectation.expected} actual={er.actual}"
                for er in f.failed_expectations
            )
            for f in report.failures
        )
        raise AssertionError(
            f"{report.failed}/{report.total} canonical scenarios regressed:\n{details}"
        )
    assert report.passed == report.total


def test_canonical_corpus_has_decay_and_allow_block_coverage():
    corpus = canonical_corpus()
    tags_seen = {tag for case in corpus.cases for tag in case.tags}
    # The corpus is meant to cover decay-sensitive and allow/block scenarios; if a
    # refactor accidentally drops one of these tags, downstream consumers running
    # `corpus.filter(tag="decay")` would silently get an empty subset.
    assert "decay" in tags_seen
    assert "allow_block" in tags_seen
    assert "threshold_levels" in tags_seen


def test_canonical_corpus_filter_returns_only_tagged_cases():
    corpus = canonical_corpus()
    decay_only = corpus.filter(tag="decay")
    assert len(decay_only.cases) > 0
    for case in decay_only.cases:
        assert "decay" in case.tags
