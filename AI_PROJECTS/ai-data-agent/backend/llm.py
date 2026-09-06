from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os 
load_dotenv()

llm_url=os.getenv("LLM_URL")
model_name=os.getenv("LLM_MODEL_NAME")

def connect_llm():

    return ChatOpenAI(
        base_url=llm_url,
        model=model_name,
        api_key="dummy"
    )
if __name__ == "__main__":

    llm_client = connect_llm()

    try:
        response = llm_client.invoke(
            "Hello! Confirm you are working."
        )

        print("LLM Response:", response.content)

    except Exception as e:
        print(f"Error connecting to local server at {llm_url}: {e}")