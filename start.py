#!/usr/bin/env python3
# SmartLib Startup Script for GamePanel
import os
import sys
import logging
from pathlib import Path

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("🚀 Starting SmartLib Server...")
        
        # Import và chạy Flask app
        from app import app
        
        # Chạy server
        app.run(
            host='0.0.0.0',
            port=int(os.getenv('PORT', 5001)),
            debug=False,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

