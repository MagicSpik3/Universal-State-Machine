# Architectural Principles for Universal State Machine

**Version 1.0** — Established Phase 1

---

## Purpose

This document formalizes the architectural contracts and invariants for the Universal State Machine platform.

It exists to prevent architectural drift and to guide future contributors (human and AI).

**Read this before making significant changes.**

---

## Foundational Principle

> **The CSLM is the single source of truth for survey logic.**
>
> Everything else is derived from it.
> 
> If something cannot be derived from CSLM, then CSLM is incomplete.

---

## The Five-Layer Architecture

```
Layer 0 — Raw Inputs
            ↓
Layer 1 — Parsing / Normalization
            ↓
Layer 2 — Canonical Survey Logic Model (CSLM)  ← TRUTH
            ↓
Layer 3 — Analysis & Transformation
            ↓
Layer 4 — Output Backends (Presentation & Generation)
```

Each layer has strict contracts with adjacent layers.

### Layer 0 — Raw Inputs

**Responsibility:** None. This is opaque source material.

**Constraints:** 
- Not part of the system
- May be messy, incomplete, ambiguous

**Examples:** SPSS syntax files, CSV routing tables, R code, Excel sheets

---

### Layer 1 — Parsing / Normalization

**Responsibility:** Translate heterogeneous formats into structured intermediate representations.

**Contract:** 
- **Input:** Opaque text/files from Layer 0
- **Output:** AST objects and structured data
- **Invariant:** Translation is semantics-preserving, not semantics-interpreting

**Critical Rules:**

1. **Do NOT interpret survey meaning here**
   - Parsing translates syntax → structure only
   - "Route to BDirNI1 if employed" is interpretation
   - "BDirNI1 guard = (BType1 == 2 OR BType1 == 3)" is translation

2. **Parsing must be reversible**
   - If you read SPSS syntax safely, you should be able to write it back identically
   - Test this property explicitly

3. **Do NOT simplify conditions here**
   - Do NOT merge `X==1 OR X==1` into `X==1`
   - Do NOT expand implicit defaults
   - Preserve all source-as-written

4. **Do NOT detect survey blocks here**
   - Block detection belongs in Layer 3
   - Just parse what you see

**Anti-Patterns:**
- ❌ Creating state machine during parsing
- ❌ Simplifying boolean conditions
- ❌ Inferring survey structure beyond what input specifies
- ❌ Storing R/SPSS code in parsed objects

---

### Layer 2 — Canonical Survey Logic Model (CSLM)

**Responsibility:** Represent survey as an abstract, language-agnostic guarded state machine.

**The CSLM must be:**
- Purely declarative
- Language-agnostic (zero R/SPSS knowledge)
- Serializable to JSON/YAML
- Immutable in delivery
- Diffable across versions
- Self-contained (everything needed to understand survey is here)

**Contract:**
- **Input:** Layer 1 ASTs and parsed structures
- **Output:** `Survey` object with `states`, `transitions`, `variables`, `blocks`
- **Invariant:** Structure is complete, semantics are unambiguous

**Core Objects:**

- `Survey` — Root container
- `Variable` — Named data slot
- `State` — Question node
- `Transition` — Directed edge with optional guard
- `Block` — Parameterized subgraph
- `Expression` (AST hierarchy) — All logic

**Critical Rules:**

1. **NEVER store language-specific code fragments**
   - ❌ `entry_guard = "Wrking == 1"`
   - ✅ `entry_guard = BinaryExpression(...)`

2. **All logic must be AST-based**
   - ❌ Strings, code snippets, regex
   - ✅ `BinaryExpression`, `VariableReference`, `Literal`

3. **Transitions must be explicit**
   - ❌ Assume implicit ordering: "next question after BType1"
   - ✅ Every possible transition explicitly declared

4. **Entry guards and validation are separate**
   - `entry_guard` = "Am I asked this question?"
   - `validation` = "Is my answer legal?"
   - Both are necessary, both are explicit

5. **Blocks are structural, not expanded**
   - `Block.state_ids = ["BType", "BDirNI", "BOwn"]` means abstract pattern
   - Actual instantiated states `BType1`, `BType2`, `BType3` live in `Survey.states`
   - Expansion happens in Layer 3, if needed
   - This keeps CSLM clean and maintainable

6. **Versioning is metadata, not routing logic**
   - `State.version = VersionRange(apply_from=2204)`
   - NOT: "if wave > 2204 then..."
   - Versioning is deployment metadata
   - Enables change impact analysis without logic duplication

7. **CSLM must be serializable**
   - If you cannot JSON/YAML serialize → model is incomplete
   - Test this continually: create CSLM → serialize → deserialize → compare

8. **CSLM is immutable in delivery**
   - Once generated, it should not change
   - Mutations belong in Layer 3 (analysis layer) with explicit audit trail

