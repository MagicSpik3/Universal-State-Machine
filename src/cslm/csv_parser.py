"""
CSV Parser for CSLM (Layer 1: Raw Input → Canonical Survey Logic Model).

Converts SPSS/survey CSV format to CSLM Survey objects.

CSV Format:
    variable, question, route, valid_response, multi, max_choices, apply_from
    
Syntax Notes:
    - SPSS-like operators: & (AND), | (OR), == (EQUALS)
    - Route column = entry_guard for the state
    - Transitions are inferred from guard patterns
"""

import csv
import re
import warnings
from typing import Dict, List, Set, Optional, Union
from io import StringIO
from dataclasses import dataclass, field

from cslm.model import Survey, State, Transition, Variable, VersionRange, Block
from cslm.expressions import (
    Expression,
    BinaryExpression,
    BinaryOperator,
    VariableReference,
    Literal,
    UnaryExpression,
    UnaryOperator,
    FunctionCall,
)


class CSVParseError(Exception):
    """Raised when CSV parsing fails."""
    pass


def normalize_expression_syntax(expr_str: str) -> Expression:
    """
    Convert SPSS-like syntax to our AST.
    
    Converts:
        & → AND
        | → OR
        ! → NOT
        == → EQUALS (already compatible)
        != → NOT_EQUALS
        < → LESS_THAN
        > → GREATER_THAN
        <= → LESS_EQUAL
        >= → GREATER_EQUAL
    
    Args:
        expr_str: Expression in SPSS syntax
    
    Returns:
        Expression AST
    
    Raises:
        CSVParseError: If syntax is invalid
    """
    if not expr_str or expr_str.strip() == "":
        return None
    
    # Normalize whitespace and newlines
    expr_str = expr_str.strip()
    expr_str = re.sub(r'\s+', ' ', expr_str)  # Collapse multiple spaces
    
    # Replace & with AND, | with OR, ! with NOT (carefully to preserve == and !=)
    # Use word boundaries or lookahead/lookbehind to avoid mangling == and != operators
    expr_str = re.sub(r'(?<!=)&(?!=)', ' AND ', expr_str)  # & not preceded/followed by =
    expr_str = re.sub(r'(?<!=)\|(?!=)', ' OR ', expr_str)   # | not preceded/followed by =
    expr_str = re.sub(r'!(?!=)', ' NOT ', expr_str)  # ! not followed by = (to preserve !=)
    expr_str = re.sub(r'(?<![\!<>=])=(?![\!<>=])', ' == ', expr_str)  # = not part of == != <= >=
    
    try:
        # Parse the normalized expression using our tokenizer
        tokens = _tokenize(expr_str)
        ast, remaining = _parse_and_expression(tokens, 0)
        
        if remaining < len(tokens):
            raise CSVParseError(f"Unexpected tokens after parsing: {tokens[remaining:]}")
        
        return ast
    except Exception as e:
        raise CSVParseError(f"Failed to parse expression '{expr_str}': {str(e)}")


def _tokenize(expr_str: str) -> List[str]:
    """Tokenize expression string."""
    # Pattern: operators, identifiers, numbers, parentheses, and dot (for function calls like is.(...))
    pattern = r'(\(|\)|AND|OR|NOT|==|!=|<=|>=|<|>|\.|[a-zA-Z_][a-zA-Z0-9_]*|-?(?:\d+(?:\.\d*)?|\.\d+))'
    tokens = re.findall(pattern, expr_str, re.IGNORECASE)
    if not tokens:
        raise CSVParseError(f"No valid tokens in expression: {expr_str}")
    return tokens


def _parse_or_expression(tokens: List[str], pos: int) -> tuple:
    """Parse OR expression."""
    left, pos = _parse_comparison_expression(tokens, pos)
    
    while pos < len(tokens) and tokens[pos].upper() == 'OR':
        pos += 1
        right, pos = _parse_comparison_expression(tokens, pos)
        left = BinaryExpression(BinaryOperator.OR, left, right)
    
    return left, pos


def _parse_and_expression(tokens: List[str], pos: int) -> tuple:
    """Parse AND expression (lowest precedence)."""
    left, pos = _parse_or_expression(tokens, pos)
    
    while pos < len(tokens) and tokens[pos].upper() == 'AND':
        pos += 1
        right, pos = _parse_or_expression(tokens, pos)
        left = BinaryExpression(BinaryOperator.AND, left, right)
    
    return left, pos


