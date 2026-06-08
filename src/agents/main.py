import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from livekit.agents import cli, WorkerOptions
from src.agents.livekit_pipline.chat import chat_entrypoint
from src.agents.livekit_pipline.voice import voice_entrypoint

def run():
    import logging
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    agent_type = os.getenv("AGENT_TYPE", "voice")
    
    # Check for CLI flags and strip them to avoid interfering with LiveKit CLI parser
    if "--chat" in sys.argv:
        agent_type = "chat"
        sys.argv.remove("--chat")
    elif "--voice" in sys.argv:
        agent_type = "voice"
        sys.argv.remove("--voice")
        
    if agent_type == "chat":
        print("Starting LiveKit CHAT agent worker...")
        entrypoint = chat_entrypoint
        agent_name = "chat-agent"
    else:
        print("Starting LiveKit VOICE agent worker...")
        entrypoint = voice_entrypoint
        agent_name = "voice-agent"

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=agent_name,
        )
    )

if __name__ == "__main__":
    run()
