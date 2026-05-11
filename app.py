import hashlib
import hmac
import json
import logging
import threading

from flask import Flask, request, jsonify

import config
from agent import process_webhook_event, process_cos_delivery_event

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_hubspot_signature(req: request) -> bool:
    """
    HubSpot v1 signature: HMAC-SHA256(client_secret + raw_body) == X-HubSpot-Signature
    https://developers.hubspot.com/docs/api/webhooks/validating-requests
    """
    signature = req.headers.get("X-HubSpot-Signature", "")
    raw_body = req.get_data()
    expected = hmac.new(
        config.HUBSPOT_CLIENT_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# COS stage detection
# ---------------------------------------------------------------------------

def _is_cos_stage_entry(event: dict) -> bool:
    """
    Return True when:
      - a deal is newly created directly in an Awaiting COS stage, OR
      - a deal's dealstage property just changed to an Awaiting COS stage.
    """
    sub_type = event.get("subscriptionType", "")
    prop_value = str(event.get("propertyValue", "")).lower()

    if sub_type == "deal.creation":
        # The creation event's propertyValue for dealstage will hold the initial stage
        return any(stage.lower() in prop_value for stage in config.AWAITING_COS_STAGES)

    if sub_type == "deal.propertyChange" and event.get("propertyName") == "dealstage":
        return any(stage.lower() in prop_value for stage in config.AWAITING_COS_STAGES)

    return False


# ---------------------------------------------------------------------------
# Background event processing
# ---------------------------------------------------------------------------

def _process_events_async(events: list[dict]):
    for event in events:
        deal_id = str(event.get("objectId", ""))
        sub_type = event.get("subscriptionType", "")

        try:
            if _is_cos_stage_entry(event):
                # Deal just entered (or was created in) an Awaiting COS stage
                previous_stage = event.get("previousValue", "")
                logger.info(
                    "COS delivery trigger fired — deal %s entered stage '%s' (was '%s')",
                    deal_id,
                    event.get("propertyValue", ""),
                    previous_stage,
                )
                summary = process_cos_delivery_event(deal_id, previous_stage)
            else:
                summary = process_webhook_event(event)

            logger.info(
                "Agent processed event [%s / %s]: %s",
                sub_type,
                deal_id,
                summary,
            )
        except Exception:
            logger.exception("Error processing event %s", event)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/webhook", methods=["POST"])
def webhook():
    if not _verify_hubspot_signature(request):
        logger.warning("Rejected webhook — invalid signature")
        return jsonify({"error": "invalid signature"}), 401

    try:
        events = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    if not isinstance(events, list):
        events = [events]

    # Accept deal and contact events; COS routing happens inside _process_events_async
    supported = {
        "deal.creation",
        "deal.propertyChange",
        "contact.creation",
        "contact.propertyChange",
    }
    filtered = [e for e in events if e.get("subscriptionType") in supported]

    if not filtered:
        return jsonify({"received": len(events), "processed": 0}), 200

    # Return 200 immediately — HubSpot expects a fast response
    thread = threading.Thread(target=_process_events_async, args=(filtered,), daemon=True)
    thread.start()

    cos_count = sum(1 for e in filtered if _is_cos_stage_entry(e))
    logger.info("Queued %d event(s) (%d COS delivery trigger(s))", len(filtered), cos_count)
    return jsonify({"received": len(events), "queued": len(filtered), "cos_triggers": cos_count}), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)
