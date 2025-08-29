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
        self.agent_classifier = self.project.agents.get_agent("asst_classifier_xxx")
        self.agent_information = self.project.agents.get_agent("asst_information_xxx") 
        self.agent_eligibility = self.project.agents.get_agent("asst_eligibility_xxx")
        self.agent_decision = self.project.agents.get_agent("asst_decision_xxx")
        
        # Create conversation thread
        self.thread = self.project.agents.threads.create()
        
        # Session state for eligibility assessment
        self.assessment_data = {}
        self.current_stage = "classification"
        
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
            url = f"{os.environ['DISTANCE_API_ENDPOINT']}/distances/{postcode}"
            headers = {
                "api-key": os.environ["DISTANCE_API_KEY"],
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Could not retrieve distance data: {str(e)}"}
    
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
                        "output": json.dumps(distance_data)
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
        
        # Check if assessment is complete
        if "ASSESSMENT_COMPLETE:" in response:
            self.current_stage = "decision"
            # Extract assessment data for decision agent
            self.assessment_data = self.extract_assessment_data(response)
        
        return response
    
    def make_eligibility_decision(self, assessment_summary: str) -> str:
        """Final stage: Make eligibility decision based on collected data"""
        decision_prompt = f"""
        Based on the following eligibility assessment data, make a final decision:
        
        {assessment_summary}
        
        Assessment Data: {json.dumps(self.assessment_data, indent=2)}
        """
        
        message = self.project.agents.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=decision_prompt
        )

        run = self.project.agents.runs.create_and_process(
            thread_id=self.thread.id,
            agent_id=self.agent_decision.id
        )
        
        messages = self.project.agents.messages.list(
            thread_id=self.thread.id, 
            order=ListSortOrder.ASCENDING
        )

        decision = next(
            (msg.text_messages[-1].text.value for msg in list(messages)[::-1] 
             if msg.text_messages), None
        )
        
        # Reset for next conversation
        self.current_stage = "classification"
        self.assessment_data = {}
        
        return decision
    
    def extract_assessment_data(self, response: str) -> Dict[str, Any]:
        """Extract structured assessment data from eligibility agent response"""
        # Implementation would parse the agent's structured output
        # This could be JSON embedded in the response or use a specific format
        try:
            if "ASSESSMENT_DATA:" in response:
                data_section = response.split("ASSESSMENT_DATA:")[1].split("ASSESSMENT_COMPLETE:")[0]
                return json.loads(data_section.strip())
        except:
            pass
        return {}
    
    def get_chat_response(self, input_text: str) -> str:
        """Main entry point - routes queries to appropriate agents"""
        
        if self.current_stage == "classification":
            # First, classify the query type
            query_type = self.classify_query(input_text)
            
            if query_type == "Information_Request":
                return self.handle_information_request(input_text)
            
            elif query_type == "Eligibility_Check":
                self.current_stage = "assessment"
                return self.conduct_eligibility_assessment(input_text)
            
            elif query_type == "General_Greeting":
                return self.handle_information_request(input_text)
            
        elif self.current_stage == "assessment":
            # Continue eligibility assessment
            response = self.conduct_eligibility_assessment(input_text)
            
            # Check if we need to move to decision stage
            if self.current_stage == "decision":
                return self.make_eligibility_decision(response)
            
            return response
        
        elif self.current_stage == "decision":
            # This shouldn't normally happen, but handle gracefully
            self.current_stage = "classification"
            return self.classify_query(input_text)
    
    def reset_conversation(self):
        """Reset conversation state for new eligibility check"""
        self.assessment_data = {}
        self.current_stage = "classification"
        # Optionally create a new thread for clean slate
        self.thread = self.project.agents.threads.create()


# Example agent directives for Azure AI Foundry configuration:

"""
AGENT 1 - Query Classification Agent:
System Prompt:
You are a query classifier for a school transport eligibility system. 
Analyze user messages and return ONLY one of these categories:
- Information_Request: User wants general info about applications, process, deadlines
- Eligibility_Check: User wants to check if they/their child qualifies for transport
- General_Greeting: General greetings, thank you messages
- Application_Status: Questions about existing applications

Return only the category name, nothing else.

AGENT 2 - Information Agent:
System Prompt:
You are an information specialist for school transport applications. 
Use the provided documentation to answer questions about:
- Application processes and deadlines
- Required documents
- Contact information
- General policies

If users ask about eligibility, redirect them to start an eligibility check.
Keep responses helpful but concise.

AGENT 3 - Eligibility Assessment Agent:
System Prompt:
You are an eligibility assessment specialist. Your job is to ask questions to determine 
school transport eligibility based on these criteria:
- Distance to nearest appropriate school
- Special educational needs
- Family financial circumstances
- Safety considerations for the route
- Student age and school level

Ask questions systematically. When you receive a postcode, use the get_school_distances 
function to check distances. Continue asking until you have all needed information.

When assessment is complete, format your response as:
ASSESSMENT_DATA: {json_data_here}
ASSESSMENT_COMPLETE: Ready for decision

AGENT 4 - Decision Agent:
System Prompt:
You are the final decision maker for transport eligibility. Based on the assessment data:
1. Make a clear ELIGIBLE or NOT ELIGIBLE decision
2. Explain the reasoning based on the criteria and answers provided
3. If eligible, provide the application website link: [your_application_url]
4. If not eligible, suggest alternatives where possible

Be thorough in your explanation so the decision is transparent.
"""