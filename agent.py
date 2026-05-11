import json
import logging
import anthropic
import hubspot_client as hs
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-sonnet-4-6"

TOOLS = [
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
        "description": "Fetch full details of a HubSpot deal by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "HubSpot deal ID"}
            },
            "required": ["deal_id"],
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
        if name == "get_contact":
            result = hs.get_contact(tool_input["contact_id"])
        elif name == "get_deal":
            result = hs.get_deal(tool_input["deal_id"])
        elif name == "update_contact":
            result = hs.update_contact(tool_input["contact_id"], tool_input["properties"])
        elif name == "update_deal":
            result = hs.update_deal(tool_input["deal_id"], tool_input["properties"])
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


def process_webhook_event(event: dict) -> str:
    """
    Run the agentic loop for a single HubSpot webhook event.
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

    messages = [{"role": "user", "content": user_message}]

    # Agentic loop — keeps running until the model stops requesting tools
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
            # Extract the final text reply
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "Agent completed with no text output."

        if response.stop_reason != "tool_use":
            return f"Agent stopped unexpectedly: {response.stop_reason}"

        # Execute all requested tool calls and feed results back
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
