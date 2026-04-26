#!/bin/bash
set -e

# Replace with your actual Google Cloud Project ID
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="ai-travel-marketplace"

echo "Building and submitting Docker image to Google Cloud Build..."
gcloud builds submit --tag gcr.io/${PROJECT_ID}/${SERVICE_NAME}

echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image gcr.io/${PROJECT_ID}/${SERVICE_NAME} \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars="GOOGLE_ADK_MODEL=gemini-2.5-flash" \
  --update-secrets="GOOGLE_API_KEY=YOUR_SECRET_NAME_IN_SECRET_MANAGER:latest"

echo "Deployment complete! Don't forget to configure your GOOGLE_API_KEY."
