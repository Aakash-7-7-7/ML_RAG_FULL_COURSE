from langchain_core.messages import HumanMessage

from csv_handler import load_csv_to_dataframe, set_current_dataframe
from agent import app


# --------------------------------
# Generate and save agent graph
# --------------------------------

graph_png = app.get_graph().draw_mermaid_png()

with open("agent_graph.png", "wb") as f:
    f.write(graph_png)

print("Graph saved successfully: agent_graph.png")


# --------------------------------
# Load CSV
# --------------------------------

df = load_csv_to_dataframe("../data/uploads/cars.csv")

set_current_dataframe(df)


# --------------------------------
# Ask agent
# --------------------------------

result = app.invoke(
    {
        "messages": [
            HumanMessage(
                content="give me the summary of the data"
            )
        ],
        "dataset_context": {}
    }
)


# --------------------------------
# Print messages
# --------------------------------

for message in result["messages"]:
    print("\n---")
    print(type(message).__name__)
    print(message.content)