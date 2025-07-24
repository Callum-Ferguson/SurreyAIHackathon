import os
import json
import asyncio
import websockets
from fastapi import Request, WebSocket
from azure.communication.callautomation import CallAutomationClient
from azure.communication.callautomation.models import (
    MediaStreamingOptions,
    StreamingTransportType,
    MediaStreamingContentType,
    MediaStreamingAudioChannelType,
    AudioFormat
)
import azure.cognitiveservices.speech as speechsdk
from api.chat.chat_handler import ChatHandler

class TelephonyHandler:
    def __init__(self):
        self.call_client = CallAutomationClient.from_connection_string(
            os.environ["AZURE_COMMUNICATION_CONNECTION_STRING"]
        )
        self.chat_handler = ChatHandler()
        
        # Speech config
        self.speech_config = speechsdk.SpeechConfig(
            subscription=os.environ["SPEECH_KEY"],
            region=os.environ["SPEECH_REGION"]
        )
        self.speech_config.speech_synthesis_voice_name = "en-GB-BellaNeural"

    async def handle_incoming_call(self, request: Request):
        """Handle incoming call webhook"""
        event_data = await request.json()
        
        if event_data.get("type") == "Microsoft.Communication.IncomingCall":
            incoming_call_context = event_data["data"]["incomingCallContext"]
            
            # Configure media streaming
            media_streaming_options = MediaStreamingOptions(
                transport_url=os.environ["WEBSOCKET_URI"],
                transport_type=StreamingTransportType.WEBSOCKET,
                content_type=MediaStreamingContentType.AUDIO,
                audio_channel_type=MediaStreamingAudioChannelType.MIXED,
                start_media_streaming=True,
                enable_bidirectional=True,
                audio_format=AudioFormat.PCM24_K_MONO
            )
            
            # Answer call with streaming
            self.call_client.answer_call(
                incoming_call_context=incoming_call_context,
                media_streaming=media_streaming_options,
                callback_url=os.environ["CALLBACK_URL"]
            )

    async def handle_media_stream(self, websocket: WebSocket):
        """Handle WebSocket media streaming"""
        await websocket.accept()
        
        # Initialize speech recognizer for streaming
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=False)
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config, 
            audio_config=audio_config
        )
        
        # Speech synthesizer for responses
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=None
        )
        
        try:
            while True:
                # Receive audio data from call
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("kind") == "AudioData":
                    # Process audio chunk
                    audio_data = message["audioData"]["data"]
                    
                    # Convert to speech (you'll need to implement streaming recognition)
                    # For now, using a simplified approach
                    await self._process_audio_chunk(audio_data, websocket, speech_synthesizer)
                    
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            await websocket.close()

    async def _process_audio_chunk(self, audio_data, websocket, speech_synthesizer):
        """Process audio chunk and send response"""
        # This is simplified - you'd need proper streaming speech recognition
        # For demo purposes, we'll simulate processing
        
        # Simulate speech recognition result
        recognized_text = "Hello, I need help with bin collection"  # This would come from actual recognition
        
        if recognized_text:
            # Get AI response using existing chat handler
            ai_response = str(self.chat_handler.get_chat_response(recognized_text))
            
            # Convert response to audio
            result = speech_synthesizer.speak_text_async(ai_response).get()
            
            if result.audio_data:
                # Send audio back through WebSocket
                response_message = {
                    "kind": "AudioData",
                    "audioData": {
                        "data": result.audio_data.hex(),
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                }
                await websocket.send_text(json.dumps(response_message))
            # Handle silence or no speech detected
            await self._continue_listening(event_data)