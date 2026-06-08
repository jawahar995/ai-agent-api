from langgraph.graph import StateGraph, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from src.agents.graph.node import build_chat_node
from src.agents.llm import create_llm
from src.agents.tools import build_tools


def build_graph(agent_config: dict):
    llm = create_llm(agent_config["llm"])

    tools = []
    if "tools" in agent_config:
        tools = build_tools(agent_config["tools"])
        llm = llm.bind_tools(tools)

    graph = StateGraph(MessagesState)

    graph.add_node(
        "chat",
        build_chat_node(llm, agent_config["system_prompt"])
    )
    graph.set_entry_point("chat")

    if tools:
        tool_node = ToolNode(tools)
        graph.add_node("tools", tool_node)
        graph.add_conditional_edges("chat", tools_condition)
        graph.add_edge("tools", "chat")
    else: 
        graph.add_edge("chat", END)

    return graph.compile()

    
