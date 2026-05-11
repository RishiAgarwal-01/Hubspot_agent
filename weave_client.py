"""
Sends structured HubSpot deal data to the Weave AI agent trigger.

Flow:
  HubSpot webhook → Flask → fetch deal → build payload → POST to Weave trigger URL
"""

import logging
import requests
from config import WEAVE_TRIGGER_URL, WEAVE_API_KEY

logger = logging.getLogger(__name__)


def _val(properties: dict, key: str) -> str | None:
    """Return the property value or None if absent/empty."""
    v = properties.get(key)
    return v if v not in (None, "", "None") else None


def build_trigger_payload(deal: dict) -> dict:
    """
    Map a raw HubSpot deal API response to the flat payload
    expected by the Weave trigger fields.
    """
    props = deal.get("properties", {})

    missing = [
        field for field in [
            "booked_delivery_slot",
            "contract_signed_date",
            "document_handling",
            "finance_gfd_date",
            "refurb_gfd_date",
            "registered_date",
            "delivery_state",
            "payment_mode",
        ]
        if not _val(props, field)
    ]

    return {
        # Core identifiers
        "deal_id":               deal.get("id", ""),
        "deal_name":             _val(props, "dealname") or "",
        "deal_stage":            _val(props, "dealstage") or "",
        "pipeline":              _val(props, "pipeline") or "",

        # Delivery tracking fields (mirror the table columns)
        "delivery_state":        _val(props, "delivery_state"),
        "payment_mode":          _val(props, "payment_mode"),
        "trade_in_opted":        _val(props, "trade_in_opted"),
        "booked_delivery_slot":  _val(props, "booked_delivery_slot"),
        "contract_signed_date":  _val(props, "contract_signed_date"),
        "document_handling":     _val(props, "document_handling"),
        "finance_gfd_date":      _val(props, "finance_gfd_date"),
        "refurb_gfd_date":       _val(props, "refurb_gfd_date"),
        "registered_date":       _val(props, "registered_date"),

        # Computed summary fields for easy use inside Weave
        "missing_fields":        ", ".join(missing) if missing else "",
        "has_missing_fields":    len(missing) > 0,
        "missing_field_count":   len(missing),
        "trigger_source":        "hubspot_cos_delivery",
    }


def fire_trigger(deal: dict) -> bool:
    """
    POST the deal payload to the Weave trigger URL.
    Returns True on success, False on failure.
    """
    if not WEAVE_TRIGGER_URL:
        logger.warning("WEAVE_TRIGGER_URL not set — skipping Weave notification")
        return False

    payload = build_trigger_payload(deal)
    headers = {"Content-Type": "application/json"}
    if WEAVE_API_KEY:
        headers["Authorization"] = f"Bearer {WEAVE_API_KEY}"

    try:
        resp = requests.post(WEAVE_TRIGGER_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(
            "Weave trigger fired for deal %s — status %s",
            payload["deal_id"],
            resp.status_code,
        )
        return True
    except requests.HTTPError as exc:
        logger.error("Weave trigger HTTP error for deal %s: %s", payload["deal_id"], exc)
    except Exception as exc:
        logger.error("Weave trigger failed for deal %s: %s", payload["deal_id"], exc)
    return False
