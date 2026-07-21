"""Pure support-hour calculations for plan-aware portal presentation."""
from decimal import Decimal
from typing import Iterable


def calculate_support_hours(included_hours, ticket_hours: Iterable) -> dict[str, Decimal]:
    included = max(Decimal("0"), Decimal(str(included_hours or 0)))
    logged = sum((max(Decimal("0"), Decimal(str(value or 0))) for value in ticket_hours), Decimal("0"))
    return {
        "included": included,
        "logged": logged,
        "remaining": max(Decimal("0"), included - logged),
        "potentially_billable": max(Decimal("0"), logged - included),
    }


def format_hours(value: Decimal) -> str:
    text = format(value.quantize(Decimal("0.01")), "f").rstrip("0").rstrip(".")
    return text or "0"


def support_ticket_notice(plan_tier: str) -> str:
    if str(plan_tier or "").lower() != "basic":
        return ""
    return (
        '<div class="mb-4 rounded-xl border border-amber-300/20 bg-amber-400/10 p-3 text-sm text-amber-100">'
        '<strong class="block mb-1">Your plan does not include monthly support hours.</strong>'
        'Support requests outside remote access, managed backup and covered platform services may be billable after review by Burghscape.'
        '</div>'
    )
