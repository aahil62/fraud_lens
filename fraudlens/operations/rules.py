"""The showcase channel-control rules, one function each.

A rule looks at the attempted payment and its prior history and returns the
flags it raises as (score, reason) pairs. Scores are prioritisation scores, not
fraud probabilities; 0.8 and above requests protection. Thresholds are integer
paise.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .money import inr

PROTECT = 0.8


@dataclass(frozen=True)
class History:
    """The payment under review and the history the rules may use (never later events)."""

    txn: dict
    now: datetime
    prior: list  # every earlier attempt, oldest first, bounded to the last 1,000
    recent: list  # this account's attempts in the last five minutes
    fifteen: list  # every attempt in the last fifteen minutes

    @classmethod
    def build(cls, txn, prior):
        now = datetime.fromisoformat(txn["timestamp"])
        recent = [
            t for t in prior if t["account_id"] == txn["account_id"] and now - timedelta(minutes=5) <= _at(t)
        ]
        fifteen = [t for t in prior if now - timedelta(minutes=15) <= _at(t)]
        return cls(txn, now, prior, recent, fifteen)


def _at(txn):
    return datetime.fromisoformat(txn["timestamp"])


def _posted(txn):
    return txn.get("payment_status", "posted") == "posted"


def shared_device_accounts(h):
    """Other accounts seen on this payment's device."""
    return {
        t["account_id"]
        for t in h.prior
        if t["account_id"] != h.txn["account_id"] and t["device_id"] == h.txn["device_id"]
    }


def credential_takeover(h):
    t = h.txn
    if t["failed_auth_attempts"] >= 3 and t["new_device"]:
        yield 0.94, "Repeated authentication failures followed by payment from a new device."


def new_device_large_beneficiary(h):
    t = h.txn
    if t["new_device"] and t["new_beneficiary"] and t["amount_minor"] >= 2_000_000:
        yield 0.91, "Large transfer to a new beneficiary from a new device."


def net_banking_beneficiary_after_failures(h):
    t = h.txn
    if t["channel"] == "net_banking" and t["failed_auth_attempts"] >= 3 and t["new_beneficiary"]:
        yield 0.95, "New beneficiary payment after repeated net-banking authentication failures."


def shared_device_transfer(h):
    t = h.txn
    if (
        t["channel"] == "upi"
        and len(shared_device_accounts(h)) >= 2
        and t["new_beneficiary"]
        and t["amount_minor"] >= 1_000_000
    ):
        yield 0.90, "Large new-beneficiary payment from a device shared by three or more accounts."


def payment_burst(h):
    if len(h.recent) >= 4:
        yield 0.87, f"{len(h.recent) + 1} attempted payments from this account within five minutes."


def cross_channel_anomaly(h):
    t = h.txn
    channels = {r["channel"] for r in h.recent} | {t["channel"]}
    if len(channels) >= 3 and (t["new_device"] or t["failed_auth_attempts"]):
        yield 0.93, "Rapid activity across three or more channels with device or authentication anomalies."


def small_card_attempts(h):
    t = h.txn
    if t["channel"] != "card":
        return
    small = [
        r for r in h.recent if r.get("instrument_id") == t["instrument_id"] and r["amount_minor"] <= 80_000
    ]
    if len(small) >= 3 and t["amount_minor"] <= 80_000:
        yield 0.92, "Four or more small attempts on the same card suggest card testing."


def atm_withdrawals(h):
    t = h.txn
    if t["channel"] != "atm":
        return
    withdrawals = [r for r in h.recent if r["channel"] == "atm"]
    if any(r["location"] != t["location"] for r in withdrawals):
        yield (
            0.89 if t["amount_minor"] >= 1_000_000 else 0.62,
            "ATM withdrawal at a changed location within five minutes; amount determines protection versus review.",
        )
    if len(withdrawals) >= 2 and sum(r["amount_minor"] for r in withdrawals) + t["amount_minor"] >= 3_000_000:
        yield 0.90, "Rapid ATM withdrawals exceed the showcase withdrawal-burst threshold."
    if t["new_device"] and t["amount_minor"] >= 1_000_000:
        yield 0.88, "High-value withdrawal at a new test terminal/device."


