"""Strict request bodies for the simulated bank's API."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:@-]+$")]
Mode = Literal["normal", "reject", "timeout_after_commit"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class PaymentInput(StrictInput):
    txn_id: Identifier
    account_id: Identifier
    channel: Literal["upi", "net_banking", "card", "atm"]
    amount_minor: Annotated[int, Field(gt=0, le=9_000_000_000_000_000)]
    instrument_id: Identifier | None = None
    beneficiary_id: Identifier | None = None

    @model_validator(mode="after")
    def require_instrument(self):
        if self.channel in {"card", "atm"} and not self.instrument_id:
            raise ValueError("Card and ATM transactions require instrument_id")
        return self


class ActionInput(StrictInput):
    action_id: Identifier
    case_id: Identifier
    operation: Literal["restrict", "release", "lien", "lien_release", "close"]
    target_type: Literal["account", "card"]
    target_id: Identifier
    amount_minor: Annotated[int, Field(gt=0, le=9_000_000_000_000_000)] | None = None

    @model_validator(mode="after")
    def action_target_and_amount(self):
        if self.operation == "lien" and self.amount_minor is None:
            raise ValueError("Lien requires a positive amount_minor")
        if self.operation != "lien" and "amount_minor" in self.model_fields_set:
            raise ValueError("amount_minor is only valid for liens")
        if self.operation in {"lien", "lien_release", "close"} and self.target_type != "account":
            raise ValueError("This operation requires an account target")
        return self


class SeedAccountInput(StrictInput):
    account_id: Annotated[str, Field(max_length=80, pattern=r"^SIM-[A-Za-z0-9_.:@-]+$")]
    balance_minor: Annotated[int, Field(ge=0, le=100_000_000)]


class SeedInput(StrictInput):
    accounts: Annotated[list[SeedAccountInput], Field(min_length=1, max_length=20)]


class ControlInput(StrictInput):
    mode: Mode
