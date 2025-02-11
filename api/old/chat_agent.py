from rest_framework.views import APIView
from django.http import StreamingHttpResponse
# from langchain_aws import ChatBedrockConverse
from langchain_core.output_parsers import StrOutputParser
from langchain import hub
import asyncio
import json
import os
from asgiref.sync import async_to_sync
from django.utils.decorators import classonlymethod
from channels.generic.http import AsyncHttpConsumer
from typing import List, Dict, Any
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import SystemMessagePromptTemplate
from typing import AsyncGenerator
from langchain_xai import ChatXAI


class ConversationAgent:

  def __init__(self,
               username: str,
               topics: list,
               type: str = "xai",
               model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
               temperature: float = 0.8):

    if (type == 'xai'):
      self.llm = ChatXAI(
          model="grok-2-1212",
          temperature=temperature,
          max_tokens=200,
      )
    # else:
    #   self.llm = ChatBedrockConverse(
    #       model=model,
    #       temperature=temperature,
    #       aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    #       aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    #       region_name="us-west-2",
    #       max_tokens=200)

    # Pull the prompt template from the hub
    self.prompt = hub.pull("chat_mr_week:02e4c2fd")
    self.username = username
    self.topics = process_topics(topics)

    # Format the prompt with username and topics
    self.prompt = self.prompt.partial(username=self.username,
                                      topics=self.topics)
    self.chain = self.prompt | self.llm | StrOutputParser()

    self.memory = ConversationBufferWindowMemory(k=50,
                                                 return_messages=True,
                                                 memory_key="chat_memory")

  async def generate_response(self, query: str) -> AsyncGenerator[str, None]:
    """Generate a streaming response to the user's query"""
    # Add the user's message to memory before generating response
    self.memory.chat_memory.add_user_message(query)

    chain_input = {
        "chat_memory": self.memory.buffer,
        "query": query,
        "topics": self.topics,
        "user_context": "none",
        "literature_help": "none"
    }

    try:
      full_response = ""
      async for chunk in self.chain.astream(chain_input):
        full_response += chunk
        yield chunk

      # After generating the complete response, add it to memory
      self.memory.chat_memory.add_ai_message(full_response)

    except Exception as e:
      error_message = f"Error generating response: {str(e)}"
      self.memory.chat_memory.add_ai_message(error_message)
      yield error_message

  def get_conversation_history(self) -> list:
    """Return the current conversation history"""
    return self.memory.buffer

  def clear_memory(self):
    """Clear the conversation history"""
    self.memory.clear()


def process_topics(topics: list):

  formatted_topics = []
  for topic in topics:
    topic_str = f"{getattr(topic, 'name', 'unknown')}: {getattr(topic, 'description', 'no description')}"
    goal = getattr(topic, 'goal', None)
    if goal:
      topic_str += f" goal: {goal}"
    formatted_topics.append(topic_str)
  return ' | '.join(formatted_topics)


class ConversationAgent4:

  def __init__(self,
               username: str,
               topics: List[Dict],
               model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
               temperature: float = 1,
               max_tokens: int = 200):

    # what is pinecone env
    # Initialize Pinecone

    # pinecone.init(api_key=os.environ.get('PINECONE_API_KEY'),
    #               environment=os.environ.get('PINECONE_ENVIRONMENT'))

    # Initialize Bedrock embeddings
    # self.embeddings = BedrockEmbeddings(
    #     model_id="amazon.titan-embed-text-v1",
    #     aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    #     aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    #     region_name="us-west-2")

    # Initialize Pinecone index with namespaces
    # self.vectorstore = Pinecone.from_existing_index(index_name="weeki",
    #                                                 embedding=self.embeddings,
    #                                                 namespace={
    #                                                     "summaries":
    #                                                     "summaries",
    #                                                     "literature":
    #                                                     "literature"
    #                                                 })

    # Initialize conversation memory
    self.memory = ConversationBufferWindowMemory(k=50,
                                                 return_messages=True,
                                                 memory_key="chat_memory")

    # Store user information
    self.username = username
    self.topics = topics

    # Initialize Bedrock Claude
    self.llm = ChatBedrockConverse(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name="us-west-2")

    # Pull prompt from hub
    self.prompt = hub.pull("chat_mr_week:02e4c2fd")

    # Create the base chain
    self.chain = self.prompt | self.llm | StrOutputParser()

  # def _get_relevant_context(self, query: str) -> Dict:
  #   """Retrieve relevant historical context and literature from Pinecone"""
  #   # Search for relevant historical conversations
  #   historical_context = self.vectorstore.similarity_search(
  #       query, namespace="summaries", k=5)

  #   # Search for relevant literature passages
  #   literature = self.vectorstore.similarity_search(query,
  #                                                   namespace="literarture",
  #                                                   k=5)

  #   return {
  #       "summaries":
  #       "\n".join([doc.page_content for doc in historical_context]),
  #       "literature": "\n".join([doc.page_content for doc in literature])
  #   }

  async def generate_response(self, query: str):
    """Generate a streaming response to the user's query"""
    # Get relevant context from RAG
    # context = self._get_relevant_context(query)

    # Prepare input for the chain
    chain_input = {
        "chat_memory": self.memory.buffer,
        "query": query,
        "topics": self.topics,
        "context": "I am happy on this world",
        "literature_help": "It is good to be happy"
        # "context": {
        #     "user_context": context["summaries"]
        # },
        # "literature_help": context["literature"]
    }

    # Generate streaming response
    try:
      async for chunk in self.chain.astream(chain_input):
        yield chunk
    except Exception as e:
      yield f"Error generating response: {str(e)}"

  # def save_conversation_summary(self, summary: str):
  #   """Save conversation summary to Pinecone for future context"""
  #   self.vectorstore.add_texts(texts=[summary],
  #                              namespace="conversation_summaries",
  #                              metadatas=[{
  #                                  "type": "summary"
  #                              }])

  # def invoke_messages(self, query: str):
  #   """Invoke the chain without streaming"""
  #   try:
  #     context = self._get_relevant_context(query)

  #     chain_input = {
  #         "chat_memory": self.memory.buffer,
  #         "query": query,
  #         "topics": self.topics,
  #         "context": {
  #             "user_context": context["user_context"]
  #         },
  #         "literature_help": context["literature_help"]
  #     }

  #     return self.chain.invoke(chain_input)
  #   except Exception as e:
  #     print(f"Error invoking messages: {str(e)}")
  #     return None
