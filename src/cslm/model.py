"""
Core Survey Model Objects

Defines the fundamental data structures of the Canonical Survey Logic Model.

These are pure data classes representing:
    - Variables (data slots)
    - States (questions)
    - Transitions (movement between states)
    - Blocks (parameterized subgraphs)
    - Surveys (root container)

ARCHITECTURAL RULE:
    These objects:
        - Know nothing about R/SPSS/target languages
        - Are mostly immutable
        - Are fully serializable
        - Represent structure, not behavior
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Union
from .expressions import Expression


@dataclass
class VersionRange:
    """
    Represents the validity window of a state or block.
    
    This is deployment/versioning metadata, NOT routing logic.
    
    Examples:
        - apply_from = 2204 (wave 2204 onwards)
        - apply_from = 2204, apply_to = 2206 (waves 2204-2206)
    
    Why separate this?
        Because version activation is metadata, not survey logic.
        It enables:
            - Change impact analysis
            - Wave-based filtering
            - Multi-version generation
    
    Properties:
        apply_from: First version/wave this applies to (optional)
        apply_to: Last version/wave this applies to (optional)
    """

    apply_from: Optional[int] = None
    apply_to: Optional[int] = None


@dataclass
class Variable:
    """
    Declares a survey variable (data slot).
    
    This is metadata only. It enables:
        - Dependency analysis
        - Reference validation
        - Documentation generation
    
    Properties:
        name: Variable identifier (e.g., "BType1")
        description: Human-readable description (optional)
        data_type: Expected data type (optional, for documentation)
    """

    name: str
    description: Optional[str] = None
    data_type: Optional[str] = None


@dataclass
class State:
    """
    Represents a single survey state, typically a question.
    
    This is the primary node type in the survey state machine.
    
    Properties:
        id: 
            Unique identifier (must be stable across versions)
            Examples: "BType1", "BDirNI2", "BOwn3"
        
        text: 
            Human-readable question text
        
        entry_guard: 
            Boolean Expression determining if this state is entered
            If None: state is always eligible (subject to transitions)
            Example: (Wrking == 1 OR JbAway == 1)
        
        validation: 
            Boolean Expression defining valid response values
            If None: any response is valid
            Example: (BType1 >= 1 AND BType1 <= 5) OR BType1 == -8
        
        version: 
            VersionRange defining when this state applies
        
        block: 
            Optional block name if this state belongs to a parameterized structure
            Example: "JobBlock" for states BType1, BType2, BType3
    
    ARCHITECTURAL RULE:
        - entry_guard is about reaching the state
        - validation is about accepting the response
        - These are separate concerns
    """

    id: str
    text: str
    entry_guard: Optional[Expression] = None
    validation: Optional[Expression] = None
    version: Optional[VersionRange] = None
    block: Optional[str] = None


@dataclass
class Transition:
    """
    Represents a directed transition from one state to another.
    
    ARCHITECTURAL RULE:
        Transitions must be explicit.
        Do NOT assume implicit fallthrough or ordering.
        Every transition must be declared.
    
    Properties:
        from_state: 
            ID of origin state
        
        to_state: 
            ID of destination state
        
        guard: 
            Optional Boolean Expression
            If None: transition is unconditional
            Example: BType1 == 2 (route to next state if BType1 == 2)
    
    Example:
        From state "BType1", transition to "BDirNI1" if (BType1 == 2 OR BType1 == 3)
        
        Transition(
            from_state="BType1",
            to_state="BDirNI1",
            guard=BinaryExpression(...)
        )
    """

    from_state: str
    to_state: str
    guard: Optional[Expression] = None


@dataclass
class Block:
    """
    Represents a parameterized group of states (subgraph structure).
    
    Handles repeated patterns without code duplication.
    
    Example:
        JobBlock represents:
            Job 1: BType1, BDirNI1, BOwn1, ...
            Job 2: BType2, BDirNI2, BOwn2, ...
            Job 3: BType3, BDirNI3, BOwn3, ...
        
        Instead of hard-coding all variants, we define:
            Block(
                name="JobBlock",
                parameters=["job_index"],
                state_ids=["BType", "BDirNI", "BOwn", ...]
            )
    
    IMPORTANT:
        - Blocks define structure, not expansion
        - Expansion (if needed) happens in analysis layer
        - This keeps CSLM clean
    
    Properties:
        name: 
            Block identifier (e.g., "JobBlock")
        
        parameters: 
            Parameter names (e.g., ["job_index"])
        
        state_ids: 
            Base state IDs in this block
            (actual instantiated states are in Survey.states)
    
    DESIGN NOTE:
        We could use state_ids to reference patterns,
        but actually we just track states in the survey itself.
        Blocks group related states conceptually.
    """

    name: str
    parameters: List[str] = field(default_factory=list)
    state_ids: List[str] = field(default_factory=list)


@dataclass
class Survey:
    """
    Root container for the entire canonical survey definition.
    
    This is THE primary artifact.
    
    Everything else (R code, SPSS code, diagrams, documentation)
    MUST be derivable from this object alone.
    
    If something cannot be derived from Survey, then the model is incomplete.
    
    ARCHITECTURAL PRINCIPLE:
        Survey is the single source of truth.
        It is immutable at delivery.
        It is language-agnostic.
        It is fully serializable.
    
    Properties:
        name: 
            Survey identifier
        
        variables: 
            All declared variables
        
        states: 
            All states (question nodes) in the survey
        
        transitions: 
            All directed edges between states
        
        blocks: 
            Parameterized substructures
        
        metadata: 
            Arbitrary key-value pairs (use sparingly)
            Example: {"source_wave": "2204", "source_system": "SPSS"}
    
    INVARIANTS:
        - All state IDs in transitions must exist in states
        - All variable references must exist in variables
        - Blocks must reference existing states
        - Survey must be serializable to JSON/YAML
    """

    name: str
    variables: List[Variable] = field(default_factory=list)
    states: List[State] = field(default_factory=list)
    transitions: List[Transition] = field(default_factory=list)
    blocks: List[Block] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def get_state(self, state_id: str) -> Optional[State]:
        """
        Retrieve a state by ID.
        
        Args:
            state_id: State identifier
        
        Returns:
            State object or None if not found
        """
        for state in self.states:
            if state.id == state_id:
                return state
        return None
    
    def get_variable(self, var_name: str) -> Optional[Variable]:
        """
        Retrieve a variable by name.
        
        Args:
            var_name: Variable name
        
        Returns:
            Variable object or None if not found
        """
        for var in self.variables:
            if var.name == var_name:
                return var
        return None
    
    def get_block(self, block_name: str) -> Optional[Block]:
        """
        Retrieve a block by name.
        
        Args:
            block_name: Block identifier
        
        Returns:
            Block object or None if not found
        """
        for block in self.blocks:
            if block.name == block_name:
                return block
        return None
