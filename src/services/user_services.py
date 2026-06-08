from src.database.mongo import db
from bson import ObjectId
from datetime import datetime

class UserService:

    
    @staticmethod
    async def update_one(query: dict, update: dict):
        update["updated_at"] = datetime.now()
        return await db["users"].update_one(query, {"$set": update})

    @staticmethod
    async def update_by_id(id: str, update: dict):
        update["updated_at"] = datetime.now()
        return await db["users"].update_one({"_id": ObjectId(id)}, {"$set": update})

    @staticmethod
    async def update_many(query: dict, update: dict):
        update["updated_at"] = datetime.now()
        return await db["users"].update_many(query, {"$set": update})

    @staticmethod
    async def find_one(query: dict = {}, projection: dict = None):
        return await db["users"].find_one(query, projection)

    @staticmethod
    async def find_by_id(id: str, projection: dict = None):
        return await db["users"].find_one({"_id": ObjectId(id)}, projection)