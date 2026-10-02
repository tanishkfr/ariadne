"""Schema compilation: a safe subset of JSON Schema becomes Ariadne primitives.

The direction of dependency matters more than the feature. An Ariadne contract
compiles *into* Ariadne :class:`~ariadne_engine.decisions.contracts.DecisionQuestion`
objects, and those are what the native Decision Runtime is handed. The runtime's
question format never appears here, and the engine never depends on it. Swapping the
engine cannot change what Ariadne considers a well-formed bounded question.

The supported subset is deliberately small, because the failure mode of a permissive
schema compiler is converting an open-ended problem into a bounded one that looks
answerable. Every rejection below exists for that reason:

* free-form string → refused, because "a short string" has no closed answer space;
* arrays and nested objects → refused, because a bounded runtime scores one closed
  label per question and cannot faithfully score a nested structure;
* ``$ref`` and recursion → refused, because the compiler would need to be a resolver
  and a resolver is where schema limits stop being enforced;
* more than :data:`MAX_OPTIONS` enum values or :data:`MAX_SCORE_LEVELS` levels →
  refused, because past that point a per-option marker budget silently gives each
  option a couple of tokens and the accuracy figure stops meaning anything;
* unbounded numeric ranges → refused, because "any number" is not a bounded answer
  space either. A numeric field needs an integer ``minimum`` and ``maximum``.

What survives is exactly what the runtime can honestly answer: an enum becomes a
choice, a boolean becomes a binary decision, and a closed integer range becomes a
scale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ...contracts import ContractError
from ..contracts import DecisionQuestion

SCHEMA_VERSION = "ar-206-schema-compiler-1"
"""The compiled-plan shape."""

MAX_PROPERTIES = 32
"""Fields per compiled contract."""

MAX_OPTIONS = 32
"""Enum values per choice question."""

MAX_SCORE_LEVELS = 10
"""Inclusive integer range width per scale question."""

SUPPORTED_TYPES = ("boolean", "string", "integer", "number", "array", "object")
"""JSON Schema types the compiler examines. Most of them only so it can refuse them
with a message that says why."""


class SchemaError(ContractError):
    """The schema cannot be represented as bounded questions.

    A subclass of :class:`~ariadne_engine.contracts.ContractError` so an ordinary
    Ariadne contract failure already catches it.
    """


@dataclass(frozen=True)
class CompiledField:
    """One field of a compiled contract."""

    name: str
    primitive: str
    options: tuple[str, ...]
    scale: tuple[str, ...]
    positive: str
    negative: str
    instructions: str

    def as_question(self, *, contract: str, consequence: str = "LOW", definition_version: str = "1") -> DecisionQuestion:
        return DecisionQuestion(
            question_id=self.name,
            instructions=self.instructions,
            primitive=self.primitive,
            options=self.options,
            scale=self.scale,
            positive=self.positive,
            negative=self.negative,
            consequence=consequence,
            definition_version=definition_version,
            projection_contract=contract,
        )


@dataclass(frozen=True)
class CompiledContract:
    """A schema compiled into independent bounded questions."""

    contract_id: str
    fields: tuple[CompiledField, ...]
    source_digest: str

    def as_questions(self, *, consequence: str = "LOW", definition_version: str = "1") -> tuple[DecisionQuestion, ...]:
        return tuple(
            field.as_question(
                contract=self.contract_id,
                consequence=consequence,
                definition_version=definition_version,
            )
            for field in self.fields
        )


def _schema_of(document: Any) -> Mapping[str, Any]:
    """Accept a JSON Schema mapping, a pydantic v2/v1 model, or a dataclass.

    Pydantic and dataclasses are *sources* of a schema, not a dependency: only their
    ``model_json_schema()``/``schema()``/``__annotations__`` output is used, and
    neither is imported here.
    """
    if isinstance(document, Mapping):
        return document
    for attribute in ("model_json_schema", "schema"):
        candidate = getattr(document, attribute, None)
        if callable(candidate):
            schema = candidate()
            if isinstance(schema, Mapping):
                return schema
    annotations = getattr(document, "__annotations__", None)
    if isinstance(annotations, Mapping) and annotations:
        properties: dict[str, Any] = {}
        for name, annotation in annotations.items():
            text = str(annotation)
            if "bool" in text:
                properties[str(name)] = {"type": "boolean"}
            elif "int" in text:
                properties[str(name)] = {"type": "integer"}
            elif "float" in text:
                properties[str(name)] = {"type": "number"}
            elif "str" in text:
                properties[str(name)] = {"type": "string"}
            else:
                properties[str(name)] = {}
        if properties:
            return {"type": "object", "properties": properties}
    raise SchemaError(f"expected a JSON schema object or a schema-bearing model, got {type(document).__name__}")


def _label(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _enum_field(path: str, block: Mapping[str, Any]) -> CompiledField:
    values = block.get("enum")
    if not isinstance(values, (list, tuple)) or not values:
        raise SchemaError(f"{path}: 'enum' must declare at least one value")
    if len(values) > MAX_OPTIONS:
        raise SchemaError(
            f"{path}: {len(values)} options exceeds MAX_OPTIONS={MAX_OPTIONS}; narrow the set or shortlist first"
        )
    labels = tuple(_label(value) for value in values)
    if len(set(labels)) != len(labels):
        raise SchemaError(f"{path}: enum values produce duplicate question options")
    if all(isinstance(value, bool) for value in values):
        # An all-boolean enum is a binary decision with the polarity the schema declared.
        return CompiledField(
            name="",
            primitive="BinaryDecision",
            options=(),
            scale=(),
            positive="true",
            negative="false",
            instructions=str(block.get("description", "") or ""),
        )
    return CompiledField(
        name="",
        primitive="ChoiceDecision",
        options=labels,
        scale=(),
        positive="yes",
        negative="no",
        instructions=str(block.get("description", "") or ""),
    )


def _score_field(path: str, block: Mapping[str, Any]) -> CompiledField:
    low = block.get("minimum")
    high = block.get("maximum")
    if not isinstance(low, int) or not isinstance(high, int) or isinstance(low, bool) or isinstance(high, bool):
        raise SchemaError(
            f"{path}: a numeric field needs integer 'minimum' and 'maximum' to become a bounded scale; "
            "an unbounded number is not a closed answer space"
        )
    if high < low:
        raise SchemaError(f"{path}: 'maximum' {high} is below 'minimum' {low}")
    span = high - low + 1
    if span > MAX_SCORE_LEVELS:
        raise SchemaError(
            f"{path}: {span} levels exceeds MAX_SCORE_LEVELS={MAX_SCORE_LEVELS}; narrow the range or use an enum"
        )
    return CompiledField(
        name="",
        primitive="ScaleDecision",
        options=(),
        scale=tuple(str(low + offset) for offset in range(span)),
        positive="yes",
        negative="no",
        instructions=str(block.get("description", "") or ""),
    )


def _field(path: str, block: Mapping[str, Any]) -> CompiledField:
    if "$ref" in block:
        raise SchemaError(f"{path}: $ref and recursion are not supported; flatten the schema")
    if "const" in block:
        return _enum_field(path, {"enum": [block["const"]], "description": block.get("description")})
    if "enum" in block:
        return _enum_field(path, block)
    for union in ("anyOf", "oneOf"):
        branches = block.get(union)
        if branches is None:
            continue
        if not isinstance(branches, (list, tuple)):
            raise SchemaError(f"{path}: '{union}' must be a list")
        real = [branch for branch in branches if isinstance(branch, Mapping) and branch.get("type") != "null"]
        if len(real) != 1:
            raise SchemaError(
                f"{path}: only optional unions (one non-null branch of '{union}') are supported, "
                f"got {len(real)}"
            )
        return _field(path, real[0])
    kind = str(block.get("type", ""))
    if kind == "boolean":
        return CompiledField(
            name="",
            primitive="BinaryDecision",
            options=(),
            scale=(),
            positive="true",
            negative="false",
            instructions=str(block.get("description", "") or ""),
        )
    if kind in ("integer", "number"):
        return _score_field(path, block)
    if kind == "string":
        raise SchemaError(
            f"{path}: a free string cannot be a fixed option set; declare 'enum' or use 'boolean'"
        )
    if kind == "array":
        raise SchemaError(f"{path}: arrays are not supported; ask one question per element")
    if kind == "object":
        raise SchemaError(f"{path}: nested objects are not supported; flatten the schema")
    if not kind:
        raise SchemaError(f"{path}: the field declares no type, so it declares no closed answer space")
    raise SchemaError(f"{path}: unsupported schema type {kind!r}")


def compile_schema(document: Any, *, contract_id: str) -> CompiledContract:
    """Compile a safe-subset JSON Schema into independent bounded questions."""
    schema = _schema_of(document)
    properties = schema.get("properties")
    if not isinstance(properties, Mapping) or not properties:
        raise SchemaError("the schema declares no properties, so it declares no bounded question")
    if len(properties) > MAX_PROPERTIES:
        raise SchemaError(f"{len(properties)} properties exceeds MAX_PROPERTIES={MAX_PROPERTIES}")
    fields: list[CompiledField] = []
    for name in sorted(str(key) for key in properties):
        block = properties[name]
        if not isinstance(block, Mapping):
            raise SchemaError(f"{name}: property is not an object")
        field = _field(name, block)
        # Re-bind the nameless inner field to its property name.
        fields.append(
            CompiledField(
                name=name,
                primitive=field.primitive,
                options=field.options,
                scale=field.scale,
                positive=field.positive,
                negative=field.negative,
                instructions=field.instructions or f"the declared {name} value for this state",
            )
        )
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), default=str)
    import hashlib

    return CompiledContract(
        contract_id=str(contract_id),
        fields=tuple(fields),
        source_digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def compile_questions(document: Any, *, contract_id: str, consequence: str = "LOW") -> tuple[DecisionQuestion, ...]:
    """Compile straight to questions, the form the Decision Plane actually uses."""
    return compile_schema(document, contract_id=contract_id).as_questions(consequence=consequence)


def describe() -> dict:
    return {
        "version": SCHEMA_VERSION,
        "max_properties": MAX_PROPERTIES,
        "max_options": MAX_OPTIONS,
        "max_score_levels": MAX_SCORE_LEVELS,
        "supported": {
            "enum/const": "ChoiceDecision (BinaryDecision when every value is boolean)",
            "boolean": "BinaryDecision",
            "integer with integer minimum+maximum": "ScaleDecision",
        },
        "refused": {
            "free string": "no closed answer space",
            "array": "the runtime scores one closed label per question",
            "nested object": "flatten the schema",
            "$ref / recursion": "the compiler is not a resolver",
            "unbounded number": "declare minimum and maximum",
            f">{MAX_OPTIONS} enum values": "shortlist the candidates first",
        },
        "note": (
            "the contract compiles into Ariadne primitives first; the runtime's own question "
            "format is never part of Ariadne's API"
        ),
    }