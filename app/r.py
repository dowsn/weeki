  import os
  import base64
  from channels.generic.websocket import AsyncWebsocketConsumer
  from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
  import json
  import asyncio
  import threading


  class TranscriptConsumer(AsyncWebsocketConsumer):

    async def connect(self):
      await self.accept()
      print("WebSocket connection established")
      self.deepgram = DeepgramClient(os.environ.get("DEEPGRAM_API_KEY"))
      self.dg_connection = None

      # new
      self.lock = threading.Lock()
      self.exit = False

      # self.is_finals = []

    async def disconnect(self, close_code):
      print(f"WebSocket disconnected with code: {close_code}")
      self.lock.acquire()
      self.exit = True
      self.lock.release()

      if self.dg_connection:
        self.dg_connection.finish()

    async def receive(self, text_data=None, bytes_data=None):
      if not self.dg_connection:
        await self.start_deepgram()

      if text_data:
        data = json.loads(text_data)
        if data.get('type') == 'test_audio':
          print("Received test audio request")
          await self.send_test_audio()
      elif bytes_data:
        # here check
        print(f"Received {len(bytes_data)} bytes of audio data")
        try:
          self.dg_connection.send(bytes_data)
        except Exception as e:
          print(f"Error sending data to Deepgram: {e}")
          await self.send_error(str(e))

    async def start_deepgram(self):
      try:
        options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
            endpointing=300,
        )

        self.dg_connection = self.deepgram.listen.websocket.v("1")

        def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            print(f"Deepgram transcription: {sentence}")
            if len(sentence) > 0:
              if result.is_final:
                self.is_finals.append(sentence)
                if result.speech_final:
                  utterance = " ".join(self.is_finals)
                  asyncio.create_task(self.send_transcription(
                      utterance, "final"))
                  self.is_finals = []
                else:
                  asyncio.create_task(
                      self.send_transcription(sentence, "is_final"))
              else:
                asyncio.create_task(self.send_transcription(sentence, "interim"))


        def on_error(self, error, **kwargs):
          print(f"Deepgram error: {error}")
          asyncio.create_task(self.send_error(str(error)))

        def on_close(self, **kwargs):
          print("Deepgram connection closed")
          asyncio.create_task(
              self.send(text_data=json.dumps({"type": "connection_closed"})))

        self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        self.dg_connection.on(LiveTranscriptionEvents.Close, on_close)

        self.dg_connection.start(options)
        print("Deepgram connection established")

      except Exception as e:
        print(f"Error starting Deepgram connection: {e}")
        await self.send_error(str(e))

    async def send_transcription(self, text, type):
      await self.send(text_data=json.dumps({"transcript": text, "type": type}))

    async def send_error(self, error):
      await self.send(text_data=json.dumps({"error": error}))

    async def send_test_audio(self):
      test_audio_base64 = "UklGRvSXAABXQVZFZm10IBAAAAABAAEARKwAAIhYAAACABAAZGF0YdCXAAAAAAEAAgADAAQABQAGAAcACAAJAAsADAANAA8AEAARABMAFAAVABcAGAAZABsAHAAdAB8AIAAhACMAJAAlACcAKAApACsALAAtAC8AMAAxADMANAA1ADcAOAA5ADsAPAA9AD8AQABBAEMARABFAEcASABJAEsATABNAE8AUABRAFMAVABVAFcAWABZAFsAXABdAF8AYABhAGMAZABlAGcAaABpAGsAbABtAG8AcABxAHMAdAB1AHcAeAB5AHsAfAB9AH8AgACBAIMAhACFAIcAiACJAIsAjACNAI8AkACRAJMAlACVAJcAmACZAJsAnACdAJ8AoAChAKMApAClAKcAqACpAKsArACtAK8AsACxALMAtAC1ALcAuAC5ALsAvAC9AL8AwADBAMMAxADFAMcAyADJAMsAzADNAM8A0ADRANMAR0gDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMA0wDTANMAMwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvAC8ALwAvACsAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAnACcAJwAjAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AHwAfAB8AFwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATABMAEwATAAMAP///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/v7+/vz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8/Pz8+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr6+vr4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj4+Pj29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb29vb09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT08vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDw8PDu7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7s7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6enp6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo6Ojo"

      print("aaaaaaaaa")
      audio_data = base64.b64decode(test_audio_base64)

      # Ensure Deepgram connection is established
      if not self.dg_connection:
        await self.start_deepgram()

      # Send the audio data to Deepgram
      try:
        self.dg_connection.send(audio_data)
        print(f"Sent {len(audio_data)} bytes of test audio data to Deepgram")
      except Exception as e:
        error_message = f"Error sending test audio data to Deepgram: {str(e)}"
        print(error_message)
        await self.send_error(error_message)

    # Decode the base64 string to bytes
