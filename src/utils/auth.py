from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from src.utils.config import config
import jwt
from fastapi import Depends, HTTPException
from src.services.user_services import UserService

security = HTTPBearer()

async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload  = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
        print("Decoded JWT payload:", payload)
        
        user_id = payload.get("user_id") or payload.get("id") or payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token payload is missing user_id, id, or sub identifier")
            
        user = await UserService.find_one({"_id": ObjectId(user_id), "is_active": True, "is_archived": False})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")