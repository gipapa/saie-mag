# `src/magent` - Multi-Agent System

This directory contains a Python-based multi-agent system designed for extensibility and interaction, allowing a coordinator agent to manage and delegate tasks to specialized agents.

## Architecture Overview

The system is built around a few core components:

1.  **`types.py`**: Defines the fundamental data structures using Pydantic models. These include:
    *   `AgentCard`: Represents the "business card" of an agent, detailing its capabilities, name, URL, etc. Served via a `/.well-known/agent.json` endpoint.
    *   `Message`: The standard format for communication between agents and users.
    *   `Part` (and its variants `TextPart`, `DataPart`, `FilePart`): Define the content of messages.
    *   `Task`, `TaskStatus`, `TaskState`: Used by the Coordinator to track delegated operations.
    *   `Role`: Enum for message sender types (user, agent, system).

2.  **`core.py`**:
    *   Provides `MagentBase`, a base class for all agents in this system.
    *   Handles common agent functionalities:
        *   Serving its `AgentCard` via `/.well-known/agent.json`.
        *   An HTTP server (based on Python's `http.server`) to listen for incoming messages on an `/invoke` endpoint.
        *   Requires subclasses to implement a `handle_message(message: Message) -> Message` method for their specific logic.

3.  **`coordinator.py`**:
    *   Implements `CoordinatorAgent`, which inherits from `MagentBase`.
    *   Acts as the central point of contact and task delegation.
    *   **Capabilities**:
        *   Manages a list of registered specialized agents.
        *   Can register new specialized agents at runtime via a `REGISTER_AGENT <agent_url>` command.
        *   Delegates tasks to specialized agents based on user commands (e.g., `DELEGATE <AgentName> <TaskText>`).
        *   Tracks delegated tasks and their status.
        *   Allows users to list registered agents (`LIST_AGENTS`) and active tasks (`LIST_TASKS`).
        *   Allows users to mark tasks for cancellation (`CANCEL_TASK <TaskID>`).

4.  **`specialized_agents/` directory**:
    *   Contains example implementations of specialized agents, such as:
        *   `echo_agent.py`: A simple agent that echoes back received text.
        *   `math_agent.py`: An agent that performs basic arithmetic operations.
    *   These agents also inherit from `MagentBase` and implement their specific skills in `handle_message`.

## Running the System

Please refer to [`TESTING_GUIDE.md`](./TESTING_GUIDE.md) for detailed instructions on:
*   Prerequisites and installing dependencies.
*   Starting the CoordinatorAgent and various specialized agents.
*   Testing the system's functionalities using `curl` or a similar tool.

## Defining a New Specialized Agent

To create a new specialized agent:

1.  **Create a Python file** for your agent (e.g., `src/magent/specialized_agents/my_new_agent.py`).
2.  **Import necessary classes**:
    ```python
    from ..core import MagentBase
    from ..types import AgentCard, Message, Part, TextPart, Role, Capabilities # Add other types as needed
    import logging

    logger = logging.getLogger(__name__)
    ```
3.  **Define your agent class**, inheriting from `MagentBase`:
    ```python
    class MyNewAgent(MagentBase):
        def __init__(self, host: str = "0.0.0.0", port: int = 80XX): # Choose a unique port
            my_agent_card = AgentCard(
                name="MyNewAgentName", # Unique and descriptive name
                description="Brief description of what this agent does.",
                default_input_modes=["text"], # Or other relevant modes
                default_output_modes=["text"],
                capabilities=Capabilities(streaming=False) # Adjust capabilities as needed
                # The URL will be set automatically by MagentBase
            )
            super().__init__(my_agent_card, host, port)

        def handle_message(self, incoming_message: Message) -> Message:
            logger.info(f"MyNewAgent ({self.agent_card.url}) received: {incoming_message.parts[0].root.text if incoming_message.parts else 'empty message'}")
            
            # --- Your agent's custom logic goes here ---
            response_text = "MyNewAgent processed your request."
            # Based on incoming_message.parts, perform actions and generate response_text
            # --- End of custom logic ---

            return Message(
                role=Role.AGENT,
                parts=[Part(root=TextPart(text=response_text))],
                context_id=incoming_message.context_id,
                task_id=incoming_message.task_id # Propagate task_id if received
            )
    ```
4.  **Add a `__main__` block** to make your agent runnable:
    ```python
    if __name__ == '__main__':
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", type=str, default="0.0.0.0")
        parser.add_argument("--port", type=int, default=80XX) # Use the port you chose
        args = parser.parse_args()

        agent = MyNewAgent(host=args.host, port=args.port)
        agent.start()
        logger.info(f"{agent.agent_card.name} running on http://{args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop.")
        try:
            while True:
                pass
        except KeyboardInterrupt:
            logger.info(f"Shutting down {agent.agent_card.name}...")
        finally:
            agent.stop()
    ```
5.  **Make it runnable**:
    ```bash
    python src/magent/specialized_agents/my_new_agent.py --port 80XX
    ```
6.  **Register with Coordinator**: Once your new agent is running, you can register it with a running CoordinatorAgent using the `REGISTER_AGENT` command:
    ```bash
    # Example using curl, assuming coordinator is on port 8000
    curl -X POST -H "Content-Type: application/json"          -d '{"role": "user", "parts": [{"root": {"text": "REGISTER_AGENT http://localhost:80XX", "kind": "text"}}]}'          http://localhost:8000/invoke
    ```

This structure allows for easy expansion with new specialized agents, each focusing on a specific capability, all orchestrated by the CoordinatorAgent.
```
