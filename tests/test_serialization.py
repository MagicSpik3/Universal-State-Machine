"""
Tests for serialization and deserialization of CSLM objects.

These tests ensure lossless JSON/YAML round-trip using the explicit
serialization functions in `cslm.serialization`.
"""

from cslm.model import Survey, Variable, State, Transition
from cslm.expressions import (
    BinaryExpression,
    BinaryOperator,
    VariableReference,
    Literal,
)
from cslm.serialization import (
    survey_to_dict,
    survey_from_dict,
    survey_to_json,
    survey_from_json,
    survey_to_yaml,
    survey_from_yaml,
)


def build_sample_survey() -> Survey:
    survey = Survey(name="Serialization Test Survey")
    survey.variables = [
        Variable(name="Wrking", description="Currently working"),
        Variable(name="BType1", description="Employment type job1"),
    ]

    # Entry guard: Wrking == 1
    guard = BinaryExpression(
        operator=BinaryOperator.EQUALS,
        left=VariableReference("Wrking"),
        right=Literal(1),
    )

    # Validation: (BType1 >=1 AND BType1 <=5) OR BType1 == -8
    range_check = BinaryExpression(
        operator=BinaryOperator.AND,
        left=BinaryExpression(
            operator=BinaryOperator.GREATER_EQUAL,
            left=VariableReference("BType1"),
            right=Literal(1),
        ),
        right=BinaryExpression(
            operator=BinaryOperator.LESS_EQUAL,
            left=VariableReference("BType1"),
            right=Literal(5),
        ),
    )
    validation = BinaryExpression(
        operator=BinaryOperator.OR,
        left=range_check,
        right=BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("BType1"),
            right=Literal(-8),
        ),
    )

    state = State(id="BType1", text="Employment type?", entry_guard=guard, validation=validation)
    survey.states = [state]
    survey.transitions = [Transition(from_state="START", to_state="BType1")]
    survey.metadata = {"source": "example_survey.csv"}

    return survey


def test_json_roundtrip():
    survey = build_sample_survey()
    before = survey_to_dict(survey)
    json_str = survey_to_json(survey)
    restored = survey_from_json(json_str)
    after = survey_to_dict(restored)
    assert before == after


def test_yaml_roundtrip():
    survey = build_sample_survey()
    before = survey_to_dict(survey)
    yaml_str = survey_to_yaml(survey)
    restored = survey_from_yaml(yaml_str)
    after = survey_to_dict(restored)
    assert before == after
