#import azure.cognitiveservices.speech as speechsdk
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
import os

class TranslationHandler:
    def __init__(self) -> None:
            
        self.llm = AzureChatOpenAI(
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
        )

    def translate_text(self, text, language):

        # bot for extracting the postcode
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Your purpose is translating text from english into {target}. Do not make any changes to the meaning of the text, and in your answer return only the translated text and nothing else."""), 
                    ("human", "Please translate the following text into {target}: {input}")
            ]
        )
        chain = prompt | self.llm
        translated_text = chain.invoke(
            {
                "input": text,
                "target": language
            }
        )
        
        return translated_text






