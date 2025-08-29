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
            # Call your distance API
            """url = f"{os.environ['DISTANCE_API_ENDPOINT']}/distances/{postcode}"
            headers = {
                "api-key": os.environ["DISTANCE_API_KEY"],
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()"""
            
            # Return structured JSON with explicit instructions
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
            
            return json.dumps(result)
            
        except Exception as e:
            return json.dumps({
                "error": f"Could not retrieve distance data: {str(e)}",
                "valid_schools_for_transport": [],
                "total_schools_found": 0
            })
    
    def classify_query(self, input_text: str) -> str:
        """First stage: Classify the type of user query"""
        message = self.project.agents.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=input_text
        )

        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id,
            agent_id=self.agent_classifier.id
        )
        
        messages = self.project.agents.messages.list(
            thread_id=self.thread.id, 
            order=ListSortOrder.ASCENDING
        )

        query_type = next(
            (msg.text_messages[-1].text.value for msg in list(messages)[::-1] 
             if msg.text_messages), None
        )
        
        return query_type.strip()
    
    def handle_information_request(self, input_text: str) -> str:
        """Handle general information queries about the application process"""

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
        
        return response
    
    def conduct_eligibility_assessment(self, input_text: str) -> str:
        """Handle eligibility assessment with function calling for distance checks"""

        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id,
            agent_id=self.agent_eligibility.id
        )
        
        # Handle function calls if the agent needs distance data
        while run.status == "requires_action":
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            
            for tool_call in tool_calls:
                if tool_call.function.name == "get_school_distances":
                    args = json.loads(tool_call.function.arguments)
                    print(args)
                    postcode = args.get("postcode")
                    distance_data = self.get_school_distances(postcode)
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": distance_data
                    })

                    print(distance_data)
            
            # Submit tool outputs back to the agent
            run = self.project.agents.runs.submit_tool_outputs_and_process(
                thread_id=self.thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )

            time.sleep(1.0)
        
        messages = self.project.agents.messages.list(
            thread_id=self.thread.id, 
            order=ListSortOrder.ASCENDING
        )

        response = next(
            (msg.text_messages[-1].text.value for msg in list(messages)[::-1] 
             if msg.text_messages), None
        )
        
        return response
    
    def get_chat_response(self, input_text: str) -> str:
        """Main entry point - routes queries to appropriate agents"""
        
        # First, classify the query type
        query_type = self.classify_query(input_text)
            
        if query_type in ["Information_Request", "General_Greeting"]:
            return self.handle_information_request(input_text)
            
        elif query_type == "Eligibility_Check":
            return self.conduct_eligibility_assessment(input_text)