def new_device_review(h, score_so_far):
    """Below the protection threshold, a sizeable new-device payment still goes to an analyst."""
    t = h.txn
    if t["new_device"] and t["amount_minor"] >= 500_000 and score_so_far < PROTECT:
        yield 0.58, "New-device payment requires analyst review; protective threshold not reached."


def mule_pass_through(h):
    """A new-beneficiary payment moving out at least 80% of a credit received in the last 15 minutes."""
    t = h.txn
    if not t["new_beneficiary"]:
        return
    credits = [r for r in h.fifteen if r.get("beneficiary_id") == t["account_id"] and _posted(r)]
    for credit in credits:
        moved_out = sum(
            r["amount_minor"]
            for r in h.fifteen
            if r["account_id"] == t["account_id"] and _posted(r) and _at(r) >= _at(credit)
        )
        outgoing = moved_out + t["amount_minor"]
        if outgoing * 100 >= credit["amount_minor"] * 80:
            percentage = min(100, outgoing * 100 / credit["amount_minor"])
            yield (
                0.86,
                f"Pass-through: received {inr(credit['amount_minor'])} and moved {percentage:.1f}% out within 15 minutes to a new beneficiary (including this attempt).",
            )
            return


def sim_swap_takeover(h):
    t = h.txn
    if t["new_device"] and t["failed_auth_attempts"] >= 3 and t["new_beneficiary"]:
        yield (
            0.92,
            "SIM-swap takeover pattern: new device, repeated authentication failures and a new beneficiary.",
        )


def card_testing(h):
    """Five or more sub-₹200 probes on one card in ten minutes, then a payment above ₹5,000."""
    t = h.txn
    if t["channel"] != "card":
        return
    probes = [
        r
        for r in h.prior
        if r["channel"] == "card"
        and r.get("instrument_id") == t["instrument_id"]
        and r["amount_minor"] < 20000
        and h.now - timedelta(minutes=10) <= _at(r)
    ]
    if len(probes) >= 5 and t["amount_minor"] > 500000:
        yield (
            0.91,
            "Card testing: five or more sub-₹200 attempts on one instrument followed by a larger payment.",
        )


def atm_cashout(h):
    t = h.txn
    if t["channel"] != "atm":
        return
    same_card = [
        r for r in h.fifteen if r["channel"] == "atm" and r.get("instrument_id") == t["instrument_id"]
    ]
    withdrawals = same_card + [t]
    if len(withdrawals) >= 3 and len({r["device_id"] for r in withdrawals}) >= 2:
        yield (
            0.88,
            "ATM burst across terminals: three or more withdrawals on one instrument across multiple terminals within 15 minutes.",
        )


# Applied in this order; new_device_review runs between the two groups because it
# depends on the score the first group reached.
CHANNEL_RULES = (
    credential_takeover,
    new_device_large_beneficiary,
    net_banking_beneficiary_after_failures,
    shared_device_transfer,
    payment_burst,
    cross_channel_anomaly,
    small_card_attempts,
    atm_withdrawals,
)
TYPOLOGY_RULES = (mule_pass_through, sim_swap_takeover, card_testing, atm_cashout)


def channel_policy(txn, prior):
    """The highest rule score (0.05 when nothing matches) and every reason raised, in rule order."""
    h = History.build(txn, prior)
    flags = [flag for rule in CHANNEL_RULES for flag in rule(h)]
    policy = max([0.05, *(score for score, _ in flags)])
    flags += list(new_device_review(h, policy))
    flags += [flag for rule in TYPOLOGY_RULES for flag in rule(h)]
    return max([0.05, *(score for score, _ in flags)]), [reason for _, reason in flags]
