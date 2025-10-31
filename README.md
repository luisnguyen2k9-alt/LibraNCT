# SmartLib Server — Deploy on Render

## What you upload
Upload only the `server/` folder as a Render Web Service.

## Start command
```
gunicorn server.app:app --bind 0.0.0.0:$PORT
```

## Requirements
`requirements.txt` includes `gunicorn` and all dependencies.

## Environment variables
Set these in Render:
```
ENVIRONMENT=production
HOST=0.0.0.0
ALLOWED_ORIGINS=https://<your-frontend-domain>
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=./serviceAccountKey.json
EMAIL_ADDRESS=<smtp-email>
EMAIL_PASSWORD=<smtp-app-password>
OCR_SPACE_API_KEY=<key>
CLOUDINARY_CLOUD_NAME=<name>
CLOUDINARY_API_KEY=<key>
CLOUDINARY_API_SECRET=<secret>
# If using Render Disk
DATA_DIR=/data
```

## Persistent data (Render Disk)
- Attach a Disk and mount it to `/data`.
- The app reads/writes JSON via `DATA_DIR` (defaults to this folder). Files:
  - `database.json`
  - `borrowers.json`

## TLS/HTTPS
Do not enable SSL in Flask. Render terminates HTTPS automatically.

## Current data state
- `borrowers.json`: reset to empty (clean start)
- `database.json`: existing titles preserved; mark borrow states as needed after launch

## Frontend
Point all API requests to your Render URL: `https://<your-service>.onrender.com`

---
Ready to deploy 🚀