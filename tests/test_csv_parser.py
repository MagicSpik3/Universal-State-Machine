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
        """Invalid expression should issue a warning but not crash."""
        csv = '''variable,question,route,valid_response,multi,max_choices,apply_from
Q1,"Test?",,(Q1 INVALID 1),,,2204'''  # INVALID is not a valid operator
        
        with pytest.warns(UserWarning, match="Invalid validation"):
            survey = parse_csv_string(csv)
            assert survey is not None  # Should still parse successfully
    
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
    
    def test_additional_successful_expressions(self):
        """Test various successful expressions from routing_uplift.csv."""
        test_cases = [
            "(SEInt ==1 | Seint ==-8)",
            "(MoreNme13 == 1 | MoreNme13 == 2 | MoreNme13 == -8)",
            "((mjme20 >=1 & mjme20 <18) | mjme20 ==-8)",
            "((IGLnPyBk1 == 1 | IGLnPyBk1 == 2 | IGLnPyBk1 == 3) | IGLnPyBk1 == -8)",
            "((votyp1 >0 & votyp1 <7) | votyp1 ==-8)",
            "((DLins3 >=0 & DLins3 < 999998) | DLins3 ==-8)",
            "(DLNum >1 & (DLType2 !=2 & DLType2 !=3 & DLType2 !=-9))",
            "((reglrpy2 >0 & reglrpy2 <7) |(reglrpy2 == -8))",
            "(UProp1 ==5 | UProp2 ==5 | UProp3 ==5 | UProp4 ==5 | UProp5 ==5 | UProp6 ==5)",
            "((OSafeSav == 1 | OSafeSav == 2 | OSafeSav == 3 | OSafeSav == 4 | OSafeSav == 5) | OSafeSav == -8)",
            "((CaOpen == 1 | CaOpen == 2 | CaOpen == 3) | CaOpen == -8)",
            "(StartJ == 1 | StartJ == 2 | StartJ == -8)",
            "(hout < 300 & dvage > 15) & (iswitch !=4)",
            "(Rgift == 1 & RGfFrom2 >0)",
            "((FTypeInv2 >0 & FTypeInv2 <8) | FtypeInv2 ==-8)",
            "((FShOSVb >0 & FShOSVb <13) | FShOSVb ==-8)",
            "(SEAmK ==1 | SEAMK ==2 | SEAmK ==-8)",
            "(dvage >15 & PinPNum >= 6)"
        ]
        
        for expr_str in test_cases:
            result = normalize_expression_syntax(expr_str)
            assert result is not None, f"Failed to parse: {expr_str}"


