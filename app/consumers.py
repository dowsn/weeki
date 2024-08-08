from channels.generic.websocket import AsyncWebsocketConsumer
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
import asyncio
import json
import os
from queue import Queue


class TranscriptConsumer(AsyncWebsocketConsumer):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.transcript_queue = Queue()
    self.is_recording = False
    self.deepgram = DeepgramClient(os.environ.get("DEEPGRAM_API_KEY"))
    self.dg_connection = None

  async def connect(self):
    await self.accept()
    print("WebSocket connection established")
    asyncio.create_task(self.process_queue())

  async def disconnect(self, close_code):
    print(f"WebSocket disconnected with code: {close_code}")
    await self.stop_deepgram()

  async def receive(self, text_data=None, bytes_data=None):
    if text_data:
      data = json.loads(text_data)
      action = data.get('action')
      if action == 'start':
        await self.start_recording()
      elif action == 'stop':
        await self.stop_recording()
    elif bytes_data and self.is_recording:
      if self.dg_connection:
        print(f"Received {len(bytes_data)} bytes of audio data")
        try:
          self.dg_connection.send(bytes_data)
        except Exception as e:
          print(f"Error sending data to Deepgram: {e}")
      else:
        print("Deepgram connection not established, but received audio data")

  async def start_recording(self):
    print("Starting recording")
    self.is_recording = True
    await self.start_deepgram()

  async def stop_recording(self):
    print("Stopping recording")
    self.is_recording = False
    await self.stop_deepgram()

  async def start_deepgram(self):
    if self.dg_connection:
      print("Deepgram connection already exists")
      return

    try:
      options = LiveOptions(
          model="nova-2",
          language="en-US",
          smart_format=True,
          interim_results=True,
      )

      queue = self.transcript_queue

      def on_message(self, result, **kwargs):
        sentence = result.channel.alternatives[0].transcript
        if len(sentence) == 0:
          return
        is_final = result.is_final
        print(
            f"Deepgram transcription: {sentence} ({'final' if is_final else 'interim'})"
        )
        queue.put({"transcript": sentence, "is_final": is_final})

      def on_error(self, error, **kwargs):
        print(f"Deepgram Error: {error}")

      def on_metadata(self, metadata, **kwargs):
        print(f"Deepgram Metadata: {metadata}")

      def on_close(self, close, **kwargs):
        print(f"Deepgram connection closed: {close}")

      print("Creating Deepgram connection")
      self.dg_connection = self.deepgram.listen.websocket.v("1")
      self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
      self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)
      self.dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
      self.dg_connection.on(LiveTranscriptionEvents.Close, on_close)

      print("Starting Deepgram connection")
      self.dg_connection.start(options)
      print("Deepgram connection started")
    except Exception as e:
      print(f"Error starting Deepgram connection: {e}")
      self.dg_connection = None

  async def stop_deepgram(self):
    if self.dg_connection:
      try:
        print("Stopping Deepgram connection")
        self.dg_connection.finish()
        print("Deepgram connection stop initiated")
      except Exception as e:
        print(f"Error stopping Deepgram connection: {e}")
      finally:
        self.dg_connection = None
    else:
      print("No Deepgram connection to stop")

  async def process_queue(self):
    while True:
      if not self.transcript_queue.empty():
        message = self.transcript_queue.get()
        await self.send(text_data=json.dumps(message))
      await asyncio.sleep(0.1)
