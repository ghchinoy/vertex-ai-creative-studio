#!/bin/bash
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

# Default SA name from main.tf
SA_NAME="service-creative-studio"
PROJECT_ID=$(gcloud config get-value project)

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID is not set. Please run 'gcloud config set project <PROJECT_ID>'"
  exit 1
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Adding Firebase and Firestore roles to ${SA_EMAIL} in project ${PROJECT_ID}..."

ROLES=(
  "roles/firebaseauth.admin"
  "roles/firebase.admin"
  "roles/datastore.user"
)

for ROLE in "${ROLES[@]}"; do
  echo "Binding ${ROLE}..."
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --no-user-output-enabled
done

echo "Done."
