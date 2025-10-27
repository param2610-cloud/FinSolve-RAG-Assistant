"""
main entry point for the flask application
"""
import os
from dotenv import load_dotenv

# load environment vars
load_dotenv()

from app import create_app

app = create_app()


if __name__ == '__main__':
    # run the app
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    print(f"🚀 Starting FinSolve RAG Assistant...")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )
