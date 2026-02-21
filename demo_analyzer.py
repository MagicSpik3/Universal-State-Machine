"""
Demo: Run analyzer on the example job survey and output the report.
"""

from cslm.examples import build_example_job_survey
from cslm.analyzer import analyze_survey
from cslm.serialization import survey_to_yaml
import json


def print_report(report):
    """Pretty-print a SurveyReport."""
    print()
    print("=" * 70)
    print(f"SURVEY ANALYSIS REPORT: {report.survey_name}")
    print("=" * 70)
    print()
    
    print("📊 BASIC METRICS")
    print(f"  Total States:          {report.total_states}")
    print(f"  Total Transitions:     {report.total_transitions}")
    print(f"  Total Variables:       {report.total_variables}")
    print(f"  Total Blocks:          {report.total_blocks}")
    print()
    
    print("📈 VARIABLE ANALYSIS")
    print(f"  Variables Referenced:  {len(report.variable_usage)}")
    print(f"  Undefined Variables:   {len(report.undefined_variables)}")
    if report.undefined_variables:
        print(f"    {report.undefined_variables}")
    print(f"  Unused Variables:      {len(report.unused_variables)}")
    if report.unused_variables:
        print(f"    {report.unused_variables}")
    print()
    
    if report.variable_usage:
        print("  Variable Usage:")
        for var, count in sorted(report.variable_usage.items()):
            print(f"    {var}: {count} reference(s)")
        print()
    
    print("🔗 GRAPH STRUCTURE")
    print(f"  Entry Points:          {report.entry_points}")
    print(f"  Exit Points:           {report.exit_points}")
    print(f"  Unreachable States:    {report.unreachable_states if report.unreachable_states else 'None'}")
    print(f"  Has Cycles:            {'YES' if report.has_cycles else 'NO'}")
    if report.has_cycles and report.cycle_example:
        print(f"    Example: {' -> '.join(report.cycle_example)}")
    print()
    
    print("📐 EXPRESSION COMPLEXITY")
    print(f"  Max Expression Depth:  {report.max_expression_depth}")
    print(f"  Avg Expression Depth:  {report.avg_expression_depth:.2f}")
    print(f"  Total Expression Nodes:{report.total_expression_nodes}")
    print()
    
    print("✅ COVERAGE METRICS")
    print(f"  States with Guard:     {report.states_with_entry_guard}/{report.total_states}")
    print(f"  States with Validation:{report.states_with_validation}/{report.total_states}")
    print(f"  Validation Coverage:   {report.validation_coverage_percent:.1f}%")
    print(f"  States with Version:   {report.states_with_version}/{report.total_states}")
    print()
    
    print("⚙️  TRANSITION METRICS")
    print(f"  Max Transitions/State: {report.max_transitions_per_state}")
    print(f"  Avg Transitions/State: {report.avg_transitions_per_state:.2f}")
    print()
    
    if report.warnings:
        print("⚠️  WARNINGS")
        for i, warning in enumerate(report.warnings, 1):
            print(f"  {i}. {warning}")
    else:
        print("✨ NO WARNINGS - Survey looks clean!")
    print()


if __name__ == "__main__":
    # Build example survey
    survey = build_example_job_survey(job_count=3, apply_from=2204)
    
    # Analyze it
    report = analyze_survey(survey)
    
    # Print report
    print_report(report)
    
    # Also save to YAML for inspection
    yaml_str = survey_to_yaml(survey)
    with open("example_survey_output.yaml", "w") as f:
        f.write(yaml_str)
    print(f"✅ Survey exported to example_survey_output.yaml")
