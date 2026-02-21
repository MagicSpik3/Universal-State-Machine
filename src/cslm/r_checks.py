"""
R Checks cross-validation and lightweight refactoring helpers.

Reads CSV files containing R code snippets (checks), extracts variable
dependencies and validates them against a CSLM Survey object.

Also contains a tiny heuristic-based refactor suggester that recognizes
the common pattern you showed (case_when -> group_by/summarize/join/filter)
and suggests a simplified pipeline using `add_count` + `filter`.
"""
from dataclasses import dataclass
from typing import List, Set, Dict, Optional
import csv
import re

from cslm.model import Survey


_IDENTIFIER_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
_DOLLAR_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


@dataclass
class RCheck:
    name: str
    code: str
    declared_variables: List[str]
    parsed_variables: Set[str]


def parse_r_checks(csv_path: str) -> List[RCheck]:
    """Read R checks CSV and return list of RCheck objects.

    Expects CSV with at least columns: `Check_name`, `Check_code`, `Variables`.
    The `Variables` cell is usually a comma-separated list of variable names.
    """
    checks: List[RCheck] = []
    with open(csv_path, newline='') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get('Check_name') or row.get('check_name') or ''
            code = row.get('Check_code') or row.get('check_code') or ''
            vars_cell = row.get('Variables') or row.get('variables') or ''
            declared = [v.strip() for v in vars_cell.split(',') if v.strip()]
            parsed = extract_variables_from_r_code(code, additional=declared)
            checks.append(RCheck(name=name.strip(), code=code, declared_variables=declared, parsed_variables=parsed))
    return checks


def extract_variables_from_r_code(code: str, additional: Optional[List[str]] = None) -> Set[str]:
    """Extract likely variable/column names from an R code snippet.

    Strategy:
    - Capture identifiers used with `$` (df$col)
    - Capture bare identifiers that match common variable names (heuristic)
    - Use `additional` as a whitelist to ensure we include variables listed in CSV
    """
    if not code:
        return set()

    found: Set[str] = set()

    # Dollar-style references: df$col
    for m in _DOLLAR_RE.finditer(code):
        found.add(m.group(1))

    # All identifiers: filter out R keywords and function names heuristically
    for m in _IDENTIFIER_RE.finditer(code):
        ident = m.group(1)
        # heuristics: skip obvious function/library names and tidytable tokens
        if ident.lower() in {
            'tidytable', 'filter', 'mutate', 'case_when', 'summarize', 'summarise',
            'group_by', 'left_join', 'bind_rows', 'anova', 'ifelse', 'true', 'false',
            'na', 'as', 'tidyverse', 'library', 'select', 'arrange', 'add_count',
            'count', 'df', 'check_data', 'df1'
        }:
            continue
        # skip numeric-looking tokens
        if ident.isdigit():
            continue
        found.add(ident)

    # Ensure declared variables are included (the CSV may be more authoritative)
    if additional:
        for v in additional:
            if v:
                found.add(v)

    return found


def cross_validate_r_checks(survey: Survey, r_checks_csv_path: str) -> Dict[str, Dict]:
    """Cross-validate R checks CSV against a CSLM Survey.

    Returns a dict keyed by check name containing:
      - declared_variables: list
      - parsed_variables: set
      - missing_in_survey: parsed_variables - survey.variable_names
      - ok: bool (no missing variables)
      - suggestion: optional refactor suggestion (if detected)
    """
    checks = parse_r_checks(r_checks_csv_path)
    survey_vars = {v.name for v in (survey.variables or [])}
    report: Dict[str, Dict] = {}

    for chk in checks:
        missing = set()
        for v in chk.parsed_variables:
            if v not in survey_vars:
                missing.add(v)

        suggestion = suggest_refactor_for_check(chk)

        report[chk.name or '<unnamed>'] = {
            'declared_variables': chk.declared_variables,
            'parsed_variables': sorted(list(chk.parsed_variables)),
            'missing_in_survey': sorted(list(missing)),
            'ok': len(missing) == 0,
            'suggestion': suggestion,
        }

    return report


def suggest_refactor_for_check(check: RCheck) -> Optional[str]:
    """Return a suggested refactor for simple patterns, or None.

    Currently implements a single heuristic: detect the 4-step pattern
    you showed (mutate case_when -> group_by + summarize -> left_join -> filter)
    and suggest a compact `add_count(...) |> filter(...)` pipeline.
    """
    code = check.code or ''
    low = code.lower()

    if 'case_when' in low and 'group_by' in low and 'summarize' in low and 'left_join' in low and 'filter(' in low:
        # attempt to find the group key and the field used for case_when
        # naive extraction: look for `group_by(<key>)` and `case_when( <var> != -9 ~ 1` pattern
        key_match = re.search(r'group_by\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)', code, re.IGNORECASE)
        case_var_match = re.search(r'case_when\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*!=', code, re.IGNORECASE)
        filter_var_match = re.search(r'filter\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*>\s*1', code, re.IGNORECASE)

        if key_match and case_var_match and filter_var_match:
            key = key_match.group(1)
            casevar = case_var_match.group(1)
            new_name = 'cbnum'
            suggestion = (
                f"# Suggested refactor (compact, dplyr-style):\n"
                f"check_data <- check_data |>\n"
                f"  add_count({key}, wt = ({casevar} != -9), name = \"{new_name}\") |>\n"
                f"  filter({new_name} > 1)\n"
            )
            return suggestion

    return None


if __name__ == '__main__':
    # simple CLI for quick inspection
    import argparse
    from cslm.csv_parser import parse_csv_file

    parser = argparse.ArgumentParser(description='Cross-validate R checks against CSLM survey')
    parser.add_argument('survey_csv', help='Path to survey CSV (will be parsed into CSLM)')
    parser.add_argument('r_checks_csv', help='Path to R_code_embedded.csv')
    args = parser.parse_args()

    survey = parse_csv_file(args.survey_csv)
    report = cross_validate_r_checks(survey, args.r_checks_csv)

    print('R Checks cross-validation report:')
    for name, info in report.items():
        print('\nCheck:', name)
        print(' Declared vars:', ','.join(info['declared_variables']) if info['declared_variables'] else '(none)')
        print(' Parsed vars :', ','.join(info['parsed_variables']))
        if info['missing_in_survey']:
            print(' Missing in survey:', ','.join(info['missing_in_survey']))
        else:
            print(' All referenced variables present in survey')
        if info['suggestion']:
            print('\n Suggestion:')
            print(info['suggestion'])
