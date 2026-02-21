#!/usr/bin/env python3
"""
Complete Pipeline Demo: CSV → CSLM → Diagrams → Analysis

Shows the full workflow:
1. Parse CSV survey definition
2. Convert to Canonical Survey Logic Model
3. Analyze the survey
4. Generate Graphviz diagrams
"""

from cslm.csv_parser import parse_csv_file
from cslm.analyzer import analyze_survey
from cslm.backends import generate_dot, save_dot_file, DotMode


def main():
    csv_path = "/home/jonny/git/Universal-State-Machine/example_survey.csv"
    
    print("=" * 80)
    print("COMPLETE PIPELINE DEMO: CSV → CSLM → Analysis → Diagrams")
    print("=" * 80)
    
    # =========================================================================
    # STEP 1: Parse CSV
    # =========================================================================
    print("\n1. PARSING CSV...")
    survey = parse_csv_file(csv_path, survey_name="ONS_Employment_Survey")
    print(f"   ✓ Loaded survey: {survey.name}")
    print(f"   ✓ States: {len(survey.states)}")
    print(f"   ✓ Variables: {len(survey.variables)}")
    print(f"   ✓ Transitions: {len(survey.transitions)}")
    
    # =========================================================================
    # STEP 2: Analyze Survey
    # =========================================================================
    print("\n2. ANALYZING SURVEY...")
    report = analyze_survey(survey)
    print(f"   ✓ Entry points: {report.entry_points}")
    print(f"   ✓ Exit points: {report.exit_points}")
    print(f"   ✓ Undefined variables: {report.undefined_variables}")
    print(f"   ✓ Unreachable states: {report.unreachable_states}")
    print(f"   ✓ Cycles detected: {report.has_cycles}")
    
    if report.warnings:
        print(f"\n   Warnings ({len(report.warnings)}):")
        for warning in report.warnings[:5]:  # Show first 5
            print(f"      - {warning}")
        if len(report.warnings) > 5:
            print(f"      ... and {len(report.warnings) - 5} more")
    
    # =========================================================================
    # STEP 3: Generate Diagrams
    # =========================================================================
    print("\n3. GENERATING DIAGRAMS...")
    
    modes = [DotMode.SIMPLE, DotMode.DETAILED, DotMode.MANAGEMENT]
    for mode in modes:
        filename = f"survey_{mode.value}.dot"
        save_dot_file(survey, filename, mode=mode)
        print(f"   ✓ Saved {filename}")
    
    # =========================================================================
    # STEP 4: Sample Output
    # =========================================================================
    print("\n4. SAMPLE SIMPLE MODE OUTPUT:")
    print("-" * 80)
    dot_output = generate_dot(survey, mode=DotMode.SIMPLE)
    lines = dot_output.split('\n')
    for line in lines[:20]:
        print(f"   {line}")
    if len(lines) > 20:
        print(f"   ... ({len(lines) - 20} more lines)")
    
    # =========================================================================
    # STEP 5: Statistics
    # =========================================================================
    print("\n5. STATISTICS:")
    print("-" * 80)
    print(f"   States with entry guards: {report.states_with_entry_guard}")
    print(f"   States with validation: {report.states_with_validation}")
    print(f"   Transition density: {len(survey.transitions) / max(len(survey.states), 1):.2f}")
    print(f"   Max transitions per state: {report.max_transitions_per_state}")
    print(f"   Avg transitions per state: {report.avg_transitions_per_state:.2f}")
    
    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE!")
    print("\nTo visualize the diagrams:")
    print("  dot -Tpng survey_simple.dot -o survey_simple.png")
    print("  dot -Tpng survey_detailed.dot -o survey_detailed.png")
    print("  dot -Tpng survey_management.dot -o survey_management.png")
    print("=" * 80)


if __name__ == "__main__":
    main()
