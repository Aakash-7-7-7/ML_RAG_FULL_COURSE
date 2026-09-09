from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os


load_dotenv()


def connect_llm() -> ChatOpenAI:

    llm_url = os.getenv("LLM_URL")
    model_name = os.getenv("LLM_MODEL_NAME")

    print("\n========== LLM CONFIG ==========")
    print(f"LLM URL: {llm_url}")
    print(f"MODEL NAME: {model_name}")
    print("================================\n")

    if not llm_url:
        raise ValueError("LLM_URL is not set.")

    if not model_name:
        raise ValueError("LLM_MODEL_NAME is not set.")

    return ChatOpenAI(
        base_url=llm_url,
        model=model_name,
        api_key=os.getenv("LLM_API_KEY", "dummy"),
        temperature=0,
    )


if __name__ == "__main__":

    try:
        llm = connect_llm()

        response = llm.invoke(
            "Hello! Confirm you are working."
        )

        print(response.content)

    except Exception as error:
        print(f"LLM connection error: {error}")