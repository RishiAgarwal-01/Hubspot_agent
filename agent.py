import json
import logging
import anthropic
import hubspot_client as hs
import weave_client
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-sonnet-4-6"

# Fields that MUST be populated for a deal in the Awaiting COS delivery view.
COS_REQUIRED_FIELDS = [
    "booked_delivery_slot",
    "contract_signed_date",
    "document_handling",
    "finance_gfd_date",
    "refurb_gfd_date",
    "registered_date",
    "delivery_state",
    "payment_mode",
]

TOOLS = [
    {
        "name": "get_cos_deal",
        "description": (
            "Fetch full details of a HubSpot deal in the 'Upcoming delivery Awaiting COS' "
            "pipeline, including all delivery tracking fields: booked_delivery_slot, "
            "contract_signed_date, document_handling, finance_gfd_date, refurb_gfd_date, "
            "registered_date, delivery_state, payment_mode, trade_in_opted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "HubSpot deal ID"}
            },
            "required": ["deal_id"],
        },
    },
    {
        "name": "get_deal_contacts",
        "description": "Get the contacts associated with a HubSpot deal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "HubSpot deal ID"}
            },
            "required": ["deal_id"],
        },
    },
    {
        "name": "get_contact",
        "description": "Fetch full details of a HubSpot contact by their ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string", "description": "HubSpot contact ID"}
            },
            "required": ["contact_id"],
        },
    },
    {
        "name": "get_deal",
        "description": "Fetch basic details of any HubSpot deal by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "HubSpot deal ID"}
            },
            "required": ["deal_id"],
        },
    },
    {
        "name": "update_deal",
        "description": "Update properties of a HubSpot deal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "HubSpot deal ID"},
                "properties": {
                    "type": "object",
                    "description": "Key-value pairs of HubSpot deal properties to update",
                },
            },
            "required": ["deal_id", "properties"],
        },
    },
    {
        "name": "update_contact",
        "description": "Update properties of a HubSpot contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string", "description": "HubSpot contact ID"},
                "properties": {
                    "type": "object",
                    "description": "Key-value pairs of HubSpot contact properties to update",
                },
            },
            "required": ["contact_id", "properties"],
        },
    },
    {
        "name": "flag_deal_missing_fields",
        "description": (
            "Create a note on the deal record listing which required COS delivery fields "
            "are missing. Call this when one or more required fields have no value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "HubSpot deal ID"},
                "missing_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of property names that are missing or empty",
                },
            },
            "required": ["deal_id", "missing_fields"],
        },
    },
    {
        "name": "search_contacts",
        "description": "Search HubSpot contacts by keyword (name, email, company).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"},
                "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_deals",
        "description": "Search HubSpot deals by keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"},
                "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
            },
            "required": ["query"],
        },
    },
]


def _dispatch_tool(name: str, tool_input: dict) -> str:
    try:
        if name == "get_cos_deal":
            result = hs.get_cos_deal(tool_input["deal_id"])
        elif name == "get_deal_contacts":
            result = hs.get_deal_contacts(tool_input["deal_id"])
        elif name == "get_contact":
            result = hs.get_contact(tool_input["contact_id"])
        elif name == "get_deal":
            result = hs.get_deal(tool_input["deal_id"])
        elif name == "update_deal":
            result = hs.update_deal(tool_input["deal_id"], tool_input["properties"])
        elif name == "update_contact":
            result = hs.update_contact(tool_input["contact_id"], tool_input["properties"])
        elif name == "flag_deal_missing_fields":
            fields = tool_input["missing_fields"]
            note_body = (
                "⚠️ Automated COS Delivery Check — Missing required fields:\n"
                + "\n".join(f"  • {f}" for f in fields)
                + "\n\nPlease update these fields to proceed with delivery."
            )
            result = hs.create_deal_note(tool_input["deal_id"], note_body)
        elif name == "search_contacts":
            result = hs.search_contacts(tool_input["query"], tool_input.get("limit", 5))
        elif name == "search_deals":
            result = hs.search_deals(tool_input["query"], tool_input.get("limit", 5))
        else:
            result = {"error": f"Unknown tool: {name}"}
        return json.dumps(result)
    except Exception as exc:
        logger.error("Tool %s failed: %s", name, exc)
        return json.dumps({"error": str(exc)})