def _parse_comparison_expression(tokens: List[str], pos: int) -> tuple:
    """Parse comparison expression (==, !=, <, >, <=, >=)."""
    left, pos = _parse_unary_expression(tokens, pos)
    
    if pos < len(tokens) and tokens[pos] in ['==', '!=', '<', '>', '<=', '>=']:
        op_str = tokens[pos]
        pos += 1
        right, pos = _parse_unary_expression(tokens, pos)
        
        op_map = {
            '==': BinaryOperator.EQUALS,
            '!=': BinaryOperator.NOT_EQUALS,
            '<': BinaryOperator.LESS_THAN,
            '>': BinaryOperator.GREATER_THAN,
            '<=': BinaryOperator.LESS_EQUAL,
            '>=': BinaryOperator.GREATER_EQUAL,
        }
        
        left = BinaryExpression(op_map[op_str], left, right)
    
    return left, pos


def _parse_unary_expression(tokens: List[str], pos: int) -> tuple:
    """Parse unary expression (NOT)."""
    if pos < len(tokens) and tokens[pos].upper() == 'NOT':
        pos += 1
        expr, pos = _parse_primary_expression(tokens, pos)
        return UnaryExpression(UnaryOperator.NOT, expr), pos
    
    return _parse_primary_expression(tokens, pos)


def _parse_primary_expression(tokens: List[str], pos: int) -> tuple:
    """Parse primary expression (literal, variable, function call, or parenthesized)."""
    if pos >= len(tokens):
        raise CSVParseError("Unexpected end of expression")
    
    token = tokens[pos]
    
    # Parenthesized expression
    if token == '(':
        pos += 1
        expr, pos = _parse_and_expression(tokens, pos)
        if pos >= len(tokens) or tokens[pos] != ')':
            raise CSVParseError("Missing closing parenthesis")
        pos += 1
        return expr, pos
    
    # Numeric literal
    if re.match(r'^-?(\d+(\.\d*)?|\.\d+)$', token):
        return Literal(float(token)), pos + 1
    
    # Variable reference or function call (identifier)
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', token):
        var_name = token
        next_pos = pos + 1
        
        # Check for function call pattern: identifier.(...) like is.(variable)
        if (next_pos < len(tokens) and tokens[next_pos] == '.' and
            next_pos + 1 < len(tokens) and tokens[next_pos + 1] == '('):
            # This is a function call
            func_name = var_name
            next_pos += 2  # Skip the '.' and '('
            
            # Parse function arguments
            arguments = []
            
            # Check if the next token is a closing paren (no arguments)
            if next_pos < len(tokens) and tokens[next_pos] != ')':
                # Parse comma-separated arguments
                while True:
                    arg, next_pos = _parse_or_expression(tokens, next_pos)
                    arguments.append(arg)
                    
                    if next_pos >= len(tokens):
                        raise CSVParseError("Missing closing parenthesis in function call")
                    
                    if tokens[next_pos] == ')':
                        break
                    elif tokens[next_pos] == ',':
                        next_pos += 1  # Skip comma, continue parsing
                    else:
                        raise CSVParseError(f"Expected ',' or ')' in function call, got '{tokens[next_pos]}'")
            
            if next_pos >= len(tokens) or tokens[next_pos] != ')':
                raise CSVParseError("Missing closing parenthesis in function call")
            
            return FunctionCall(func_name, arguments), next_pos + 1
        else:
            # Regular variable reference
            return VariableReference(var_name), next_pos
    
    raise CSVParseError(f"Unexpected token: {token}")


@dataclass
class CSVRow:
    """Parsed CSV row."""
    variable: str
    question: str
    route: str  # Will become entry_guard
    valid_response: str  # Will become validation
    apply_from: Optional[int] = None
    multi: Optional[str] = None
    max_choices: Optional[int] = None


def _parse_csv_rows(csv_content: str) -> List[CSVRow]:
    """Parse CSV content into structured rows."""
    reader = csv.DictReader(StringIO(csv_content))
    
    if reader.fieldnames is None:
        raise CSVParseError("CSV is empty")
    
    required_columns = ['variable', 'question', 'route', 'valid_response']
    missing = [col for col in required_columns if col not in reader.fieldnames]
    if missing:
        raise CSVParseError(f"Missing required columns: {missing}")
    
    rows = []
    for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
        try:
            csv_row = CSVRow(
                variable=row.get('variable', '').strip(),
                question=row.get('question', '').strip(),
                route=row.get('route', '').strip(),
                valid_response=row.get('valid_response', '').strip(),
                apply_from=int(row.get('apply_from', '')) if row.get('apply_from', '').strip() else None,
                multi=row.get('multi', '').strip() or None,
                max_choices=int(row.get('max_choices', '')) if row.get('max_choices', '').strip() else None,
            )
            rows.append(csv_row)
        except (ValueError, KeyError) as e:
            raise CSVParseError(f"Error parsing row {row_num}: {str(e)}")
    
    return rows


