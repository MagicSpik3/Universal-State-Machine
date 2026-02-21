"""
Tests for the Survey Analyzer.

Tests verify that the analyzer correctly:
    - Inventories variables and transitions
    - Detects undefined/unused variables
    - Finds reachability and cycles
    - Measures expression complexity
    - Reports coverage metrics
"""

import pytest
from cslm.model import Survey, Variable, State, Transition, VersionRange
from cslm.expressions import (
    BinaryExpression,
    BinaryOperator,
    VariableReference,
    Literal,
)
from cslm.analyzer import analyze_survey


def test_simple_linear_survey():
    """Analyze a simple linear survey: START -> S1 -> S2."""
    survey = Survey(name="Linear")
    survey.variables = [Variable(name="X")]
    survey.states = [
        State(id="S1", text="Q1", entry_guard=BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("X"),
            right=Literal(1)
        )),
        State(id="S2", text="Q2"),
    ]
    survey.transitions = [
        Transition(from_state="START", to_state="S1"),
        Transition(from_state="S1", to_state="S2"),
    ]

    report = analyze_survey(survey)
    
    assert report.total_states == 2
    assert report.total_transitions == 2
    assert report.total_variables == 1
    assert "X" in report.variable_usage
    assert len(report.undefined_variables) == 0
    assert len(report.unused_variables) == 0
    assert not report.has_cycles


def test_undefined_variables():
    """Should detect variables referenced but not declared."""
    survey = Survey(name="Undefined")
    survey.variables = [Variable(name="X")]
    survey.states = [
        State(
            id="S1", 
            text="Q1",
            entry_guard=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("Y"),  # Y not declared
                right=Literal(1)
            )
        ),
    ]
    survey.transitions = [Transition(from_state="START", to_state="S1")]

    report = analyze_survey(survey)
    
    assert "Y" in report.undefined_variables
    assert len(report.warnings) > 0


def test_unused_variables():
    """Should detect declared variables not used."""
    survey = Survey(name="Unused")
    survey.variables = [
        Variable(name="X"),
        Variable(name="Y"),
    ]
    survey.states = [
        State(
            id="S1",
            text="Q1",
            entry_guard=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("X"),
                right=Literal(1)
            )
        ),
    ]
    survey.transitions = [Transition(from_state="START", to_state="S1")]

    report = analyze_survey(survey)
    
    assert "Y" in report.unused_variables
    assert "X" not in report.unused_variables


def test_reachability():
    """Should identify unreachable states."""
    survey = Survey(name="Unreachable")
    survey.states = [
        State(id="S1", text="Q1"),
        State(id="S2", text="Q2"),
        State(id="ORPHAN", text="Orphaned"),  # Never reached
    ]
    survey.transitions = [
        Transition(from_state="START", to_state="S1"),
        Transition(from_state="S1", to_state="S2"),
    ]

    report = analyze_survey(survey)
    
    assert "ORPHAN" in report.unreachable_states
    assert "S1" not in report.unreachable_states
    assert "S2" not in report.unreachable_states


def test_cycles():
    """Should detect cycles in the state graph."""
    survey = Survey(name="Cyclic")
    survey.states = [
        State(id="S1", text="Q1"),
        State(id="S2", text="Q2"),
    ]
    survey.transitions = [
        Transition(from_state="START", to_state="S1"),
        Transition(from_state="S1", to_state="S2"),
        Transition(from_state="S2", to_state="S1"),  # Creates cycle S1 -> S2 -> S1
    ]

    report = analyze_survey(survey)
    
    assert report.has_cycles
    assert report.cycle_example is not None
    assert len(report.warnings) > 0


