from langchain_aws import BedrockEmbeddings


class Embedding:

  def __init__(self):
    self.model_id = "amazon.titan-embed-text-v2:0"
    self.embeddings = BedrockEmbeddings(model_id=self.model_id)

  def embed_query(self, query):
    return self.embeddings.embed_query(query)
