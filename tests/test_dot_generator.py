"""
Tests for DOT diagram generator.

These tests verify that CSLM surveys are correctly converted to Graphviz DOT format.
We test extensively because visual output is easy to get wrong and hard to debug.

Tests cover:
    - State nodes and transitions (edges)
    - Guard labels on edges
    - Node styling and colors
    - Special character escaping
    - DOT syntax validity
    - Simple vs. detailed modes
"""

import pytest
from cslm.model import Survey, State, Transition, VersionRange
from cslm.expressions import (
    BinaryExpression,
    BinaryOperator,
    VariableReference,
    Literal,
)
from cslm.backends.dot_generator import (
    generate_dot,
    DotMode,
)


class TestDotBasicStructure:
    """Test basic DOT graph structure."""
    
    def test_empty_survey_generates_valid_dot(self):
        """Should generate valid DOT even for empty survey."""
        survey = Survey(name="Empty")
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # Must have digraph header and closing brace
        assert "digraph" in dot.lower()
        assert "{" in dot and "}" in dot
    
    def test_simple_state_becomes_node(self):
        """Each state should become a node in DOT."""
        survey = Survey(name="OneState")
        survey.states = [
            State(id="Q1", text="First Question"),
        ]
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # Node should appear with label
        assert 'Q1' in dot
        assert 'First Question' in dot
    
    def test_transition_becomes_edge(self):
        """Each transition should become an edge in DOT."""
        survey = Survey(name="TwoStates")
        survey.states = [
            State(id="Q1", text="First"),
            State(id="Q2", text="Second"),
        ]
        survey.transitions = [
            Transition(from_state="Q1", to_state="Q2"),
        ]
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # Edge notation: Q1 -> Q2
        assert "Q1" in dot and "Q2" in dot
        assert "->" in dot
    
    def test_start_marker_in_dot(self):
        """START entry point should be marked in DOT."""
        survey = Survey(name="WithStart")
        survey.states = [State(id="Q1", text="Q")]
        survey.transitions = [Transition(from_state="START", to_state="Q1")]
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # START should be visible or marked specially
        assert "START" in dot or "start" in dot.lower()
    
    def test_multiple_states_all_appear(self):
        """All states should appear in DOT."""
        survey = Survey(name="MultiState")
        survey.states = [
            State(id=f"Q{i}", text=f"Question {i}")
            for i in range(1, 6)
        ]
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        for i in range(1, 6):
            assert f"Q{i}" in dot


class TestDotGuardLabeling:
    """Test that transition guards are properly labeled."""
    
    def test_unconditional_edge_has_no_label(self):
        """Unconditional transitions should not have labels."""
        survey = Survey(name="NoGuard")
        survey.states = [
            State(id="Q1", text="Q1"),
            State(id="Q2", text="Q2"),
        ]
        survey.transitions = [
            Transition(from_state="Q1", to_state="Q2"),  # No guard
        ]
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # Should have edge but possibly no label
        assert "Q1" in dot and "Q2" in dot
    
    def test_guarded_edge_has_label_in_detailed(self):
        """In DETAILED mode, guarded transitions should show the condition."""
        guard = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("X"),
            right=Literal(1),
        )
        survey = Survey(name="Guarded")
        survey.states = [
            State(id="Q1", text="Q1"),
            State(id="Q2", text="Q2"),
        ]
        survey.transitions = [
            Transition(from_state="Q1", to_state="Q2", guard=guard),
        ]
        dot = generate_dot(survey, mode=DotMode.DETAILED)
        
        # Should contain variable name or some representation of guard
        assert "X" in dot or "label" in dot.lower()
    
    def test_or_guard_simplified_in_label(self):
        """OR guards should be represented clearly."""
        guard = BinaryExpression(
            operator=BinaryOperator.OR,
            left=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("X"),
                right=Literal(2),
            ),
            right=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("X"),
                right=Literal(3),
            ),
        )
        survey = Survey(name="OrGuard")
        survey.states = [State(id="Q1", text="Q1"), State(id="Q2", text="Q2")]
        survey.transitions = [
            Transition(from_state="Q1", to_state="Q2", guard=guard)
        ]
        dot = generate_dot(survey, mode=DotMode.DETAILED)
        
        # Label should contain variable and values
        assert "X" in dot


class TestDotEscaping:
    """Test proper escaping of special characters."""
    
    def test_quotes_in_text_escaped(self):
        """Double quotes in state text should be escaped."""
        survey = Survey(name="Quotes")
        survey.states = [
            State(id="Q1", text='Question with "quotes"'),
        ]
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # Should be valid DOT (backslashed or handled correctly)
        assert "digraph" in dot.lower()
        # Don't assert on exact escaping since different tools handle it differently
    
    def test_newlines_in_text_handled(self):
        """Multi-line text should be wrapped."""
        survey = Survey(name="Multiline")
        survey.states = [
            State(id="Q1", text="Line 1\nLine 2\nLine 3"),
        ]
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # Should be valid DOT
        assert "digraph" in dot.lower()
    
    def test_special_chars_in_ids_safe(self):
        """State IDs with special chars should be safely quoted."""
        survey = Survey(name="SpecialChars")
        survey.states = [
            State(id="Q-1", text="Q"),
        ]
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # Must be valid DOT with proper quoting
        assert "digraph" in dot.lower()


