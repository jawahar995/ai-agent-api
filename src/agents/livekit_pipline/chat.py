import os
import asyncio
import time
from livekit.agents import JobContext
from livekit import rtc
from src.services.agent_fn import AgentFunction
from src.agents.graph.builder import build_graph
from src.services.history import HistoryService, count_tokens

async def chat_entrypoint(ctx: JobContext):
    # Establish connection to the LiveKit room
    await ctx.connect()
    print("Connected to the LiveKit room", ctx.job)
    # Attempt to load agent configuration from MongoDB using session_id in job metadata,
    # or fallback to room metadata or room name as agent_id
    agent_data = None
    session_id = ctx.job.metadata
    session_data = None
    print("Session ID", session_id) 
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
            agent_type="chat",
            user_id=user_id
        )
        print(f"Created chat history master record with ID: {master_id}")
    except Exception as history_err:
        print(f"Failed to create history master: {history_err}")
        master_id = None

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
            "system_prompt": "You are a helpful text assistant. Keep responses brief. You have access to a custom_api tool that gets the weather. Use it if asked about weather.",
            "tools": [
                {
                    "name": "custom_api",
                    "description": "Get current weather for a city.",
                    "url": "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true",
                    "method": "GET"
                }
            ]
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
            "system_prompt": agent_data.get("system_prompt", "You are a helpful assistant. Keep responses brief."),
            "tools": agent_data.get("tools", [])
        }
        
    try:
        graph = build_graph(agent_config)
    except Exception as e:
        print(f"Failed to build LangGraph from config: {e}")
        return

    print("Chat agent is ready and listening for messages...")

    welcome_message = agent_data.get("welcome_message") or agent_data.get("bot_settings", {}).get("welcome_message") or agent_data.get("bot_settings", {}).get("greeting_message", "Hello! How can I assist you today?")
    
    async def send_welcome():
        await asyncio.sleep(1.0)
        try:
            import json
            import uuid
            message_id = f"msg_{uuid.uuid4().hex[:8]}"
            payload = json.dumps({
                "type": "chat_chunk",
                "message_id": message_id,
                "content": welcome_message,
                "done": True
            })
            await ctx.room.local_participant.publish_data(
                payload=payload,
                topic="lk-chat-topic",
                reliable=True
            )
            print(f"Sent welcome message: {welcome_message}")
        except Exception as e:
            print(f"Failed to send welcome message: {e}")

    asyncio.create_task(send_welcome())

    # Conversation history: messages is a list of (role, content) tuples
    conversation_state = {"messages": []}

    # Listen to incoming data packets on chat topics
    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        topic = data_packet.topic
        print(f"[DEBUG] data_received event. Topic: {topic}, Sender: {data_packet.participant.identity if data_packet.participant else 'None'}")
        
        # 1. Ignore messages sent by ourselves
        if data_packet.participant and data_packet.participant.identity == ctx.room.local_participant.identity:
            return

        # We accept standard chat topics: lk-chat-topic, general-chat, chat, or empty topic
        if not topic or topic in ("lk-chat-topic", "general-chat", "chat"):
            try:
                user_msg = data_packet.data.decode("utf-8")
                
                # 2. Ignore JSON-formatted stream chunks (which are sent by the agent)
                try:
                    import json
                    parsed = json.loads(user_msg)
                    if isinstance(parsed, dict) and (parsed.get("type") == "chat_chunk" or "message_id" in parsed):
                        return
                except Exception:
                    pass
                
                # 3. Ignore if the message matches the last assistant response (prevents loops)
                if conversation_state["messages"]:
                    last_role, last_content = conversation_state["messages"][-1]
                    if last_role == "assistant" and user_msg.strip() == last_content.strip():
                        return

                print(f"Received message from participant: {user_msg}")
                
                # Update user_id in history_master if it was None
                if data_packet.participant and master_id:
                    asyncio.create_task(HistoryService.update_master_user(master_id, data_packet.participant.identity))
                
                asyncio.create_task(process_and_reply(user_msg))
            except Exception as e:
                print(f"Error handling data packet: {e}")

    async def process_and_reply(user_msg: str):
        import uuid
        import json

        conversation_state["messages"].append(("user", user_msg))
        
        # Unique message ID for the stream
        message_id = f"msg_{uuid.uuid4().hex[:8]}"

        async def on_token(token: str):
            try:
                payload = json.dumps({
                    "type": "chat_chunk",
                    "message_id": message_id,
                    "content": token,
                    "done": False
                })
                await ctx.room.local_participant.publish_data(
                    payload=payload,
                    topic="lk-chat-topic",
                    reliable=True
                )
            except Exception as e:
                print(f"Error publishing stream token chunk: {e}")

        try:
            start_time = time.time()
            # Invoke the LangGraph with our on_token callback in configurable
            response = await graph.ainvoke(
                conversation_state,
                config={"configurable": {"on_token_callback": on_token}}
            )
            response_time = f"{time.time() - start_time:.2f}"
            
            messages = response.get("messages", [])
            if messages:
                final_msg = messages[-1].content
                conversation_state["messages"].append(("assistant", final_msg))
                
                print(f"Streaming finished. Final reply: {final_msg}")
                
                # Save to MongoDB history
                if master_id:
                    try:
                        last_message = messages[-1]
                        usage = getattr(last_message, "usage_metadata", None)
                        if usage:
                            input_tokens = usage.get("input_tokens", 0)
                            output_tokens = usage.get("output_tokens", 0)
                        else:
                            input_tokens = count_tokens(user_msg)
                            output_tokens = count_tokens(final_msg)
                            
                        await HistoryService.add_message(
                            master_id=master_id,
                            human=user_msg,
                            agent=final_msg,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            response_time=response_time
                        )
                    except Exception as db_err:
                        print(f"Failed to record message in history: {db_err}")
                
                # Send the final 'done' message
                try:
                    payload = json.dumps({
                        "type": "chat_chunk",
                        "message_id": message_id,
                        "content": "",
                        "done": True
                    })
                    await ctx.room.local_participant.publish_data(
                        payload=payload,
                        topic="lk-chat-topic",
                        reliable=True
                    )
                except Exception as e:
                    print(f"Error sending stream done packet: {e}")
                    
 
                    
        except Exception as e:
            error_msg = f"Sorry, I encountered an error processing that request: {e}"
            print(error_msg)
            try:
                await ctx.room.local_participant.publish_data(
                    payload=error_msg,
                    topic="lk-chat-topic",
                    reliable=True
                )
            except Exception:
                pass