import os
import requests

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from api.search.search_handler import SearchHandler
import json
from types import SimpleNamespace


from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder

search_handler = SearchHandler()


class ChatHandler:
    def __init__(self) -> None:
        self.llm = AzureChatOpenAI(
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
        )

        self.project = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]+'projects/councilHackathon')
        
        self.agent_greeting = self.project.agents.get_agent("")
        self.bot_classification = self.project.agents.get_agent("")
        self.agent_general = self.project.agents.get_agent("")
        self.thread = self.project.agents.threads.create()
    
    def trigger_api_post_request(self,url, payload):
        headers = {
            "api-key": os.environ["AZURE_RBG_ADDRESS_KEY"],
            "Ocp-Apim-Subscription-Key": os.environ["AZURE_RBG_APIM_WS_KEY"],
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raises an error for bad responses (4xx/5xx)
        return response.json()
    
    def trigger_api_get_request(self,url):
        headers = {
            "Ocp-Apim-Subscription-Key": os.environ["AZURE_RBG_APIM_WS_KEY"],
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an error for bad responses (4xx/5xx)
        return response.json()
    
    def parse_conversation(self, conversation_str):
        messages = []
        lines = conversation_str.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            if line.startswith('User: '):
                # Extract user message (may span multiple lines)
                user_content = line[6:]  # Remove "User: " prefix
                i += 1
                while i < len(lines) and not (lines[i].startswith('User: ') or lines[i].startswith('Assistant: ')):
                    user_content += '\n' + lines[i]
                    i += 1
                messages.append(("human", user_content.strip()))
            elif line.startswith('Assistant: '):
                # Extract assistant message (may span multiple lines)
                ai_content = line[11:]  # Remove "Assistant: " prefix
                i += 1
                while i < len(lines) and not (lines[i].startswith('User: ') or lines[i].startswith('Assistant: ')):
                    ai_content += '\n' + lines[i]
                    i += 1
                messages.append(("ai", ai_content.strip()))
            else:
                i += 1
        
        return messages

    def get_chat_response(self, input_text):

        # Bot for checking conversation and checking what query is about
        message = self.project.agents.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=input_text
        )

        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id,
            agent_id=self.bot_classification.id)
        
        messages = self.project.agents.messages.list(thread_id=self.thread.id, order=ListSortOrder.ASCENDING)

        query_type = next(
                (msg.text_messages[-1].text.value for msg in list(messages)[::-1] if msg.text_messages),
                None
            )


        if query_type == 'Undetermined':
        # Agent for greeting customer and checking what query is about         

            message = self.project.agents.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=input_text
            )

            run = self.project.agents.runs.create_and_process(
                thread_id=self.thread.id,
                agent_id=self.agent_greeting.id)
            
            messages = self.project.agents.messages.list(thread_id=self.thread.id, order=ListSortOrder.ASCENDING)


            # messages = self.parse_conversation(input_text)
            # search_response = search_handler.get_query_response(str(input_text))


            response = next(
                (msg.text_messages[-1].text.value for msg in list(messages)[::-1] if msg.text_messages),
                None
            )

            return response

        elif query_type == 'Example Category 1':


            message = self.project.agents.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=input_text
            )

            run = self.project.agents.runs.create_and_process(
                thread_id=self.thread.id,
                agent_id=self.agent_general.id)
            
            messages = self.project.agents.messages.list(thread_id=self.thread.id, order=ListSortOrder.ASCENDING)


            # messages = self.parse_conversation(input_text)
            # search_response = search_handler.get_query_response(str(input_text))

            response = next(
                (msg.text_messages[-1].text.value for msg in list(messages)[::-1] if msg.text_messages),
                None
            )


            return response
        
        # return response
        
    def get_chat_completions(self, system_prompt,user_prompt): 
        
        prompt = ChatPromptTemplate.from_messages(
                        [
                            (
                                "system",
                                        system_prompt,
                            ),
                            ("user", user_prompt)
                        ] 
                    )

        chain = prompt | self.llm
        response = chain.invoke(
                        {
                            "user_prompt": user_prompt,
                            "system_prompt": system_prompt
                        }
                    )

        return response.content
