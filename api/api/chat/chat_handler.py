import os
import json
import time
from typing import Dict

from fastapi import FastAPI
from pydantic import BaseModel

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ListSortOrder, FunctionTool, ToolSet
from langchain_openai import AzureChatOpenAI

class ChatHandler:
    def __init__(self) -> None:
        # Initialize LLM
        self.llm = AzureChatOpenAI(
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
        )

        # Initialize Azure AI Project client
        self.project = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"] + "api/projects/councildemo"
        )

        # Initialize agents
        self.agent_classifier = self.project.agents.get_agent("asst_nCjO26kHQms2Zdpe7UGybmsB")
        self.agent_information = self.project.agents.get_agent("asst_qKo3BWukyXvfqOM5Eiu7jxl3")
        self.agent_eligibility = self.project.agents.get_agent("asst_nQej1R20aXi3n46pnuwuwdEy")

        # Create conversation thread
        self.thread = self.project.agents.threads.create()

        # Setup tools/functions for automatic function calling
        self.setup_agents_with_tools()

    def setup_agents_with_tools(self):
        """Register Python functions as tools for the eligibility agent"""

        # Wrap the Python function in FunctionTool
        school_distance_tool = FunctionTool(functions=[self.get_school_distances])

        # Use ToolSet to allow multiple tools
        toolset = ToolSet()
        toolset.add(school_distance_tool)

        # Enable auto function calls for the eligibility agent
        self.project.agents.enable_auto_function_calls(toolset)

    def get_school_distances(self, postcode: str) -> str:
        """Return eligible schools for transport based on postcode"""

        print(f"[DEBUG] get_school_distances called with postcode: {postcode}")

        # Simulated responses
        if postcode.startswith("E"):
            result = {
                "postcode": postcode,
                "valid_schools_for_transport": ["East London High School", "St Peter's School"],
                "total_schools_found": 2,
                "important_note": "These are the ONLY schools within transport range."
            }
        elif postcode.startswith("SW"):
            result = {
                "postcode": postcode,
                "valid_schools_for_transport": ["West London High School", "St Paul's School"],
                "total_schools_found": 2,
                "important_note": "These are the ONLY schools within transport range."
            }
        else:
            result = {
                "postcode": postcode,
                "valid_schools_for_transport": [],
                "total_schools_found": 0,
                "important_note": "No schools are within transport range for this postcode."
            }

        return json.dumps(result)

    def classify_query(self, input_text: str) -> str:
        """Classify the query type"""
        message = self.project.agents.messages.create(
            thread_id=self.thread.id, role="user", content=input_text
        )

        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id, agent_id=self.agent_classifier.id
        )

        # Fetch last agent message
        messages = self.project.agents.messages.list(
            thread_id=self.thread.id, order=ListSortOrder.ASCENDING
        )
        last_message = next(
            (msg.text_messages[-1].text.value for msg in list(messages)[::-1] if msg.text_messages),
            "Unknown"
        )

        print(f"[DEBUG] Classifier full output: {last_message}")
        return last_message.strip()

    def handle_information_request(self, input_text: str) -> str:
        """Handle general information queries"""
        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id, agent_id=self.agent_information.id
        )

        messages = self.project.agents.messages.list(
            thread_id=self.thread.id, order=ListSortOrder.ASCENDING
        )
        response = next(
            (msg.text_messages[-1].text.value for msg in list(messages)[::-1] if msg.text_messages),
            "Sorry, I couldn’t provide information at this time."
        )

        print(f"[DEBUG] Information Agent response: {response}")
        return response

    def conduct_eligibility_assessment(self, input_text: str) -> str:
        """Handle eligibility assessment via auto function calls"""
        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id,
            agent_id=self.agent_eligibility.id
        )

        # Wait until the run is complete
        while run.status in ("in_progress", "queued"):
            time.sleep(1)
            run = self.project.agents.runs.get(thread_id=self.thread.id, run_id=run.id)

        messages = self.project.agents.messages.list(
            thread_id=self.thread.id, order=ListSortOrder.ASCENDING
        )
        response = next(
            (msg.text_messages[-1].text.value for msg in list(messages)[::-1] if msg.text_messages),
            "Sorry, I couldn’t generate an eligibility response."
        )
        return response

    def get_chat_response(self, input_text: str) -> str:
        """Main entry point to route queries"""
        query_type = self.classify_query(input_text)
        print(f"[DEBUG] Classified query type: {query_type}")

        if query_type in ["Information_Request", "General_Greeting"]:
            return self.handle_information_request(input_text)
        elif query_type == "Eligibility_Check":
            return self.conduct_eligibility_assessment(input_text)
        else:
            # Default fallback
            return self.handle_information_request(input_text)