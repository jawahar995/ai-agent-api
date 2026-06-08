from src.database.mongo import db
from bson import ObjectId
from datetime import datetime


class AgentFunction:

    @staticmethod
    async def find(query: dict = {}, projection: dict = None, sort: list = None):
        cursor = db["agents"].find(query, projection)
        if sort:
            cursor = cursor.sort(sort)
        return await cursor.to_list(length=None)
    
    @staticmethod
    async def find_one(query: dict = {}, projection: dict = None):
        return await db["agents"].find_one(query, projection)

    @staticmethod
    async def find_by_id(agent_id: str, projection: dict = None):
        return await db["agents"].find_one({"_id": ObjectId(agent_id)}, projection)
    

    @staticmethod
    async def create_session(agent_data: dict):
        agent_data["created_at"] = datetime.utcnow()
        result = await db["agents_sessions"].insert_one(agent_data)
        return str(result.inserted_id)


    @staticmethod
    async def update_session(agent_id: str, update_data: dict):
        update_data["updated_at"] = datetime.utcnow()
        result = await db["agents_sessions"].update_one(
            {"_id": ObjectId(agent_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0 
    @staticmethod
    async def delete_session(agent_id: str):
        result = await db["agents_sessions"].delete_one({"_id": ObjectId(agent_id)})
        return result.deleted_count > 0
    
    @staticmethod
    async def find_sessions(query: dict = {}, projection: dict = None, sort: list = None):
        cursor = db["agents_sessions"].find(query, projection)
        if sort:
            cursor = cursor.sort(sort)
        return await cursor.to_list(length=None)
    @staticmethod
    async def find_session_by_id(session_id: str, projection: dict = None):
        return await db["agents_sessions"].find_one({"_id": ObjectId(session_id)}, projection)  