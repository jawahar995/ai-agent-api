import os
from src.services.agent_fn import AgentFunction
from asyncio import base_futures
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from src.utils.auth import validate_token
# pyrefly: ignore [missing-import]
from bson import ObjectId
from src.services.data import DataService
from src.services.embedded_fn import embedding_cost_calculate, ingest_data_into_vector_db

router = APIRouter(prefix="/embedded", tags=["embedded"])




# @router.get("/embedded/{agent_name}")
# async def get_embedded_code(agent_name: str, theme: str = "light"):
#     agent = await AgentFunction.find_by_name(agent_name)
#     if not agent:
#         raise HTTPException(status_code=404, detail="Agent not found")
#     code = generate_embedded_code(agent, theme)
#     return JSONResponse({"code": code})

@router.get("/estimate/{file_id}")
async def ingest_data(file_id: str, user: dict = Depends(validate_token)):
    try:
        query = {"_id": ObjectId(file_id), "user_id": user.get("_id")}
        doc = await DataService.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="File not found")
        agentDetails = await AgentFunction.find_by_id(doc.get("agent_id")) 
        if not agentDetails:
            raise HTTPException(status_code=404, detail="Agent not found")  
        settings = agentDetails.get("llm_settings") 
        embedding_cost = await embedding_cost_calculate(doc.get("src_url"), settings.get("embedding_model"))
        await DataService.update({"_id": ObjectId(file_id), "user_id": user.get("_id")}, {"total_tokens": embedding_cost.get("total_tokens"), "estimated_cost": embedding_cost.get("total_cost")})
        return JSONResponse(embedding_cost, status_code=200)    
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500) 
    


@router.post("/test-estimate")
async def test_estimate(payload: dict):
    try:
        url = payload.get("url")
        model = payload.get("model")
        embedding_cost = await embedding_cost_calculate(url, model)
        return JSONResponse(embedding_cost, status_code=200)    
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500) 


@router.get("/ingest/{file_id}")
async def ingest_file(file_id: str, background_tasks: BackgroundTasks, user: dict = Depends(validate_token)):
    try:
        query = {"_id": ObjectId(file_id), "user_id": user.get("_id")}
        doc = await DataService.find_one(query)
        if not doc:
            raise HTTPException(status_code=404, detail="File not found")
            
        agentDetails = await AgentFunction.find_by_id(doc.get("agent_id")) 
        if not agentDetails:
            raise HTTPException(status_code=404, detail="Agent not found")  
            
        settings = agentDetails.get("llm_settings") or {}
        
        # Before the Embedding Prepare the data like Provider and API key from user table and Embedding Model from agent table
        user_settings = user.get("settings") or {}
        user_llm = user_settings.get("llm") or {}
        
        llm_details = {
            "provider": user_llm.get("provider") or "openAI",
            "api_key": user_llm.get("apikey") or user_llm.get("api_key") or os.getenv("OPENAI_API_KEY"),
            "embedding_model": settings.get("embedding_model") or "text-embedding-3-small",
            "kb_id": str(doc.get("kb_id")),
            "file_id": file_id,
            "file_name": doc.get("name")
        }
        
        # Run in the background to ingest the data into the vector DB
        background_tasks.add_task(
            ingest_data_into_vector_db,
            llm_details,
            doc.get("src_url")
        )
        await DataService.update({"_id": ObjectId(file_id)}, {"status": 2})
        return JSONResponse({
            "message": "Ingestion started in background",
            "status": 2
        }, status_code=200)
        
    except HTTPException as http_ex:
        await DataService.update({"_id": ObjectId(file_id)}, {"status": 4})
        raise http_ex
    except Exception as e:
        await DataService.update({"_id": ObjectId(file_id)}, {"status": 4})
        return JSONResponse({"error": str(e)}, status_code=500) 
