"""Typed contracts shared by discovery, compilation, and replay."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ActionType = Literal["click", "type", "extract", "navigate", "wait", "finish", "escalate"]


class RiskLevel(str, Enum):
    READ = "read"
    SAFE_WRITE = "safe_write"
    IRREVERSIBLE = "irreversible"


class RunStatus(str, Enum):
    SUCCESS = "success"
    BUSINESS_OUTCOME = "business_outcome"
    RECOVERABLE_ERROR = "recoverable_error"
    HARD_FAILURE = "hard_failure"
    ESCALATED = "escalated"


class ControlOwner(str, Enum):
    AUTOMATION = "automation"
    HUMAN = "human"


class LocatorHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["css", "xpath", "text"]
    value: str


class Target(BaseModel):
    """Surface-independent description of a UI control."""

    model_config = ConfigDict(extra="forbid")

    role: str | None = None
    name: str | None = None
    text: str | None = None
    near_text: str | None = None
    frame_hint: str | None = None
    fallbacks: list[LocatorHint] = Field(default_factory=list)


class ObservationElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str
    role: str
    name: str | None = None
    value: str | None = None
    text: str | None = None


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str
    elements: list[ObservationElement] = Field(default_factory=list)
    visible_text: str = ""
    dialog_present: bool = False


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    target: Target | None = None
    value: str | None = None
    output_name: str | None = None
    reason: str
    risk: RiskLevel = RiskLevel.READ


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    message: str = ""
    value: Any | None = None


CheckpointType = Literal[
    "element_visible", "text_visible", "url_matches", "value_equals", "any_of", "all_of", "output_extracted"
]


class Checkpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: CheckpointType
    value: str | None = None
    target: Target | None = None
    output_name: str | None = None
    conditions: list["Checkpoint"] = Field(default_factory=list)


class InputSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["string", "number", "boolean"]
    required: bool = True
    description: str = ""


class OutputSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["string", "number", "boolean"]
    required: bool = False
    description: str = ""


class CapabilityStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: ActionType
    target: Target | None = None
    value: str | None = None
    output_name: str | None = None
    checkpoint: Checkpoint | None = None
    timeout_ms: int = Field(default=5000, ge=100, le=120000)
    retries: int = Field(default=0, ge=0, le=3)
    risk: RiskLevel = RiskLevel.READ


class TargetApp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str
    entry_point: str
    version: str = "mock-1"


class BusinessOutcomeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    description: str
    checkpoint: Checkpoint


class SafetyPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    allowed_actions: list[ActionType] = Field(
        default_factory=lambda: ["click", "type", "extract", "navigate", "wait", "finish", "escalate"]
    )
    blocked_routes: list[str] = Field(default_factory=list)
    require_human_for_risk: list[RiskLevel] = Field(default_factory=lambda: [RiskLevel.IRREVERSIBLE])
    target_risks: dict[str, RiskLevel] = Field(default_factory=dict)


class CapabilityMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author: str = "interface.ai take-home"
    created_at: str
    source: str = "discovery"
    tags: list[str] = Field(default_factory=list)


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    capability_id: str
    name: str
    description: str
    target_app: TargetApp
    inputs: list[InputSpec]
    outputs: list[OutputSpec]
    steps: list[CapabilityStep]
    success_condition: Checkpoint
    business_outcomes: list[BusinessOutcomeSpec] = Field(default_factory=list)
    safety_policy: SafetyPolicy = Field(default_factory=SafetyPolicy)
    metadata: CapabilityMetadata


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RunStatus
    capability_id: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    business_outcome: str | None = None
    failed_step_id: str | None = None
    message: str | None = None
    evidence: list[str] = Field(default_factory=list)


Checkpoint.model_rebuild()