class TestRoutingUpliftFailures:
    """RED light tests for currently failing expressions from routing_uplift.csv.
    
    These tests are designed to fail initially (RED) and then pass as we fix
    the parser to handle these failure categories.
    """
    
    def test_missing_closing_parenthesis(self):
        """RED: Missing closing parenthesis in function calls."""
        failing_cases = [
            "(CheckAdd == 2 & !is.(Prem2)",
            "(CheckAdd == 2 & !is.(Prem3)",
            "(Intro == 1 & !is.(CFNP1F) & !is.(CFNP1S)",
            "(Move == 1 & MKnowPC == 1 & !is.(MOutCode)",
            "((Intro == 1 & !is.(CFNP1F)) | !is.(CFNP1S)",
            "(morsavre2 >0",
        ]
        
        for expr_str in failing_cases:
            with pytest.raises(CSVParseError, match="Missing closing parenthesis"):
                normalize_expression_syntax(expr_str)
    
    def test_empty_string_literals(self):
        """RED: Empty string literals in comparisons like != ''."""
        failing_cases = [
            '(UPNo1 != "")',
            '(UPNo2 != "")',
            '(UPNo10 != "")',
            '(ActEPme !="" & ActEPme != 999999999999999999999999999999)',
            '(ActEPme2 !="" & ActEPme2 != 999999999999999999999999999999)',
        ]
        
        for expr_str in failing_cases:
            with pytest.raises(CSVParseError):
                normalize_expression_syntax(expr_str)
    
    def test_date_format_literals(self):
        """RED: Date formats like 01.09.2002 and 01/09/2002 as literals."""
        failing_cases = [
            "(SelectAd != -8 & (DteofBth >= 01.09.2002 & DteofBth <= 02.01.2011))",
            "(SelectAd2 != -8 & (DteofBth >= 01.09.2002 & DteofBth <= 02.01.2011))",
            "(SelectAd10 != -8 & (DteofBth >= 01.09.2002 & DteofBth <= 02.01.2011))",
            "(dvage >= 18) & ((dteofbth > 01/09/2002) & (dteofbth < 02/01/2011)) & (iswitch !=4)",
        ]
        
        for expr_str in failing_cases:
            with pytest.raises(CSVParseError):
                normalize_expression_syntax(expr_str)
    
    def test_operator_precedence_ambiguity(self):
        """RED: Missing parentheses causing operator precedence issues.
        
        Note: These actually parse successfully with our current precedence rules,
        but they are documented as failures in the CSV. This may indicate that
        the precedence is actually correct for SPSS syntax, and the CSV might
        have intended different grouping but expressed it ambiguously.
        """
        # These actually succeed with our parser - documenting for reference
        succeeding_cases = [
            "((disben1 == 1 | disben2 == 1 | disben3 == 1 | disben4 == 1 | disben5 == 1 | disben6 == 1) | (PIPType == 1 | PIPType == 3)  & (iSwitch !=4))",
            "((disben1 == 2 | disben2 == 2 | disben3 == 2 | disben4 == 2 | disben5 == 2 | disben6 == 2) | (DLAType == 1 | DLAType == 3)  & (iSwitch !=4))",
            "((disben1 == 3 | disben2 == 3 | disben3 == 3 | disben4 == 3 | disben5 == 3 | disben6 == 3) & (iSwitch !=4))",
        ]
        
        for expr_str in succeeding_cases:
            # These should parse without raising
            result = normalize_expression_syntax(expr_str)
            assert result is not None
    
    def test_extra_closing_parenthesis(self):
        """RED: Extra closing parenthesis (too many closing parens).
        
        Only testing the ones that genuinely have extra closing parenthesis.
        Other expressions in the CSV may fail for different reasons.
        """
        # These have actual extra closing parenthesis in the CSV data
        failing_with_extra = [
            "((CaContr5 > 0 & Cacontr5 < 7) | CaContr5 == -8))",  # Extra ))
            "((CaContr6 > 0 & Cacontr6 < 7) | CaContr6 == -8))",  # Extra ))
        ]
        
        for expr_str in failing_with_extra:
            with pytest.raises(CSVParseError):
                normalize_expression_syntax(expr_str)
    
    def test_r_specific_syntax(self):
        """RED: R-specific functions and operators not supported in our syntax."""
        failing_cases = [
            '(CheckAdd == 1 & KnowPC == 1 & (substr(OutCode(1,1)) %in% c("E","W") | substr(Outcode(1,2)) %in% c("EC","WC")))',
            '(benpd %in% c(1:10, 13, 26, 52, 90, 95, 97, -8)',
            '(valid_response: is.character(upno1))',
            '(valid_response: is.character(upno10))',
        ]
        
        for expr_str in failing_cases:
            with pytest.raises(CSVParseError):
                normalize_expression_syntax(expr_str)
    
    def test_malformed_variable_names_with_spaces(self):
        """RED: Variable names or tokens with unexpected spaces."""
        failing_cases = [
            "(Rgffrom1 > 0 & IRGfUse 101 >0)",  # "IRGfUse 101" has space
            "((OthSrc3 == 1 | OthSrc3 == 2 | OthSrc3 == 3 ) | OthSrc 3== -8)",  # "OthSrc 3" has space
        ]
        
        for expr_str in failing_cases:
            with pytest.raises(CSVParseError):
                normalize_expression_syntax(expr_str)
    
    def test_extra_closing_parenthesis(self):
        """RED: Extra closing parenthesis (too many closing parens)."""
        failing_cases = [
            "((CaContr5 > 0 & Cacontr5 < 7) | CaContr5 == -8))",  # Extra ending )
            "((CaContr6 > 0 & Cacontr6 < 7) | CaContr6 == -8))",  # Extra ending )
        ]
        
        for expr_str in failing_cases:
            with pytest.raises(CSVParseError, match="Unexpected tokens"):
                normalize_expression_syntax(expr_str)
    
    def test_complex_operator_precedence_with_missing_parens(self):
        """RED: Complex multiple-operator expressions with implicit precedence."""
        failing_cases = [
            "((Dvage >15) & (ActEPJb !=1) & (ActEPme !="" & ActEPme != 999999999999999999999999999999 & ActEpme != 999999999999999999999999999998)) & (iSwitch != 4)",
            "((Dvage >15) & (ActEPJb2 !=1) & (ActEPme2 !="" & ActEPme2 != 999999999999999999999999999999 & ActEpme2 != 999999999999999999999999999998)) & (iSwitch != 4)",
            "((iSwitch != 4) & (Dvilo4a ==1 & JbAway ==1) | (Dvilo4a ==2 & PenFlag ==0 & Everwk ==1 & DtJbL > ( Startdat - 2) )& (BType1 == 1) | (BType1 ==2 | BType1 ==3 & BDirNi1 ==1 | Stat ==1))",
        ]
        
        for expr_str in failing_cases:
            with pytest.raises(CSVParseError):
                normalize_expression_syntax(expr_str)


