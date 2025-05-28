import json
import logging
import httpx # For making HTTP requests to specialized agents
from typing import Dict, Optional
import uuid # For generating task IDs

from pydantic import ValidationError

from .core import MagentBase
from .types import (
    AgentCard,
    Message,
    Part,
    TextPart,
    Role,
    Task,
    TaskStatus,
    TaskState,
    Capabilities
)

logger = logging.getLogger(__name__)

class CoordinatorAgent(MagentBase):
    def __init__(
        self,
        name: str = "CoordinatorAgent",
        description: str = "Manages tasks and delegates to specialized agents.",
        host: str = "0.0.0.0",
        port: int = 8000 # Default port for the coordinator
    ):
        coordinator_card = AgentCard(
            name=name,
            description=description,
            default_input_modes=["text"], # Can accept text commands
            default_output_modes=["text"],
            capabilities=Capabilities(streaming=False)
            # URL will be set by MagentBase
        )
        super().__init__(coordinator_card, host, port)
        self.specialized_agents: Dict[str, AgentCard] = {} # name -> AgentCard
        self.active_tasks: Dict[str, Task] = {} # task_id -> Task

    def register_specialized_agent(self, agent_card: AgentCard):
        """Registers a specialized agent with the coordinator."""
        if agent_card.name in self.specialized_agents:
            logger.warning(f"Agent {agent_card.name} is already registered. Updating.")
        self.specialized_agents[agent_card.name] = agent_card
        logger.info(f"Specialized agent {agent_card.name} registered at {agent_card.url}")

    def _find_agent_by_capability(self, capability_keyword: str) -> Optional[AgentCard]:
        """Finds an agent that might handle a given capability (very basic)."""
        # This is a placeholder for more sophisticated capability matching.
        # For now, it can check if the keyword is in the agent's name or description.
        for agent_card in self.specialized_agents.values():
            if capability_keyword.lower() in agent_card.name.lower() or \
               (agent_card.description and capability_keyword.lower() in agent_card.description.lower()):
                return agent_card
        return None

    def handle_message(self, incoming_message: Message) -> Message:
        logger.info(f"Coordinator received message: {incoming_message.model_dump_json(indent=1)}")
        
        response_text = "Coordinator: Command not understood."
        
        # Simple command processing from the first text part
        if incoming_message.parts:
            # Assuming the part is Part(root=TextPart(...))
            # Accessing part.root to get to TextPart, DataPart, etc.
            part_content = incoming_message.parts[0].root 
            if isinstance(part_content, TextPart):
                command_full_text = part_content.text.strip()
                parts_cmd = command_full_text.split(" ", 1) # Renamed 'parts' to 'parts_cmd' to avoid conflict
                command = parts_cmd[0].upper()
                args_text = parts_cmd[1] if len(parts_cmd) > 1 else ""

                if command == "LIST_AGENTS":
                    if not self.specialized_agents:
                        response_text = "Coordinator: No specialized agents registered."
                    else:
                        agent_list_str = "\n".join([
                            f"- {name} ({agent.url})" for name, agent in self.specialized_agents.items()
                        ])
                        response_text = f"Coordinator: Registered Agents:\n{agent_list_str}"

                elif command == "REGISTER_AGENT" and args_text:
                    agent_url_to_register = args_text.strip()
                    if not agent_url_to_register.startswith(("http://", "https://")):
                        response_text = "Coordinator: Invalid URL format for REGISTER_AGENT. Must start with http:// or https://."
                    else:
                        # Ensure the URL for .well-known/agent.json is correctly formed
                        base_url = agent_url_to_register.rstrip('/')
                        agent_json_url = f"{base_url}/.well-known/agent.json"
                        logger.info(f"Coordinator attempting to register agent from: {agent_json_url}")
                        try:
                            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                                http_response = client.get(agent_json_url)
                                http_response.raise_for_status() 
                                agent_data = http_response.json()
                            
                            # Ensure the discovered URL is part of the card if not present or empty in agent.json
                            if 'url' not in agent_data or not agent_data['url']:
                                agent_data['url'] = base_url 
                            
                            discovered_agent_card = AgentCard(**agent_data)
                            
                            # If the card's URL is still not set (e.g. if agent.json had an empty string for url), set it.
                            # This is another safeguard, though the above should handle most cases.
                            if not discovered_agent_card.url:
                                discovered_agent_card.url = base_url

                            self.register_specialized_agent(discovered_agent_card)
                            response_text = f"Coordinator: Successfully registered agent '{discovered_agent_card.name}' from {discovered_agent_card.url}."
                        
                        except httpx.RequestError as e:
                            logger.error(f"Coordinator: HTTP request error while trying to fetch agent.json from {agent_json_url}: {e}")
                            response_text = f"Coordinator: Could not connect to or fetch agent.json from {agent_url_to_register}. Error: {e}"
                        except json.JSONDecodeError: 
                            logger.error(f"Coordinator: Invalid JSON received from {agent_json_url}")
                            response_text = f"Coordinator: Invalid JSON format for agent.json from {agent_url_to_register}."
                        except ValidationError as e: 
                            logger.error(f"Coordinator: Validation error for agent.json from {agent_json_url}: {e}")
                            response_text = f"Coordinator: Agent data from {agent_url_to_register} does not match expected format. Details: {e}"
                        except Exception as e: 
                            logger.error(f"Coordinator: Unexpected error during agent registration from {agent_url_to_register}: {e}", exc_info=True)
                            response_text = f"Coordinator: An unexpected error occurred during registration from {agent_url_to_register}."
                
                elif command == "DELEGATE" and args_text:
                    delegate_parts = args_text.split(" ", 1)
                    agent_name_target = delegate_parts[0]
                    task_text_for_agent = delegate_parts[1] if len(delegate_parts) > 1 else ""

                    if not agent_name_target or not task_text_for_agent:
                        response_text = "Coordinator: DELEGATE command requires AgentName and Task Text. Usage: DELEGATE <AgentName> <TextForAgent>"
                    elif agent_name_target in self.specialized_agents:
                        target_agent_card = self.specialized_agents[agent_name_target]
                        if not target_agent_card.url:
                            response_text = f"Coordinator: Agent {agent_name_target} has no URL configured."
                        else:
                            # 1. Create and store the task
                            task_id = str(uuid.uuid4())
                            new_task = Task(
                                id=task_id,
                                status=TaskStatus(state=TaskState.SUBMITTED, message=Message(role=Role.SYSTEM, parts=[Part(root=TextPart(text=f"Task submitted for delegation to {agent_name_target}."))])),
                                context_id=incoming_message.context_id
                            )
                            self.active_tasks[task_id] = new_task
                            
                            task_message_to_agent = Message(
                                role=Role.USER,
                                parts=[Part(root=TextPart(text=task_text_for_agent))],
                                context_id=incoming_message.context_id,
                                task_id=task_id # Pass task_id to specialized agent
                            )
                            logger.info(f"Coordinator delegating to {agent_name_target} (Task ID: {task_id}): {task_message_to_agent.model_dump_json(indent=1)}")
                            
                            try:
                                self.active_tasks[task_id].status = TaskStatus(state=TaskState.WORKING, message=Message(role=Role.SYSTEM, parts=[Part(root=TextPart(text=f"Task delegated to {agent_name_target}."))]))
                                with httpx.Client() as client:
                                    agent_invoke_url = f"{target_agent_card.url}/invoke"
                                    # Using model_dump(by_alias=False) as we expect snake_case internally
                                    # If specialized agents expect camelCase, then by_alias=True would be needed
                                    http_response = client.post(
                                        agent_invoke_url,
                                        json=task_message_to_agent.model_dump(by_alias=False), 
                                        timeout=10.0
                                    )
                                http_response.raise_for_status()
                                delegated_response_data = http_response.json()
                                delegated_message = Message(**delegated_response_data)
                                
                                self.active_tasks[task_id].status = TaskStatus(state=TaskState.COMPLETED, message=delegated_message)
                                if delegated_message.parts and isinstance(delegated_message.parts[0].root, TextPart):
                                    response_text = f"Task {task_id} completed. Response from {agent_name_target}: {delegated_message.parts[0].root.text}"
                                else:
                                    response_text = f"Task {task_id} completed. Coordinator: Received a non-text or empty response from {agent_name_target}."

                            except httpx.RequestError as e:
                                logger.error(f"Coordinator: HTTP request error (Task ID: {task_id}) for {agent_name_target}: {e}")
                                self.active_tasks[task_id].status = TaskStatus(state=TaskState.FAILED, message=Message(role=Role.SYSTEM, parts=[Part(root=TextPart(text=f"HTTP Error: {e}"))]))
                                response_text = f"Task {task_id} failed. Coordinator: Error connecting to agent {agent_name_target}."
                            except ValidationError as e: # Handles Pydantic validation for delegated_message
                                logger.error(f"Coordinator: Validation error (Task ID: {task_id}) for {agent_name_target}: {e}")
                                self.active_tasks[task_id].status = TaskStatus(state=TaskState.FAILED, message=Message(role=Role.SYSTEM, parts=[Part(root=TextPart(text=f"Response validation error: {e}"))]))
                                response_text = f"Task {task_id} failed. Coordinator: Invalid response format from agent {agent_name_target}."
                            except json.JSONDecodeError as e: # Handles JSON decoding for http_response.json()
                                logger.error(f"Coordinator: JSON decode error (Task ID: {task_id}) for {agent_name_target}: {e}")
                                self.active_tasks[task_id].status = TaskStatus(state=TaskState.FAILED, message=Message(role=Role.SYSTEM, parts=[Part(root=TextPart(text=f"Invalid JSON response from agent: {e}"))]))
                                response_text = f"Task {task_id} failed. Coordinator: Invalid JSON response from agent {agent_name_target}."
                            except Exception as e:
                                logger.error(f"Coordinator: Unexpected error (Task ID: {task_id}) for {agent_name_target}: {e}", exc_info=True)
                                self.active_tasks[task_id].status = TaskStatus(state=TaskState.FAILED, message=Message(role=Role.SYSTEM, parts=[Part(root=TextPart(text=f"Unexpected error: {e}"))]))
                                response_text = f"Task {task_id} failed. Coordinator: An unexpected error occurred with agent {agent_name_target}."
                    else:
                        response_text = f"Coordinator: Agent '{agent_name_target}' not recognized."

                elif command == "LIST_TASKS":
                    if not self.active_tasks:
                        response_text = "Coordinator: No active tasks."
                    else:
                        task_list_items = []
                        for task_id_iter, task_iter in self.active_tasks.items():
                            detail_text = "N/A"
                            if task_iter.status.message and task_iter.status.message.parts:
                                first_part_root = task_iter.status.message.parts[0].root
                                if isinstance(first_part_root, TextPart):
                                    detail_text = first_part_root.text
                            task_list_items.append(
                                f"- Task ID: {task_id_iter}, Status: {task_iter.status.state.value}, Details: {detail_text}"
                            )
                        task_list_str = "\n".join(task_list_items)
                        response_text = f"Coordinator: Active Tasks:\n{task_list_str}"
                
                elif command == "CANCEL_TASK" and args_text:
                    task_id_to_cancel = args_text.strip()
                    if task_id_to_cancel in self.active_tasks:
                        # Using TaskState.CANCELLED as it was added in types.py
                        self.active_tasks[task_id_to_cancel].status = TaskStatus(
                            state=TaskState.CANCELLED, 
                            message=Message(role=Role.SYSTEM, parts=[Part(root=TextPart(text="Task marked as cancelled by user."))])
                        )
                        response_text = f"Coordinator: Task {task_id_to_cancel} marked as cancelled."
                        logger.info(f"Task {task_id_to_cancel} marked as cancelled by user.")
                    else:
                        response_text = f"Coordinator: Task ID '{task_id_to_cancel}' not found."
                
                else:
                    response_text = (
                        "Coordinator: Unknown command. Try 'LIST_AGENTS', "
                        "'REGISTER_AGENT <AgentFullURL>', 'DELEGATE <AgentName> <TaskText>', "
                        "'LIST_TASKS', or 'CANCEL_TASK <TaskID>'."
                    )
            else:
                response_text = "Coordinator: Received a non-text message part. Please send text commands."

        return Message(
            role=Role.AGENT,
            parts=[Part(root=TextPart(text=response_text))],
            context_id=incoming_message.context_id,
            task_id=incoming_message.task_id 
        )

