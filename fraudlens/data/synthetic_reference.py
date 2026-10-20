"""Reference data and small helpers for the synthetic transaction generator."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

# ── Reference data ───────────────────────────────────────────────────────

_NORMAL_MERCHANT_CATEGORIES = [
    "groceries",
    "electronics",
    "restaurants",
    "gas_station",
    "pharmacy",
    "clothing",
    "entertainment",
    "travel",
    "utilities",
    "subscription",
    "home_improvement",
    "education",
]

# Matches fraudlens.core.scoring.rule_agent's risky-category list so the
# rule agent actually reacts to this data.
_RISKY_MERCHANT_CATEGORIES = [
    "crypto_exchange",
    "gambling",
    "gift_cards",
    "jewelry",
    "luxury_goods",
    "money_transfer",
    "digital_goods",
]

_NORMAL_LOCATIONS = ["us", "uk", "ca", "de", "fr", "in", "au", "jp", "br", "mx"]

# Matches fraudlens.core.scoring.rule_agent's risky-location list.
_RISKY_LOCATIONS = [
    "nigeria",
    "russia",
    "north_korea",
    "iran",
    "offshore",
    "anonymous_proxy",
    "tor_exit_node",
    "unknown",
]

_CHANNELS = ["online", "in_store", "mobile_app", "atm"]

# INR, scaled from the original USD design (~85 INR/USD) and consistent with
# the thresholds in rule_agent.py and velocity_agent.py; rescale together.
_AMOUNT_RANGES: dict[str, tuple[float, float]] = {
    "groceries": (800, 12_000),
    "electronics": (4_000, 170_000),
    "restaurants": (800, 10_000),
    "gas_station": (1_500, 7_500),
    "pharmacy": (400, 7_000),
    "clothing": (1_500, 25_000),
    "entertainment": (800, 12_000),
    "travel": (8_000, 250_000),
    "utilities": (2_500, 20_000),
    "subscription": (400, 5_000),
    "home_improvement": (1_500, 85_000),
    "education": (4_000, 170_000),
    "crypto_exchange": (15_000, 680_000),
    "gambling": (4_000, 250_000),
    "gift_cards": (2_000, 170_000),
    "jewelry": (8_000, 500_000),
    "luxury_goods": (15_000, 750_000),
    "money_transfer": (8_000, 400_000),
    "digital_goods": (800, 40_000),
}

FRAUD_PATTERN_TYPES = (
    "high_amount",
    "risky_merchant",
    "odd_hour",
    "card_testing",
    "high_velocity",
    "fraud_ring",
)


# ── Small helpers ─────────────────────────────────────────────────────────


def _rand_id(rng: random.Random, prefix: str, length: int = 8) -> str:
    return f"{prefix}-{''.join(rng.choices('0123456789ABCDEF', k=length))}"


def _new_txn_id(rng: random.Random) -> str:
    return f"TXN-{rng.getrandbits(64):016X}"


def _rand_ip(rng: random.Random) -> str:
    return f"{rng.randint(1, 223)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _random_timestamp(rng: random.Random, start: datetime, end: datetime) -> datetime:
    delta_seconds = max(int((end - start).total_seconds()), 0)
    return start + timedelta(seconds=rng.randint(0, delta_seconds))


def _daytime_timestamp(rng: random.Random, day: datetime) -> datetime:
    """Normal customer activity skews toward waking hours, 7am-10pm."""
    return day.replace(hour=rng.randint(7, 22), minute=rng.randint(0, 59), second=rng.randint(0, 59))


def _odd_hour_timestamp(rng: random.Random, day: datetime) -> datetime:
    return day.replace(hour=rng.randint(0, 3), minute=rng.randint(0, 59), second=rng.randint(0, 59))


# ── Individual transaction builders ───────────────────────────────────────
