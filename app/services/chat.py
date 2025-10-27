"""
chat and conversation service
handles conversations,  queries, and rag responses
"""
from flask import Blueprint, request, jsonify, Response, stream_with_context
from app.services.auth import require_auth
from app.services.users import ROLE_PERMISSIONS
from datetime import datetime
import json
import os
import uuid
import time

chat_bp = Blueprint('chat', __name__)

# store chat memories
chat_memories = {}


def save_conversation(user_id: int, conversation_id: str, messages: list, title: str = None):
    """save conversation to json"""
    chat_dir = "resources/database/chat_history"
    os.makedirs(chat_dir, exist_ok=True)
    
    filepath = os.path.join(chat_dir, f"user_{user_id}_conversations.json")
    
    # load existing conversations
    conversations = {}
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            conversations = json.load(f)
    
    # generate title from first user messge if not provided
    if not title and messages:
        first_msg = next((m['content'] for m in messages if m['role'] == 'user'), "new chat")
        title = first_msg[:50] + "..." if len(first_msg) > 50 else first_msg
    
    # save conversation
    conversations[conversation_id] = {
        "title": title or "new chat",
        "messages": messages,
        "timestamp": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat()
    }
    
    with open(filepath, 'w') as f:
        json.dump(conversations, f, indent=2)


def load_conversations(user_id: int):
    """load all conversations for user"""
    chat_dir = "resources/database/chat_history"
    filepath = os.path.join(chat_dir, f"user_{user_id}_conversations.json")
    
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}


def delete_conversation(user_id: int, conversation_id: str):
    """delete a conversation"""
    conversations = load_conversations(user_id)
    if conversation_id in conversations:
        del conversations[conversation_id]
        
        chat_dir = "resources/database/chat_history"
        filepath = os.path.join(chat_dir, f"user_{user_id}_conversations.json")
        with open(filepath, 'w') as f:
            json.dump(conversations, f, indent=2)


@chat_bp.route('/conversations', methods=['GET', 'OPTIONS'])
@require_auth
def get_conversations():
    """get all conversations for user"""
    if request.method == 'OPTIONS':
        return '', 204
    
    user_id = request.user['id']
    conversations = load_conversations(user_id)
    
    # sort by last updated
    sorted_convs = sorted(
        conversations.items(),
        key=lambda x: x[1].get('last_updated', ''),
        reverse=True
    )
    
    return jsonify({
        "conversations": [
            {
                "id": conv_id,
                "title": conv_data['title'],
                "timestamp": conv_data['timestamp'],
                "last_updated": conv_data['last_updated'],
                "message_count": len(conv_data['messages'])
            }
            for conv_id, conv_data in sorted_convs[:20]
        ]
    })


@chat_bp.route('/conversations/<conversation_id>', methods=['GET', 'OPTIONS'])
@require_auth
def get_conversation(conversation_id):
    """get specific conversation"""
    if request.method == 'OPTIONS':
        return '', 204
    
    user_id = request.user['id']
    conversations = load_conversations(user_id)
    
    if conversation_id not in conversations:
        return jsonify({"error": "conversation not found"}), 404
    
    return jsonify({
        "conversation": conversations[conversation_id]
    })


@chat_bp.route('/conversations/<conversation_id>', methods=['DELETE', 'OPTIONS'])
@require_auth
def delete_conversation_endpoint(conversation_id):
    """delete conversation"""
    if request.method == 'OPTIONS':
        return '', 204
    
    user_id = request.user['id']
    delete_conversation(user_id, conversation_id)
    
    # cleanup memory
    if conversation_id in chat_memories:
        del chat_memories[conversation_id]
    
    return jsonify({"message": "conversation deleted"})


@chat_bp.route('/conversations', methods=['POST', 'OPTIONS'])
@require_auth
def create_conversation():
    """create new conversation"""
    if request.method == 'OPTIONS':
        return '', 204
    
    from langchain_core.chat_history import InMemoryChatMessageHistory
    
    conversation_id = str(uuid.uuid4())
    chat_memories[conversation_id] = InMemoryChatMessageHistory()
    
    return jsonify({
        "conversation_id": conversation_id,
        "message": "conversation created"
    })


@chat_bp.route('/conversations/<conversation_id>/save', methods=['POST', 'OPTIONS'])
@require_auth
def save_conversation_endpoint(conversation_id):
    """save conversation history"""
    if request.method == 'OPTIONS':
        return '', 204
    
    user_id = request.user['id']
    data = request.json
    messages = data.get('messages', [])
    title = data.get('title')
    
    save_conversation(user_id, conversation_id, messages, title)
    
    return jsonify({"message": "conversation saved"})


@chat_bp.route('/query', methods=['POST', 'OPTIONS'])
@require_auth
def query():
    """main query endpoint with streaming response"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        from app.utils.rag_engine import stream_rag_response
        from app.utils.query_processor import query_processor
        from langchain_core.chat_history import InMemoryChatMessageHistory
    except ImportError as e:
        print(f"[QUERY] Import error: {str(e)}")
        return jsonify({"error": f"Missing dependency: {str(e)}"}), 500
    
    data = request.json
    question = data.get('question')
    conversation_id = data.get('conversation_id')
    
    if not question:
        return jsonify({"error": "question is required"}), 400
    
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
    
    # get or create chat memory
    if conversation_id not in chat_memories:
        chat_memories[conversation_id] = InMemoryChatMessageHistory()
    
    chat_memory = chat_memories[conversation_id]
    user_role = request.user['role']
    user_id = request.user['id']
    
    # proces query
    processed_query = query_processor.process_query(question)
    
    def generate():
        try:
            for chunk in stream_rag_response(question, user_role, processed_query, chat_memory):
                yield chunk
        except Exception as e:
            print(f"[QUERY] Stream error: {str(e)}")
            yield json.dumps({"type": "error", "content": f"error: {str(e)}"}) + "\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='application/x-ndjson',
        headers={
            'X-Conversation-ID': conversation_id,
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@chat_bp.route('/permissions', methods=['GET', 'OPTIONS'])
@require_auth
def get_permissions():
    """get user permissions"""
    if request.method == 'OPTIONS':
        return '', 204
    
    user_role = request.user['role']
    permissions = ROLE_PERMISSIONS.get(user_role, ["general"])
    
    return jsonify({
        "role": user_role,
        "permissions": permissions
    })
