import os
import requests
import json
from typing import Dict, Any, Optional, List

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
        
    def setup_agents_with_tools(self):
        """Configure agents with necessary function calling tools"""
        
        # Distance lookup tool for eligibility agent
        distance_tool = {
            "type": "function",
            "function": {
                "name": "get_school_distances",
                "description": "Get walking and driving distances from postcode to nearby schools",
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
    
    def get_school_distances(self, postcode: str) -> Dict[str, Any]:
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
            if postcode[0] == "E":
                return "Valid Schools are East London High and St Peter's School only."
            elif postcode[0:1] == "SW":
                return "Valid Schools are West London High and St Paul's School only."
            else:
                return "There are no valid schools in range."
            
        except Exception as e:
            return f"Could not retrieve distance data: {str(e)}"
    
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
        message = self.project.agents.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=input_text
        )

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
        message = self.project.agents.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=input_text
        )

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
                    postcode = args.get("postcode")
                    distance_data = self.get_school_distances(postcode)
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": distance_data #json.dumps(distance_data)
                    })
            
            # Submit tool outputs back to the agent
            run = self.project.agents.runs.submit_tool_outputs_and_process(
                thread_id=self.thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
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
    
    def get_chat_response(self, input_text: str) -> str:
        """Main entry point - routes queries to appropriate agents"""
        
        # First, classify the query type
        query_type = self.classify_query(input_text)
            
        if query_type in ["Information_Request", "General_Greeting"]:
            return self.handle_information_request(input_text)
            
        elif query_type == "Eligibility_Check":
            return self.conduct_eligibility_assessment(input_text)

# Example agent directives for Azure AI Foundry configuration:

"""
AGENT 1 - Query Classification Agent (callum_asst_classifier):
System Prompt:
You are a query classifier for a school transport eligibility system. 
Analyze the users most recent message in the context of the whole conversation and return ONLY one of these categories:
- Information_Request: User wants general info about applications, process, deadlines
- Eligibility_Check: User wants to check if they/their child qualifies for transport
- General_Greeting: General greetings, thank you messages

Return only the category name, nothing else.

AGENT 2 - Information Agent (callum_asst_information):
System Prompt:
You are an information specialist for school transport applications. 
Use the provided documentation to answer questions about:
- Application processes and deadlines
- Required documents
- Contact information
- General policies

If users ask about eligibility, redirect them to start an eligibility check.
Keep responses helpful but concise.

AGENT 3 - Eligibility Assessment Agent (callum_asst_eligibility):
System Prompt:
You are an eligibility assessment specialist. Your job is to ask questions to determine 
school transport eligibility based on meeting all of these criteria:
- Whether the chosen schools is within range of the student's post code
- Whether the student is younger than 14 years old or has special educational needs

Ask questions systematically. When you receive a postcode, use the get_school_distances 
function to check which schools are in valid distance including the student's desired school. List all schools within a valid distance based on the function only, even if they are not the desired school.
Only consider schools which are provided by the function output.

Continue asking questions until you have all needed information to accurately determine eligibility but do not ask unnecessary additional questions if that is not going to change the outcome.

When assessment is complete, based on the assessment data:
1. Make a clear ELIGIBLE or NOT ELIGIBLE decision
2. If eligible, provide the application website link: https://www.surreycouncilexample.govt.uk/application
3. If not eligible, explain the reasoning based on the criteria and answers provided, suggest alternative schools where possible

Give the decision as per the below examples, based on the answers and function output:
- This student is ELIGIBLE for school transport and can apply at - https://www.surreycouncilexample.govt.uk/application
- This student is NOT ELIGIBLE for school transport as they are too far from the desired school, have you considered East London High?
"""