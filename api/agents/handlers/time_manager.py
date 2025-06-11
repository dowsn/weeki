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
    self._is_paused = False  # ✅ Add pause state
    self._pause_start_time = None  # ✅ Track when pause started

  async def start_monitoring(self) -> None:
    print("monitoring started")
    if self._monitor_task:
      self._monitor_task.cancel()

    
    self._monitor_task = asyncio.create_task(self._monitor_time())

  async def _monitor_time(self) -> None:
    print("monitoring time")
    try:
        while self.remaining_minutes > 0:
            print("remaining_minutes", self.remaining_minutes)

            # ✅ Track elapsed seconds accurately
            seconds_elapsed = 0
            
            # Sleep in 1-second intervals to check pause state
            while seconds_elapsed < 60 and self.remaining_minutes > 0:
                await asyncio.sleep(1)

                # Check if cancelled
                if not self._monitor_task or self._monitor_task.cancelled():
                    print("Task cancelled, stopping time monitoring")
                    return

                # ✅ Only count seconds when not paused
                if not self._is_paused:
                    seconds_elapsed += 1
                else:
                    print(f"Timer paused, seconds elapsed so far: {seconds_elapsed}")

            # ✅ Only decrement time if we've actually counted 60 seconds
            if seconds_elapsed >= 60 and self.remaining_minutes > 0:
                self.remaining_minutes -= 1
                print("remaining_minutes after count down", self.remaining_minutes)
                await self._update_chat_session(self.remaining_minutes)
                await self.on_time_update(1)

    except asyncio.CancelledError:
        print("Time monitoring cancelled via exception")
        return
    except Exception as e:
        print(f"Error in time monitoring: {e}")

  @sync_to_async
  def _update_chat_session(self, time_left):
    chat_session = Chat_Session.objects.get(id=self.chat_session.id)
    chat_session.time_left = time_left
    chat_session.save()

  def pause_monitoring(self) -> None:
    """Pause the timer without stopping it"""
    if self._is_paused:
        print("⏸️ Timer is already paused")
        return
    print("⏸️ Pausing time monitoring")
    self._is_paused = True
    self._pause_start_time = datetime.now()
    print(f"Timer paused at {self._pause_start_time}")

  def resume_monitoring(self) -> None:
    """Resume the timer"""
    if not self._is_paused:
        print("▶️ Timer is not paused, nothing to resume")
        return
    if self._is_paused:
        pause_duration = datetime.now() - self._pause_start_time if self._pause_start_time else timedelta(0)
        print(f"▶️ Resuming time monitoring (was paused for {pause_duration})")
        self._is_paused = False
        self._pause_start_time = None

  def stop_monitoring(self) -> None:
    if self._monitor_task:
      self._monitor_task.cancel()
      self._monitor_task = None

  async def get_remaining_time(self) -> int:
    return self.remaining_minutes
