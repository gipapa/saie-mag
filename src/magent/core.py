import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Type, Callable, Optional

from pydantic import ValidationError

from .types import AgentCard, Message as MagentMessage, Role, Capabilities # Added Role and Capabilities for the example

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MagentHttpHandler(BaseHTTPRequestHandler):
    # These class variables will be set by the MagentBase class
    agent_card_instance: Optional[AgentCard] = None
    message_handler_func: Optional[Callable[[MagentMessage], MagentMessage]] = None

    def do_GET(self):
        if self.path == '/.well-known/agent.json':
            if MagentHttpHandler.agent_card_instance:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                # Use by_alias=True if you want to output camelCase keys in JSON
                # as defined in the original AgentCard if you used Field(alias=...)
                # For now, assuming snake_case keys are fine for internal consistency.
                self.wfile.write(MagentHttpHandler.agent_card_instance.model_dump_json(indent=2).encode('utf-8'))
            else:
                self.send_error(404, "Agent Card not configured")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == '/invoke':
            if MagentHttpHandler.message_handler_func:
                try:
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    
                    logger.info(f"Received POST data: {post_data.decode('utf-8')}")
                    
                    message_data = json.loads(post_data.decode('utf-8'))
                    incoming_message = MagentMessage(**message_data)
                    
                    logger.info(f"Parsed incoming message: {incoming_message}")

                    response_message = MagentHttpHandler.message_handler_func(incoming_message)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(response_message.model_dump_json(indent=2).encode('utf-8'))
                    
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                    self.send_error(400, "Invalid JSON")
                except ValidationError as e:
                    logger.error(f"Message validation error: {e}")
                    self.send_error(400, f"Message validation error: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}", exc_info=True)
                    self.send_error(500, f"Internal Server Error: {e}")
            else:
                self.send_error(501, "Message handler not implemented")
        else:
            self.send_error(404, "Not Found")

class MagentBase:
    def __init__(self, agent_card: AgentCard, host: str = "0.0.0.0", port: int = 8000):
        self.agent_card = agent_card
        self.host = host
        self.port = port
        self.http_server: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None

        # Update the agent_card URL if it's not set or needs to reflect the server address
        if not self.agent_card.url: # Check if URL is None or empty string
            self.agent_card.url = f"http://{self.host}:{self.port}"
        
        # Pass the agent card and message handler to the request handler class
        MagentHttpHandler.agent_card_instance = self.agent_card
        MagentHttpHandler.message_handler_func = self.handle_message

    def handle_message(self, message: MagentMessage) -> MagentMessage:
        """
        Abstract method to be implemented by subclasses.
        This method will be called when a message is received at the /invoke endpoint.
        It should process the incoming message and return a response message.
        """
        raise NotImplementedError("Subclasses must implement handle_message")

    def start(self):
        """Starts the HTTP server in a separate thread."""
        if self.http_server:
            logger.info("Server already running.")
            return

        server_address = (self.host, self.port)
        self.http_server = HTTPServer(server_address, MagentHttpHandler)
        
        self.thread = Thread(target=self.http_server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"Agent {self.agent_card.name} started on {self.agent_card.url}")

    def stop(self):
        """Stops the HTTP server."""
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close() # Important to release the port
            if self.thread:
                self.thread.join()
            logger.info(f"Agent {self.agent_card.name} stopped.")
            self.http_server = None
            self.thread = None
        else:
            logger.info("Server not running.")

    def get_agent_json(self) -> str:
        """Returns the AgentCard as a JSON string."""
        return self.agent_card.model_dump_json(indent=2)

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    
    # Define a simple echo agent for testing
    class EchoAgent(MagentBase):
        def __init__(self, host: str = "0.0.0.0", port: int = 8080):
            card = AgentCard(
                name="EchoAgent",
                description="A simple agent that echoes back messages.",
                default_input_modes=["text"],
                default_output_modes=["text"],
                capabilities=Capabilities(streaming=False) # Make sure Capabilities is imported
            )
            super().__init__(card, host, port)

        def handle_message(self, message: MagentMessage) -> MagentMessage:
            logger.info(f"EchoAgent received message: {message.model_dump_json(indent=2)}")
            # Echo back the same parts
            return MagentMessage(
                role=Role.AGENT, # Make sure Role is imported
                parts=message.parts,
                context_id=message.context_id,
                task_id=message.task_id
            )

    echo_agent = EchoAgent(port=8080)
    echo_agent.start()

    try:
        logger.info(f"Access agent.json at: http://{echo_agent.host}:{echo_agent.port}/.well-known/agent.json")
        logger.info(f"POST to /invoke at: http://{echo_agent.host}:{echo_agent.port}/invoke")
        # Keep the main thread alive until interrupted
        while True:
            pass
    except KeyboardInterrupt:
        logger.info("Shutting down EchoAgent...")
    finally:
        echo_agent.stop()
