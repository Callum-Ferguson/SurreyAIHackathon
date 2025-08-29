import os
import requests
import json
from typing import Dict, Any, Optional, List
import time

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder

class ChatHandler:
    def __init__(self) -> None:
        self.llm = AzureChatOpenAI(
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
        )

        self.project = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"] + 'api/projects/councildemo')
        
        # Initialize specialized agents
        self.agent_classifier = self.project.agents.get_agent("asst_nCjO26kHQms2Zdpe7UGybmsB")
        self.agent_information = self.project.agents.get_agent("asst_qKo3BWukyXvfqOM5Eiu7jxl3") 
        self.agent_eligibility = self.project.agents.get_agent("asst_nQej1R20aXi3n46pnuwuwdEy")
        
        # Create conversation thread
        self.thread = self.project.agents.threads.create()

        self.setup_agents_with_tools()
        
    def setup_agents_with_tools(self):
        """Configure agents with necessary function calling tools"""
        
        # Distance lookup tool for eligibility agent
        distance_tool = {
            "type": "function",
            "function": {
                "name": "get_school_distances",
                "description": "Get ONLY the valid schools within transport range for a given postcode. This function returns the COMPLETE and EXCLUSIVE list of schools that qualify for transport. Do not reference any schools not returned by this function.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "postcode": {
                            "type": "string",
                            "description": "UK postcode to check distances from"
                        }
                    },
                    "required": ["postcode"]
                }
            }
        }
        
        # Update eligibility agent with distance tool
        self.project.agents.update_agent(
            agent_id=self.agent_eligibility.id,
            tools=[distance_tool]
        )
    
    def get_school_distances(self, postcode: str) -> str:
        """Function to retrieve distance data for a given postcode"""
        try:
            print(f"[DEBUG] get_school_distances called with postcode: {postcode}")

            # Simulated API response (replace with live API if needed)
            if postcode[0] == "E":
                result = {
                    "postcode": postcode,
                    "valid_schools_for_transport": [
                        "East London High School",
                        "St Peter's School"
                    ],
                    "total_schools_found": 2,
                    "important_note": "These are the ONLY schools within transport range. Do not reference any other schools."
                }
            elif postcode[0:2] == "SW":
                result = {
                    "postcode": postcode,
                    "valid_schools_for_transport": [
                        "West London High School", 
                        "St Paul's School"
                    ],
                    "total_schools_found": 2,
                    "important_note": "These are the ONLY schools within transport range. Do not reference any other schools."
                }
            else:
                result = {
                    "postcode": postcode,
                    "valid_schools_for_transport": [],
                    "total_schools_found": 0,
                    "important_note": "No schools are within transport range for this postcode."
                }

            result_json = json.dumps(result)
            print(f"[DEBUG] get_school_distances returning: {result_json}")
            return result_json

        except Exception as e:
            error_result = {
                "error": f"Could not retrieve distance data: {str(e)}",
                "valid_schools_for_transport": [],
                "total_schools_found": 0
            }
            print(f"[DEBUG] get_school_distances error: {error_result}")
            return json.dumps(error_result)
    
    def classify_query(self, input_text: str) -> tuple[str, str]:
        """First stage: Classify the type of user query.
        Returns (classification_label, full_agent_message) for debugging.
        """

        # Send message to classifier agent
        message = self.project.agents.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=input_text
        )

        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id,
            agent_id=self.agent_classifier.id
        )

        # Fetch messages
        messages = self.project.agents.messages.list(
            thread_id=self.thread.id, 
            order=ListSortOrder.ASCENDING
        )

        # Last agent message
        last_message = next(
            (msg.text_messages[-1].text.value for msg in list(messages)[::-1] 
             if msg.text_messages), None
        )

        if not last_message:
            return ("Unknown", "")

        # Assume classifier returns just a label like "Eligibility_Check"
        classification_label = last_message.strip()

        print(f"[DEBUG] Classifier full output: {last_message}")

        return classification_label, last_message
    
    def handle_information_request(self, input_text: str) -> str:
        """Handle general information queries about the application process"""

        print(f"[DEBUG] Information request received: {input_text}")

        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id,
            agent_id=self.agent_information.id
        )
        
        messages = self.project.agents.messages.list(
            thread_id=self.thread.id, 
            order=ListSortOrder.ASCENDING
        )

        response = next(
            (msg.text_messages[-1].text.value for msg in list(messages)[::-1] 
             if msg.text_messages), None
        )

        print(f"[DEBUG] Information Agent response: {response}")
        return response if response else "Sorry, I couldn’t provide information at this time."
    
    def conduct_eligibility_assessment(self, input_text: str) -> str:
        """Handle eligibility assessment with function calling for distance checks"""

        # Register the Python function so the runtime knows how to call it
        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id,
            agent_id=self.agent_eligibility.id,
            enable_auto_function_calls={
                "get_school_distances": lambda args: self.get_school_distances(args["postcode"])
            }
        )

        # Loop until the run is finished
        while run.status in ("in_progress", "queued"):
            time.sleep(1.0)
            run = self.project.agents.runs.get(
                thread_id=self.thread.id,
                run_id=run.id
            )

        # Now fetch the latest agent messages
        messages = self.project.agents.messages.list(
            thread_id=self.thread.id, 
            order=ListSortOrder.ASCENDING
        )

        response = next(
            (msg.text_messages[-1].text.value for msg in list(messages)[::-1] 
             if msg.text_messages), None
        )

        return response if response else "Sorry, I couldn’t generate an eligibility response."
    
    def get_chat_response(self, input_text: str) -> str:
        """Main entry point - routes queries to appropriate agents"""
        
        query_type, classifier_raw = self.classify_query(input_text)
        print(f"[DEBUG] Classified query type: {query_type}")
        print(f"[DEBUG] Classifier raw message: {classifier_raw}")

        # Make sure query_type is a string, not tuple
        if isinstance(query_type, tuple):
            query_type = query_type[0]

        if query_type in ["Information_Request", "General_Greeting"]:
            print("[DEBUG] Routing to Information Agent")
            response = self.handle_information_request(input_text)
            print(f"[DEBUG] Information Agent response: {response}")
            return response

        elif query_type == "Eligibility_Check":
            print("[DEBUG] Routing to Eligibility Agent")
            response = self.conduct_eligibility_assessment(input_text)
            print(f"[DEBUG] Eligibility Agent response: {response}")
            return response

        else:
            print("[DEBUG] Unknown classification, defaulting to Information Agent")
            response = self.handle_information_request(input_text)
            print(f"[DEBUG] Fallback response: {response}")
            return response