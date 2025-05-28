import logging
from ..core import MagentBase
from ..types import AgentCard, Message, Part, TextPart, Role, Capabilities

logger = logging.getLogger(__name__)

class SimpleMathAgent(MagentBase):
    def __init__(self, host: str = "0.0.0.0", port: int = 8082): # Default port for MathAgent
        agent_card = AgentCard(
            name="SimpleMathAgent",
            description="Performs simple arithmetic: add, subtract, multiply, divide. Usage: <operation> <num1> <num2>",
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=Capabilities(streaming=False)
        )
        super().__init__(agent_card, host, port)

    def handle_message(self, incoming_message: Message) -> Message:
        logger.info(f"SimpleMathAgent ({self.agent_card.url}) received message: {incoming_message.model_dump_json(indent=1)}")
        response_text = "MathAgent: Could not process request. Usage: <add|subtract|multiply|divide> <num1> <num2>"

        if incoming_message.parts:
            first_part_root = incoming_message.parts[0].root
            if isinstance(first_part_root, TextPart):
                command_text = first_part_root.text.strip().lower()
                parts = command_text.split()
                if len(parts) == 3:
                    op, s_num1, s_num2 = parts
                    try:
                        num1 = float(s_num1)
                        num2 = float(s_num2)
                        result = None
                        if op == "add":
                            result = num1 + num2
                        elif op == "subtract":
                            result = num1 - num2
                        elif op == "multiply":
                            result = num1 * num2
                        elif op == "divide":
                            if num2 == 0:
                                response_text = "MathAgent: Error - Division by zero."
                            else:
                                result = num1 / num2
                        else:
                            response_text = f"MathAgent: Unknown operation '{op}'. Choose add, subtract, multiply, or divide."
                        
                        if result is not None:
                            response_text = f"MathAgent: Result of {command_text} is {result}"
                    except ValueError:
                        response_text = "MathAgent: Error - Invalid numbers provided."
                    except Exception as e:
                        logger.error(f"MathAgent error processing '{command_text}': {e}", exc_info=True)
                        response_text = f"MathAgent: An unexpected error occurred."
        
        return Message(
            role=Role.AGENT,
            parts=[Part(root=TextPart(text=response_text))],
            context_id=incoming_message.context_id,
            task_id=incoming_message.task_id
        )

if __name__ == '__main__':
    agent_port = 8082 # Default port for this agent instance
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for the agent server")
    parser.add_argument("--port", type=int, default=agent_port, help="Port for the agent server")
    args = parser.parse_args()

    math_agent = SimpleMathAgent(host=args.host, port=args.port)
    math_agent.start()
    logger.info(f"SimpleMathAgent running on http://{args.host}:{args.port}")
    logger.info("Press Ctrl+C to stop.")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logger.info("Shutting down SimpleMathAgent...")
    finally:
        math_agent.stop()
