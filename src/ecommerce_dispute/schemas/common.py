"""Shared strict-model primitives and schema versioning."""

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "1.0"


class StrictModel(BaseModel):
    """Reject unknown fields at every external and inter-component boundary."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FrozenStrictModel(BaseModel):
    """Immutable payload used for committed worker handoffs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
