import os
from dotenv import load_dotenv

load_dotenv()

HUBSPOT_CLIENT_SECRET = os.environ["HUBSPOT_CLIENT_SECRET"]
HUBSPOT_ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-prod")
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# HubSpot internal stage IDs that belong to the "Upcoming delivery Awaiting COS" view.
# Add or remove stage values to match your pipeline configuration.
# These are the dealstage internal values (visible in HubSpot → Settings → Deals → Pipelines).
AWAITING_COS_STAGES: set[str] = {
    stage.strip()
    for stage in os.getenv(
        "AWAITING_COS_STAGES",
        "awaiting_cos,awaiting_refurb_gfd,6,appointmentscheduled",
    ).split(",")
    if stage.strip()
}
