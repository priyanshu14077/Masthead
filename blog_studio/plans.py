"""Plans, features and limits, read from plans.json: the same file the marketing site renders."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PLANS_FILE = Path(__file__).resolve().parent.parent / "plans.json"


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_monthly: int
    per_seat: bool
    min_seats: int
    features: frozenset[str]
    limits: dict[str, int | None]  # None means unlimited

    def has(self, feature: str) -> bool:
        return feature in self.features

    def limit(self, key: str) -> int | None:
        return self.limits.get(key)


@cache
def catalogue() -> dict[str, Plan]:
    raw = json.loads(PLANS_FILE.read_text())
    return {
        p["id"]: Plan(
            id=p["id"],
            name=p["name"],
            price_monthly=p["price_monthly"],
            per_seat=p["per_seat"],
            min_seats=p.get("min_seats", 1),
            features=frozenset(p["features"]),
            limits=dict(p["limits"]),
        )
        for p in raw["plans"]
    }


def get(plan_id: str | None) -> Plan:
    plans = catalogue()
    return plans.get(plan_id or "free", plans["free"])


def feature_label(feature: str) -> str:
    return json.loads(PLANS_FILE.read_text())["feature_labels"].get(feature, feature)


def coming_soon() -> list[str]:
    """Features a plan lists but the product doesn't do yet. Shown as coming, never enforced."""
    return json.loads(PLANS_FILE.read_text()).get("coming_soon", [])


def cheapest_with(feature: str) -> Plan | None:
    """The lowest plan that includes a feature, for upgrade prompts."""
    for plan in sorted(catalogue().values(), key=lambda p: p.price_monthly):
        if plan.has(feature):
            return plan
    return None
