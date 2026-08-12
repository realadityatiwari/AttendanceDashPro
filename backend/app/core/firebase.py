import os
import logging
import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger(__name__)

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK.
    Safe to call multiple times (e.g., during reloads).
    Requires GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_PATH.
    """
    if firebase_admin._apps:
        return firebase_admin.get_app()

    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not service_account_path or not os.path.exists(service_account_path):
        logger.error("CRITICAL: Firebase service account credentials not found. Authentication will fail.")
        # We do not crash the app, but auth endpoints will fail when verification is attempted.
        return None

    try:
        cred = credentials.Certificate(service_account_path)
        app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully.")
        return app
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return None
