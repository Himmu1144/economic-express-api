#!/bin/sh
set -eu
# Call after the Render service is live. Does not query the app database.
# Usage: sh scripts/configure-demo-scheduler.sh https://SERVICE.onrender.com
backend_url=${1:?Pass the deployed HTTPS Render backend URL}
case "$backend_url" in
  https://*.onrender.com) ;;
  *) echo 'Expected an HTTPS onrender.com service URL without a trailing slash.' >&2; exit 1 ;;
esac
project_id=${GCLOUD_PROJECT:-bcrm121}
region=${SCHEDULER_REGION:-asia-southeast1}
job_name=economic-express-demo-health
if gcloud scheduler jobs describe "$job_name" --project="$project_id" --location="$region" >/dev/null 2>&1; then
  command_action=update
else
  command_action=create
fi
gcloud scheduler jobs "$command_action" http "$job_name" \
  --project="$project_id" --location="$region" \
  --schedule='*/10 * * * *' --time-zone='Asia/Kolkata' \
  --uri="$backend_url/health/" --http-method=GET \
  --attempt-deadline=180s --max-retry-attempts=2 \
  --description='Temporary Economic.Express demo liveness check. No database access.' \
  --quiet
gcloud scheduler jobs run "$job_name" --project="$project_id" --location="$region"
