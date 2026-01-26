#!/bin/bash

# Google Cloud Function Deployment Script
# This script deploys the Slack Redirect Automation to Google Cloud Functions

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-europe-west1}"
FUNCTION_NAME="slack-redirect-automation"
RUNTIME="python311"
MEMORY="256MB"
TIMEOUT="120s"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Slack Redirect Automation Deployment ===${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${YELLOW}Please log in to Google Cloud:${NC}"
    gcloud auth login
fi

# Set the project
echo -e "${YELLOW}Setting project to: ${PROJECT_ID}${NC}"
gcloud config set project "${PROJECT_ID}"

# Check if .env file exists
if [ ! -f "../.env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create a .env file with the required configuration"
    exit 1
fi

# Load environment variables from .env
export $(grep -v '^#' ../.env | xargs)

# Verify required environment variables
if [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_CHANNEL_ID" ] || [ -z "$GOOGLE_SHEETS_ID" ] || [ -z "$N8N_WEBHOOK_URL" ]; then
    echo -e "${RED}Error: Missing required environment variables${NC}"
    echo "Required: SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, GOOGLE_SHEETS_ID, N8N_WEBHOOK_URL"
    exit 1
fi

# Create a temporary directory for deployment
DEPLOY_DIR=$(mktemp -d)
echo -e "${YELLOW}Preparing deployment in: ${DEPLOY_DIR}${NC}"

# Copy source files
cp -r ../src/* "${DEPLOY_DIR}/"
cp ../requirements.txt "${DEPLOY_DIR}/"

# Create main.py entry point for Cloud Functions
cat > "${DEPLOY_DIR}/main.py" << 'EOF'
"""Cloud Function entry point."""
import functions_framework
from src.main import cloud_function_handler

@functions_framework.http
def handle_request(request):
    """HTTP Cloud Function entry point."""
    response_body, status_code = cloud_function_handler(request)
    return response_body, status_code
EOF

# Move src files to proper location
mkdir -p "${DEPLOY_DIR}/src"
mv "${DEPLOY_DIR}"/*.py "${DEPLOY_DIR}/src/" 2>/dev/null || true
mv "${DEPLOY_DIR}/src/main.py" "${DEPLOY_DIR}/main.py" 2>/dev/null || true

# Deploy the function
echo -e "${YELLOW}Deploying Cloud Function...${NC}"
gcloud functions deploy "${FUNCTION_NAME}" \
    --gen2 \
    --runtime="${RUNTIME}" \
    --region="${REGION}" \
    --source="${DEPLOY_DIR}" \
    --entry-point=handle_request \
    --trigger-http \
    --allow-unauthenticated \
    --memory="${MEMORY}" \
    --timeout="${TIMEOUT}" \
    --set-env-vars="SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN},SLACK_CHANNEL_ID=${SLACK_CHANNEL_ID},GOOGLE_SHEETS_ID=${GOOGLE_SHEETS_ID},N8N_WEBHOOK_URL=${N8N_WEBHOOK_URL},GOOGLE_CREDENTIALS_JSON=${GOOGLE_CREDENTIALS_JSON:-}"

# Clean up
rm -rf "${DEPLOY_DIR}"

echo -e "${GREEN}Deployment complete!${NC}"

# Get the function URL
FUNCTION_URL=$(gcloud functions describe "${FUNCTION_NAME}" --region="${REGION}" --format="value(serviceConfig.uri)")
echo -e "${GREEN}Function URL: ${FUNCTION_URL}${NC}"

# Create Cloud Scheduler job
echo -e "${YELLOW}Setting up Cloud Scheduler...${NC}"
SCHEDULER_NAME="${FUNCTION_NAME}-scheduler"

# Delete existing scheduler if it exists
gcloud scheduler jobs delete "${SCHEDULER_NAME}" --location="${REGION}" --quiet 2>/dev/null || true

# Create new scheduler job (runs every 4 hours)
gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --schedule="0 */4 * * *" \
    --uri="${FUNCTION_URL}" \
    --http-method=POST \
    --time-zone="Europe/Madrid"

echo -e "${GREEN}Cloud Scheduler configured to run every 4 hours${NC}"
echo -e "${GREEN}=== Deployment Complete ===${NC}"
