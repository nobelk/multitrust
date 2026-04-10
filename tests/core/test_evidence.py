from __future__ import annotations

import time

import pytest

from multitrust.core.errors import InvalidEvidenceError
from multitrust.core.evidence import Evidence, EvidenceResult


def test_valid_creation():
    ev = Evidence(agent_id="a1", authority_id="auth1", positive=3.0, negative=1.0)
    assert ev.agent_id == "a1"
    assert ev.authority_id == "auth1"
    assert ev.positive == pytest.approx(3.0)
    assert ev.negative == pytest.approx(1.0)


def test_negative_evidence_raises():
    with pytest.raises(InvalidEvidenceError):
        Evidence(agent_id="a1", authority_id="auth1", positive=-1.0, negative=0.0)
    with pytest.raises(InvalidEvidenceError):
        Evidence(agent_id="a1", authority_id="auth1", positive=0.0, negative=-1.0)


def test_defaults():
    ev = Evidence(agent_id="a1", authority_id="auth1")
    assert ev.positive == pytest.approx(0.0)
    assert ev.negative == pytest.approx(0.0)
    assert ev.rule_name is None
    assert isinstance(ev.metadata, dict)
    assert isinstance(ev.timestamp, float)
    # Timestamp should be recent
    assert ev.timestamp == pytest.approx(time.time(), abs=5.0)


def test_rule_name_and_metadata():
    ev = Evidence(
        agent_id="a1",
        authority_id="auth1",
        positive=1.0,
        rule_name="honesty",
        metadata={"source": "observation"},
    )
    assert ev.rule_name == "honesty"
    assert ev.metadata["source"] == "observation"


def test_evidence_result():
    er = EvidenceResult(positive=2.0, negative=1.0, metadata={"key": "val"})
    assert er.positive == pytest.approx(2.0)
    assert er.negative == pytest.approx(1.0)
    assert er.metadata["key"] == "val"


def test_evidence_result_defaults():
    er = EvidenceResult()
    assert er.positive == pytest.approx(0.0)
    assert er.negative == pytest.approx(0.0)
    assert er.metadata == {}
