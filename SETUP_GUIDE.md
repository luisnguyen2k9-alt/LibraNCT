# SmartLib Backend - Render Setup (Preferred)

Quick start on Render:

1) Create Web Service from folder `server/`
2) Build: `pip install -r server/requirements.txt`
3) Start: `gunicorn server.app:app --bind 0.0.0.0:$PORT`
4) Env vars: set credentials and `ALLOWED_ORIGINS`; optional `DATA_DIR=/data` if using Render Disk
5) Public URL: `https://<service>.onrender.com` (HTTPS auto by Render)

---

# SmartLib Backend - GamePanel Setup Guide

## 🐍 Backend Setup (GamePanel)

### 📁 Upload Files to GamePanel:
```
server/
├── app.py                 # Main Flask application
├── services.py           # Service functions
├── start.py              # Entry point for GamePanel
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables
├── database.json         # Book database
├── borrowers.json        # Borrow records
├── borrowers.db.json     # Backup
├── fonts/                # Font files
└── README.md            # This file
```

### ⚙️ GamePanel Configuration:

1. **Create Python App** on GamePanel
2. **Set Entry Point**: `start.py`
3. **Port**: 5001 (or let GamePanel assign)
4. **Environment**: Production

### 🔧 Update .env file with your credentials:
```env
ENVIRONMENT=production
HOST=0.0.0.0
PORT=5001
SSL_ENABLED=false

# Firebase Configuration
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=./serviceAccountKey.json

# Email Configuration
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# OCR Configuration
OCR_SPACE_API_KEY=your-ocr-space-api-key

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# CORS Configuration (UPDATE WITH YOUR FRONTEND DOMAIN)
ALLOWED_ORIGINS=https://your-domain.123host.com
```

### 🚀 After Upload:
1. GamePanel will install dependencies automatically
2. Server will start on assigned port
3. Get the server URL (e.g., `https://your-app.gamepanel.com:5001`)

### 📊 Database Status:
- **Books**: 71 books (all available)
- **Borrows**: 0 records (clean start)
- **Ready for production**: ✅

## 🌐 Frontend Setup (123host)

### 📁 Upload Files to 123host:
```
SmartLib/
├── admin/                # Admin panel
├── ar/                   # AR functionality
├── card/                 # Card scanning
├── danhgia/              # Rating system
├── home/                 # Main app
├── login/                # Login page
├── mindmap.html          # Mindmap
├── reset/                # Password reset
├── signup/               # Registration
├── welcome/              # Welcome page
└── index.html            # Main index
```

### 🔧 Update API Endpoints:
Update all API calls in frontend files to point to your GamePanel backend:

**Find and replace in all HTML files:**
```javascript
// OLD:
'https://139.162.35.154:25436/'

// NEW:
'https://your-app.gamepanel.com:5001/'
```

### 📝 Files to Update:
- `home/lending.html` - Book scanning
- `card/index.html` - Card scanning  
- `admin/*.html` - Admin functions
- `home/return.html` - Return books
- All other files with API calls

### 🎯 Final Setup:
1. **Backend**: Running on GamePanel
2. **Frontend**: Hosted on 123host
3. **API calls**: Point to GamePanel backend
4. **CORS**: Configured for 123host domain

## ✅ Ready for Production! 🚀





