import requests
from config import HUBSPOT_ACCESS_TOKEN

BASE_URL = "https://api.hubapi.com"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

# All properties tracked in the "Upcoming delivery Awaiting COS" table.
# Verify these internal API names match your HubSpot portal's custom properties.
COS_DEAL_PROPERTIES = ",".join([
    "dealname",
    "dealstage",
    "pipeline",
    "hubspot_owner_id",
    "delivery_state",
    "payment_mode",
    "trade_in_opted",
    "booked_delivery_slot",
    "contract_signed_date",
    "document_handling",
    "finance_gfd_date",
    "refurb_gfd_date",
    "registered_date",
    "closedate",
    "amount",
])


def _get(path: str, params: dict = None) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _patch(path: str, data: dict) -> dict:
    resp = requests.patch(f"{BASE_URL}{path}", headers=HEADERS, json={"properties": data}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, data: dict) -> dict:
    resp = requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=data, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_contact(contact_id: str) -> dict:
    return _get(
        f"/crm/v3/objects/contacts/{contact_id}",
        params={"properties": "firstname,lastname,email,phone,lifecyclestage,hs_lead_status,company"},
    )


def get_deal(deal_id: str) -> dict:
    return _get(
        f"/crm/v3/objects/deals/{deal_id}",
        params={"properties": "dealname,amount,dealstage,closedate,pipeline,hubspot_owner_id"},
    )


def get_cos_deal(deal_id: str) -> dict:
    """Fetch a deal with all COS delivery tracking fields."""
    return _get(
        f"/crm/v3/objects/deals/{deal_id}",
        params={"properties": COS_DEAL_PROPERTIES},
    )


def get_deal_contacts(deal_id: str) -> dict:
    """Return contacts associated with a deal."""
    return _get(
        f"/crm/v3/objects/deals/{deal_id}/associations/contacts",
    )


def update_contact(contact_id: str, properties: dict) -> dict:
    return _patch(f"/crm/v3/objects/contacts/{contact_id}", properties)


def update_deal(deal_id: str, properties: dict) -> dict:
    return _patch(f"/crm/v3/objects/deals/{deal_id}", properties)


def create_deal_note(deal_id: str, note_body: str) -> dict:
    """Create a note on a deal record (used for flagging missing fields)."""
    note = _post("/crm/v3/objects/notes", {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": _current_timestamp_ms(),
        }
    })
    note_id = note["id"]
    # Associate note → deal
    _post(
        f"/crm/v3/objects/notes/{note_id}/associations/deals/{deal_id}/202",
        {},
    )
    return note


def _current_timestamp_ms() -> str:
    import time
    return str(int(time.time() * 1000))


def search_contacts(query: str, limit: int = 5) -> dict:
    payload = {
        "query": query,
        "limit": limit,
        "properties": ["firstname", "lastname", "email", "lifecyclestage"],
    }
    resp = requests.post(f"{BASE_URL}/crm/v3/objects/contacts/search", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def search_deals(query: str, limit: int = 5) -> dict:
    payload = {
        "query": query,
        "limit": limit,
        "properties": ["dealname", "amount", "dealstage", "closedate"],
    }
    resp = requests.post(f"{BASE_URL}/crm/v3/objects/deals/search", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()
