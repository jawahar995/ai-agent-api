from src.database.mongo import db
from bson import ObjectId
from datetime import datetime


class DataService:

    @staticmethod
    async def find_one(query: dict = {}, projection: dict = None):
        return await db["datas"].find_one(query, projection)

    
    @staticmethod
    async def find_by_id(id: str, projection: dict = None):
        return await db["datas"].find_one({"_id": ObjectId( id)}, projection)

    
    @staticmethod
    async def update(query: dict, update: dict):
        await db["datas"].update_one(query, {"$set": update})

    @staticmethod
    async def update_by_id(id: str, update: dict):
        await db["datas"].update_one({"_id": ObjectId(id)}, {"$set": update})

    @staticmethod
    async def update_many(query: dict, update: dict):
        await db["datas"].update_many(query, {"$set": update})
        
