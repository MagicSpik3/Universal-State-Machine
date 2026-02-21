"""
Serialization helpers for CSLM objects (Survey, State, Expression, etc.).

Provides lossless JSON/YAML round-trip via intermediate dict representation.
This module intentionally keeps serialization structure stable and explicit.
"""
from __future__ import annotations

import json
from typing import Any, Dict

import yaml

from cslm.model import (
    Survey,
    Variable,
    State,
    Transition,
    Block,
    VersionRange,
)
from cslm.expressions import (
    Expression,
    BinaryExpression,
    VariableReference,
    Literal,
    UnaryExpression,
    BinaryOperator,
    UnaryOperator,
)


def expr_to_dict(expr: Expression | None) -> Any:
    if expr is None:
        return None
    if isinstance(expr, BinaryExpression):
        return {
            "type": "binary",
            "operator": expr.operator.value,
            "left": expr_to_dict(expr.left),
            "right": expr_to_dict(expr.right),
        }
    if isinstance(expr, VariableReference):
        return {"type": "var", "name": expr.name}
    if isinstance(expr, Literal):
        return {"type": "lit", "value": expr.value}
    if isinstance(expr, UnaryExpression):
        return {
            "type": "unary",
            "operator": expr.operator.value,
            "operand": expr_to_dict(expr.operand),
        }
    raise TypeError(f"Unsupported Expression type: {type(expr)}")


def expr_from_dict(d: Any) -> Expression | None:
    if d is None:
        return None
    t = d.get("type")
    if t == "binary":
        op = BinaryOperator(d["operator"])
        left = expr_from_dict(d["left"])
        right = expr_from_dict(d["right"])
        return BinaryExpression(operator=op, left=left, right=right)
    if t == "var":
        return VariableReference(d["name"])
    if t == "lit":
        return Literal(d["value"])
    if t == "unary":
        op = UnaryOperator(d["operator"])
        operand = expr_from_dict(d["operand"])
        return UnaryExpression(operator=op, operand=operand)
    raise TypeError(f"Unsupported expression dict type: {t}")


def version_to_dict(v: VersionRange | None) -> Dict[str, Any] | None:
    if v is None:
        return None
    return {"apply_from": v.apply_from, "apply_to": v.apply_to}


def version_from_dict(d: Dict[str, Any] | None) -> VersionRange | None:
    if d is None:
        return None
    return VersionRange(apply_from=d.get("apply_from"), apply_to=d.get("apply_to"))


def variable_to_dict(v: Variable) -> Dict[str, Any]:
    return {"name": v.name, "description": v.description, "data_type": v.data_type}


def variable_from_dict(d: Dict[str, Any]) -> Variable:
    return Variable(name=d["name"], description=d.get("description"), data_type=d.get("data_type"))


def state_to_dict(s: State) -> Dict[str, Any]:
    return {
        "id": s.id,
        "text": s.text,
        "entry_guard": expr_to_dict(s.entry_guard),
        "validation": expr_to_dict(s.validation),
        "version": version_to_dict(s.version),
        "block": s.block,
    }


def state_from_dict(d: Dict[str, Any]) -> State:
    return State(
        id=d["id"],
        text=d.get("text", ""),
        entry_guard=expr_from_dict(d.get("entry_guard")),
        validation=expr_from_dict(d.get("validation")),
        version=version_from_dict(d.get("version")),
        block=d.get("block"),
    )


def transition_to_dict(t: Transition) -> Dict[str, Any]:
    return {"from_state": t.from_state, "to_state": t.to_state, "guard": expr_to_dict(t.guard)}


def transition_from_dict(d: Dict[str, Any]) -> Transition:
    return Transition(from_state=d["from_state"], to_state=d["to_state"], guard=expr_from_dict(d.get("guard")))


def block_to_dict(b: Block) -> Dict[str, Any]:
    return {"name": b.name, "parameters": b.parameters, "state_ids": b.state_ids}


def block_from_dict(d: Dict[str, Any]) -> Block:
    return Block(name=d["name"], parameters=d.get("parameters", []), state_ids=d.get("state_ids", []))


def survey_to_dict(s: Survey) -> Dict[str, Any]:
    return {
        "name": s.name,
        "variables": [variable_to_dict(v) for v in s.variables],
        "states": [state_to_dict(st) for st in s.states],
        "transitions": [transition_to_dict(t) for t in s.transitions],
        "blocks": [block_to_dict(b) for b in s.blocks],
        "metadata": s.metadata,
    }


def survey_from_dict(d: Dict[str, Any]) -> Survey:
    s = Survey(name=d.get("name", ""))
    s.variables = [variable_from_dict(v) for v in d.get("variables", [])]
    s.states = [state_from_dict(st) for st in d.get("states", [])]
    s.transitions = [transition_from_dict(t) for t in d.get("transitions", [])]
    s.blocks = [block_from_dict(b) for b in d.get("blocks", [])]
    s.metadata = d.get("metadata", {})
    return s


def survey_to_json(s: Survey) -> str:
    return json.dumps(survey_to_dict(s), sort_keys=True)


def survey_from_json(s: str) -> Survey:
    d = json.loads(s)
    return survey_from_dict(d)


def survey_to_yaml(s: Survey) -> str:
    return yaml.safe_dump(survey_to_dict(s))


def survey_from_yaml(s: str) -> Survey:
    d = yaml.safe_load(s)
    return survey_from_dict(d)
