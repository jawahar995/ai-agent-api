from langchain.tools import BaseTool
from pydantic import Field, PrivateAttr
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from typing import Any, Dict

class SQLTool(BaseTool):
    name: str = "sql_query_tool"
    description: str = (
        "Query database using natural language. Only supports read-only queries."
    )
    db_url: str = Field(..., exclude=True)
    llm_config: Dict[str, Any] = Field(..., exclude=True)

    _agent: Any = PrivateAttr(default=None)

    def __init__(self, db_url: str, llm_config: Dict[str, Any], **kwargs):
        super().__init__(db_url=db_url, llm_config=llm_config, **kwargs)
        try:
            db = SQLDatabase.from_uri(db_url)
            
            # Extract chat model and temperature
            chat_model = llm_config.get("chat_model", "gpt-4o-mini")
            if chat_model == "gpt-4.1-mini":
                chat_model = "gpt-4o-mini"
                
            llm = ChatOpenAI(
                model=chat_model,
                temperature=llm_config.get("temperature", 0),
                api_key=llm_config.get("api_key")
            )
            toolkit = SQLDatabaseToolkit(db=db, llm=llm)
            self._agent = create_react_agent(llm, toolkit.get_tools())
        except Exception as e:
            print(f"SQLTool initialization warning: {e}")
            self._agent = None

    def _run(self, question: str) -> str:
        if not self._agent:
            return "SQL Agent Error: Database or LLM client not initialized properly."
        try:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(self._arun(question), loop)
                return future.result()
            else:
                return asyncio.run(self._arun(question))
        except Exception as e:
            return f"SQL Agent Error: {str(e)}"

    async def _arun(self, question: str) -> str:
        if not self._agent:
            return "SQL Agent Error: Database or LLM client not initialized properly."
        try:
            response = await self._agent.ainvoke(
                {
                    "messages": [
                        (
                            "system",
                            """
                            You are a SQL assistant.

                            Rules:
                            - Only generate SELECT queries
                            - Never modify database
                            - Never use DELETE
                            - Never use UPDATE
                            - Never use INSERT
                            - Never use DROP
                            - Always LIMIT results to 20
                            """
                        ),
                        (
                            "human",
                            question
                        )
                    ]
                }
            )
            messages = response["messages"]
            final_message = messages[-1]
            return final_message.content
        except Exception as e:
            return f"SQL Agent Error: {str(e)}"