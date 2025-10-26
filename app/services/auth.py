"""
authentication service
handles login, token generation, and user verification
"""
from flask import Blueprint, request, jsonify
from functools import wraps
import hashlib
import jwt
from datetime import datetime, timedelta
import os

auth_bp = Blueprint('auth', __name__)

# load users from json
def load_users():
    import json
    users_path = "resources/database/users.json"
    if os.path.exists(users_path):
        with open(users_path, 'r') as f:
            return json.load(f)
    return []


USERS_DB = load_users()


def hash_password(password: str) -> str:
    """hash password using sha256"""
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate_user(email: str, password: str):
    """check if user credentials are valid"""
    password_hash = hash_password(password)
    for user in USERS_DB:
        if user['email'] == email and user['password'] == password_hash:
            return user
    return None


def generate_token(user_id: int):
    """create jwt token for user"""
    for user in USERS_DB:
        if user['id'] == user_id:
            payload = {
                "id": user['id'],
                "role": user['role'],
                "exp": datetime.utcnow() + timedelta(hours=8)
            }
            secret = os.getenv("JWT_SECRET_KEY", "n5jlk3n45jk3n5kjn")
            token = jwt.encode(payload, secret, algorithm='HS256')
            return token, user
    return None, None


def verify_token(token: str):
    """verify jwt token"""
    try:
        secret = os.getenv("JWT_SECRET_KEY", "n5jlk3n45jk3n5kjn")
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("token has expired")
    except jwt.InvalidTokenError:
        raise Exception("invalid or expired token")


def require_auth(f):
    """decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "no authorization header"}), 401
        
        try:
            token = auth_header.split(" ")[1] if " " in auth_header else auth_header
            payload = verify_token(token)
            request.user = payload
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": str(e)}), 401
    
    return decorated_function


@auth_bp.route('/login', methods=['POST'])
def login():
    """login endpoint"""
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    
    # check credentials
    user = authenticate_user(email, password)
    if not user:
        return jsonify({"error": "invalid credentials"}), 401
    
    # generate token
    token, user_info = generate_token(user['id'])
    if not token:
        return jsonify({"error": "failed to generate token"}), 500
    
    return jsonify({
        "token": token,
        "user": {
            "id": user_info['id'],
            "name": user_info['name'],
            "email": user_info['email'],
            "role": user_info['role']
        }
    })