**Anti-Patterns:**
- ❌ Adding `to_r_code()` method to State
- ❌ Storing R semantics (e.g., "coerce to numeric")
- ❌ Performing transformations (simplification, reordering)
- ❌ Embedding formatting rules
- ❌ Cross-layer convenience methods
- ❌ String concatenation for logic

---

### Layer 3 — Analysis & Transformation (Optional)

**Responsibility:** Analyze, simplify, expand, and optimize CSLM without executing it.

**Contract:**
- **Input:** Layer 2 CSLM
- **Output:** New CSLM (possibly simplified/optimized)
- **Invariant:** All transformations are explicit and reversible (or at least trackable)

**Operations (examples):**
- Simplify boolean expressions
- Expand parameterized blocks
- Detect dead/unreachable states
- Analyze variable dependencies
- Version-based filtering
- Change impact analysis

**Critical Rules:**

1. **Does NOT execute the survey**
2. **Does NOT emit code**
3. **Produces output CSLM, not intermediate data**
4. **All transformations are auditable**

**Why isolate this?**
- Optimization and analysis are optional
- They should not pollute parsing or generation
- Analysis is where your intellectual value lives
- Keeping it separate allows controlled deployment

---

### Layer 4 — Output Backends

**Responsibility:** Consume CSLM and emit target format (R, SPSS, diagrams, documentation).

**Contract:**
- **Input:** Layer 2 (or 3) CSLM
- **Output:** R code / SPSS syntax / Diagrams / Markdown
- **Invariant:** Backends are pure functions, deterministic, stateless

**Each backend is a separate module:**
- `r_generator.py` → R code
- `spss_generator.py` → SPSS syntax
- `diagram_generator.py` → Graphviz DOT
- `doc_generator.py` → Markdown documentation

**Critical Rules:**

1. **Backends must NOT modify CSLM**
   - Read-only access only
   - If you need to modify, that belongs in Layer 3

2. **Backends must be language-agnostic**
   - No semantic assumptions specific to target language
   - If backend needs special interpretation, it means CSLM is missing a concept
   - Add it to CSLM first, then trivialize the backend

3. **Backends must be deterministic**
   - Same CSLM → same output every time
   - No randomness, no timestamps, no filesystem calls
   - Enables testing, diffing, auditing

4. **Backends are stateless**
   - No shared memory across calls
   - No caching (or cacheable state visible to user)
   - Pure function semantics

5. **Complex formatting logic belongs here**
   - Whitespace, indentation, comments: backends only
   - Not in CSLM

**Anti-Patterns:**
- ❌ "Let's simplify this condition in the R backend"
- ❌ "This variable needs special R handling, store it in CSLM"
- ❌ Backend mutates CSLM to optimize rendering
- ❌ Backends have persistent state

---

## Serialization Contract

All objects in CSLM must be serializable to JSON/YAML without loss.

**This is non-negotiable.**

**Why?**
- CSLM objects must be portable
- CSLM files become audit artifacts
- Enables human inspection
- Required for version control

**What this means:**
- No lambda functions
- No class instances that aren't serializable
- All `Expression` objects must have clean JSON representation
- Provide `to_dict()` and `from_dict()` methods

**Test this continually:**
```python
survey = build_survey(...)
json_str = survey_to_json(survey)
survey_restored = json_from_string(json_str)
assert survey == survey_restored  # Lossless round-trip
```

---

## Testing Invariants

### TDD Rule

All features must be preceded by tests that will pass before implementation.

### Architectural Tests (Not Just Unit Tests)

Beyond unit tests, verify:

1. **Serialization**
   - Can I serialize CSLM to JSON?
   - Can I deserialize and get identical object?

2. **Reversal**
   - Can I generate SPSS back from CSLM?
   - Does it look like original input?

3. **Independence**
   - Can I delete the R backend and still have coherent CSLM?
   - Can I understand survey from CSLM alone?

4. **Composition**
   - Can I build a survey with multiple blocks?
   - Can blocks have parameterized guards?

5. **Immutability**
   - Does CSLM remain unchanged after generation?
   - Are there any hidden side effects?

---

## Graph Properties to Verify

These are properties EVERY survey CSLM should satisfy:

1. **Nodes are only `State` objects**
2. **Edges are only `Transition` objects**
3. **Every node referenced in transitions exists in `Survey.states`**
4. **No cycles (or cycles are documented and auditable)**
5. **All variable references exist in `Survey.variables`**
6. **All block references exist in `Survey.blocks`**
7. **State IDs are unique**
8. **Variable names are unique**
9. **Expression tree depth is reasonable (prevent stack overflow)**

These should be checked by a validator before any backend processing.

---

## Handover Notes for Future Contributors

If you are reading this, assume:

1. **The author cared about clean architecture.**
2. **The separation of concerns is intentional.**
3. **Shortcuts feel convenient and are poison.**
4. **"Just this once" becomes architectural collapse.**

Before you add a feature, ask:

