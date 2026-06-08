from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig


def build_chat_node(llm, system_prompt):

    async def chatbot_node(state, config: RunnableConfig = None):

        messages = [
            SystemMessage(content=system_prompt),
            *state["messages"]
        ]

        configurable = config.get("configurable", {}) if config else {}
        on_token_callback = configurable.get("on_token_callback")

        if on_token_callback:
            response = None
            async for chunk in llm.astream(messages):
                if response is None:
                    response = chunk
                else:
                    response += chunk

                token = chunk.content
                if token:
                    await on_token_callback(token)

            if response is None:
                response = await llm.ainvoke(messages)
        else:
            response = await llm.ainvoke(messages)

        # Log tool call decisions
        if hasattr(response, "tool_calls") and response.tool_calls:
            print(f"[DEBUG] LLM decided to invoke tool(s): {response.tool_calls}")

        return {
            "messages": [response]
        }

    return chatbot_node