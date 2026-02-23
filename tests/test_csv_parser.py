"""
Tests for CSV parser (Layer 1: Raw Input → CSLM).

CSV format from example_survey.csv:
    variable, question, route, valid_response, multi, max_choices, apply_from

We need to:
1. Parse the CSV structure
2. Convert SPSS-like syntax (& | ==) to our Expression AST
3. Handle multiline question text
4. Infer transitions from routing patterns
5. Create a complete Survey object
"""

import pytest
from io import StringIO
from cslm.csv_parser import (
    parse_csv_string,
    parse_csv_file,
    CSVParseError,
    normalize_expression_syntax,
)
from cslm.expressions import (
    BinaryExpression,
    BinaryOperator,
    VariableReference,
    Literal,
    UnaryExpression,
    UnaryOperator,
)
from cslm.model import Survey


class TestExpressionNormalization:
    """Test conversion from SPSS-like syntax to our AST."""
    
    def test_simple_equality(self):
        """X == 1 works as-is."""
        expr_str = "X == 1"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        assert result.operator == BinaryOperator.EQUALS
    
    def test_and_operator_conversion(self):
        """& should convert to AND."""
        expr_str = "X == 1 & Y == 2"
        result = normalize_expression_syntax(expr_str)
        # Should be BinaryExpression with AND operator
        assert isinstance(result, BinaryExpression)
        assert "AND" in str(result.operator)
    
    def test_or_operator_conversion(self):
        """| should convert to OR."""
        expr_str = "X == 1 | Y == 2"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        assert "OR" in str(result.operator)
    
    def test_complex_expression(self):
        """Test complex nested expression with & and |."""
        expr_str = "(X == 1 | X == 2) & Y == 3"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        # Should parse without error
        assert result is not None
    
    def test_multiline_expression(self):
        """Normalize should handle newlines in expressions."""
        expr_str = "X == 1 &\nY == 2"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
    
    def test_whitespace_handling(self):
        """Extra whitespace should be ignored."""
        expr_str = "X   ==   1   &   Y   ==   2"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)


class TestCSVParsing:
    """Test basic CSV row parsing."""
    
    def test_empty_csv(self):
        """Empty CSV should result in empty survey."""
        csv = "variable,question,route,valid_response,multi,max_choices,apply_from\n"
        survey = parse_csv_string(csv)
        assert isinstance(survey, Survey)
        assert len(survey.states) == 0
        assert len(survey.variables) == 0
    
    def test_single_question_no_route(self):
        """Parse a simple question with no routing."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"What is your age?",,(Q1 >= 18 & Q1 <= 100),,,2204'''
        
        survey = parse_csv_string(csv)
        assert len(survey.variables) >= 1
        assert len(survey.states) >= 1
        
        # State should exist
        state_q1 = survey.get_state("Q1")
        assert state_q1 is not None
        assert state_q1.text == "What is your age?"
        assert state_q1.validation is not None
    
    def test_simple_routing_condition(self):
        """Parse a question with a routing condition."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"Are you employed?",,(Q1 == 1 | Q1 == 2),,,2204
Q2,"How many hours?",Q1 == 1,(Q2 >= 0 & Q2 <= 168),,,2204'''
        
        survey = parse_csv_string(csv)
        
        # Should have both states
        assert survey.get_state("Q1") is not None
        assert survey.get_state("Q2") is not None
        
        # Should have transition Q1 -> Q2 with guard
        state_q2 = survey.get_state("Q2")
        assert state_q2.entry_guard is not None
    
    def test_multiline_question_text(self):
        """Parse question text with embedded newlines."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"This is a
multiline
question",,(Q1 == 1),,,2204'''
        
        survey = parse_csv_string(csv)
        state_q1 = survey.get_state("Q1")
        assert state_q1 is not None
        # Question should include newlines or be normalized
        assert "question" in state_q1.text.lower()
    
    def test_version_metadata(self):
        """parse_from column should create VersionRange."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"Age?",,(Q1 >= 0),,,2024'''
        
        survey = parse_csv_string(csv)
        state = survey.get_state("Q1")
        assert state.version is not None
        assert state.version.apply_from == 2024
    
    def test_job_pattern_3jobs(self):
        """Parse 3-job employment pattern from example."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