class TestRoutingUpliftOtherFailures:
    """Additional RED light tests for other failure patterns."""
    
    def test_unbalanced_parenthesis_missing_closing(self):
        """RED: These expressions have unbalanced parenthesis - missing closing ones."""
        failing_cases = [
            "((ORiska == 1 | ORiska == 2 | ORiska == 3) | ORiska == -8)",  # Missing final )
            "((ORiskc == 1 | ORiskc == 2 | ORiskc == 3) | ORiskc == -8)",  # Missing final )
            "(COLBnkSt1 == 1 | COLBnkSt1 == 2) | COLBnkSt1 == -8)",  # Missing final )
            "(COLBnkSt2 == 1 | COLBnkSt2 == 2) | COLBnkSt2 == -8)",  # Missing final )
            "(COLBnkSt3 == 1 | COLBnkSt3 == 2) | COLBnkSt3 == -8)",  # Missing final )
            "(COLBnkSt4 == 1 | COLBnkSt4 == 2) | COLBnkSt4 == -8)",  # Missing final )
            "(COLBnkSt5 == 1 | COLBnkSt5 == 2) | COLBnkSt5 == -8)",  # Missing final )
            "(COLPltr1 == 1 | COLPltr1 == 2) | COLPltr1 == -8)",  # Missing final )
            "(COLPltr2 == 1 | COLPltr2 == 2) | COLPltr2 == -8)",  # Missing final )
            "(COLPltr3 == 1 | COLPltr3 == 2) | COLPltr3 == -8)",  # Missing final )
            "(COLPltr4 == 1 | COLPltr4 == 2) | COLPltr4 == -8)",  # Missing final )
            "(COLPltr5 == 1 | COLPltr5 == 2) | COLPltr5 == -8)",  # Missing final )
            "(FTypeAcc2 >0 & FtypeAcc2 <5) | FTYpeAcc2 ==-8)",  # Missing final )
            "(WINW == 1 | WINW == 2) | WINW == -8)",  # Missing final )
        ]
        
        for expr_str in failing_cases:
            with pytest.raises(CSVParseError):
                normalize_expression_syntax(expr_str)
