# from typing import Optional, Union, Tuple, Any, Dict, List, Sequence
# from langchain_xai import ChatXAI
# from langchain_core.messages import BaseMessage
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from pydantic import BaseModel, SecretStr
# import os

# class EnhancedChatXAI:
#   """
#     Enhanced wrapper for ChatXAI with comprehensive parameter support and streaming capabilities.

#     Attributes:
#         model (str): Name of the model to use
#         temperature (float): Sampling temperature for generation
#         max_tokens (Optional[int]): Maximum number of tokens to generate
#         logprobs (Optional[bool]): Whether to return logprobs
#         timeout (Optional[Union[float, Tuple[float, float], Any]]): Timeout for requests
#         max_retries (int): Maximum number of retries
#         api_key (Optional[str]): xAI API key
#         cache (Optional[bool]): Whether to use caching
#         streaming (bool): Whether to stream responses by default
#         seed (Optional[int]): Seed for deterministic generation
#     """

#   def __init__(
#       self,
#       model: str = "grok-2-1212",
#       temperature: float = 0.7,
#       max_tokens: Optional[int] = None,
#       logprobs: Optional[bool] = None,
#       timeout: Optional[Union[float, Tuple[float, float], Any]] = None,
#       max_retries: int = 2,
#       cache: Optional[bool] = None,
#       streaming: bool = False,
#       seed: Optional[int] = None,
#       frequency_penalty: Optional[float] = None,
#       presence_penalty: Optional[float] = None,
#       top_p: Optional[float] = None,
#       top_logprobs: Optional[int] = None,
#       stop: Optional[Union[str, List[str]]] = None,
#   ):
#     """
#         Initialize the EnhancedChatXAI instance.

#         Args:
#             model (str): Name of model to use
#             temperature (float): Sampling temperature (0-1)
#             max_tokens (Optional[int]): Max tokens to generate
#             logprobs (Optional[bool]): Whether to return logprobs
#             timeout (Optional[Union[float, Tuple[float, float], Any]]): Request timeout
#             max_retries (int): Max number of retries
#             api_key (Optional[str]): xAI API key
#             cache (Optional[bool]): Whether to use caching
#             streaming (bool): Whether to stream by default
#             seed (Optional[int]): Random seed
#             frequency_penalty (Optional[float]): Frequency penalty (0-2)
#             presence_penalty (Optional[float]): Presence penalty (0-2)
#             top_p (Optional[float]): Top p sampling parameter
#             top_logprobs (Optional[int]): Number of top logprobs to return
#             stop (Optional[Union[str, List[str]]]): Stop sequences
#         """
#     self.llm = ChatXAI(
#         model=model,
#         temperature=temperature,
#         max_tokens=max_tokens,
#         logprobs=logprobs,
#         timeout=timeout,
#         max_retries=max_retries,
#         api_key=os.environ.get('XAI_API_KEY'),
#         cache=cache,
#         streaming=streaming,
#         seed=seed,
#         frequency_penalty=frequency_penalty,
#         presence_penalty=presence_penalty,
#         top_p=top_p,
#         top_logprobs=top_logprobs,
#         stop=stop,
#     )

#   def create_messages(
#       self,
#       messages: Union[str, List[Union[BaseMessage, Tuple[str, str],
#                                       Dict[str, Any], str]]],
#       system_message: Optional[str] = None) -> List[BaseMessage]:
#     """
#         Create properly formatted messages for the chat model.

#         Args:
#             messages: Input messages in various formats
#             system_message: Optional system message to prepend

#         Returns:
#             List[BaseMessage]: Properly formatted messages
#         """
#     if isinstance(messages, str):
#       messages = [("human", messages)]

#     formatted_messages = []
#     if system_message:
#       formatted_messages.append(("system", system_message))

#     if isinstance(messages, list):
#       formatted_messages.extend(messages)

#     return formatted_messages

#   def invoke(self,
#              messages: Union[str, List[Union[BaseMessage, Tuple[str, str],
#                                              Dict[str, Any], str]]],
#              system_message: Optional[str] = None,
#              stop: Optional[List[str]] = None,
#              **kwargs: Any) -> BaseMessage:
#     """
#         Send a message to the model and get a response without streaming.

#         Args:
#             messages: Input messages in various formats
#             system_message: Optional system message
#             stop: Optional stop sequences
#             **kwargs: Additional arguments to pass to the model

#         Returns:
#             BaseMessage: Model's response
#         """
#     try:
#       formatted_messages = self.create_messages(messages, system_message)
#       return self.llm.invoke(formatted_messages, stop=stop, **kwargs)
#     except Exception as e:
#       print(f"Error invoking messages: {str(e)}")
#       return None

#   def stream(self,
#              messages: Union[str, List[Union[BaseMessage, Tuple[str, str],
#                                              Dict[str, Any], str]]],
#              system_message: Optional[str] = None,
#              stop: Optional[List[str]] = None,
#              **kwargs: Any) -> Any:
#     """
#         Stream the model's response chunk by chunk.

#         Args:
#             messages: Input messages in various formats
#             system_message: Optional system message
#             stop: Optional stop sequences
#             **kwargs: Additional arguments to pass to the model

#         Yields:
#             Chunks of the model's response
#         """
#     try:
#       formatted_messages = self.create_messages(messages, system_message)
#       for chunk in self.llm.stream(formatted_messages, stop=stop, **kwargs):
#         yield chunk
#     except Exception as e:
#       print(f"Error streaming messages: {str(e)}")
#       yield None

#   def bind_tools(self,
#                  tools: Sequence[Union[Dict[str, Any], type[BaseModel], Any]],
#                  tool_choice: Optional[Union[Dict, str, bool]] = None,
#                  strict: Optional[bool] = None) -> Any:
#     """
#         Bind tools to the chat model for function/tool calling.

#         Args:
#             tools: Sequence of tools to bind
#             tool_choice: Which tool to require the model to call
#             strict: Whether to enforce strict schema validation

#         Returns:
#             Modified chat model instance with tools bound
#         """
#     return self.llm.bind_tools(tools, tool_choice=tool_choice, strict=strict)

#   def with_structured_output(self,
#                              schema: Union[Dict[str, Any], type[BaseModel],
#                                            type, None] = None,
#                              method: str = 'function_calling',
#                              include_raw: bool = False,
#                              strict: Optional[bool] = None) -> Any:
#     """
#         Configure the model to return structured outputs matching a schema.

#         Args:
#             schema: Output schema specification
#             method: Method for steering generation ('function_calling', 'json_mode', 'json_schema')
#             include_raw: Whether to include raw model output
#             strict: Whether to enforce strict schema validation

#         Returns:
#             Modified chat model instance configured for structured output
#         """
#     return self.llm.with_structured_output(schema=schema,
#                                            method=method,
#                                            include_raw=include_raw,
#                                            strict=strict)

#   def get_num_tokens(self, text: str) -> int:
#     """
#         Get the number of tokens in a text string.

#         Args:
#             text: Input text

#         Returns:
#             Number of tokens
#         """
#     return self.llm.get_num_tokens(text)

#   def get_num_tokens_from_messages(
#       self,
#       messages: List[BaseMessage],
#       tools: Optional[Sequence[Union[Dict[str, Any], type[BaseModel],
#                                      Any]]] = None
#   ) -> int:
#     """
#         Calculate the number of tokens in a message list.

#         Args:
#             messages: List of messages
#             tools: Optional list of tools to include in count

#         Returns:
#             Number of tokens
#         """
#     return self.llm.get_num_tokens_from_messages(messages, tools)