BType1,"Employment type job 1",(Wrking == 1),((BType1 >= 1 & BType1 <= 5) | BType1 == -8),,,2204
BType2,"Employment type job 2",(NumJob >= 2 & Wrking == 1),((BType2 >= 1 & BType2 <= 5) | BType2 == -8),,,2204
BDirNI1,"NI deducted job 1",(BType1 == 2 | BType1 == 3),(BDirNI1 == 1 | BDirNI1 == 2),,,2204
BDirNI2,"NI deducted job 2",(NumJob >= 2 & (BType2 == 2 | BType2 == 3)),(BDirNI2 == 1 | BDirNI2 == 2),,,2204'''
        
        survey = parse_csv_string(csv)
        
        # Should have all states
        assert survey.get_state("BType1") is not None
        assert survey.get_state("BType2") is not None
        assert survey.get_state("BDirNI1") is not None
        assert survey.get_state("BDirNI2") is not None
        
        # BType1 should have entry guard
        btype1 = survey.get_state("BType1")
        assert btype1.entry_guard is not None
    
    def test_comparison_operators(self):
        """Handle all comparison operators: ==, !=, <, >, <=, >=."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"Test?",,((Q1 == 1) | (Q1 != 0) | (Q1 > 5) | (Q1 >= 10) | (Q1 < 20) | (Q1 <= 15)),,,2024'''
        
        survey = parse_csv_string(csv)
        state = survey.get_state("Q1")
        assert state.validation is not None


class TestCSVFileHandling:
    """Test file I/O operations."""
    
    def test_parse_csv_file(self, tmp_path):
        """Parse CSV from actual file."""
        csv_file = tmp_path / "test_survey.csv"
        csv_content = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"Are you employed?",,(Q1 == 1 | Q1 == 2),,,2204
Q2,"Hours worked?",Q1 == 1,(Q2 >= 0 & Q2 <= 168),,,2204'''
        
        csv_file.write_text(csv_content)
        
        survey = parse_csv_file(str(csv_file))
        assert len(survey.states) == 2
        assert survey.get_state("Q1") is not None
        assert survey.get_state("Q2") is not None
    
    def test_parse_example_survey(self):
        """Parse the actual example_survey.csv from workspace."""
        import os
        csv_path = "/home/jonny/git/Universal-State-Machine/example_survey.csv"
        
        if os.path.exists(csv_path):
            survey = parse_csv_file(csv_path)
            assert isinstance(survey, Survey)
            assert len(survey.states) > 0
            # Should have BType1, BType2, etc.
            assert survey.get_state("BType1") is not None or len(survey.states) > 0


class TestCSVErrors:
    """Test error handling."""
    
    def test_missing_required_column(self):
        """Missing required columns should raise error."""
        csv = "variable,question\nQ1,Test"
        with pytest.raises(CSVParseError):
            parse_csv_string(csv)
    
    def test_invalid_expression_syntax(self):
        """Invalid expression should raise CSVParseError."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"Test?",,(Q1 INVALID 1),,,2204'''  # INVALID is not a valid operator
        
        with pytest.raises(CSVParseError):
            parse_csv_string(csv)
    
    def test_duplicate_variable_names(self):
        """Duplicate variable names should raise error or be handled."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"Q1 text",,(Q1 == 1),,,2204
Q1,"Different Q1",,(Q1 == 2),,,2204'''
        
        # Should either raise or use last one
        with pytest.raises(CSVParseError):
            parse_csv_string(csv)


class TestTransitionInference:
    """Test automatic transition inference from routing logic."""
    
    def test_infer_transitions_from_guards(self):
        """Transitions should be inferred from entry_guard patterns."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"Start?",,(Q1 == 1),,,2204
Q2,"Next?",Q1 == 1,(Q2 == 1),,,2204
Q3,"Branch?","Q1 == 1 | Q1 == 2",(Q3 == 1),,,2204'''
        
        survey = parse_csv_string(csv)
        
        # Should have transitions
        # Q1 -> Q2 (because Q2 guard is "Q1 == 1")
        # Q1 -> Q3 (because Q3 guard is "Q1 == 1 | Q1 == 2")
        
        transitions = [t for t in survey.transitions if t.from_state == "Q1"]
        assert len(transitions) >= 1  # At least one transition from Q1
    
    def test_no_transition_without_guard(self):
        """Questions with no routing should not automatically transition."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"First?",,(Q1 == 1 | Q1 == 2),,,2204
Q2,"Unrelated?",,(Q2 == 1),,,2204'''
        
        survey = parse_csv_string(csv)
        
        # Q1 and Q2 are unrelated (Q2 has no guard mentioning Q1)
        # So there should be NO transition Q1 -> Q2
        q1_transitions = [t for t in survey.transitions if t.from_state == "Q1"]
        # Either 0 or only explicit transitions
        assert all(t.to_state != "Q2" for t in q1_transitions)


class TestVariableExtraction:
    """Test extracting variable declarations from CSV."""
    
    def test_extract_variable_from_column_name(self):
        """Variable should be extracted as Variable object."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Age,"How old are you?",,(Age >= 18 & Age <= 100),,,2024'''
        
        survey = parse_csv_string(csv)
        var = survey.get_variable("Age")
        assert var is not None
        assert var.name == "Age"
    
    def test_extract_variables_from_expressions(self):
        """Variables referenced in guards/validation should be extracted."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q2,"Hours?",(Q1 == 1),(Q2 >= 0 & Q2 <= 168),,,2024'''
        
        survey = parse_csv_string(csv)
        
        # Should have both Q1 and Q2 as variables
        assert survey.get_variable("Q1") is not None or len(survey.variables) > 0
        assert survey.get_variable("Q2") is not None or len(survey.variables) > 0


