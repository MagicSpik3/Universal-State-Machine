"""
Expression System for CSLM

All survey logic conditions (routing guards, validation constraints)
are represented as Abstract Syntax Trees (ASTs), never as strings.

This ensures:
    - Type safety
    - Language independence
    - Serialization capability
    - Composability for analysis

ARCHITECTURAL RULE:
    No raw strings or code fragments in CSLM.
    All logic must be AST-based.
"""

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Union


class Expression(ABC):
    """
    Base class for all AST expressions.
    
    This is intentionally minimal.
    It exists to provide type-safety for the expression hierarchy.
    
    DO NOT:
        - Add evaluation logic here (belongs in interpreter layer)
        - Add string representations (belongs in backends)
        - Add simplification logic (belongs in analysis layer)
    
    This class is structure only.
    """
    pass


class BinaryOperator(Enum):
    """
    Binary operators supported in canonical expressions.
    
    Keep this minimal. Every operator here must be:
        - Meaningful in survey logic context
        - Language-independent
        - Unambiguous
    """

    # Logical operators
    AND = "AND"
    OR = "OR"
    
    # Comparison operators
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    LESS_THAN = "<"
    LESS_EQUAL = "<="


@dataclass(frozen=True)
class BinaryExpression(Expression):
    """
    Represents a binary logical or comparison expression.
    
    Example:
        (BType1 == 2 OR BType1 == 3)
    
    Becomes:
        BinaryExpression(
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
    
    Properties:
        operator: BinaryOperator enum
        left: Left operand (Expression)
        right: Right operand (Expression)
    
    IMPORTANT:
        This object is immutable (frozen=True).
        It contains structure only.
        It does NOT evaluate itself.
    """

    operator: BinaryOperator
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class VariableReference(Expression):
    """
    References a survey variable.
    
    Examples:
        - BType1
        - NumJob
        - Wrking
        - BDirNI[2]  (parameterized reference)
    
    Properties:
        name: Variable identifier
    
    IMPORTANT:
        This object does NOT validate variable existence.
        Validation belongs in analysis layer.
        
        This is just a name reference.
    """

    name: str


@dataclass(frozen=True)
class Literal(Expression):
    """
    Represents a literal constant value.
    
    Examples:
        - 1
        - -8
        - "Yes"
        - True
    
    Properties:
        value: The literal value (int, float, str, bool)
    
    IMPORTANT:
        We intentionally allow Union types here.
        Type validation and semantic rules belong elsewhere.
    """

    value: Union[int, float, str, bool]


class UnaryOperator(Enum):
    """
    Unary operators (for future use if needed).
    
    Currently minimal to keep MVP simple.
    """
    NOT = "NOT"


@dataclass(frozen=True)
class UnaryExpression(Expression):
    """
    Represents a unary operation (e.g., NOT).
    
    Example:
        NOT (Wrking == 1)
    
    Becomes:
        UnaryExpression(
            operator=UnaryOperator.NOT,
            operand=BinaryExpression(...)
        )
    """

    operator: UnaryOperator
    operand: Expression
