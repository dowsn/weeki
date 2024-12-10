from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain import hub
import os


class BedrockClaude:

  def __init__(
      self,
      temperature=0,
      max_tokens=None,
      top_p=None,
  ):
    # Initialize the Bedrock Converse model
    self.llm = ChatBedrockConverse(
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        temperature=temperature,
        max_tokens=max_tokens,
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name="us-west-2")

    self.prompt = hub.pull("test_prompt")

    self.chain = self.prompt | self.llm | StrOutputParser()

  def stream_messages(self, input):
    """
        Stream messages using the chain

        Args:
            query (str): The input query to process
    """
    try:
      # Stream the response using the chain
      for chunk in self.chain.stream(input):
        print(chunk, end="")
    except Exception as e:
      print(f"Error streaming messages: {str(e)}")

  def invoke_messages(self, input):
    """
        Invoke the chain without streaming

        Args:
            query (str): The input query to process

        Returns:
            str: The model's response
        """
    try:
      return self.chain.invoke(input)
    except Exception as e:
      print(f"Error invoking messages: {str(e)}")
      return None
