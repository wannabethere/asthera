from typing import TypedDict, Annotated
from typing import Any, TypedDict, Tuple, Annotated
import operator
# from models.gemini_models import GeminiModel, GeminiJSONModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents.agent_types import AgentType
#from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_openai import OpenAIEmbeddings
from app.core.settings import get_settings
import os
settings = get_settings()
#os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
os.environ["LANGCHAIN_API_KEY"] = "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"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "Plan-and-execute"

openai_api_key = settings.OPENAI_API_KEY
llm = ChatOpenAI(model="gpt-4o-mini")
opus_model_id = 'claude-3-opus-20240229'
sonnet_model_id = 'claude-3-sonnet-20240229'
haiku_model_id = 'claude-3-haiku-20240307'
embedding_provider: str = "openai"
embedding_model: str = "text-embedding-3-small"
    
embeddings_model = OpenAIEmbeddings(
            model=embedding_model, openai_api_key=openai_api_key
)
llm_opus = ChatAnthropic(model=opus_model_id, temperature=0)
llm_sonnet = ChatAnthropic(model=sonnet_model_id, temperature=0)


def get_open_ai(temperature=0.0, model='gpt-4o-mini'):
    llm = ChatOpenAI(
        model=model,
        temperature = temperature,
    )
    return llm

def get_open_ai_json(temperature=0.0, model='gpt-4o-mini'):
    llm = ChatOpenAI(
        model=model,
        temperature = temperature,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    return llm