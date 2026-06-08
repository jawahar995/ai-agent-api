from langchain_core.tools import BaseTool, StructuredTool
from src.agents.tools.retriver_tool import build_retriever_tool
from src.agents.tools.custom_tool import build_api_tool
from src.agents.tools.sql import SQLTool

def wrap_tool_with_logging(tool: BaseTool) -> BaseTool:
    """Wraps a tool's invoke/ainvoke methods to print debug/execution logs."""
    original_invoke = tool.invoke
    original_ainvoke = tool.ainvoke

    def new_invoke(input, *args, **kwargs):
        print(f"[DEBUG] [TOOL CALL] tool: '{tool.name}' | input: {input} | args: {args} | kwargs: {kwargs}")
        try:
            res = original_invoke(input, *args, **kwargs)
            print(f"[DEBUG] [TOOL SUCCESS] tool: '{tool.name}' | result: {res}")
            return res
        except Exception as e:
            print(f"[DEBUG] [TOOL ERROR] tool: '{tool.name}' | error: {e}")
            raise e

    async def new_ainvoke(input, *args, **kwargs):
        print(f"[DEBUG] [TOOL CALL ASYNC] tool: '{tool.name}' | input: {input} | args: {args} | kwargs: {kwargs}")
        try:
            res = await original_ainvoke(input, *args, **kwargs)
            print(f"[DEBUG] [TOOL SUCCESS ASYNC] tool: '{tool.name}' | result: {res}")
            return res
        except Exception as e:
            print(f"[DEBUG] [TOOL ERROR ASYNC] tool: '{tool.name}' | error: {e}")
            raise e

    object.__setattr__(tool, "invoke", new_invoke)
    object.__setattr__(tool, "ainvoke", new_ainvoke)
    return tool

def build_tools(tools_config):
    tools = []
    for tool_config in tools_config:
        if tool_config["name"] == "sql":
            tool = SQLTool(db_url=tool_config["db_url"], llm_config=tool_config["llm"])
            tools.append(tool)
        elif tool_config["name"] == "custom_api":
            from .custom_tool import build_api_tool
            tool = build_api_tool(
                name=tool_config["name"],
                description=tool_config["description"],
                url=tool_config["url"],
                method=tool_config.get("method", "GET"),
                schema_dict=tool_config.get("schema_dict")
            )
            tools.append(tool)
        elif tool_config["name"] in ("retriever", "retriver"):
            tool = build_retriever_tool(tool_config)
            tools.append(tool)
            
    # Wrap all built tools with the logging wrapper
    return [wrap_tool_with_logging(t) for t in tools]