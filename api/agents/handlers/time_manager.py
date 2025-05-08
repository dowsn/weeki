from asgiref.sync import sync_to_async
from datetime import datetime, timedelta
from typing import Optional
import asyncio
from functools import partial
from app.models import Chat_Session


class TimeManager:

  def __init__(self, chat_session: Chat_Session, remaining_minutes: int,
               on_time_update):
    self.remaining_minutes: int = remaining_minutes
    self.on_time_update = on_time_update
    self._monitor_task: Optional[asyncio.Task] = None
    self.chat_session = chat_session

  async def start_monitoring(self) -> None:
    if self._monitor_task:
      self._monitor_task.cancel()
    self._monitor_task = asyncio.create_task(self._monitor_time())

  async def _monitor_time(self) -> None:
    while self.remaining_minutes > 0:
      await asyncio.sleep(60)
      self.remaining_minutes -= 1

      # Use sync_to_async for database operations
      await self._update_chat_session(self.remaining_minutes)
      await self.on_time_update(1)

  @sync_to_async
  def _update_chat_session(self, time_left):
    chat_session = Chat_Session.objects.get(id=self.chat_session.id)
    chat_session.time_left = time_left
    chat_session.save()

  def stop_monitoring(self) -> None:
    if self._monitor_task:
      self._monitor_task.cancel()
      self._monitor_task = None

  async def get_remaining_time(self) -> int:
    return self.remaining_minutes
