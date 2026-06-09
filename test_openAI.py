import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI


def build_llm():
    load_dotenv()

    api_type = os.getenv("OPENAI_API_TYPE", "azure").lower()
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0"))

    if api_type == "azure":
        required_vars = [
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
        ]
        api_version = os.getenv("AZURE_OPENAI_API_VERSION") or os.getenv(
            "OPENAI_API_VERSION"
        )
        missing = [
            var
            for var in required_vars
            if not os.getenv(var) or os.getenv(var, "").startswith("replace-with")
        ]

        if not api_version:
            missing.append("AZURE_OPENAI_API_VERSION or OPENAI_API_VERSION")

        if missing:
            raise RuntimeError(
                "Missing Azure OpenAI configuration: " + ", ".join(missing)
            )
        print("ENDPOINT:", os.getenv("AZURE_OPENAI_ENDPOINT"))
        print("DEPLOYMENT:", os.getenv("AZURE_OPENAI_DEPLOYMENT"))
        print("API_VERSION:", os.getenv("OPENAI_API_VERSION"))
        return AzureChatOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            api_version=api_version,
            temperature=temperature,
        )

    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "").startswith(
        "replace-with"
    ):
        raise RuntimeError("Missing OpenAI configuration: OPENAI_API_KEY")

    return ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=temperature,
    )


if __name__ == "__main__":
    prompt = os.getenv("OPENAI_TEST_PROMPT", "Reply with only: pong")
    response = build_llm().invoke([HumanMessage(content=prompt)])
    print(response.content)
