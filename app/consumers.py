import json
from channels.generic.websocket import AsyncWebsocketConsumer
from deepgram import Deepgram
from django.conf import settings
import base64
import logging


DG_API_KEY = settings.DEEPGRAM_API_KEY
deepgram = Deepgram(DG_API_KEY)


            logger = logging.getLogger(__name__)

            class TranscriptionConsumer(AsyncWebsocketConsumer):
                async def connect(self):
                    await self.accept()
                    logger.info("WebSocket connection accepted.")

                async def disconnect(self, close_code):
                    logger.info(f"WebSocket connection closed with code: {close_code}")

                async def receive(self, text_data):
                    try:
                        audio_base64 = json.loads(text_data)['audio']
                        audio_bytes = base64.b64decode(audio_base64)

                        response = await deepgram.transcription.prerecorded(
                            audio_bytes, options={'language': 'en-US'})
                        transcript = response['results']['channels'][0]['alternatives'][0]['transcript']

                        await self.send(text_data=json.dumps({'message': transcript}))
                        logger.info("Transcription sent to client.")
                    except Exception as e:
                        logger.error(f"Error in receiving data: {e}")
                        await self.send(text_data=json.dumps({'message': 'Error in processing audio'}))
                        await self.close()
