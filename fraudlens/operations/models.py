"""Strict operational inputs; currency is integer paise, never floating point."""
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

Channel = Literal["upi", "net_banking", "card", "atm"]
Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:@-]+$")]


class TransactionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    txn_id: Identifier
    account_id: Identifier
    channel: Channel
    amount_minor: Annotated[StrictInt, Field(gt=0, le=100_000_000)]
    timestamp: datetime
    instrument_id: Identifier | None = None
    beneficiary_id: Identifier | None = None
    merchant_id: Identifier = "merchant-demo"
    device_id: Identifier = "device-known"
    ip_address: str = Field(default="127.0.0.1", min_length=1, max_length=64)
    location: str = Field(default="Pune", min_length=1, max_length=100)
    new_device: bool = False
    new_beneficiary: bool = False
    failed_auth_attempts: Annotated[StrictInt, Field(ge=0, le=100)] = 0

    @field_validator("timestamp")
    @classmethod
    def utc_timestamp(cls, value):
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def card_reference(self):
        if self.channel in {"card", "atm"} and not self.instrument_id:
            raise ValueError("card and ATM attempts require instrument_id")
        return self


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["investigate", "escalate", "confirm_fraud", "false_positive"]
    expected_version: Annotated[StrictInt, Field(ge=1)]
    notes: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def require_rationale(self):
        self.notes = self.notes.strip()
        if self.action in {"confirm_fraud", "false_positive"} and not self.notes:
            raise ValueError("A rationale is required for a final analyst verdict")
        return self


class ScenarioInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Channel
    scenario: Literal["normal", "fraud", "false_positive", "cross_channel"]


class ControlInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    running: bool | None = None
    interval_seconds: float | None = Field(default=None, ge=2, le=60)
    bank_mode: Literal["normal", "reject", "timeout_after_commit"] | None = None
