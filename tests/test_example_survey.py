"""
Test the proof-of-concept example survey built from the CSV snippet.

Validates that the example builder creates the expected states, guards,
and version metadata for the job-pattern.
"""

from cslm.examples import build_example_job_survey


def test_example_job_survey_structure():
    survey = build_example_job_survey(job_count=3, apply_from=2204)

    # Expect 3 jobs * 3 states each = 9 states
    assert len(survey.states) == 9

    # Check first job state exists and has validation/version
    btype1 = survey.get_state("BType1")
    assert btype1 is not None
    assert btype1.version is not None
    assert btype1.version.apply_from == 2204

    # Check transitions include START -> BType1
    start_transitions = [t for t in survey.transitions if t.from_state == "START" and t.to_state == "BType1"]
    assert len(start_transitions) == 1

    # Check guarded transitions from BType1 to BDirNI1 and BOwn1
    guards = {t.to_state: t.guard for t in survey.transitions if t.from_state == "BType1"}
    assert "BDirNI1" in guards
    assert "BOwn1" in guards
