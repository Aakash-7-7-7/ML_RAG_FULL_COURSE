from langchain_core.messages import HumanMessage

from csv_handler import load_csv_to_dataframe, set_current_dataframe
from agent import app


# Load CSV
df = load_csv_to_dataframe("Salary.csv")

# Store it as the current dataset
set_current_dataframe(df)


# Ask the agent a question
result = app.invoke(
    {
        "messages": [
            HumanMessage(
                content="show line plot of age and salary"
            )
        ],
        "dataset_context": {}
    }
)


# Print all messages
for message in result["messages"]:
    print("\n---")
    print(type(message).__name__)
    print(message.content)