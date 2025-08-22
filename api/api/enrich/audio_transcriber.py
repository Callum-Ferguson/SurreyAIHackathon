import os
import struct
from typing import BinaryIO
#import azure.cognitiveservices.speech as speechsdk
import time
#from langdetect import detect


class AudioTranscriber:
    def __init__(self, speech_config) -> None:
            
        self.speech_config = speech_config
   
    async def transcribe_from_audio(self):
        
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)    
        
        auto_detect_source_language_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=["en-GB", "it-IT", "es-ES", "en-IN"])

        translation_config = speechsdk.translation.SpeechTranslationConfig(
            subscription=os.environ.get("SPEECH_KEY"),
            region=os.environ.get("SPEECH_REGION"),
            speech_recognition_language='en-GB'
            )
        
        to_language ="en"
        translation_config.add_target_language(to_language)

        # Creates a translation recognizer using and audio file as input.
        speech_recognizer = speechsdk.translation.TranslationRecognizer(
            translation_config=translation_config, 
            audio_config=audio_config,
            auto_detect_source_language_config = auto_detect_source_language_config
            )
        
        speech_recognition_result = speech_recognizer.recognize_once_async().get()
        
        detectedSrcLang = detect(speech_recognition_result.text)
       
        return speech_recognition_result.translations['en'], detectedSrcLang, speech_recognition_result.text
        
            
        
    