import redis
import os
import json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Get Redis configuration from environment variables
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# Create Redis client
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Set default expiration time for cache entries (1 hour)
CACHE_EXPIRATION = 3600

class SessionManager:
    PREFIX = "food_analysis:"
    
    @staticmethod
    def create_session(data: dict) -> str:
        """Create a new session with data"""
        from uuid import uuid4
        session_id = str(uuid4())
        key = f"{SessionManager.PREFIX}{session_id}"
        
        # Add timestamp to the data
        data['created_at'] = datetime.now().isoformat()
        
        redis_client.setex(
            key,
            CACHE_EXPIRATION,
            json.dumps(data)
        )
        return session_id
    
    @staticmethod
    def get_session(session_id: str) -> dict:
        """Retrieve session data"""
        key = f"{SessionManager.PREFIX}{session_id}"
        data = redis_client.get(key)
        return json.loads(data) if data else None
    
    @staticmethod
    def delete_session(session_id: str) -> bool:
        """Delete a session"""
        key = f"{SessionManager.PREFIX}{session_id}"
        return redis_client.delete(key) > 0
    
    @staticmethod
    def cleanup_old_files():
        """Clean up old uploaded files"""
        import os
        from pathlib import Path
        
        # Get all sessions
        keys = redis_client.keys(f"{SessionManager.PREFIX}*")
        active_files = set()
        
        # Collect active files
        for key in keys:
            data = redis_client.get(key)
            if data:
                session_data = json.loads(data)
                if session_data.get('uploaded_image'):
                    active_files.add(session_data['uploaded_image'])
        
        # Clean up unused files
        upload_dir = Path('static/uploads')
        if upload_dir.exists():
            for file_path in upload_dir.iterdir():
                if file_path.name != '.gitkeep' and file_path.name not in active_files:
                    try:
                        file_path.unlink()
                    except Exception as e:
                        print(f"Error deleting file {file_path}: {e}")

# Cleanup task function
async def cleanup_task():
    """Periodic cleanup task"""
    import asyncio
    while True:
        try:
            SessionManager.cleanup_old_files()
        except Exception as e:
            print(f"Error in cleanup task: {e}")
        await asyncio.sleep(3600)  # Run every hour 