if __name__ == '__main__':
    coordinator = CoordinatorAgent(port=8000)
    coordinator.start()
    
    logger.info(f"Coordinator Agent '{coordinator.agent_card.name}' running on {coordinator.agent_card.url}")
    logger.info("You can register agents by calling coordinator.register_specialized_agent(agent_card_instance) or using the REGISTER_AGENT command.")
    logger.info("Example commands to send to coordinator via POST to /invoke:")
    logger.info('  { "role": "user", "parts": [{ "root": { "text": "LIST_AGENTS", "kind": "text" } }] }')
    logger.info('  { "role": "user", "parts": [{ "root": { "text": "REGISTER_AGENT http://localhost:8081", "kind": "text" } }] }')
    logger.info('  { "role": "user", "parts": [{ "root": { "text": "DELEGATE EchoAgent Hello from coordinator task system", "kind": "text" } }] }')
    logger.info('  { "role": "user", "parts": [{ "root": { "text": "LIST_TASKS", "kind": "text" } }] }')
    logger.info('  { "role": "user", "parts": [{ "root": { "text": "CANCEL_TASK <some_task_id>", "kind": "text" } }] }')


    logger.info(f"Consider running specialized agents, e.g.:")
    logger.info(f"  python -m src.magent.specialized_agents.echo_agent --port 8081")
    logger.info(f"  python -m src.magent.specialized_agents.math_agent --port 8082")
    logger.info("Then use REGISTER_AGENT, DELEGATE, LIST_TASKS, CANCEL_TASK commands.")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        logger.info("Shutting down CoordinatorAgent...")
    finally:
        coordinator.stop()
```