def _run_agent_loop(system_prompt: str, user_message: str) -> str:
    """Core agentic loop — keeps running until the model stops requesting tools."""
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "Agent completed with no text output."

        if response.stop_reason != "tool_use":
            return f"Agent stopped unexpectedly: {response.stop_reason}"

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                logger.info("Agent calling tool: %s %s", block.name, block.input)
                result_json = _dispatch_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_json,
                })

        messages.append({"role": "user", "content": tool_results})


def process_cos_delivery_event(deal_id: str, previous_stage: str = "") -> str:
    """
    Triggered when a deal enters (or is created in) an Awaiting COS delivery stage.

    Steps:
      1. Fetch the full deal from HubSpot immediately.
      2. Fire the Weave trigger with the structured deal payload.
      3. Run the Claude agent to validate fields and flag gaps in HubSpot.
    """
    # Step 1 — fetch the deal now so we can pass real data to Weave
    try:
        deal = hs.get_cos_deal(deal_id)
        weave_client.fire_trigger(deal)
    except Exception:
        logger.exception("Failed to pre-fetch deal %s for Weave trigger", deal_id)

    # Step 2 — run the full Claude validation loop
    required_fields_info = "\n".join(f"  - {f}" for f in COS_REQUIRED_FIELDS)

    system_prompt = (
        "You are a HubSpot CRM delivery operations assistant. "
        "Your job is to validate deals that have just entered the 'Upcoming delivery Awaiting COS' pipeline. "
        "This view tracks upcoming vehicle deliveries and requires these fields to be populated before delivery can proceed:\n"
        f"{required_fields_info}\n\n"
        "When a deal arrives in this stage:\n"
        "1. Fetch the deal using get_cos_deal to retrieve all delivery fields.\n"
        "2. Check each required field — if its value is null, empty, or '(No value)', it is missing.\n"
        "3. If any required fields are missing, call flag_deal_missing_fields with the list.\n"
        "4. Optionally fetch associated contacts for context.\n"
        "5. Summarise what you found and what action you took in 2-3 sentences."
    )

    user_message = (
        f"Deal ID {deal_id} has just entered the 'Upcoming delivery Awaiting COS' stage"
        + (f" (previous stage: {previous_stage})" if previous_stage else "")
        + ".\n\nValidate this deal and flag any missing required delivery fields."
    )

    return _run_agent_loop(system_prompt, user_message)


def process_webhook_event(event: dict) -> str:
    """
    Route a raw HubSpot webhook event to the appropriate agent handler.
    Returns the agent's final summary string.
    """
    object_type = event.get("subscriptionType", "unknown")
    object_id = str(event.get("objectId", ""))
    change_source = event.get("changeSource", "")
    property_name = event.get("propertyName", "")
    property_value = event.get("propertyValue", "")

    system_prompt = (
        "You are a HubSpot CRM assistant embedded in a webhook processing pipeline. "
        "When a webhook event arrives, analyze it, fetch relevant data using the provided tools, "
        "and take appropriate actions (e.g., enriching records, flagging issues, updating fields). "
        "Be concise in your final summary — one to three sentences describing what you did."
    )

    user_message = (
        f"A HubSpot webhook event was received:\n"
        f"- Subscription type: {object_type}\n"
        f"- Object ID: {object_id}\n"
        f"- Change source: {change_source}\n"
        f"- Changed property: {property_name} = {property_value}\n\n"
        f"Fetch the relevant record, assess the change, and take any useful action."
    )

    return _run_agent_loop(system_prompt, user_message)
