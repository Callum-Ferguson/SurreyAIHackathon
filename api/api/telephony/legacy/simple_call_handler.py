import os
from fastapi import Request
from azure.communication.callautomation import CallAutomationClient
from azure.communication.callautomation import (
    RecognizeInputType,
    TextSource,
    SsmlSource,
    VoiceKind,
    FileSource
)
import pyodbc
import azure.cognitiveservices.speech as speechsdk
from api.chat.chat_handler import ChatHandler

class SimpleTelephonyHandler:
    def __init__(self):
        self.call_client = CallAutomationClient.from_connection_string(
            os.environ["AZURE_COMMUNICATION_CONNECTION_STRING"]
        )
        self.chat_handler = ChatHandler()

    async def handle_incoming_call(self, request: Request):
        """Handle incoming call webhook"""
        events = await request.json()
        
        if isinstance(events, list):
            for event in events:
                result = await self._process_event(event)
                if result:
                    return result
        else:
            result = await self._process_event(events)
            if result:
                return result
        
        return {"status": "ok"}
    
    async def _process_event(self, event_data):
        """Process individual event"""
        event_type = event_data.get("eventType") or event_data.get("type")
        
        # Handle Event Grid validation
        if event_type == "Microsoft.EventGrid.SubscriptionValidationEvent":
            validation_code = event_data["data"]["validationCode"]
            return {"validationResponse": validation_code}
        
        if event_type == "Microsoft.Communication.IncomingCall":
            await self._answer_call(event_data)
        elif event_type == "Microsoft.Communication.CallConnected":
            await self._start_conversation(event_data)
        elif event_type == "Microsoft.Communication.RecognizeCompleted":
            await self._process_speech(event_data)
        elif event_type == "Microsoft.Communication.PlayCompleted":
            await self._continue_listening(event_data)

    async def _answer_call(self, event_data):
        """Answer incoming call"""
        incoming_call_context = event_data["data"]["incomingCallContext"]

        self.call_client.answer_call(
            incoming_call_context=incoming_call_context,
            callback_url=os.environ["CALLBACK_URL"],
            cognitive_services_endpoint=f"https://{os.environ['SPEECH_REGION']}.api.cognitive.microsoft.com/"
        )

        from_number = (
            event_data.get('data', {})
            .get('from', {})
            .get('phoneNumber', {})
            .get('value'))

        """
        Connects to Azure Synapse SQL using Entra ID (no MFA),
        queries the WHATSAPP_TELNUMBERS table for a specific phone number,
        and returns the result.
        """
        server = "sqlserverislingtoncouncil.database.windows.net"
        database = "ssislingtoncouncil"
        table = "[AUTOMATION].[WHATSAPP_TELNUMBERS]"

        # Construct the SQL query
        query = f"SELECT Name FROM {table} WHERE AuthPhoneNumber = '{from_number}'"

        # Connection string using Active Directory Integrated authentication
        username = os.environ["SQL_USERNAME"]
        password = os.environ["SQL_PASSWORD"]

        connection_string = (
            f"Driver={{ODBC Driver 18 for SQL Server}};"
            f"Server={server};"
            f"Database={database};"
            f"UID={username};"
            f"PWD={password};"
            f"Encrypt=no;"
            f"TrustServerCertificate=no;"
        )


        # Connect and execute
        with pyodbc.connect(connection_string) as conn:
            
            cursor = conn.cursor()
            cursor.execute(query)
            name = cursor.fetchall()

        print(f"Query result: {name}")


    async def _start_conversation(self, event_data):
        """Start conversation with greeting"""
        call_connection_id = event_data["data"]["callConnectionId"]
        call_connection = self.call_client.get_call_connection(call_connection_id)
        
        greeting = "Hello, I am your AI assistant for council services. Please speak after the tone."


        try:
                # Approach 2: Simple TextSource with en-GB locale
                play_source = TextSource(
                    text=greeting,
                    source_locale="en-GB",
                    voice_kind=VoiceKind.FEMALE
                )
               
                result = call_connection.play_media_to_all(
                    play_source=play_source
                )
                print(f"Play media result (TextSource GB): {result}")
               
        except :
                print(f"TextSource GB failed: {e2}")
                try:
                    # Approach 3: Basic TextSource without locale
                    play_source = TextSource(text=greeting)
                   
                    result = call_connection.play_media_to_all(
                        play_source=play_source
                    )
                    print(f"Play media result (Basic): {result}")
                   
                except Exception as e3:
                    print(f"All playback approaches failed: {e3}")
 
    async def _continue_listening(self, event_data):
        """Start listening after greeting"""
        call_connection_id = event_data["data"]["callConnectionId"]
        call_connection = self.call_client.get_call_connection(call_connection_id)
        
        participants = list(call_connection.list_participants())
        call_connection.start_recognizing_media(
            input_type=RecognizeInputType.SPEECH,
            target_participant=participants[0],
            operation_context="user_input",
            initial_silence_timeout=10
        )

    async def _process_speech(self, event_data):
        """Process recognized speech"""
        recognition_result = event_data["data"]["recognitionResult"]
        
        if recognition_result.get("recognitionType") == "speech":
            recognized_text = recognition_result["speech"]
            
            # Get AI response
            ai_response = str(self.chat_handler.get_chat_response(recognized_text))
            
            # Play response
            call_connection_id = event_data["data"]["callConnectionId"]
            call_connection = self.call_client.get_call_connection(call_connection_id)
            
            play_source = TextSource(
                text=ai_response,
                source_locale="en-US",
                voice_kind=VoiceKind.FEMALE
            )
            
            try:
                result = call_connection.play_media_to_all(
                    play_source=play_source,
                    operation_context="ai_response"
                )
                print(f"Play AI response result: {result}")
            except Exception as e:
                print(f"Error playing AI response: {e}")