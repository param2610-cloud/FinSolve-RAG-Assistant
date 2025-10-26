"""
Vercel serverless function entry point for Flask app
"""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import the Flask app factory
from app import create_app

# Create the Flask app instance
app = create_app()

# Vercel expects the app to be available at the module level
# The app will be called by Vercel's Python runtime
