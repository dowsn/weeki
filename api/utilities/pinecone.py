import getpass
import os
import time

from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore


if not os.getenv("PINECONE_API_KEY"):
  os.environ["PINECONE_API_KEY"] = getpass.getpass(
      "Enter your Pinecone API key: ")

pinecone_api_key = os.environ.get("PINECONE_API_KEY")

pc = Pinecone(api_key=pinecone_api_key)



vector_store = PineconeVectorStore(index=index, embedding=embeddings)