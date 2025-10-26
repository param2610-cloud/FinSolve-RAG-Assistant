"""
data schemas for validation
"""
from typing import Optional, List, Dict, Any


class UserSchema:
    """user data schema"""
    
    def __init__(self, id: int, name: str, email: str, role: str):
        self.id = id
        self.name = name
        self.email = email
        self.role = role
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role
        }


class MessageSchema:
    """message schema for chat"""
    
    def __init__(self, role: str, content: str, timestamp: str, 
                 type: Optional[str] = None, data: Optional[Any] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.type = type
        self.data = data
    
    def to_dict(self):
        result = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }
        if self.type:
            result["type"] = self.type
        if self.data:
            result["data"] = self.data
        return result


class ConversationSchema:
    """conversation schema"""
    
    def __init__(self, id: str, title: str, messages: List[Dict], 
                 timestamp: str, last_updated: str):
        self.id = id
        self.title = title
        self.messages = messages
        self.timestamp = timestamp
        self.last_updated = last_updated
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "messages": self.messages,
            "timestamp": self.timestamp,
            "last_updated": self.last_updated,
            "message_count": len(self.messages)
        }
