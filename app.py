import gradio as gr
from ai import chat_with_ai
import os

def respond(message, history):
    # message is a dict with 'text' and 'files'
    text = message.get("text", "")
    files = message.get("files", [])
    
    file_path = None
    if files:
        # Gradio multimodal files can be a list of paths or dicts
        first_file = files[0]
        if isinstance(first_file, dict):
            file_path = first_file.get("path")
        else:
            file_path = first_file
    
    # In Gradio 5+, history is a list of dicts: [{"role": "user", "content": "..."}, ...]
    # We need to convert it back to tuples for ai.py OR update ai.py
    # Let's convert it to tuples here to minimize changes in ai.py
    formatted_history = []
    user_msg = None
    for msg in history:
        if msg["role"] == "user":
            user_msg = msg["content"]
        elif msg["role"] == "assistant":
            if user_msg is not None:
                formatted_history.append((user_msg, msg["content"]))
                user_msg = None
    
    response = chat_with_ai(text, formatted_history, file_path)
    return response

# Customizing the UI
custom_css = """
footer {visibility: hidden}
.gradio-container {
    background-color: #f0f2f5;
}
"""

with gr.Blocks(title="Airline Support AI") as demo:
    gr.Markdown("# ✈️ Airline Multimodal Support Assistant")
    gr.Markdown("Upload your boarding pass or type your query below. Our AI agent can help you with bookings, seat changes, and support tickets.")
    
    chat_interface = gr.ChatInterface(
        fn=respond,
        multimodal=True,
        examples=[
            [{"text": "Get my booking details for ABC123", "files": []}],
            [{"text": "I want to change my seat to 15A", "files": []}],
            [{"text": "I have an issue with my meal, create a ticket", "files": []}]
        ]
    )

if __name__ == "__main__":
    demo.launch(css=custom_css)
