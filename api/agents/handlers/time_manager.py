from datetime import datetime, timedelta
from typing import Optional
import asyncio
from functools import partial


class TimeManager:

  def __init__(self, remaining_minutes: int, on_time_update):
    self.remaining_minutes:int = remaining_minutes
    self.on_time_update = on_time_update
    self._monitor_task: Optional[asyncio.Task] = None

  async def start_monitoring(self) -> None:
    if self._monitor_task:
      self._monitor_task.cancel()
    self._monitor_task = asyncio.create_task(self._monitor_time())

  async def _monitor_time(self) -> None:  # Fixed method name
    while self.remaining_minutes > 0:
      await asyncio.sleep(60)
      self.remaining_minutes -= 1
      await self.on_time_update(1)

  def stop_monitoring(self) -> None:
    if self._monitor_task:
      self._monitor_task.cancel()
      self._monitor_task = None

  async def get_remaining_time(self) -> int:
    return self.remaining_minutes
