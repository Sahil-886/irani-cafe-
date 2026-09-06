import os
import sys

# Ensure root directory is on Python path so app module can be imported
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import CafeHandler, init_db

# Initialize database in /tmp for Vercel serverless environment
init_db()

class handler(CafeHandler):
    pass
