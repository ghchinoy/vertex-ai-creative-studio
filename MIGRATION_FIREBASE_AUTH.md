# Migration Guide: Firebase Authentication & Direct GCS Access

This guide outlines the steps required to migrate an existing GenMedia Creative Studio installation to the **Firebase Authentication** system, enabling direct browser-to-GCS media streaming and robust session management.

## 1. Prerequisites

*   **Firebase Project:** An active project with **Authentication** (Google provider) and **Firestore** (Native Mode) enabled.
*   **GCS Bucket:** Your media bucket (e.g., `creative-studio-${PROJECT_ID}-assets`).

## 2. Infrastructure & IAM

The Creative Studio service account and the Firebase Service Agent both require specific permissions.

### Service Account Roles
Run the provided script to grant the Creative Studio SA permissions to verify tokens and manage Firestore:
```bash
./infra/add_firebase_iam_roles.sh
```

### Firebase Service Agent Roles
The Firebase Storage Service Agent needs `Storage Admin` to "sign" and resolve `gs://` URIs for the browser.
```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

gcloud storage buckets add-iam-policy-binding gs://your-bucket-name \
    --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-firebasestorage.iam.gserviceaccount.com" \
    --role="roles/storage.admin"
```

### Firestore Indexes
Filtering by user email and media type requires composite indexes. These are managed in `main.tf`, but can be created manually if needed:
```bash
gcloud firestore indexes composite create \
  --project=your-project-id \
  --database=create-studio-asset-metadata \
  --collection-group=genmedia \
  --field-config=user_email=ASCENDING,field-config=media_type=ASCENDING,field-config=timestamp=DESCENDING
```

## 3. GCS Bucket Setup

### Import to Firebase
1.  Go to **Firebase Console** > **Storage**.
2.  Click **"Add bucket"** or **"Import existing Google Cloud Storage buckets"**.
3.  Select your asset bucket.

### Configure CORS
The browser requires a CORS policy to fetch media directly from GCS.
```bash
echo '[{
  "origin": ["http://localhost:8080", "https://*.cloudshell.dev"],
  "method": ["GET", "HEAD", "OPTIONS"],
  "responseHeader": ["Content-Type", "Authorization", "Content-Length"],
  "maxAgeSeconds": 3600
}]' > cors.json

gcloud storage buckets update gs://your-bucket-name --cors-file=cors.json
```

### Storage Security Rules
Ensure the imported bucket allows authenticated reads. In **Firebase Console** > **Storage** > **Rules**:
```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /{allPaths=**} {
      allow read: if request.auth != null;
    }
  }
}
```

## 4. Application Configuration

### Environment Variables (.env)
Populate your Firebase Web Config values and ensure bucket names are consistent:
```bash
# Firebase Web Config
FIREBASE_API_KEY="..."
FIREBASE_AUTH_DOMAIN="..."
FIREBASE_PROJECT_ID="..."
FIREBASE_STORAGE_BUCKET="creative-studio-your-project-id-assets"
FIREBASE_APP_ID="..."

# Ensure buckets match your actual GCS bucket names
GENMEDIA_BUCKET="creative-studio-your-project-id-assets"

# Direct Access vs Proxy
# Set to false to use direct Browser-to-GCS streaming (Offloads app server)
USE_MEDIA_PROXY=false

# Domain Allowlist
# Comma-separated list of domains allowed to access the app (e.g., google.com, example.com)
DOMAIN_ALLOWLIST="google.com"
```

### Content Security Policy (CSP)
The application handles CSP automatically in `main.py`, but ensure these are allowed if using a custom gateway:
*   **script-src:** `https://www.gstatic.com`, `https://apis.google.com`
*   **connect-src:** `https://*.googleapis.com`, `https://*.firebaseio.com`, `https://www.gstatic.com`
*   **frame-src:** `https://*.firebaseapp.com`, `https://*.firebaseauth.com`, `https://accounts.google.com`
*   **img-src/media-src:** `https://firebasestorage.googleapis.com`

## 5. New Authentication Flow

*   **Redirection:** Unauthenticated users are now automatically redirected to the `/welcome` page.
*   **Identity Propagation:** The FastAPI middleware now injects the verified Firebase identity into the `X-Goog-Authenticated-User-Email` header, ensuring all Mesop pages and components correctly identify the user.
*   **Direct GCS:** UI components like `media_tile` and `image_thumbnail` now resolve `gs://` URIs directly via the Firebase SDK, removing the need for an application-level media proxy.

## 6. Development Verification

1.  **Identity:** Sign in on the `/welcome` page and verify your email appears in the app header and config page.
2.  **Direct Access:** Open browser DevTools > Network. Verify images are being resolved via `firebasestorage.googleapis.com`.
3.  **Metadata:** Ensure new generations in Firestore correctly attribute `user_email` to your authenticated address.
