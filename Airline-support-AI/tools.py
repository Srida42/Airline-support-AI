from db import get_booking_details, update_seat, create_ticket

def get_booking_tool(pnr: str, last_name: str = None):
    """
    Fetches booking details from the database using PNR and optionally the last name.
    """
    return get_booking_details(pnr, last_name)

def change_seat_tool(pnr: str, new_seat: str):
    """
    Changes the seat for a given PNR.
    """
    return update_seat(pnr, new_seat)

def create_ticket_tool(pnr: str, issue: str):
    """
    Creates a support ticket for a flight booking issue.
    """
    return create_ticket(pnr, issue)

# Define tool schemas for OpenAI
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_booking_details",
            "description": "Get flight booking information using PNR and passenger last name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string", "description": "The Passenger Name Record (PNR) number."},
                    "last_name": {"type": "string", "description": "The last name of the passenger."}
                },
                "required": ["pnr"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "change_seat",
            "description": "Update the seat number for a passenger's booking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string", "description": "The Passenger Name Record (PNR) number."},
                    "new_seat": {"type": "string", "description": "The new seat number (e.g., '14B')."}
                },
                "required": ["pnr", "new_seat"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Create a support ticket for issues related to a booking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string", "description": "The Passenger Name Record (PNR) number."},
                    "issue": {"type": "string", "description": "Detailed description of the issue."}
                },
                "required": ["pnr", "issue"]
            }
        }
    }
]

# Map tool names to actual functions
TOOL_MAP = {
    "get_booking_details": get_booking_tool,
    "change_seat": change_seat_tool,
    "create_support_ticket": create_ticket_tool
}
