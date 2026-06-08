import os
import asyncio
from livekit.agents import JobContext, AgentSession, Agent, MetricsCollectedEvent, UserInputTranscribedEvent
from livekit.plugins import openai, deepgram, silero
from livekit.plugins.langchain import LLMAdapter
from src.services.agent_fn import AgentFunction
from src.agents.graph.builder import build_graph
from src.services.history import HistoryService, count_tokens

async def voice_entrypoint(ctx: JobContext):
    # Establish connection to the LiveKit room
    await ctx.connect()
    
    # Attempt to load agent configuration from MongoDB using session_id in job metadata,
    # or fallback to room metadata or room name as agent_id
    agent_data = None
    session_id = ctx.job.metadata
    session_data = None
    if session_id and len(session_id) == 24 and all(c in "0123456789abcdefABCDEF" for c in session_id):
        try:
            session_data = await AgentFunction.find_session_by_id(session_id)
        except Exception as e:
            print(f"Failed to fetch session data for id '{session_id}': {e}")

    if session_data:
        agent_data = {
            "_id": session_data.get("agent_id"),
            "name": f"Session-{session_id}",
            "provider": session_data.get("llm_settings", {}).get("provider", "openai"),
            "llm_settings": session_data.get("llm_settings", {}),
            "system_prompt": session_data.get("system_prompt"),
            "speech_settings": session_data.get("speech_settings", {}),
            "kb_id": session_data.get("kb_id"),
            "welcome_message": session_data.get("welcome_message"),
            "tools": session_data.get("tools", [])
        }
    else:
        agent_id = ctx.room.metadata or ctx.room.name
        if agent_id:
            try:
                # Check if agent_id is a valid ObjectId (24 hex characters)
                if len(agent_id) == 24 and all(c in "0123456789abcdefABCDEF" for c in agent_id):
                    agent_data = await AgentFunction.find_by_id(agent_id)
            except Exception as e:
                print(f"Failed to fetch agent data for id '{agent_id}': {e}")
            
    if agent_data and "tools" not in agent_data and agent_data.get("kb_id"):
        db_llm = agent_data.get("llm_settings", {})
        embedding_type = db_llm.get("provider", "openai").lower()
        if embedding_type == "google":
            embedding_type = "google_genai"
        agent_data["tools"] = [{
            "name": "retriever",
            "kb_id": str(agent_data.get("kb_id")),
            "embedding_type": embedding_type,
            "embedding_api_key": db_llm.get("api_key", ""),
            "embedding_model": db_llm.get("embedding_model", "")
        }]

    # Try to get remote participant identity
    remote_participants = [p.identity for p in ctx.room.remote_participants.values()]
    user_id = remote_participants[0] if remote_participants else None

    # Create history_master record
    try:
        master_id = await HistoryService.create_master(
            session_id=await ctx.room.sid,
            agent_id=agent_data.get("_id") if agent_data else None,
            agent_type="voice",
            user_id=user_id
        )
        print(f"Created voice history master record with ID: {master_id}")
    except Exception as history_err:
        print(f"Failed to create history master: {history_err}")
        master_id = None

    # Define agent configuration using database settings or fallback defaults
    if not agent_data:
        print("Using default fallback agent configuration")
        agent_config = {
            "llm": {
                "provider": "openai",
                "llm_settings": {
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "chat_model": "gpt-4o-mini",
                    "temperature": 0.7
                }
            },
            "system_prompt": "You are a voice-based AI assistant. Keep responses short, direct, and conversational.",
        }
    else:
        print(f"Loaded agent configuration: {agent_data.get('name')}")
        db_llm = agent_data.get("llm_settings", {})
        agent_config = {
            "llm": {
                "provider": agent_data.get("provider", "openai"),
                "llm_settings": {
                    "api_key": db_llm.get("api_key", os.getenv("OPENAI_API_KEY")),
                    "chat_model": db_llm.get("chat_model", "gpt-4o-mini"),
                    "temperature": db_llm.get("temperature", 0.7)
                }
            },
            "system_prompt": agent_data.get("system_prompt", "You are a helpful voice assistant. Keep answers brief."),
            "tools": agent_data.get("tools", [])
        }
        
    # Build LangGraph and adapt to LiveKit LLM
    try:
        graph = build_graph(agent_config)
        llm = LLMAdapter(graph)
    except Exception as e:
        print(f"Failed to build LangGraph from config: {e}. Falling back to standard OpenAI LLM.")
        llm = openai.LLM(model="gpt-4o-mini")

    # Initialize STT, VAD, and TTS plugins
    stt = deepgram.STT()
    vad = silero.VAD.load()
    tts = openai.TTS()

    # Orchestrate Voice Session
    session = AgentSession(
        stt=stt,
        vad=vad,
        llm=llm,
        tts=tts,
        allow_interruptions=True,
    )

    if master_id:
        @session.on("user_input_transcribed")
        def on_user_input_transcribed(ev: UserInputTranscribedEvent):
            if ev.is_final and ev.transcript:
                # Update user_id dynamically if it's set
                if ev.speaker_id:
                    asyncio.create_task(HistoryService.update_master_user(master_id, ev.speaker_id))
                else:
                    remote_parts = [p.identity for p in ctx.room.remote_participants.values()]
                    if remote_parts:
                        asyncio.create_task(HistoryService.update_master_user(master_id, remote_parts[0]))
                
                # Estimate STT tokens and increment stt_token in master record
                stt_tok = count_tokens(ev.transcript)
                asyncio.create_task(HistoryService.update_master_tokens(master_id, stt_tokens_add=stt_tok))

        @session.on("metrics_collected")
        def on_metrics_collected(ev: MetricsCollectedEvent):
            async def handle_metrics():
                try:
                    if ev.metrics.type == "llm_metrics":
                        input_tokens = ev.metrics.prompt_tokens
                        output_tokens = ev.metrics.completion_tokens
                        response_time = f"{ev.metrics.duration:.2f}"
                        
                        # Fetch the matching conversation turn from history
                        history = session.history.items
                        assistant_msg = None
                        user_msg = None
                        
                        for item in reversed(history):
                            if item.type == "message" and item.role == "assistant":
                                assistant_msg = item
                                break
                                
                        if assistant_msg:
                            idx = history.index(assistant_msg)
                            for item in reversed(history[:idx]):
                                if item.type == "message" and item.role == "user":
                                    user_msg = item
                                    break
                                    
                        human_text = user_msg.text_content if user_msg else ""
                        agent_text = assistant_msg.text_content if assistant_msg else ""
                        
                        if human_text or agent_text:
                            await HistoryService.add_message(
                                master_id=master_id,
                                human=human_text or "",
                                agent=agent_text or "",
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                response_time=response_time
                            )
                            
                            # Estimate tts_tokens based on agent text and add to tts_token in master
                            tts_tok = count_tokens(agent_text)
                            await HistoryService.update_master_tokens(master_id, tts_tokens_add=tts_tok)
                except Exception as ex:
                    print(f"Error handling metrics in background: {ex}")
            
            asyncio.create_task(handle_metrics())

    agent = Agent(
        instructions=agent_config["system_prompt"]
    )

    # Start the voice session in the room
    await session.start(agent=agent, room=ctx.room)

    welcome_message = agent_data.get("welcome_message") or agent_data.get("bot_settings", {}).get("welcome_message") or agent_data.get("bot_settings", {}).get("greeting_message", "Hello! How can I assist you today?")
    
    async def say_welcome():
        await asyncio.sleep(1.0)
        try:
            session.say(welcome_message, allow_interruptions=True)
            print(f"Said welcome message: {welcome_message}")
        except Exception as e:
            print(f"Failed to say welcome message: {e}")

    asyncio.create_task(say_welcome())
