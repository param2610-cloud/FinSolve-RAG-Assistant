"""
Flask app initialization
"""
from flask import Flask
from flask_cors import CORS
import os


def create_app():
    # init flask app
    app = Flask(__name__, 
                static_folder='../resources/static',
                template_folder='../resources/static')
    
    # enable cors for api calls
    CORS(app)
    
    # load config
    app.config['SECRET_KEY'] = os.getenv("JWT_SECRET_KEY", "n5jlk3n45jk3n5kjn")
    app.config['JWT_EXPIRATION_HOURS'] = 8
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16mb max file size
    
    
    # register blueprints
    from app.services.auth import auth_bp
    from app.services.documents import docs_bp
    from app.services.chat import chat_bp
    from app.services.users import users_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(docs_bp, url_prefix='/api/documents')
    app.register_blueprint(chat_bp, url_prefix='/api')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    
    # static routes
    @app.route('/')
    def index():
        from flask import send_from_directory
        return send_from_directory('../resources/static', 'index.html')
    
    @app.route('/<path:path>')
    def serve_static(path):
        from flask import send_from_directory
        return send_from_directory('../resources/static', path)
    
    
    # health check
    @app.route('/api/health')
    def health():
        from flask import jsonify
        from datetime import datetime
        from app.utils.rag_engine import vector_store
        from app.utils.query_processor import query_processor
        from app.utils.hr_helper import hr_helper
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "vector_store": vector_store is not None,
                "query_processor": query_processor.nlp is not None,
                "hr_data": hr_helper.df is not None
            }
        })
    
    # initialize resources before first request
    @app.before_request
    def init_resources():
        if not hasattr(app, '_initialized'):
            from app.utils.rag_engine import initialize_vector_store
            
            initialize_vector_store()
            app._initialized = True
    
    
    return app
