from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os


load_dotenv()


def connect_llm() -> ChatOpenAI:

    api_key = os.getenv("GROQ_API_KEY")
    model_name = os.getenv("GROQ_MODEL_NAME")
    base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    print("\n========== LLM CONFIG ==========")
    print(f"LLM URL: {base_url}")
    print(f"MODEL NAME: {model_name}")
    print(f"API KEY SET: {'yes' if api_key else 'no'}")
    print("================================\n")

    if not api_key:
        raise ValueError("GROQ_API_KEY is not set.")

    if not model_name:
        raise ValueError("GROQ_MODEL_NAME is not set.")

    return ChatOpenAI(
        base_url=base_url,
        model=model_name,
        api_key=api_key,
        temperature=0,
        max_tokens=700,
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