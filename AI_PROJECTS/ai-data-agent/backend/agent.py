from langgraph.graph import StateGraph , START
from langgraph.prebuilt import ToolNode , tools_condition

from state import State
from llm import connect_llm
from tools import tools

llm=connect_llm()
llm_with_tools=llm.bind_tools(tools)

def agent(state:State):
    response=llm_with_tools.invoke(
        state["messages"]
    )

    return{
        "messages":[response]
    }


graph=StateGraph(State)

graph.add_node("agent",agent)
graph.add_node("tools",ToolNode(tools))

graph.add_edge(START,"agent")
graph.add_conditional_edges("agent",tools_condition)

graph.add_edge("tools","agent")

app=graph.compile()