def test_expression_complexity():
    """Should measure expression depth and node count."""
    # Simple: Literal(1)
    simple = Literal(1)
    
    # Medium: (X == 1 OR X == 2)
    medium = BinaryExpression(
        operator=BinaryOperator.OR,
        left=BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("X"),
            right=Literal(1)
        ),
        right=BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("X"),
            right=Literal(2)
        ),
    )
    
    # Complex: (X >= 1 AND X <= 5) OR X == -8
    complex_expr = BinaryExpression(
        operator=BinaryOperator.OR,
        left=BinaryExpression(
            operator=BinaryOperator.AND,
            left=BinaryExpression(
                operator=BinaryOperator.GREATER_EQUAL,
                left=VariableReference("X"),
                right=Literal(1),
            ),
            right=BinaryExpression(
                operator=BinaryOperator.LESS_EQUAL,
                left=VariableReference("X"),
                right=Literal(5),
            ),
        ),
        right=BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("X"),
            right=Literal(-8),
        ),
    )

    survey = Survey(name="ComplexExpr")
    survey.states = [
        State(id="S1", text="Q1", entry_guard=medium),
        State(id="S2", text="Q2", validation=complex_expr),
    ]
    survey.transitions = [Transition(from_state="START", to_state="S1")]

    report = analyze_survey(survey)
    
    assert report.max_expression_depth >= 2
    assert report.total_expression_nodes > 0


def test_validation_coverage():
    """Should report validation coverage."""
    survey = Survey(name="Coverage")
    survey.states = [
        State(id="S1", text="Q1", validation=Literal(True)),  # Has validation
        State(id="S2", text="Q2"),  # No validation
        State(id="S3", text="Q3"),  # No validation
    ]
    survey.transitions = [
        Transition(from_state="START", to_state="S1"),
        Transition(from_state="S1", to_state="S2"),
        Transition(from_state="S2", to_state="S3"),
    ]

    report = analyze_survey(survey)
    
    assert report.states_with_validation == 1
    assert report.validation_coverage_percent == pytest.approx(33.33, rel=1)


def test_entry_and_exit_points():
    """Should identify entry and exit points in the graph."""
    survey = Survey(name="EntryExit")
    survey.states = [
        State(id="S1", text="Q1"),
        State(id="S2", text="Q2"),
        State(id="S3", text="Q3"),
    ]
    survey.transitions = [
        Transition(from_state="START", to_state="S1"),
        Transition(from_state="S1", to_state="S2"),
        Transition(from_state="S2", to_state="S3"),
    ]

    report = analyze_survey(survey)
    
    # S1 is entry (START -> S1)
    assert "S1" in report.entry_points
    # S3 is exit (no outgoing transitions)
    assert "S3" in report.exit_points


def test_version_coverage():
    """Should report states with version metadata."""
    survey = Survey(name="Versioning")
    survey.states = [
        State(id="S1", text="Q1", version=VersionRange(apply_from=2204)),
        State(id="S2", text="Q2"),  # No version
    ]
    survey.transitions = [Transition(from_state="START", to_state="S1")]

    report = analyze_survey(survey)
    
    assert report.states_with_version == 1


def test_transitions_per_state():
    """Should measure transitions per state."""
    survey = Survey(name="TransPerState")
    survey.states = [
        State(id="S1", text="Q1"),
        State(id="S2", text="Q2"),
        State(id="S3", text="Q3"),
    ]
    survey.transitions = [
        Transition(from_state="START", to_state="S1"),
        Transition(from_state="S1", to_state="S2"),  # S1 -> S2
        Transition(from_state="S1", to_state="S3"),  # S1 -> S3 (2 outgoing from S1)
    ]

    report = analyze_survey(survey)
    
    assert report.max_transitions_per_state >= 2
    assert report.avg_transitions_per_state > 0


def test_no_warnings_clean_survey():
    """Clean survey should produce no warnings."""
    survey = Survey(name="Clean")
    survey.variables = [Variable(name="X")]
    survey.states = [
        State(
            id="S1",
            text="Q1",
            entry_guard=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("X"),
                right=Literal(1),
            ),
            validation=Literal(True),
            version=VersionRange(apply_from=2204),
        ),
        State(id="S2", text="Q2"),
    ]
    survey.transitions = [
        Transition(from_state="START", to_state="S1"),
        Transition(from_state="S1", to_state="S2"),
    ]

    report = analyze_survey(survey)
    
    # Should have no warnings
    assert len(report.warnings) == 0