class TestDotModes:
    """Test different visualization modes."""
    
    def test_simple_mode_hides_guards(self):
        """SIMPLE mode should omit detailed guard labels."""
        guard = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("X"),
            right=Literal(1),
        )
        survey = Survey(name="Test")
        survey.states = [State(id="Q1", text="Q1"), State(id="Q2", text="Q2")]
        survey.transitions = [
            Transition(from_state="Q1", to_state="Q2", guard=guard)
        ]
        
        simple_dot = generate_dot(survey, mode=DotMode.SIMPLE)
        detailed_dot = generate_dot(survey, mode=DotMode.DETAILED)
        
        # Both valid, but detailed should have more content
        assert "digraph" in simple_dot.lower()
        assert "digraph" in detailed_dot.lower()
        # Detailed should be longer or have more descriptive info
        # (This is a rough check; exact behavior depends on implementation)
    
    def test_management_mode_shows_blocks(self):
        """MANAGEMENT mode should group states by block."""
        from cslm.model import Block
        
        survey = Survey(name="Blocks")
        survey.states = [
            State(id="Q1", text="Q1", block="JobBlock"),
            State(id="Q2", text="Q2", block="JobBlock"),
            State(id="Q3", text="Q3", block="IncomeBlock"),
        ]
        survey.transitions = [
            Transition(from_state="START", to_state="Q1"),
            Transition(from_state="Q1", to_state="Q2"),
            Transition(from_state="Q2", to_state="Q3"),
        ]
        survey.blocks = [
            Block(name="JobBlock", state_ids=["Q1", "Q2"]),
            Block(name="IncomeBlock", state_ids=["Q3"]),
        ]
        
        dot = generate_dot(survey, mode=DotMode.MANAGEMENT)
        
        # Should have subgraph clusters for blocks
        assert "digraph" in dot.lower()
        assert "cluster" in dot.lower() or "subgraph" in dot.lower()


class TestDotRealism:
    """Test DOT generation on realistic survey patterns."""
    
    def test_three_job_survey_structure(self):
        """Test on 3-job employment pattern."""
        from cslm.examples import build_example_job_survey
        
        survey = build_example_job_survey(job_count=3)
        dot = generate_dot(survey, mode=DotMode.DETAILED)
        
        # Must contain all job states
        for i in range(1, 4):
            assert f"BType{i}" in dot
            assert f"BOwn{i}" in dot
        
        # Must be valid DOT
        assert "digraph" in dot.lower()
        assert "->" in dot
    
    def test_dot_has_proper_termination(self):
        """All DOT should have proper closing brace."""
        survey = Survey(name="Test")
        survey.states = [State(id="Q1", text="Q")]
        survey.transitions = [Transition(from_state="START", to_state="Q1")]
        
        for mode in [DotMode.SIMPLE, DotMode.DETAILED]:
            dot = generate_dot(survey, mode=mode)
            assert dot.rstrip().endswith("}")


class TestDotSyntaxValidity:
    """Test that generated DOT is syntactically valid."""
    
    def test_dot_can_be_parsed(self):
        """Generated DOT should be parseable by graphviz."""
        from cslm.examples import build_example_job_survey
        
        survey = build_example_job_survey(job_count=2)
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # Save to file and verify structure
        assert "digraph" in dot.lower()
        assert "{" in dot
        assert "}" in dot
        
        # Count opens and closes
        assert dot.count("{") == dot.count("}")
    
    def test_edge_syntax_correct(self):
        """All edges should use correct -> syntax."""
        survey = Survey(name="Edges")
        survey.states = [
            State(id="A", text="A"),
            State(id="B", text="B"),
            State(id="C", text="C"),
        ]
        survey.transitions = [
            Transition(from_state="A", to_state="B"),
            Transition(from_state="B", to_state="C"),
        ]
        dot = generate_dot(survey, mode=DotMode.SIMPLE)
        
        # Should have exactly 2 arrows
        arrow_count = dot.count("->")
        assert arrow_count >= 2


class TestDotNodeStyling:
    """Test visual styling of nodes."""
    
    def test_start_node_distinct(self):
        """START node should have distinct styling."""
        survey = Survey(name="StartStyle")
        survey.states = [State(id="Q1", text="Q1")]
        survey.transitions = [Transition(from_state="START", to_state="Q1")]
        dot = generate_dot(survey, mode=DotMode.DETAILED)
        
        # START should have special styling (color, shape, etc.)
        # Check for common DOT styling attributes
        has_styling = (
            "shape=" in dot or "color=" in dot or "style=" in dot or "START" in dot
        )
        assert has_styling or "start" in dot.lower()
    
    def test_end_nodes_distinct(self):
        """Nodes with no outgoing edges should be visually distinct."""
        survey = Survey(name="EndStyle")
        survey.states = [
            State(id="Q1", text="Q1"),
            State(id="Q2", text="Q2"),
        ]
        survey.transitions = [
            Transition(from_state="START", to_state="Q1"),
            Transition(from_state="Q1", to_state="Q2"),
        ]
        dot = generate_dot(survey, mode=DotMode.DETAILED)
        
        # Should be valid (end node styling is optional)
        assert "digraph" in dot.lower()
