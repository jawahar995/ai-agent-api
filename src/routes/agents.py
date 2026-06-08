from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from livekit.api import AccessToken, VideoGrants, LiveKitAPI, CreateAgentDispatchRequest
from src.services.agent_fn import AgentFunction
from src.services.user_services import UserService
from src.utils.serializer import serialize_doc
from src.utils.config import config

router = APIRouter(prefix="/agent", tags=["agent"])

class TokenRequest(BaseModel):
    room_name: str
    participant_name: str
    agent_type: str = "chat"  # "chat" or "voice"
class CreateAgentRequest(BaseModel):
    room_name: str
    participant_name: str
@router.get("/status")
async def get_agent_status():
    return JSONResponse(content={"status": "Agent is running"}, status_code=200)

@router.post("/token")
async def get_token(req: TokenRequest):
    try:
        # 1. Generate client joining token
        token = AccessToken(
            api_key=config.livekit_api_key,
            api_secret=config.livekit_api_secret
        )
        token.with_identity(req.participant_name)
        grants = VideoGrants(
            room_join=True,
            room=req.room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True
        )
        token.with_grants(grants)
        
        # 2. Trigger explicit agent dispatch
        # Convert websocket URL to HTTP/HTTPS for API calls
        api_url = config.livekit_server_url
        if api_url.startswith("wss://"):
            api_url = api_url.replace("wss://", "https://")
        elif api_url.startswith("ws://"):
            api_url = api_url.replace("ws://", "http://")
            
        agent_name = "chat-agent" if req.agent_type == "chat" else "voice-agent"
        
        lkapi = LiveKitAPI(
            url=api_url,
            api_key=config.livekit_api_key,
            api_secret=config.livekit_api_secret
        )
        try:
            await lkapi.agent_dispatch.create_dispatch(
                CreateAgentDispatchRequest(
                    agent_name=agent_name,
                    room=req.room_name
                )
            )
            print(f"Triggered explicit dispatch for '{agent_name}' in room '{req.room_name}'")
        except Exception as dispatch_err:
            print(f"Agent dispatch failed: {dispatch_err}")
        finally:
            await lkapi.aclose()
            
        return JSONResponse(
            content={
                "token": token.to_jwt(),
                "server_url": config.livekit_server_url
            },
            status_code=200
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/create/{agent_id}")
async def create_agent(agent_id: str, req: CreateAgentRequest):
    agent_data = await AgentFunction.find_by_id(agent_id, projection={"_id": 1, "name": 1, "agent_type": 1, "llm_settings": 1, "bot_settings": 1, "kb_id": 1, "speech_settings": 1,"created_by": 1})
    if not agent_data:
        raise HTTPException(status_code=404, detail="Agent not found")
    # once the agent is Exist means form a JSON to update a agent session    
    user_Details = await UserService.find_by_id(agent_data.get("created_by"), projection={"_id": 1, "configuration": 1})
    llm_settings = agent_data.get("llm_settings", {})
    if not llm_settings.get("api_key"):
        llm_settings["api_key"] = user_Details.get("configuration", {}).get("llm_key", "")
    if not llm_settings.get("provider"):
        llm_settings["provider"] = user_Details.get("configuration", {}).get("llm_provider", "openai")
    session_data = {
        "agent_id": str(agent_data.get("_id")),
        "agent_type": agent_data.get("agent_type", "chat"),
        "llm_settings": agent_data.get("llm_settings", {}),
        "kb_id": agent_data.get("kb_id"),
        "speech_settings": agent_data.get("speech_settings", {}),
        "welcome_message": agent_data.get("bot_settings", {}).get("welcome_message") or agent_data.get("bot_settings", {}).get("greeting_message", "Hello! How can I assist you today?"),
        "user_id": str(agent_data.get("created_by")),
        "fallback_message": agent_data.get("bot_settings", {}).get("fallback_message", "I'm sorry, I didn't understand that. Can you please rephrase?"),
        "system_prompt": agent_data.get("system_prompt", "You are a helpful assistant. Keep responses brief."),
        "tools": []
    }
    if agent_data.get("kb_id"):
        embedding_type = llm_settings.get("provider", "openai").lower()
        if embedding_type == "google":
            embedding_type = "google_genai"
        session_data["tools"].append({
            "name": "retriever",
            "kb_id": str(agent_data.get("kb_id")),
            "db_type": config.vector_store_type,
            "embedding_type": embedding_type,
            "embedding_api_key": llm_settings.get("api_key", ""),
            "embedding_model": llm_settings.get("embedding_model", "")
        })
    session_id = await AgentFunction.create_session(session_data)
    token = AccessToken(
            api_key=config.livekit_api_key,
            api_secret=config.livekit_api_secret
        )
    token.with_identity(req.participant_name)
    grants = VideoGrants(
            room_join=True,
            room=req.room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True
        )
    token.with_grants(grants)
    api_url = config.livekit_server_url
    if api_url.startswith("wss://"):
        api_url = api_url.replace("wss://", "https://")
    elif api_url.startswith("ws://"):
        api_url = api_url.replace("ws://", "http://")
    #agent name should be the name registered by the worker ("chat-agent" or "voice-agent")
    agent_type = agent_data.get("agent_type", "chat")
    agent_name = "chat-agent" if agent_type == "chat" else "voice-agent"
    lkapi = LiveKitAPI(
            url=api_url,
            api_key=config.livekit_api_key,
            api_secret=config.livekit_api_secret
        )
    try:
        await lkapi.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                agent_name=agent_name,
                room=req.room_name,
                metadata=session_id
            )
        )
        print(f"Triggered explicit dispatch for '{agent_name}' in room '{req.room_name}' with session ID '{session_id}'")
    except Exception as dispatch_err:
        print(f"Agent dispatch failed: {dispatch_err}")
    finally:        
        await lkapi.aclose()
    print(f"Creating agent with ID: {agent_data.get('_id')}")
    return JSONResponse(
            content={
                "token": token.to_jwt(),
                "server_url": config.livekit_server_url
            },
            status_code=200
        )