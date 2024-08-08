from channels.generic.websocket import AsyncWebsocketConsumer
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
import asyncio
import threading
import json
import os


class TranscriptConsumer(AsyncWebsocketConsumer):

  async def connect(self):
    await self.accept()
    print("WebSocket connection established")
    self.deepgram = DeepgramClient(os.environ.get("DEEPGRAM_API_KEY"))
    self.dg_connection = None
    self.lock = threading.Lock()
    self.exit = False

  async def disconnect(self, close_code):
    print(f"WebSocket disconnected with code: {close_code}")
    self.lock.acquire()
    self.exit = True
    self.lock.release()
    if self.dg_connection:
      await self.dg_connection.finish()

  async def receive(self, text_data=None, bytes_data=None):
    if not self.dg_connection:
      await self.start_deepgram()

    if bytes_data:
      print(f"Received {len(bytes_data)} bytes of audio data")
      try:
        self.dg_connection.send(bytes_data)
      except Exception as e:
        print(f"Error sending data to Deepgram: {e}")

  async def start_deepgram(self):
    try:
      options = LiveOptions(model="nova-2",
                            language="en-US",
                            interim_results=True)

      def on_message(self, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if len(sentence) == 0:
          return
        print(f"Deepgram transcription: {sentence}")
        asyncio.run_coroutine_threadsafe(
            self.send(text_data=json.dumps({"transcript": sentence})),
            asyncio.get_running_loop())

      self.dg_connection = self.deepgram.listen.websocket.v("1")
      self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

      print("Starting Deepgram connection")
      await self.dg_connection.start(options)
      print("Deepgram connection established")

    except Exception as e:
      print(f"Error starting Deepgram connection: {e}")