- [ ] Does this belong in Layer 2 (CSLM)?
- [ ] Or Layer 3 (Analysis)?
- [ ] Or Layer 4 (Backend)?
- [ ] Have I written tests first?
- [ ] Is CSLM still serializable?
- [ ] Can the system still be understood on one page?

If any answer is uncertain, **stop and refactor**.

---

## Anti-Patterns (Do Not Do These)

### 1. Blurring Layer Boundaries

**Bad:**
```python
# state.py
class State:
    def to_r_code(self):  # ❌ Layer 4 logic in Layer 2
        return f"if ({self.entry_guard}) ask(...)"
```

**Good:**
```python
# model.py (Layer 2)
class State:
    id: str
    entry_guard: Expression

# r_generator.py (Layer 4)
def generate_state(state: State) -> str:
    return f"if ({expression_to_r(state.entry_guard)}) ..."
```

### 2. Storing Language-Specific Information

**Bad:**
```python
class State:
    r_variable_name: str  # ❌ R-specific
    spss_label: str       # ❌ SPSS-specific
```

**Good:**
```python
class State:
    id: str               # ✅ Generic, backend-neutral
```
Then backends derive `r_variable_name` from `id` using backend-specific rules.

### 3. Performing Transformations in Parsing

**Bad:**
```python
# csv_parser.py
def parse_csv(file):
    # ... parser code ...
    state.guard = simplify_expression(state.guard)  # ❌
    return state
```

**Good:**
```python
# csv_parser.py (Layer 1)
def parse_csv(file):
    # ... parser code, exact as-written ...
    return state

# analyzer.py (Layer 3)
def optimize_survey(survey: Survey) -> Survey:
    return survey_with_simplified_guards(survey)
```

### 4. String-Based Logic

**Bad:**
```python
state.guard = "(Wrking == 1)"  # ❌ String logic
```

**Good:**
```python
state.guard = BinaryExpression(
    operator=BinaryOperator.EQUALS,
    left=VariableReference("Wrking"),
    right=Literal(1)
)  # ✅ AST
```

### 5. Implicit Ordering

**Bad:**
```python
# Assumes: states are in survey order, questions asked in order
for state in survey.states:
    ask(state)
```

**Good:**
```python
# Load transitions explicitly
current = survey.get_state("START")
while current:
    ask(current)
    next_state = find_next_by_transition(current)
    current = next_state
```

### 6. Cross-Layer Shortcuts

**Bad:**
```python
# r_generator.py
def generate(survey):
    for state in survey.states:
        for block in survey.blocks:  # ❌ Shouldn't know about blocks
            if state.id == block.name + "1":
                # special handling
```

**Good:**
```python
# Layer 3 pre-processes blocks
simplified_survey = expand_blocks(survey)

# Layer 4 only sees flat survey
for state in simplified_survey.states:
    emit_r_code(state)
```

### 7. Hidden State or Mutation

**Bad:**
```python
class RGenerator:
    def __init__(self):
        self.generated_code = ""  # ❌ Mutable state
    
    def generate(self, survey):
        self.generated_code = "..."  # Side effect
        return self.generated_code
```

**Good:**
```python
def generate_r_code(survey: Survey) -> str:
    # Pure function, no shared state
    return "..."
```

---

## Code Review Checklist

When reviewing code, ask:

- [ ] Is this logic in the correct layer?
- [ ] Are there tests before code?
- [ ] Does CSLM remain language-agnostic?
- [ ] Are there any strings that should be AST?
- [ ] Is serialization tested?
- [ ] Are side effects avoided?
- [ ] Is the change explainable in 2-3 sentences?
- [ ] Does it maintain existing interface contracts?

---

## When to Refactor

Refactor immediately if you notice:

1. **A backend needs special logic** → Add it to CSLM
2. **A parser is interpreting survey meaning** → Move to Layer 3
3. **CSLM cannot serialize** → Remove the offending attribute
4. **A feature spans multiple layers** → Separate concerns
5. **Understanding the system takes more than one page** → Simplify
6. **A class knows about multiple layers** → Split it

---

## Summary

| Layer | Responsibility | Input | Output | Constraint |
|-------|---|---|---|---|
| 0 | (none) | Raw text | - | Opaque |
| 1 | Translate syntax | Files | AST, structured data | Semantics-preserving |
| 2 | Define survey | AST | CSLM | Language-agnostic, immutable, serializable |
| 3 | Analyze & optimize | CSLM | CSLM | Non-destructive (with audit trail) |
| 4 | Generate output | CSLM | Code / Diagrams / Docs | Pure functions |

---

## Questions? 

If you have to ask "which layer does this belong in?", the answer is almost always:

> Write a test that defines the correct answer, then implement the minimal code to pass it.

That process will reveal the right layer.

---

**Last updated:** February 2026
**Author:** Architecture Phase 1 Design
**Status:** Active — Read before making changes
