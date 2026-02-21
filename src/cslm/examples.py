"""
Example survey builder for proof-of-concept based on the provided CSV snippet.

Builds a simple JobBlock instantiation for 3 jobs with BType, BDirNI, BOwn states,
including guards, validations and version metadata.
"""
from cslm.model import Survey, Variable, State, Transition, Block, VersionRange
from cslm.expressions import (
    BinaryExpression,
    BinaryOperator,
    VariableReference,
    Literal,
)


def build_example_job_survey(job_count: int = 3, apply_from: int = 2204) -> Survey:
    survey = Survey(name="Example Job Survey")

    # Common variables
    survey.variables = [
        Variable(name="Wrking", description="Currently working"),
        Variable(name="JbAway", description="Job away flag"),
        Variable(name="OwnBus", description="Owns a business"),
        Variable(name="NumJob", description="Number of jobs"),
    ]

    # Block definition
    job_block = Block(name="JobBlock", parameters=["job_index"], state_ids=["BType", "BDirNI", "BOwn", "BAccsA"]) 
    survey.blocks = [job_block]

    states = []
    transitions = []

    # Entry guard shared: (Wrking == 1 OR JbAway == 1 OR OwnBus == 1)
    entry_guard = BinaryExpression(
        operator=BinaryOperator.OR,
        left=BinaryExpression(
            operator=BinaryOperator.OR,
            left=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("Wrking"),
                right=Literal(1),
            ),
            right=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference("JbAway"),
                right=Literal(1),
            ),
        ),
        right=BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference("OwnBus"),
            right=Literal(1),
        ),
    )

    for i in range(1, job_count + 1):
        # Variable names like BType1, BDirNI1, BOwn1
        btype_id = f"BType{i}"
        bdir_id = f"BDirNI{i}"
        bown_id = f"BOwn{i}"

        # Validation: (BType >=1 AND BType <=5) OR BType == -8
        range_check = BinaryExpression(
            operator=BinaryOperator.AND,
            left=BinaryExpression(
                operator=BinaryOperator.GREATER_EQUAL,
                left=VariableReference(btype_id),
                right=Literal(1),
            ),
            right=BinaryExpression(
                operator=BinaryOperator.LESS_EQUAL,
                left=VariableReference(btype_id),
                right=Literal(5),
            ),
        )
        validation = BinaryExpression(
            operator=BinaryOperator.OR,
            left=range_check,
            right=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference(btype_id),
                right=Literal(-8),
            ),
        )

        state_btype = State(
            id=btype_id,
            text=f"Employment type for job {i}",
            entry_guard=entry_guard,
            validation=validation,
            version=VersionRange(apply_from=apply_from),
            block="JobBlock",
        )

        # BDirNI asked if BType == 2 or 3
        bdir_guard = BinaryExpression(
            operator=BinaryOperator.OR,
            left=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference(btype_id),
                right=Literal(2),
            ),
            right=BinaryExpression(
                operator=BinaryOperator.EQUALS,
                left=VariableReference(btype_id),
                right=Literal(3),
            ),
        )
        state_bdir = State(
            id=bdir_id,
            text=f"National Insurance deducted at source for job {i}",
            entry_guard=bdir_guard,
            version=VersionRange(apply_from=apply_from),
            block="JobBlock",
        )

        # BOwn asked if BType == 3
        bown_guard = BinaryExpression(
            operator=BinaryOperator.EQUALS,
            left=VariableReference(btype_id),
            right=Literal(3),
        )
        state_bown = State(
            id=bown_id,
            text=f"Do you own part of this business for job {i}",
            entry_guard=bown_guard,
            version=VersionRange(apply_from=apply_from),
            block="JobBlock",
        )

        states.extend([state_btype, state_bdir, state_bown])

        # Transitions: from BType -> BDirNI if guard, to BOwn if guard
        transitions.append(Transition(from_state=btype_id, to_state=bdir_id, guard=bdir_guard))
        transitions.append(Transition(from_state=btype_id, to_state=bown_id, guard=bown_guard))

    # Add a START transition to first job BType1
    transitions.insert(0, Transition(from_state="START", to_state="BType1"))

    survey.states = states
    survey.transitions = transitions

    return survey