def _extract_variables_from_expression(expr: Expression) -> Set[str]:
    """Extract all variable names from an expression."""
    if expr is None:
        return set()
    
    if isinstance(expr, VariableReference):
        return {expr.name}
    elif isinstance(expr, BinaryExpression):
        return _extract_variables_from_expression(expr.left) | _extract_variables_from_expression(expr.right)
    elif isinstance(expr, UnaryExpression):
        return _extract_variables_from_expression(expr.expr)
    
    return set()


def _extract_all_variables(rows: List[CSVRow]) -> Set[str]:
    """Extract all variable references from all expressions in CSV."""
    all_vars = set()
    
    for row in rows:
        # The variable itself
        all_vars.add(row.variable)
        
        # Variables in guard
        if row.route:
            try:
                expr = normalize_expression_syntax(row.route)
                all_vars.update(_extract_variables_from_expression(expr))
            except:
                pass
        
        # Variables in validation
        if row.valid_response:
            try:
                expr = normalize_expression_syntax(row.valid_response)
                all_vars.update(_extract_variables_from_expression(expr))
            except:
                pass
    
    return all_vars


def _infer_transitions(rows: List[CSVRow]) -> List[dict]:
    """
    Infer transitions from entry guard patterns.
    
    For each state with an entry_guard, find which previous states could lead to it.
    Look for variable references in the guard that match previous state IDs.
    """
    transitions = []
    var_to_row = {row.variable: row for row in rows}
    
    for row in rows:
        if not row.route:
            continue
        
        # Parse the guard to extract variable references
        try:
            guard_expr = normalize_expression_syntax(row.route)
            guard_vars = _extract_variables_from_expression(guard_expr)
        except:
            continue
        
        # For each variable in the guard that matches a previous question
        for var_ref in guard_vars:
            if var_ref in var_to_row and var_ref != row.variable:
                # Create a transition from var_ref to row.variable
                transitions.append({
                    'from': var_ref,
                    'to': row.variable,
                    'guard': guard_expr
                })
    
    return transitions


def parse_csv_string(csv_content: str, survey_name: str = "CSVSurvey") -> Survey:
    """
    Parse CSV content into a Survey object.
    
    Args:
        csv_content: CSV as string
        survey_name: Name for the survey
    
    Returns:
        Survey object with states, variables, transitions
    
    Raises:
        CSVParseError: If parsing fails
    """
    rows = _parse_csv_rows(csv_content)
    
    if not rows:
        return Survey(name=survey_name)
    
    # Check for duplicates
    var_names = [row.variable for row in rows]
    if len(var_names) != len(set(var_names)):
        duplicates = [name for name in var_names if var_names.count(name) > 1]
        raise CSVParseError(f"Duplicate variable names: {set(duplicates)}")
    
    # Extract all variables
    all_var_names = _extract_all_variables(rows)
    
    # Create Variable objects
    variables = [
        Variable(name=name) for name in sorted(all_var_names)
    ]
    
    # Create State objects
    states = []
    for row in rows:
        entry_guard = None
        if row.route:
            try:
                entry_guard = normalize_expression_syntax(row.route)
            except CSVParseError as e:
                warnings.warn(f"Invalid route for {row.variable}: {str(e)}", UserWarning)
        
        validation = None
        if row.valid_response:
            try:
                validation = normalize_expression_syntax(row.valid_response)
            except CSVParseError as e:
                warnings.warn(f"Invalid validation for {row.variable}: {str(e)}", UserWarning)
        
        version = None
        if row.apply_from:
            version = VersionRange(apply_from=row.apply_from)
        
        state = State(
            id=row.variable,
            text=row.question,
            entry_guard=entry_guard,
            validation=validation,
            version=version,
        )
        states.append(state)
    
    # Infer transitions
    transitions = []
    inferred = _infer_transitions(rows)
    for inf in inferred:
        transitions.append(Transition(
            from_state=inf['from'],
            to_state=inf['to'],
            guard=inf['guard']
        ))
    
    # Create survey
    survey = Survey(
        name=survey_name,
        variables=variables,
        states=states,
        transitions=transitions,
    )
    
    return survey


def parse_csv_file(filepath: str, survey_name: Optional[str] = None) -> Survey:
    """
    Parse CSV file into a Survey object.
    
    Args:
        filepath: Path to CSV file
        survey_name: Optional name for survey (defaults to filename)
    
    Returns:
        Survey object
    
    Raises:
        FileNotFoundError: If file doesn't exist
        CSVParseError: If parsing fails
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    
    if survey_name is None:
        import os
        survey_name = os.path.splitext(os.path.basename(filepath))[0]
    
    return parse_csv_string(content, survey_name=survey_name)


__all__ = [
    "parse_csv_string",
    "parse_csv_file",
    "CSVParseError",
    "normalize_expression_syntax",
]
