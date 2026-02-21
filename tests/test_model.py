"""
Tests for CSLM Core Model Objects

Test-driven development: define expected behavior before implementation.

These tests verify:
    - Basic model creation
    - Relationships between objects
    - Invariants and constraints
    - Retrieval methods
    - Serialization readiness
"""

import pytest
from cslm.model import (
    Variable,
    State,
    Transition,
    Block,
    Survey,
    VersionRange,
)
from cslm.expressions import (
    BinaryExpression,
    BinaryOperator,
    VariableReference,
    Literal,
)


class TestVariable:
    """Test Variable objects."""
    
    def test_create_variable(self):
        """Should create a variable with name."""
        var = Variable(name="BType1")
        assert var.name == "BType1"
    
    def test_variable_with_description(self):
        """Should store optional description."""
        var = Variable(
            name="Wrking",
            description="Whether currently working"
        )
        assert var.name == "Wrking"
        assert var.description == "Whether currently working"
    
    def test_variable_with_data_type(self):
        """Should store optional data type."""
        var = Variable(
            name="NumJob",
            data_type="integer"
        )
        assert var.data_type == "integer"


class TestVersionRange:
    """Test VersionRange objects."""
    
    def test_apply_from_only(self):
        """Should support apply_from without apply_to."""
        vr = VersionRange(apply_from=2204)
        assert vr.apply_from == 2204
        assert vr.apply_to is None
    
    def test_apply_from_and_to(self):
        """Should support both apply_from and apply_to."""
        vr = VersionRange(apply_from=2204, apply_to=2206)
        assert vr.apply_from == 2204
        assert vr.apply_to == 2206
    
    def test_empty_version_range(self):
        """Should allow empty version range."""
        vr = VersionRange()
        assert vr.apply_from is None
        assert vr.apply_to is None


class TestState:
    """Test State (question) objects."""
    
    def test_minimal_state(self):
        """Should create state with just id and text."""
        state = State(
            id="BType1",
            text="Now, thinking of your job..."
        )
        assert state.id == "BType1"
        assert state.text == "Now, thinking of your job..."
        assert state.entry_guard is None
        assert state.validation is None
    
    def test_state_with_entry_guard(self):
        """Should attach entry guard expression."""
        guard = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("Wrking"),
            right=Literal(1)
        )
        state = State(
            id="BType1",
            text="Question...",
            entry_guard=guard
        )
        assert state.entry_guard is not None
        assert state.entry_guard.operator == BinaryOperator.EQUALS
    
    def test_state_with_validation(self):
        """Should attach validation expression."""
        validation = BinaryExpression(
            operator=BinaryOperator.OR,
            left=BinaryExpression(
                operator=BinaryOperator.GREATER_EQUAL,
                left=VariableReference("BType1"),
                right=Literal(1)
            ),
            right=BinaryExpression(
                operator=BinaryOperator.LESS_EQUAL,
                left=VariableReference("BType1"),
                right=Literal(5)
            )
        )
        state = State(
            id="BType1",
            text="Question...",
            validation=validation
        )
        assert state.validation is not None
    
    def test_state_with_version(self):
        """Should attach version range."""
        state = State(
            id="BType1",
            text="Question...",
            version=VersionRange(apply_from=2204)
        )
        assert state.version is not None
        assert state.version.apply_from == 2204
    
    def test_state_with_block(self):
        """Should mark state as belonging to a block."""
        state = State(
            id="BType1",
            text="Question...",
            block="JobBlock"
        )
        assert state.block == "JobBlock"
    
    def test_state_full_definition(self):
        """Should support state with all attributes."""
        guard = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("Wrking"),
            right=Literal(1)
        )
        validation = BinaryExpression(
            operator=BinaryOperator.OR,
            left=Literal(1),
            right=Literal(-8)
        )
        state = State(
            id="BType1",
            text="Employment type...",
            entry_guard=guard,
            validation=validation,
            version=VersionRange(apply_from=2204),
            block="JobBlock"
        )
        assert state.id == "BType1"
        assert state.entry_guard is not None
        assert state.validation is not None
        assert state.version is not None
        assert state.block == "JobBlock"


class TestTransition:
    """Test Transition (edge) objects."""
    
    def test_unconditional_transition(self):
        """Should create transition without guard."""
        trans = Transition(
            from_state="BType1",
            to_state="BDirNI1"
        )
        assert trans.from_state == "BType1"
        assert trans.to_state == "BDirNI1"
        assert trans.guard is None
    
    def test_guarded_transition(self):
        """Should create transition with guard condition."""
        guard = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("BType1"),
            right=Literal(2)
        )
        trans = Transition(
            from_state="BType1",
            to_state="BDirNI1",
            guard=guard
        )
        assert trans.guard is not None
        assert trans.guard.operator == BinaryOperator.EQUALS
    
    def test_or_guarded_transition(self):
        """Should support complex OR guards."""
        guard = BinaryExpression(
            operator=BinaryOperator.OR,
            left=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("BType1"),
                right=Literal(2)
            ),
            right=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("BType1"),
                right=Literal(3)
            )
        )
        trans = Transition(
            from_state="BType1",
            to_state="BDirNI1",
            guard=guard
        )
        assert trans.guard is not None