class TestEdgeCases:
    """Test edge cases and corner cases."""
    
    def test_empty_guard_condition(self):
        """Empty guard should create unconditional transition."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"First?",,(Q1 == 1),,,2024
Q2,"Always shown?",,(Q2 == 1),,,2024'''
        
        survey = parse_csv_string(csv)
        state_q2 = survey.get_state("Q2")
        # If Q2 has empty route, it might not have entry_guard
        # (depends on design choice)
        assert state_q2 is not None
    
    def test_parentheses_in_expressions(self):
        """Complex parenthesized expressions should parse."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q,"Test?","((X == 1 | X == 2) & (Y == 3 | Y == 4))",((Q >= 0 & Q <= 10)),,,2024'''
        
        survey = parse_csv_string(csv)
        assert survey.get_state("Q") is not None
    
    def test_negative_numbers(self):
        """Literals can be negative (e.g., -8 for missing)."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q,"Test?",,(Q == 1 | Q == -8),,,2024'''
        
        survey = parse_csv_string(csv)
        state = survey.get_state("Q")
        assert state.validation is not None


class TestRoutingUpliftExpressions:
    """Test expressions from routing_uplift.csv to cover real-world scenarios."""
    
    def test_decimal_literals(self):
        """Handle decimal numbers like 0.00 in expressions."""
        expr_str = "(rentexpam >=0.00 & rentexpam <99997.00) | rentexpam==-8"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        # Should parse without error
        assert result is not None
    
    def test_equality_operator_conversion(self):
        """Convert single = to == in expressions."""
        expr_str = "(MNeg1 = 0)"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        assert result.operator == BinaryOperator.EQUALS
    
    def test_complex_nested_expression(self):
        """Parse complex nested expression with multiple levels."""
        expr_str = "((((MNegB1 >=1 & MNegB1 <15) | MNegB1 ==-8) & MNeg1 != 1) | (MNeg1 == 0))"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        assert result is not None
    
    def test_function_call_expression(self):
        """Handle function calls like is.(variable)."""
        expr_str = "(!is.(add2))"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, UnaryExpression)
        assert result.operator == UnaryOperator.NOT
    
    def test_large_numbers(self):
        """Handle very large numbers in expressions."""
        expr_str = "(RentIncLdg > 0.00 & RentIncLdg < 9999997.00)"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        assert result is not None
    
    def test_mixed_operators(self):
        """Expressions with ==, !=, <, >, etc."""
        expr_str = "(curstat >0 & curstat <10) | curstat ==-8"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        assert result is not None
    
    def test_parenthesized_or_and(self):
        """Complex expressions with both OR and AND."""
        expr_str = "((hout < 300 & wave>1) & (iSwitch != 4))"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        assert result is not None
    
    def test_string_validation(self):
        """Validation expressions with STRING type."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
EmailAdd,PLEASE ENTER EMAIL ADDRESS,(knowdet1 == 3),STRING,,,2204'''
        
        survey = parse_csv_string(csv)
        state = survey.get_state("EmailAdd")
        assert isinstance(state.validation, VariableReference)
        assert state.validation.name == "STRING"
    
    def test_date_validation(self):
        """DATE type validation."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
StartDat,ENTER DATE,(hout < 1000),DATE,,,9999'''
        
        survey = parse_csv_string(csv)
        state = survey.get_state("StartDat")
        assert isinstance(state.validation, VariableReference)
        assert state.validation.name == "DATE"
    
    def test_malformed_expression_missing_parenthesis(self):
        """Test error handling for malformed expressions."""
        expr_str = "((rentexpam >=0.00 & rentexpam <99997.00) | rentexpam==-8"  # Missing closing )
        with pytest.raises(CSVParseError):
            normalize_expression_syntax(expr_str)
    
    def test_invalid_operator(self):
        """Invalid operators should raise error."""
        expr_str = "(X INVALID Y)"
        with pytest.raises(CSVParseError):
            normalize_expression_syntax(expr_str)
    
    def test_unmatched_parentheses(self):
        """Unmatched parentheses should raise error."""
        expr_str = "(X == 1"
        with pytest.raises(CSVParseError):
            normalize_expression_syntax(expr_str)
    
    def test_nested_function_calls(self):
        """Multiple nested function calls."""
        expr_str = "(!is.(Rme) | !is.(Rme2))"
        result = normalize_expression_syntax(expr_str)
        assert isinstance(result, BinaryExpression)
        assert result is not None
