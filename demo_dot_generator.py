#!/usr/bin/env python3
"""
Demo: Generate Graphviz DOT diagrams from survey.

Shows all three visualization modes (SIMPLE, DETAILED, MANAGEMENT).
"""

from cslm.examples import build_example_job_survey
from cslm.backends import generate_dot, save_dot_file, DotMode


def main():
    # Build example survey
    survey = build_example_job_survey(job_count=3)
    
    print("=" * 80)
    print("DOT GENERATOR DEMO")
    print("=" * 80)
    
    # Generate in each mode
    modes = [DotMode.SIMPLE, DotMode.DETAILED, DotMode.MANAGEMENT]
    
    for mode in modes:
        print(f"\n{mode.value.upper()} MODE:")
        print("-" * 80)
        
        dot_output = generate_dot(survey, mode=mode)
        print(dot_output)
        
        # Save to file
        filename = f"survey_{mode.value}.dot"
        save_dot_file(survey, filename, mode=mode)
        print(f"\nSaved to: {filename}")
    
    print("\n" + "=" * 80)
    print("To visualize the diagrams:")
    print("  dot -Tpng survey_simple.dot -o survey_simple.png")
    print("  dot -Tpng survey_detailed.dot -o survey_detailed.png")
    print("  dot -Tpng survey_management.dot -o survey_management.png")
    print("=" * 80)


if __name__ == "__main__":
    main()
