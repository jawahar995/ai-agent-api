from src.database.mongo import db
from bson import ObjectId
from datetime import datetime
import tiktoken

try:
    _encoding = tiktoken.get_encoding("cl100k_base")
except Exception:
    _encoding = None


def count_tokens(text: str) -> int:
    if not text:
        return 0
    if _encoding:
        return len(_encoding.encode(text))
    return len(text.split())


class HistoryService:

    @staticmethod
    async def create_master(
        session_id: str,
        agent_id: str | ObjectId | None,
        agent_type: str,
        user_id: str | None = None
    ) -> ObjectId:
        if isinstance(agent_id, str) and len(agent_id) == 24:
            try:
                agent_id = ObjectId(agent_id)
            except Exception:
                pass
        
        doc = {
            "agent_id": agent_id if isinstance(agent_id, ObjectId) else None,
            "session_id": session_id,
            "llm_token": 0,
            "stt_token": 0,
            "tts_token": 0,
            "user_id": user_id,
            "agent_type": agent_type,
            "created_at": datetime.utcnow()
        }
        result = await db["history_masters"].insert_one(doc)
        return result.inserted_id

    @staticmethod
    async def update_master_user(master_id: ObjectId, user_id: str):
        await db["history_masters"].update_one(
            {"_id": master_id},
            {"$set": {"user_id": user_id}}
        )

    @staticmethod
    async def update_master_tokens(
        master_id: ObjectId,
        llm_tokens_add: int = 0,
        stt_tokens_add: int = 0,
        tts_tokens_add: int = 0
    ):
        update_fields = {}
        if llm_tokens_add:
            update_fields["llm_token"] = llm_tokens_add
        if stt_tokens_add:
            update_fields["stt_token"] = stt_tokens_add
        if tts_tokens_add:
            update_fields["tts_token"] = tts_tokens_add
            
        if update_fields:
            await db["history_masters"].update_one(
                {"_id": master_id},
                {"$inc": update_fields}
            )

    @staticmethod
    async def add_message(
        master_id: ObjectId,
        human: str,
        agent: str,
        input_tokens: int,
        output_tokens: int,
        response_time: str
    ):
        doc = {
            "history_master_id": master_id,
            "human": human,
            "agent": agent,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "response_time": response_time,
            "created_at": datetime.utcnow()
        }
        await db["history_messages"].insert_one(doc)
        
        # Increment llm_token in master record
        total_msg_tokens = input_tokens + output_tokens
        await HistoryService.update_master_tokens(master_id, llm_tokens_add=total_msg_tokens)
