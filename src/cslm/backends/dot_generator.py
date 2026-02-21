"""
Graphviz DOT diagram generator for CSLM surveys.

Converts a Survey object into Graphviz DOT format for visualization.

Supports multiple modes:
    - SIMPLE: Basic state flow (no guard labels)
    - DETAILED: Full guards, validation, and metadata
    - MANAGEMENT: Hierarchical with blocks as clusters
"""

from enum import Enum
from typing import Dict, List
from cslm.model import Survey, State, Transition
from cslm.expressions import (
    Expression,
    BinaryExpression,
    VariableReference,
    Literal,
    BinaryOperator,
)


class DotMode(Enum):
    """Visualization modes for DOT output."""
    SIMPLE = "simple"          # Just state flow
    DETAILED = "detailed"      # Include guards, validation
    MANAGEMENT = "management"  # Hierarchical with blocks


def _escape_dot_string(s: str) -> str:
    """Escape special characters for DOT labels."""
    if not s:
        return '""'
    # Replace newlines with spaces or \n for wrapped text
    s = s.replace('\n', '\\n')
    # Escape backslashes first
    s = s.replace('\\', '\\\\')
    # Escape quotes
    s = s.replace('"', '\\"')
    return f'"{s}"'


def _escape_dot_id(identifier: str) -> str:
    """Escape/quote an identifier for DOT."""
    # If it starts with a digit or contains special chars, quote it
    if identifier[0].isdigit() or not identifier.replace('_', '').isalpha():
        return f'"{identifier}"'
    return identifier


def _expr_to_dot_label(expr: Expression | None) -> str:
    """Convert an expression to a readable DOT label."""
    if expr is None:
        return ""
    
    if isinstance(expr, BinaryExpression):
        left = _expr_to_dot_label(expr.left)
        right = _expr_to_dot_label(expr.right)
        op_map = {
            BinaryOperator.AND: "AND",
            BinaryOperator.OR: "OR",
            BinaryOperator.EQUALS: "==",
            BinaryOperator.NOT_EQUALS: "!=",
            BinaryOperator.GREATER_THAN: ">",
            BinaryOperator.GREATER_EQUAL: ">=",
            BinaryOperator.LESS_THAN: "<",
            BinaryOperator.LESS_EQUAL: "<=",
        }
        op_str = op_map.get(expr.operator, str(expr.operator.value))
        return f"({left} {op_str} {right})"
    
    elif isinstance(expr, VariableReference):
        return expr.name
    
    elif isinstance(expr, Literal):
        return str(expr.value)
    
    return "?"


def generate_dot(survey: Survey, mode: DotMode = DotMode.SIMPLE) -> str:
    """
    Generate Graphviz DOT format for a survey.
    
    Args:
        survey: Survey object to visualize
        mode: Visualization mode (SIMPLE, DETAILED, MANAGEMENT)
    
    Returns:
        String containing DOT graph definition
    """
    lines = []
    
    # Header
    lines.append("digraph survey {")
    lines.append("  rankdir=LR;")
    lines.append("  node [shape=box, style=filled, fillcolor=lightblue];")
    
    if mode == DotMode.MANAGEMENT:
        lines.append("  edge [style=solid];")
    
    # =========================================================================
    # NODES
    # =========================================================================
    
    # Fake START node
    lines.append('  START [shape=ellipse, fillcolor=lightgreen, label="START"];')
    
    # Real states
    state_by_id: Dict[str, State] = {s.id: s for s in survey.states}
    
    for state in survey.states:
        state_id = _escape_dot_id(state.id)
        label = state.text or state.id
        
        if mode == DotMode.DETAILED:
            # Add metadata to label
            info = []
            if state.entry_guard:
                guard_str = _expr_to_dot_label(state.entry_guard)
                info.append(f"Guard: {guard_str}")
            if state.validation:
                val_str = _expr_to_dot_label(state.validation)
                info.append(f"Valid: {val_str}")
            if state.version:
                if state.version.apply_from:
                    info.append(f"From: {state.version.apply_from}")
            
            if info:
                label = f"{label}\\n({'\\n'.join(info)})"
        
        label_str = _escape_dot_string(label)
        lines.append(f'  {state_id} [label={label_str}];')
    
    # =========================================================================
    # EDGES (TRANSITIONS)
    # =========================================================================
    
    for trans in survey.transitions:
        from_id = _escape_dot_id(trans.from_state)
        to_id = _escape_dot_id(trans.to_state)
        
        edge_attr = ""
        
        if trans.guard and mode == DotMode.DETAILED:
            guard_label = _expr_to_dot_label(trans.guard)
            # Shorten for readability
            if len(guard_label) > 40:
                guard_label = guard_label[:37] + "..."
            edge_attr = f' [label={_escape_dot_string(guard_label)}]'
        
        lines.append(f"  {from_id} -> {to_id}{edge_attr};")
    
    # =========================================================================
    # BLOCKS (MANAGEMENT MODE)
    # =========================================================================
    
    if mode == DotMode.MANAGEMENT and survey.blocks:
        # Group states by block
        states_by_block: Dict[str, List[str]] = {}
        for state in survey.states:
            if state.block:
                if state.block not in states_by_block:
                    states_by_block[state.block] = []
                states_by_block[state.block].append(state.id)
        
        # Create subgraph for each block
        for block_name, state_ids in states_by_block.items():
            lines.append(f'  subgraph "cluster_{block_name}" {{')
            lines.append(f'    label={_escape_dot_string(block_name)};')
            lines.append('    style=filled;')
            lines.append('    color=lightgrey;')
            for state_id in state_ids:
                quoted_id = _escape_dot_id(state_id)
                lines.append(f"    {quoted_id};")
            lines.append("  }")
    
    # Footer
    lines.append("}")
    
    return "\n".join(lines)


def save_dot_file(survey: Survey, filename: str, mode: DotMode = DotMode.SIMPLE) -> None:
    """
    Generate DOT and save to file.
    
    Args:
        survey: Survey to visualize
        filename: Output file path (.dot extension recommended)
        mode: Visualization mode
    """
    dot = generate_dot(survey, mode=mode)
    with open(filename, 'w') as f:
        f.write(dot)


__all__ = ["DotMode", "generate_dot", "save_dot_file"]
