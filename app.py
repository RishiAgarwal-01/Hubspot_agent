import hashlib
import hmac
import json
import logging
import threading

from flask import Flask, request, jsonify

import config
from agent import process_webhook_event

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
# Background event processing
# ---------------------------------------------------------------------------

def _process_events_async(events: list[dict]):
    for event in events:
        try:
            summary = process_webhook_event(event)
            logger.info(
                "Agent processed event [%s / %s]: %s",
                event.get("subscriptionType"),
                event.get("objectId"),
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

    # Filter to only supported object types
    supported = {"contact.creation", "contact.propertyChange", "deal.creation", "deal.propertyChange"}
    filtered = [e for e in events if e.get("subscriptionType") in supported]

    if not filtered:
        return jsonify({"received": len(events), "processed": 0}), 200

    # Process events in a background thread so HubSpot gets a fast 200 response
    thread = threading.Thread(target=_process_events_async, args=(filtered,), daemon=True)
    thread.start()

    logger.info("Queued %d event(s) for agent processing", len(filtered))
    return jsonify({"received": len(events), "queued": len(filtered)}), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)
