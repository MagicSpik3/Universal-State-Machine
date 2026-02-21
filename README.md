# Universal State Machine: Survey Logic Compiler Platform

A language-agnostic Survey Logic Compiler platform that represents survey behavior as a Canonical Survey Logic Model (CSLM) — a guarded state machine — from which multiple backends (R, SPSS, documentation, diagrams) can be derived.

## Status

**Phase 1 — MVP (Current) ✅**

- [x] Project structure
- [x] CSLM core model defined (Expressions, States, Transitions, Blocks, Survey)
- [x] Test suite written (TDD) — 63 tests
- [x] Basic tests passing (52 unit tests)
- [x] Serialization/deserialization (JSON/YAML round-trip) — 2 tests
- [x] Example survey instantiation (3-job PoC)
- [x] Survey Analyzer (Layer 3 diagnostics) — 11 tests
  - Variable inventory & usage
  - Reachability & cycles
  - Expression complexity metrics
  - Coverage analysis (guards, validation, versioning)

## What This Is

This is **NOT** an SPSS-to-R converter.

This is a **Survey Logic Compiler** with a canonical internal representation:

```
Raw Input (SPSS/CSV/R) 
    → Parse → CSLM (Universal State Machine)
    → Analyze/Transform (optional)
    → Generate (R / SPSS / Diagrams / Docs)
```

The CSLM is the primary artifact. Everything else is derived from it.

## Architecture Layers

```
Layer 0 — Raw Inputs (SPSS, CSV, R, Excel, ...)
Layer 1 — Parsing & Normalization (AST builders)
Layer 2 — Canonical Survey Logic Model (CSLM) ← TRUTH
Layer 3 — Analysis & Transformation (optional)
Layer 4 — Output Backends (R, SPSS, Diagrams, Docs)
```

## Key Architectural Invariants

1. **CSLM contains zero target-language code** (no R, no SPSS, no strings)
2. **All logic is AST-based** (never strings or code fragments)
3. **Transitions are explicit** (no implicit ordering or fallthrough)
4. **Blocks are first-class objects** (handles parameterized repetition)
5. **Versioning is metadata** (not routing logic)
6. **Backends are pure functions** (consume CSLM unchanged)
7. **CSLM is fully serializable** (JSON/YAML lossless)

## Getting Started

### Prerequisites

- Python 3.10+
- pip or conda

### Installation (Development)

```bash
cd /home/jonny/git/Universal-State-Machine

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/cslm --cov-report=html
```

## Core Concepts

### Survey

Root container for a complete survey definition.

```python
survey = Survey(
    name="Employment Survey",
    variables=[...],
    states=[...],
    transitions=[...],
    blocks=[...],
    metadata={...}
)
```

### Variables

Named data slots.

```python
Variable(name="BType1", description="Employment type, Job 1")
```

### States

Survey question nodes in the state machine.

```python
State(
    id="BType1",
    text="Now, thinking of your job...",
    entry_guard=BinaryExpression(...),    # Condition to enter
    validation=BinaryExpression(...),     # Valid response values
    version=VersionRange(apply_from=2204) # When applies
)
```

### Transitions

Directed edges between states.

```python
Transition(
    from_state="BType1",
    to_state="BDirNI1",
    guard=BinaryExpression(...)  # Optional routing condition
)
```

### Expressions

All logic is AST-based, never strings:

```python
# (BType1 == 2 OR BType1 == 3)
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
```

### Blocks

Parameterized subgraphs for repeated structures:

```python
# JobBlock represents repeated structure for multiple jobs
Block(
    name="JobBlock",
    parameters=["job_index"],
    state_ids=["BType", "BDirNI", "BOwn", ...]
)
```

## Example: Simple Survey

```python
from cslm.model import Survey, Variable, State, Transition
from cslm.expressions import (
    BinaryExpression, BinaryOperator,
    VariableReference, Literal
)

# Define survey
survey = Survey(name="Employment Check")

# Add variable
survey.variables = [
    Variable(name="Wrking", description="Currently working")
]

# Add state
survey.states = [
    State(
        id="BType1",
        text="What type of employment?",
        entry_guard=BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("Wrking"),
            right=Literal(1)
        )
    )
]

# Add transition
survey.transitions = [
    Transition(from_state="START", to_state="BType1")
]

# Survey is now canonical and language-independent
```

## Development Roadmap

### Phase 1 (MVP) — Complete ✅
- [x] Core CSLM model structure
- [x] TDD test suite (63 tests, all passing)
- [x] JSON/YAML serialization + round-trip validation
- [x] Example survey builder (3-job employment pattern)
- [x] Survey analyzer with diagnostics and warnings

### Phase 2
- [ ] SPSS syntax parser
- [ ] R code generation backend
- [ ] Diagram generation (Graphviz DOT)
- [ ] Human documentation backend

### Phase 3
- [ ] Expression simplification (analysis layer)
- [ ] Block expansion analysis
- [ ] Dead state detection
- [ ] Dependency analysis

### Phase 4
- [ ] Multi-backend support (SPSS generator)
- [ ] Version/wave management
- [ ] Change impact analysis
- [ ] Formal validation rules

## Project Structure

```
Universal-State-Machine/
├── src/cslm/                    # Core model (Layer 2)
│   ├── __init__.py
│   ├── expressions.py           # AST expression system
│   └── model.py                 # Survey/State/Transition/Block
├── tests/                       # TDD test suite
│   ├── test_expressions.py
│   ├── test_model.py
│   ├── test_serialization.py    # (coming)
│   └── test_parser.py           # (coming)
├── src/cslm/parsers/            # Layer 1 (coming)
│   ├── csv_parser.py
│   └── spss_parser.py
├── src/cslm/analysis/           # Layer 3 (coming)
│   └── analyzer.py
├── src/cslm/backends/           # Layer 4 (coming)
│   ├── r_generator.py
│   ├── spss_generator.py
│   ├── diagram_generator.py
│   └── doc_generator.py
├── pyproject.toml
├── README.md                    # This file
└── ARCHITECTURE_PRINCIPLES.md   # Formal architecture rules
```

## Architectural Guardrails

See [ARCHITECTURE_PRINCIPLES.md](ARCHITECTURE_PRINCIPLES.md) for formal design rules, anti-patterns, and handover notes for future contributors.

## Philosophy

> "The primary artifact is the state machine, not the target code."

This platform treats survey logic as a formal system (a guarded state machine) that exists independently of implementation language. The code (R, SPSS, etc.) is generated from this formal definition.

This approach enables:
- **Interoperability** between systems
- **Audit trails** via formal definitions
- **Change impact analysis**
- **Multi-language support**
- **Documentation automation**

At ONS scale, this becomes infrastructure for survey science across groups.

## License

MIT License (see LICENSE file)

## Contributing

All changes must:
1. Maintain strict layer separation
2. Add tests before code (TDD)
3. Document architectural implications
4. Avoid adding language-specific idioms to CSLM

See ARCHITECTURE_PRINCIPLES.md for full guidelines.
