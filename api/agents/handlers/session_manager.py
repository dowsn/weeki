from typing import Dict, Any
from langchain_xai import ChatXAI
from langchain import hub


class SessionManager:

  def __init__(self, beginner: bool, ai_model: ChatXAI):
    self.ai_model = ai_model
    self.prompts = {
        "first_intro": hub.pull("first_session_intro"),
        "other_intro": hub.pull("other_session_intro"),
        "end_session": hub.pull("end_of_session"),
        "end_soon": hub.pull("end_of_session_soon")
    }

  async def handle_ending_soon(self) -> str:
    prompt = self.prompts["end_soon"].format(username=self.state.username, )
    # give there that 5 minutes is left to prompt
    response = await self.ai_model.ainvoke(prompt)
    return response

  async def handle_start(self) -> str:
    if self.beginner:
      prompt = self.prompts["first_intro"].format(username=self.state.username)
    else:
      prompt = self.prompts["other_intro"].format(
          username=self.state.username,
          conversation_context=self.state.conversation_context)
    response = await self.ai_model.ainvoke(prompt)
    return response

  async def handle_end(self) -> str:
    prompt = self.prompts["end_session"].format(
        username=self.state.username,
        conversation_context=self.state.conversation_context)
    response = await self.ai_model.ainvoke(prompt)
    return response

  # async def process_message(self, message: str) -> str:
  #     # Process message through graph and generate response
  #     return await self.model.ainvoke(self.state.conversation_context + f"\nHuman: {message}")

  # @staticmethod
  # def route_by_stage(state: Dict[str, Any]) -> str:
  #     stages = {
  #         SessionStage.DURING: "process_message",
  #         SessionStage.FIRST_MESSAGE: "handle_start",
  #         SessionStage.ENDING_SOON: "handle_ending_soon",
  #         SessionStage.ENDED: "handle_end"
  #     }
  #     return stages.get(state["session_stage"], "process_message")
