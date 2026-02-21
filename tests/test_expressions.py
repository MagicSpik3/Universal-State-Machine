"""
Tests for CSLM Expression System

Test-driven development: write tests that define expected behavior
before implementing code.

These tests verify:
    - Expression objects can be created
    - Expression tree composition
    - Expression immutability
    - Expression serialization-readiness
"""

import pytest
from cslm.expressions import (
    Expression,
    BinaryExpression,
    BinaryOperator,
    VariableReference,
    Literal,
    UnaryExpression,
    UnaryOperator,
)


class TestVariableReference:
    """Test variable reference expressions."""
    
    def test_create_variable_reference(self):
        """Should create a reference to a named variable."""
        var_ref = VariableReference("BType1")
        assert var_ref.name == "BType1"
    
    def test_variable_reference_is_expression(self):
        """Variables should be valid expressions."""
        var_ref = VariableReference("Wrking")
        assert isinstance(var_ref, Expression)
    
    def test_variable_reference_immutable(self):
        """Variable references should be immutable."""
        var_ref = VariableReference("BType1")
        with pytest.raises(AttributeError):
            var_ref.name = "Changed"


class TestLiteral:
    """Test literal value expressions."""
    
    def test_integer_literal(self):
        """Should create integer literal."""
        lit = Literal(5)
        assert lit.value == 5
    
    def test_float_literal(self):
        """Should create float literal."""
        lit = Literal(3.14)
        assert lit.value == 3.14
    
    def test_string_literal(self):
        """Should create string literal."""
        lit = Literal("Yes")
        assert lit.value == "Yes"
    
    def test_boolean_literal(self):
        """Should create boolean literal."""
        lit = Literal(True)
        assert lit.value is True
    
    def test_negative_literal(self):
        """Should handle negative values (e.g., missing value code -8)."""
        lit = Literal(-8)
        assert lit.value == -8
    
    def test_literal_is_expression(self):
        """Literals should be valid expressions."""
        lit = Literal(42)
        assert isinstance(lit, Expression)
    
    def test_literal_immutable(self):
        """Literals should be immutable."""
        lit = Literal(5)
        with pytest.raises(AttributeError):
            lit.value = 10


class TestBinaryExpression:
    """Test binary logical and comparison expressions."""
    
    def test_equality_expression(self):
        """Should create equality comparison."""
        expr = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("BType1"),
            right=Literal(2)
        )
        assert expr.operator == BinaryOperator.EQUALS
        assert isinstance(expr.left, VariableReference)
        assert isinstance(expr.right, Literal)
    
    def test_or_expression(self):
        """Should create OR logical expression."""
        left = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("BType1"),
            right=Literal(2)
        )
        right = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("BType1"),
            right=Literal(3)
        )
        expr = BinaryExpression(
            operator=BinaryOperator.OR,
            left=left,
            right=right
        )
        assert expr.operator == BinaryOperator.OR
        assert isinstance(expr.left, BinaryExpression)
        assert isinstance(expr.right, BinaryExpression)
    
    def test_and_expression(self):
        """Should create AND logical expression."""
        left = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("BType1"),
            right=Literal(2)
        )
        right = BinaryExpression(
            operator=BinaryOperator.GREATER_EQUAL,
            left=VariableReference("NumJob"),
            right=Literal(2)
        )
        expr = BinaryExpression(
            operator=BinaryOperator.AND,
            left=left,
            right=right
        )
        assert expr.operator == BinaryOperator.AND
    
    def test_comparison_operators(self):
        """Should support all comparison operators."""
        operators = [
            BinaryOperator.EQUALS,
            BinaryOperator.NOT_EQUALS,
            BinaryOperator.GREATER_THAN,
            BinaryOperator.GREATER_EQUAL,
            BinaryOperator.LESS_THAN,
            BinaryOperator.LESS_EQUAL,
        ]
        for op in operators:
            expr = BinaryExpression(
                operator=op,
                left=VariableReference("X"),
                right=Literal(1)
            )
            assert expr.operator == op
    
    def test_nested_expressions(self):
        """Should support deeply nested expressions."""
        # (BType1 >= 1 AND BType1 <= 5) OR BType1 == -8
        inner_and = BinaryExpression(
            operator=BinaryOperator.AND,
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
        expr = BinaryExpression(
            operator=BinaryOperator.OR,
            left=inner_and,
            right=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("BType1"),
                right=Literal(-8)
            )
        )
        assert expr.operator == BinaryOperator.OR
        assert isinstance(expr.left, BinaryExpression)
    
    def test_binary_expression_immutable(self):
        """Binary expressions should be immutable."""
        expr = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("X"),
            right=Literal(1)
        )
        with pytest.raises(AttributeError):
            expr.operator = BinaryOperator.OR


class TestUnaryExpression:
    """Test unary expressions like NOT."""
    
    def test_not_expression(self):
        """Should create NOT expression."""
        operand = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("Wrking"),
            right=Literal(1)
        )
        expr = UnaryExpression(
            operator=UnaryOperator.NOT,
            operand=operand
        )
        assert expr.operator == UnaryOperator.NOT
        assert isinstance(expr.operand, BinaryExpression)
    
    def test_not_of_variable(self):
        """Should allow NOT of a simple variable."""
        expr = UnaryExpression(
            operator=UnaryOperator.NOT,
            operand=VariableReference("HasJob")
        )
        assert expr.operator == UnaryOperator.NOT


class TestExpressionComposition:
    """Test complex expression building (MVP routing example)."""
    
    def test_jobs_routing_guard(self):
        """
        Test: Route to BDirNI2 if:
            NumJob >= 2 AND (BType2 == 2 OR BType2 == 3)
        
        This is from the example_survey.csv BDirNI2 routing.
        """
        # BType2 == 2 OR BType2 == 3
        btype_condition = BinaryExpression(
            operator=BinaryOperator.OR,
            left=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("BType2"),
                right=Literal(2)
            ),
            right=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("BType2"),
                right=Literal(3)
            )
        )
        
        # NumJob >= 2 AND (BType2 == 2 OR BType2 == 3)
        full_guard = BinaryExpression(
            operator=BinaryOperator.AND,
            left=BinaryExpression(
                operator=BinaryOperator.GREATER_EQUAL,
                left=VariableReference("NumJob"),
                right=Literal(2)
            ),
            right=btype_condition
        )
        
        assert full_guard.operator == BinaryOperator.AND
        assert isinstance(full_guard.left, BinaryExpression)
        assert isinstance(full_guard.right, BinaryExpression)
    
    def test_validation_range(self):
        """
        Test validation: (BType1 >= 1 AND BType1 <= 5) OR BType1 == -8
        
        This is from example_survey.csv BType1 validation.
        """
        # BType1 >= 1 AND BType1 <= 5
        range_check = BinaryExpression(
            operator=BinaryOperator.AND,
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
        
        # ... OR BType1 == -8
        validation = BinaryExpression(
            operator=BinaryOperator.OR,
            left=range_check,
            right=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("BType1"),
                right=Literal(-8)
            )
        )
        
        assert validation.operator == BinaryOperator.OR
