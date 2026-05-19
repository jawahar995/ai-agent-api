from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent


logger = logging.getLogger(__name__)
load_dotenv()


try:
    from livekit.agents import Agent, AgentSession, JobContext, cli
    from livekit.agents.llm.mcp import MCPServerHTTP
    from livekit.plugins import deepgram, langchain, silero
except Exception:  # pragma: no cover - optional dependency guard for local API-only mode
    Agent = None
    AgentSession = None
    JobContext = Any
    MCPServerHTTP = None
    cli = None
    deepgram = None
    langchain = None
    silero = None

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional dependency guard for local API-only mode
    ChatOpenAI = None


MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "")
MEMORY_SERVICE_BASE_URL = os.getenv("MEMORY_SERVICE_BASE_URL", "")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "")
LIVEKIT_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "enterprise-voice-agent")


@tool
async def update_user_profile_webhook(client_id: str, user_id: str, email: str) -> str:
    """Update a user profile email in an external control-plane webhook."""
    if not WEBHOOK_BASE_URL:
        return "Webhook base URL is not configured."

    webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}/v1/clients/{client_id}/users/{user_id}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.patch(webhook_url, json={"email": email}, timeout=5.0)
            if response.status_code == 200:
                return "Successfully updated user profile via internal webhook."
            return f"Failed to update profile. Server responded with status: {response.status_code}"
        except Exception as exc:
            return f"Webhook connection failed: {exc}"


async def _fetch_user_memory(user_id: str) -> str:
    if not MEMORY_SERVICE_BASE_URL:
        return "No previous history available."

    memory_url = f"{MEMORY_SERVICE_BASE_URL.rstrip('/')}/v1/memory/{user_id}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(memory_url, timeout=5.0)
            if response.status_code != 200:
                return "No previous history available."
            payload = response.json()
            return payload.get("summary") or "No previous history available."
        except Exception:
            return "No previous history available."


async def _load_mcp_tools() -> tuple[list[Any], str | None]:
    if not MCP_SERVER_URL:
        return [], None
    if MCPServerHTTP is None:
        return [], "MCP not available (livekit-agents not installed)."

    try:
        server = MCPServerHTTP(url=MCP_SERVER_URL)
        await server.initialize()
        return await server.list_tools(), None
    except Exception as exc:
        return [], f"Skipping MCP setup due to connection failure: {exc}"


async def create_agent_brain(client_id: str, user_id: str) -> tuple[Any, int, list[str]]:
    """Build the LangGraph brain with custom tools, memory context, and optional MCP tools."""
    if ChatOpenAI is None:
        raise RuntimeError("langchain-openai is not installed. Install project requirements.")

    model_name = os.getenv("AGENT_MODEL", "gpt-4o-mini")
    model = ChatOpenAI(model=model_name, streaming=True)
    memory_summary = await _fetch_user_memory(user_id)
    notes: list[str] = []

    @tool
    async def update_profile_email(email: str) -> str:
        """Update the current user's profile email address."""
        return await update_user_profile_webhook.ainvoke(
            {"client_id": client_id, "user_id": user_id, "email": email}
        )

    tools: list[Any] = [update_profile_email]

    mcp_tools, mcp_error = await _load_mcp_tools()
    if mcp_error:
        notes.append(mcp_error)
    tools.extend(mcp_tools)

    system_prompt = (
        "You are an advanced low-latency voice assistant. "
        "Keep responses brief, natural, and speech-friendly. "
        f"Here is remembered history from prior calls for this user: {memory_summary}"
    )

    graph_agent = create_react_agent(model=model, tools=tools, state_modifier=system_prompt)
    return graph_agent, len(tools), notes


async def run_realtime_agent_event_loop(room_metadata: dict[str, Any]) -> dict[str, Any]:
    client_id = room_metadata.get("client_id", "default")
    user_id = room_metadata.get("user_id", "guest")

    _, tool_count, notes = await create_agent_brain(client_id=client_id, user_id=user_id)

    return {
        "status": "ready",
        "client_id": client_id,
        "user_id": user_id,
        "tool_count": tool_count,
        "mcp_enabled": bool(MCP_SERVER_URL),
        "message": "Realtime agent brain initialized.",
        "notes": notes,
    }


if cli is not None:
    cli_server = cli.AgentServer()

    @cli_server.rtc_session(agent_name=LIVEKIT_AGENT_NAME)
    async def entrypoint(ctx: JobContext) -> None:
        await ctx.connect()
        client_id = getattr(ctx.room, "metadata", {}).get("client_id", "default")
        user_id = getattr(ctx.room, "metadata", {}).get("user_id", "guest")

        langgraph_brain, _, notes = await create_agent_brain(client_id=client_id, user_id=user_id)
        for note in notes:
            logger.warning(note)

        session = AgentSession(
            vad=silero.VAD.load(),
            stt=deepgram.STT(model=os.getenv("LIVEKIT_STT_MODEL", "deepgram/nova-3")),
            llm=langchain.LLMAdapter(graph=langgraph_brain),
            tts=deepgram.TTS(model=os.getenv("LIVEKIT_TTS_MODEL", "deepgram/aura-2")),
        )

        agent = Agent()
        await session.start(agent=agent, room=ctx.room)
        await session.generate_reply(
            instructions="Greet the user warmly by name if found in memory summary."
        )


if __name__ == "__main__":
    if cli is None:
        raise RuntimeError(
            "livekit-agents is not installed. Install requirements and run again."
        )
    cli.run_app(cli_server)
