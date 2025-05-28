import logging
from ..core import MagentBase
from ..types import AgentCard, Message, Part, TextPart, Role, Capabilities

logger = logging.getLogger(__name__)

class EchoAgent(MagentBase):
    def __init__(self, host: str = "0.0.0.0", port: int = 8081): # Default port for EchoAgent
        agent_card = AgentCard(
            name="EchoAgent",
            description="A simple agent that echoes back the primary text part of a message.",
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=Capabilities(streaming=False)
            # URL will be set by MagentBase constructor
        )
        super().__init__(agent_card, host, port)

    def handle_message(self, incoming_message: Message) -> Message:
        logger.info(f"EchoAgent ({self.agent_card.url}) received message: {incoming_message.model_dump_json(indent=1)}")
        
        response_text = "EchoAgent: No text part found to echo."
        if incoming_message.parts:
            first_part_root = incoming_message.parts[0].root
            if isinstance(first_part_root, TextPart):
                response_text = f"Echo: {first_part_root.text}"
        
        return Message(
            role=Role.AGENT,
            parts=[Part(root=TextPart(text=response_text))],
            context_id=incoming_message.context_id,
            task_id=incoming_message.task_id
        )

if __name__ == '__main__':
    agent_port = 8081 # Default port for this agent instance
    # Example: python echo_agent.py --port 8081
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for the agent server")
    parser.add_argument("--port", type=int, default=agent_port, help="Port for the agent server")
    args = parser.parse_args()

    echo_agent = EchoAgent(host=args.host, port=args.port)
    echo_agent.start()
    logger.info(f"EchoAgent running on http://{args.host}:{args.port}")
    logger.info("Press Ctrl+C to stop.")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logger.info("Shutting down EchoAgent...")
    finally:
        echo_agent.stop()
