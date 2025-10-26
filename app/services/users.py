"""
user management service
handles user creation and retrival
"""
from flask import Blueprint, request, jsonify
from app.services.auth import require_auth, hash_password, USERS_DB
import json
import os

users_bp = Blueprint('users', __name__)


def save_users_db(users):
    """save users to json file"""
    users_path = "resources/database/users.json"
    with open(users_path, 'w') as f:
        json.dump(users, f, indent=2)


def load_role_permissions():
    """load role permissions"""
    permissions_path = "resources/database/role_permissions.json"
    if os.path.exists(permissions_path):
        with open(permissions_path, 'r') as f:
            return json.load(f)
    return {}


ROLE_PERMISSIONS = load_role_permissions()


@users_bp.route('', methods=['GET'])
def get_demo_users():
    """get demo users for login page"""
    demo_users = [
        {"id": u['id'], "name": u['name'], "email": u['email'], "role": u['role']}
        for u in USERS_DB[:3]
    ]
    return jsonify({"users": demo_users})


@users_bp.route('/add', methods=['POST'])
@require_auth
def add_user():
    """add new user - manager only"""
    # check if user is manager
    if request.user['role'] not in ['manager', 'Manager']:
        return jsonify({"error": "access denied: only managers can add users"}), 403
    
    data = request.json
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', '').strip()
    
    
    # validaton
    if not all([name, email, password, role]):
        return jsonify({"error": "all fields are required"}), 400
    
    if role not in ['manager', 'hr_specialist', 'employee']:
        return jsonify({"error": "invalid role"}), 400
    
    # check if email already exists
    if any(u['email'] == email for u in USERS_DB):
        return jsonify({"error": "email already exists"}), 400
    
    # create new user
    new_user_id = max([u['id'] for u in USERS_DB]) + 1 if USERS_DB else 1
    new_user = {
        "id": new_user_id,
        "name": name,
        "email": email,
        "password": hash_password(password),
        "role": role
    }
    
    # add to database
    USERS_DB.append(new_user)
    save_users_db(USERS_DB)
    
    return jsonify({
        "message": "user created successfully",
        "user": {
            "id": new_user_id,
            "name": name,
            "email": email,
            "role": role
        }
    }), 201


@users_bp.route('/permissions', methods=['GET'])
@require_auth
def get_permissions():
    """get user permissions"""
    user_role = request.user['role']
    permissions = ROLE_PERMISSIONS.get(user_role, ["general"])
    
    return jsonify({
        "role": user_role,
        "permissions": permissions
    })
