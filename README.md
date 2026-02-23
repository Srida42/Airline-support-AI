# Airline Support AI Assistant

A multimodal, agentic AI assistant built with Gradio, OpenAI GPT-4o-mini, and MySQL.

## Features
- **Multimodal Support**: Upload images of boarding passes or documents.
- **Agentic Tools**: AI can lookup bookings, change seats, and create support tickets.
- **Database Driven**: Uses MySQL to store and retrieve real-time flight data.
- **Professional UI**: Built with Gradio for a responsive and clean user experience.

## Project Structure
- `app.py`: The Gradio frontend and main entry point.
- `ai.py`: OpenAI integration and tool calling logic.
- `db.py`: MySQL database connection and operations.
- `tools.py`: Tool definitions and mappings for the AI.
- `schema.sql`: SQL script to set up the database.
- `requirements.txt`: Python package dependencies.

## Setup Instructions

1. **Database Setup**:
   - Ensure you have a MySQL server running.
   - Run the script in `schema.sql` to create the database and tables.

2. **Environment Configuration**:
   - Create a `.env` file in the root directory.
   - Add the following variables (refer to `.env.template`):
     ```env
     OPENAI_API_KEY=your_key
     MYSQL_HOST=localhost
     MYSQL_USER=your_user
     MYSQL_PASSWORD=your_password
     MYSQL_DATABASE=airline_support
     ```

3. **Install Requirements**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the App**:
   ```bash
   python app.py
   ```

## Usage
- Start chatting with the assistant.
- Upload a boarding pass image to automatically extract your booking info.
- Ask to change your seat or raise a support ticket.
