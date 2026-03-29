import os
import base64
import json
from openai import OpenAI
from dotenv import load_dotenv
from tools import TOOLS, TOOL_MAP

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key == "your_key":
    client = None
else:
    client = OpenAI(api_key=api_key)

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """
You are a professional and helpful Airline Support Assistant.
You can help passengers with:
1. Searching for available flights by origin and/or destination (city name or airport code).
2. Checking booking details using PNR and last name.
3. Changing seats for an existing booking.
4. Creating support tickets for issues.

When searching flights, always call the search_flights tool with the origin and/or destination
extracted from the user's message. Never answer flight search queries from memory.

When a user uploads an image of a boarding pass, extract the PNR, passenger name, and flight number.
Always be polite and professional. If you perform an action like a seat change, confirm it with the user.
If you need more information (like PNR or last name), ask the user clearly.
"""

def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None

def chat_with_ai(message, history, file_path=None):
    if not client:
        return "⚠️ OpenAI API Key is missing or invalid. Please add your `OPENAI_API_KEY` to the `.env` file to use the AI assistant."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add history
    for human, assistant in history:
        # human can be a string or a dict {"text": "...", "files": [...]}
        if isinstance(human, dict):
            human_text = human.get("text", "")
        else:
            human_text = str(human)
            
        messages.append({"role": "user", "content": human_text})
        messages.append({"role": "assistant", "content": assistant})
    
    # Prepare current user content
    user_content = []
    if message:
        user_content.append({"type": "text", "text": message})
    
    if file_path:
        base64_image = encode_image(file_path)
        if base64_image:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
            # If image is provided but no message, add a default prompt
            if not message:
                user_content.insert(0, {"type": "text", "text": "I've uploaded a file. Can you check my booking details from it?"})
    
    if not user_content:
        return "Please provide a message or an image."

    messages.append({"role": "user", "content": user_content})
    
    try:
        # Call OpenAI
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        if tool_calls:
            # Add assistant message with tool calls to history
            messages.append(response_message)
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Execute tool
                function_to_call = TOOL_MAP.get(function_name)
                if function_to_call:
                    function_response = function_to_call(**function_args)
                    
                    # Add tool result to conversation
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(function_response),
                    })
            
            # Second call to get final response
            second_response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
            )
            return second_response.choices[0].message.content
        
        return response_message.content
    except Exception as e:
        return f"❌ Error communicating with AI: {str(e)}"