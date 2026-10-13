"""Billing with Stripe: Checkout to subscribe, the customer portal to manage, webhooks to stay in sync.

The database's plan for a workspace changes only in response to a verified Stripe webhook, never
because a browser said so. Prices are found by lookup key (team_monthly, team_yearly,
business_monthly, business_yearly), so they can be changed in Stripe without a deploy.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

import stripe

from . import plans
from .db import DB

LIVE_STATUSES = {"active", "trialing", "past_due"}  # past_due keeps access while Stripe retries the card
TRIAL_DAYS = 14


class BillingError(Exception):
    pass


def effective_plan(sub: dict[str, Any]) -> plans.Plan:
    """What a workspace can use right now."""
    return plans.get(sub["plan"] if sub.get("status") in LIVE_STATUSES else "free")


def plan_from_lookup_key(key: str | None) -> str:
    if not key:
        return "free"
    tier = key.split("_", 1)[0]
    return tier if tier in plans.catalogue() else "free"


class Gateway(Protocol):
    def checkout(self, *, customer: str | None, workspace_id: int, email_hint: str | None, lookup_key: str, seats: int, trial: bool, success_url: str, cancel_url: str) -> dict[str, str]: ...
    def portal(self, *, customer: str, return_url: str) -> str: ...
    def verify(self, payload: bytes, signature: str | None) -> dict[str, Any]: ...


@dataclass
class StripeGateway:
    secret_key: str
    webhook_secret: str
    automatic_tax: bool = False

    def __post_init__(self) -> None:
        self.client = stripe.StripeClient(self.secret_key)

    def _price(self, lookup_key: str) -> str:
        found = self.client.v1.prices.list(params={"lookup_keys": [lookup_key], "active": True, "limit": 1})
        if not found.data:
            raise BillingError(f"No active Stripe price with lookup key {lookup_key}. Create it in the Stripe dashboard.")
        return found.data[0].id

    def checkout(self, *, customer, workspace_id, email_hint, lookup_key, seats, trial, success_url, cancel_url):  # type: ignore[no-untyped-def]
        if not customer:
            customer = self.client.v1.customers.create(params={"metadata": {"workspace_id": str(workspace_id)}}).id
        params: dict[str, Any] = {
            "mode": "subscription",
            "customer": customer,
            "client_reference_id": str(workspace_id),
            "line_items": [{"price": self._price(lookup_key), "quantity": seats}],
            "allow_promotion_codes": True,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "subscription_data": {"metadata": {"workspace_id": str(workspace_id)}},
        }
        if trial:
            params["subscription_data"]["trial_period_days"] = TRIAL_DAYS
        if self.automatic_tax:
            params["automatic_tax"] = {"enabled": True}
            params["customer_update"] = {"address": "auto", "name": "auto"}
        session = self.client.v1.checkout.sessions.create(params=params)
        return {"url": session.url, "customer": customer}

    def portal(self, *, customer, return_url):  # type: ignore[no-untyped-def]
        return self.client.v1.billing_portal.sessions.create(params={"customer": customer, "return_url": return_url}).url

    def verify(self, payload, signature):  # type: ignore[no-untyped-def]
        try:
            event = stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
        except (ValueError, stripe.SignatureVerificationError) as e:
            raise BillingError("Webhook signature check failed.") from e
        return event.to_dict() if hasattr(event, "to_dict") else dict(event)


def gateway_from_env() -> Gateway | None:
    key, hook = os.environ.get("STRIPE_SECRET_KEY"), os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not key or not hook:
        return None
    return StripeGateway(key, hook, automatic_tax=os.environ.get("STRIPE_AUTOMATIC_TAX") == "1")


# Webhooks ---------------------------------------------------------------------
def _subscription_fields(sub: dict[str, Any]) -> dict[str, Any]:
    item = (sub.get("items", {}).get("data") or [{}])[0]
    price = item.get("price") or {}
    status = sub.get("status", "none")
    # current_period_end moved from the subscription to its items in newer API versions.
    period_end = item.get("current_period_end") or sub.get("current_period_end")
    return {
        "stripe_subscription_id": sub.get("id"),
        "stripe_customer_id": sub.get("customer"),
        "plan": plan_from_lookup_key(price.get("lookup_key")) if status not in {"canceled", "incomplete_expired"} else "free",
        "status": status,
        "seats": int(item.get("quantity") or 1),
        "current_period_end": str(period_end) if period_end else None,
        "cancel_at_period_end": 1 if sub.get("cancel_at_period_end") else 0,
    }


def handle_event(db: DB, event: dict[str, Any]) -> str:
    """Applies one verified Stripe event. Returns a short description of what happened."""
    if not db.first_time_event(event["id"], event["type"]):
        return "duplicate, ignored"
    kind, obj = event["type"], event["data"]["object"]

    def workspace() -> int | None:
        meta = obj.get("metadata") or {}
        if meta.get("workspace_id"):
            return int(meta["workspace_id"])
        if obj.get("client_reference_id"):
            return int(obj["client_reference_id"])
        return db.workspace_by_customer(obj.get("customer") or "")

    wid = workspace()
    if wid is None or db.workspace(wid) is None:
        return "no matching workspace"

    if kind == "checkout.session.completed":
        db.save_subscription(wid, {"stripe_customer_id": obj.get("customer"), "stripe_subscription_id": obj.get("subscription")})
        db.audit(wid, None, "billing.checkout_completed", obj.get("subscription") or "")
        return "checkout recorded"
    if kind in {"customer.subscription.created", "customer.subscription.updated"}:
        fields = _subscription_fields(obj)
        db.save_subscription(wid, fields)
        db.audit(wid, None, "billing.subscription_" + kind.rsplit(".", 1)[1], fields["plan"], {"status": fields["status"], "seats": fields["seats"]})
        return f"{fields['plan']} ({fields['status']}, {fields['seats']} seats)"
    if kind == "customer.subscription.deleted":
        db.save_subscription(wid, {"plan": "free", "status": "canceled", "seats": 1, "cancel_at_period_end": 0})
        db.audit(wid, None, "billing.subscription_deleted")
        return "downgraded to free"
    if kind == "invoice.payment_failed":
        db.save_subscription(wid, {"status": "past_due"})
        db.audit(wid, None, "billing.payment_failed", obj.get("id") or "")
        return "marked past due"
    if kind == "invoice.paid":
        db.audit(wid, None, "billing.invoice_paid", obj.get("id") or "", {"amount": obj.get("amount_paid")})
        return "invoice recorded"
    return "ignored"
