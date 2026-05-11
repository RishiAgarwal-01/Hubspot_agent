import os
from dotenv import load_dotenv

load_dotenv()

HUBSPOT_CLIENT_SECRET = os.environ["HUBSPOT_CLIENT_SECRET"]
HUBSPOT_ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-prod")
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Weave AI agent trigger
WEAVE_TRIGGER_URL: str = os.getenv(
    "WEAVE_TRIGGER_URL",
    "https://weave.c24.tech/api/v1/execution/6a01716d6cee0781f8a0765d/run",
)
WEAVE_API_KEY: str = os.getenv(
    "WEAVE_API_KEY",
    "exec_w_5EZKrZhSnBCui92-eeZCsUnJg63D6NjKy4fW-_Fbc",
)
WEAVE_TEAM_ID: str = os.getenv("WEAVE_TEAM_ID", "6912eb397d0bd58868444c88")

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