class TestBlock:
    """Test Block (parameterized subgraph) objects."""
    
    def test_create_block(self):
        """Should create named block."""
        block = Block(name="JobBlock")
        assert block.name == "JobBlock"
    
    def test_block_with_parameters(self):
        """Should store parameter names."""
        block = Block(
            name="JobBlock",
            parameters=["job_index"]
        )
        assert block.parameters == ["job_index"]
    
    def test_block_with_states(self):
        """Should reference state IDs in block."""
        block = Block(
            name="JobBlock",
            parameters=["job_index"],
            state_ids=["BType", "BDirNI", "BOwn"]
        )
        assert block.state_ids == ["BType", "BDirNI", "BOwn"]


class TestSurvey:
    """Test Survey (root container) objects."""
    
    def test_create_empty_survey(self):
        """Should create survey with just a name."""
        survey = Survey(name="Employment Survey")
        assert survey.name == "Employment Survey"
        assert len(survey.variables) == 0
        assert len(survey.states) == 0
        assert len(survey.transitions) == 0
    
    def test_survey_with_variables(self):
        """Should add variables to survey."""
        survey = Survey(name="Test")
        survey.variables = [
            Variable(name="BType1"),
            Variable(name="Wrking"),
        ]
        assert len(survey.variables) == 2
        assert survey.variables[0].name == "BType1"
    
    def test_survey_with_states(self):
        """Should add states to survey."""
        survey = Survey(name="Test")
        survey.states = [
            State(id="Q1", text="First question"),
            State(id="Q2", text="Second question"),
        ]
        assert len(survey.states) == 2
    
    def test_survey_with_transitions(self):
        """Should add transitions to survey."""
        survey = Survey(name="Test")
        survey.transitions = [
            Transition(from_state="Q1", to_state="Q2"),
        ]
        assert len(survey.transitions) == 1
    
    def test_survey_with_metadata(self):
        """Should store arbitrary metadata."""
        survey = Survey(
            name="Test",
            metadata={"source_wave": "2204"}
        )
        assert survey.metadata["source_wave"] == "2204"
    
    def test_get_state(self):
        """Should retrieve state by ID."""
        survey = Survey(name="Test")
        survey.states = [
            State(id="Q1", text="First"),
            State(id="Q2", text="Second"),
        ]
        state = survey.get_state("Q1")
        assert state is not None
        assert state.text == "First"
    
    def test_get_state_not_found(self):
        """Should return None for missing state."""
        survey = Survey(name="Test")
        state = survey.get_state("Missing")
        assert state is None
    
    def test_get_variable(self):
        """Should retrieve variable by name."""
        survey = Survey(name="Test")
        survey.variables = [
            Variable(name="X"),
            Variable(name="Y"),
        ]
        var = survey.get_variable("X")
        assert var is not None
        assert var.name == "X"
    
    def test_get_variable_not_found(self):
        """Should return None for missing variable."""
        survey = Survey(name="Test")
        var = survey.get_variable("Missing")
        assert var is None
    
    def test_get_block(self):
        """Should retrieve block by name."""
        survey = Survey(name="Test")
        survey.blocks = [
            Block(name="JobBlock"),
            Block(name="IncomeBlock"),
        ]
        block = survey.get_block("JobBlock")
        assert block is not None
        assert block.name == "JobBlock"
    
    def test_get_block_not_found(self):
        """Should return None for missing block."""
        survey = Survey(name="Test")
        block = survey.get_block("Missing")
        assert block is None
    
    def test_simple_survey_composition(self):
        """Should build a simple multi-state survey."""
        survey = Survey(name="Simple Employment Survey")
        
        # Add variables
        survey.variables = [
            Variable(name="Wrking", description="Currently working"),
            Variable(name="BType1", description="Employment type - Job 1"),
        ]
        
        # Add states
        survey.states = [
            State(
                id="BType1",
                text="Now, thinking of your job...",
                entry_guard=BinaryExpression(
                    operator=BinaryOperator.EQUALS,
                    left=VariableReference("Wrking"),
                    right=Literal(1)
                )
            ),
        ]
        
        # Add transitions
        survey.transitions = [
            Transition(from_state="START", to_state="BType1"),
        ]
        
        assert survey.get_variable("Wrking") is not None
        assert survey.get_state("BType1") is not None
        assert len(survey.transitions) == 1
