import requests
from config import HUBSPOT_ACCESS_TOKEN

BASE_URL = "https://api.hubapi.com"

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def _get(path: str, params: dict = None) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _patch(path: str, data: dict) -> dict:
    resp = requests.patch(f"{BASE_URL}{path}", headers=HEADERS, json={"properties": data}, timeout=10)
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


def update_contact(contact_id: str, properties: dict) -> dict:
    return _patch(f"/crm/v3/objects/contacts/{contact_id}", properties)


def update_deal(deal_id: str, properties: dict) -> dict:
    return _patch(f"/crm/v3/objects/deals/{deal_id}", properties)


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
