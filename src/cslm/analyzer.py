"""
Survey Analyzer — Early diagnostics and inventory of CSLM surveys.

This module provides lightweight analysis of Survey objects:
    - Variable usage inventory
    - Graph reachability and cycles
    - Expression complexity metrics
    - Coverage and completeness checks
    - Warning flags for implementation risk

IMPORTANT: This is Layer 3 (Analysis). It does NOT modify the survey.
It only produces read-only reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, List, Dict, Optional, Tuple
from collections import defaultdict

from cslm.model import Survey, State, Variable, Transition
from cslm.expressions import Expression, BinaryExpression, VariableReference, Literal, UnaryExpression


@dataclass
class ExpressionMetrics:
    """Metrics about a single expression tree."""
    depth: int = 0
    node_count: int = 0
    variable_references: Set[str] = field(default_factory=set)

    def add(self, other: ExpressionMetrics) -> None:
        self.depth = max(self.depth, other.depth)
        self.node_count += other.node_count
        self.variable_references.update(other.variable_references)


def _analyze_expression(expr: Expression | None) -> ExpressionMetrics:
    """Recursively analyze an expression tree."""
    if expr is None:
        return ExpressionMetrics(depth=0, node_count=0)
    
    metrics = ExpressionMetrics(node_count=1)
    
    if isinstance(expr, BinaryExpression):
        left = _analyze_expression(expr.left)
        right = _analyze_expression(expr.right)
        metrics.depth = 1 + max(left.depth, right.depth)
        metrics.node_count += left.node_count + right.node_count
        metrics.variable_references.update(left.variable_references)
        metrics.variable_references.update(right.variable_references)
    
    elif isinstance(expr, UnaryExpression):
        operand = _analyze_expression(expr.operand)
        metrics.depth = 1 + operand.depth
        metrics.node_count += operand.node_count
        metrics.variable_references.update(operand.variable_references)
    
    elif isinstance(expr, VariableReference):
        metrics.variable_references.add(expr.name)
    
    elif isinstance(expr, Literal):
        # Literals don't reference variables
        pass
    
    return metrics


def _find_cycles_dfs(graph: Dict[str, List[str]], start: str, visited: Set[str], 
                     rec_stack: Set[str], path: List[str]) -> Optional[List[str]]:
    """DFS to find a cycle starting from a node."""
    visited.add(start)
    rec_stack.add(start)
    path.append(start)
    
    for neighbor in graph.get(start, []):
        if neighbor not in visited:
            cycle = _find_cycles_dfs(graph, neighbor, visited, rec_stack, path[:])
            if cycle:
                return cycle
        elif neighbor in rec_stack:
            # Found a cycle
            cycle_start_idx = path.index(neighbor)
            return path[cycle_start_idx:] + [neighbor]
    
    rec_stack.remove(start)
    return None


@dataclass
class SurveyReport:
    """Comprehensive analysis report for a survey."""
    
    survey_name: str
    total_states: int = 0
    total_transitions: int = 0
    total_variables: int = 0
    total_blocks: int = 0
    
    # Variable usage
    variable_usage: Dict[str, int] = field(default_factory=dict)
    undefined_variables: Set[str] = field(default_factory=set)
    unused_variables: Set[str] = field(default_factory=set)
    
    # Graph properties
    entry_points: List[str] = field(default_factory=list)  # States with no incoming edges
    exit_points: List[str] = field(default_factory=list)   # States with no outgoing edges
    unreachable_states: Set[str] = field(default_factory=set)
    has_cycles: bool = False
    cycle_example: Optional[List[str]] = None
    
    # Expression complexity
    max_expression_depth: int = 0
    avg_expression_depth: float = 0.0
    total_expression_nodes: int = 0
    
    # Coverage metrics
    states_with_validation: int = 0
    states_with_entry_guard: int = 0
    states_with_version: int = 0
    validation_coverage_percent: float = 0.0
    
    # Per-state metrics
    max_transitions_per_state: int = 0
    avg_transitions_per_state: float = 0.0
    
    # Warnings and flags
    warnings: List[str] = field(default_factory=list)
    
    def add_warning(self, msg: str) -> None:
        """Add a warning to the report."""
        if msg not in self.warnings:
            self.warnings.append(msg)


def analyze_survey(survey: Survey) -> SurveyReport:
    """
    Perform comprehensive analysis of a Survey.
    
    Checks for:
    - Variable definitions and usage
    - Graph structure (reachability, cycles)
    - Expression complexity
    - Coverage (validation, guards, versioning)
    
    Returns a SurveyReport with metrics and warnings.
    """
    report = SurveyReport(survey_name=survey.name)
    
    # Basic counts
    report.total_states = len(survey.states)
    report.total_transitions = len(survey.transitions)
    report.total_variables = len(survey.variables)
    report.total_blocks = len(survey.blocks)
    
    # Build lookup tables
    state_by_id = {s.id: s for s in survey.states}
    variable_by_name = {v.name: v for v in survey.variables}
    
    # =========================================================================
    # 1. VARIABLE ANALYSIS
    # =========================================================================
    
    all_referenced_vars: Set[str] = set()
    declared_vars: Set[str] = set(variable_by_name.keys())
    
    for state in survey.states:
        # Entry guard
        if state.entry_guard:
            metrics = _analyze_expression(state.entry_guard)
            all_referenced_vars.update(metrics.variable_references)
        
        # Validation
        if state.validation:
            metrics = _analyze_expression(state.validation)
            all_referenced_vars.update(metrics.variable_references)
    
    for trans in survey.transitions:
        if trans.guard:
            metrics = _analyze_expression(trans.guard)
            all_referenced_vars.update(metrics.variable_references)
    
    # Undefined variables (referenced but not declared)
    report.undefined_variables = all_referenced_vars - declared_vars
    
    # Unused variables (declared but not referenced)
    report.unused_variables = declared_vars - all_referenced_vars
    
    # Variable usage count
    report.variable_usage = defaultdict(int)
    for var in all_referenced_vars:
        report.variable_usage[var] = 0
    
    for state in survey.states:
        if state.entry_guard:
            metrics = _analyze_expression(state.entry_guard)
            for var in metrics.variable_references:
                report.variable_usage[var] += 1
        if state.validation:
            metrics = _analyze_expression(state.validation)
            for var in metrics.variable_references:
                report.variable_usage[var] += 1
    
    for trans in survey.transitions:
        if trans.guard:
            metrics = _analyze_expression(trans.guard)
            for var in metrics.variable_references:
                report.variable_usage[var] += 1
    
    # =========================================================================
    # 2. EXPRESSION COMPLEXITY
    # =========================================================================
    
    all_depths = []
    total_nodes = 0
    
    for state in survey.states:
        if state.entry_guard:
            metrics = _analyze_expression(state.entry_guard)
            all_depths.append(metrics.depth)
            total_nodes += metrics.node_count
        if state.validation:
            metrics = _analyze_expression(state.validation)
            all_depths.append(metrics.depth)
            total_nodes += metrics.node_count
    
    for trans in survey.transitions:
        if trans.guard:
            metrics = _analyze_expression(trans.guard)
            all_depths.append(metrics.depth)
            total_nodes += metrics.node_count
    
    if all_depths:
        report.max_expression_depth = max(all_depths)
        report.avg_expression_depth = sum(all_depths) / len(all_depths)
    report.total_expression_nodes = total_nodes
    
    # =========================================================================
    # 3. COVERAGE METRICS
    # =========================================================================
    
    for state in survey.states:
        if state.validation is not None:
            report.states_with_validation += 1
        if state.entry_guard is not None:
            report.states_with_entry_guard += 1
        if state.version is not None:
            report.states_with_version += 1
    
    if report.total_states > 0:
        report.validation_coverage_percent = (report.states_with_validation / report.total_states) * 100
    
    # =========================================================================
    # 4. GRAPH STRUCTURE ANALYSIS
    # =========================================================================
    
    # Build adjacency lists
    outgoing: Dict[str, List[str]] = defaultdict(list)
    incoming: Dict[str, List[str]] = defaultdict(list)
    
    for trans in survey.transitions:
        outgoing[trans.from_state].append(trans.to_state)
        incoming[trans.to_state].append(trans.from_state)
    
    # Entry points: states reachable ONLY from START (first-level)
    report.entry_points = outgoing.get("START", [])
    
    # Exit points: states with no outgoing transitions
    for state in survey.states:
        if state.id not in outgoing:
            report.exit_points.append(state.id)
    
    # Reachability: starting from START
    reachable: Set[str] = set()
    stack = ["START"]
    while stack:
        node = stack.pop()
        if node in reachable:
            continue
        reachable.add(node)
        for neighbor in outgoing.get(node, []):
            if neighbor not in reachable:
                stack.append(neighbor)
    
    # Find unreachable states
    for state in survey.states:
        if state.id not in reachable:
            report.unreachable_states.add(state.id)
    
    # Cycle detection
    visited: Set[str] = set()
    for state_id in outgoing.keys():
        if state_id not in visited:
            cycle = _find_cycles_dfs(outgoing, state_id, visited, set(), [])
            if cycle:
                report.has_cycles = True
                report.cycle_example = cycle
                break
    
    # =========================================================================
    # 5. TRANSITION METRICS
    # =========================================================================
    
    transitions_per_state = defaultdict(int)
    for trans in survey.transitions:
        transitions_per_state[trans.from_state] += 1
    
    if transitions_per_state:
        report.max_transitions_per_state = max(transitions_per_state.values())
        report.avg_transitions_per_state = sum(transitions_per_state.values()) / len(transitions_per_state)
    
    # =========================================================================
    # 6. WARNING FLAGS
    # =========================================================================
    
    if report.undefined_variables:
        report.add_warning(
            f"Undefined variable references: {', '.join(sorted(report.undefined_variables))}"
        )
    
    if report.unused_variables:
        report.add_warning(
            f"Unused variables: {', '.join(sorted(report.unused_variables))}"
        )
    
    if report.unreachable_states:
        report.add_warning(
            f"Unreachable states: {', '.join(sorted(report.unreachable_states))}"
        )
    
    if report.has_cycles:
        report.add_warning(
            f"Cycle detected: {' -> '.join(report.cycle_example)}"
        )
    
    if report.validation_coverage_percent < 50:
        report.add_warning(
            f"Low validation coverage: {report.validation_coverage_percent:.1f}% of states have validation"
        )
    
    if report.states_with_version == 0 and report.total_states > 0:
        report.add_warning(
            f"Missing version metadata: {report.total_states - report.states_with_version} states"
        )
    
    if report.max_expression_depth > 5:
        report.add_warning(
            f"High expression complexity: max depth {report.max_expression_depth}"
        )
    
    return report
