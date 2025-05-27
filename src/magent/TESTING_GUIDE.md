# Multi-Agent System Testing Guide

This guide provides steps to manually test the coordinator and specialized agents.

## Prerequisites

1.  **Python Environment**: Ensure Python 3.7+ is installed.
2.  **pip**: Ensure pip is installed for managing Python packages.
3.  **Install Dependencies**:
    ```bash
    pip install pydantic httpx
    ```
    (Note: `pydantic` is used for data validation, `httpx` for the coordinator to call other agents).
4.  **Terminals**: You will need multiple terminal windows to run the coordinator and specialized agents simultaneously.

## Step 1: Start the Agents

Open three separate terminal windows.

1.  **Terminal 1: Start the CoordinatorAgent**
    Navigate to the root directory of this project.
    Run:
    ```bash
    python src/magent/coordinator.py --port 8000
    ```
    *Expected Output:* Logs indicating the CoordinatorAgent is running on `http://0.0.0.0:8000`.

2.  **Terminal 2: Start the EchoAgent**
    Navigate to the root directory of this project.
    Run:
    ```bash
    python src/magent/specialized_agents/echo_agent.py --port 8081
    ```
    *Expected Output:* Logs indicating the EchoAgent is running on `http://0.0.0.0:8081`.

3.  **Terminal 3: Start the SimpleMathAgent**
    Navigate to the root directory of this project.
    Run:
    ```bash
    python src/magent/specialized_agents/math_agent.py --port 8082
    ```
    *Expected Output:* Logs indicating the SimpleMathAgent is running on `http://0.0.0.0:8082`.

## Step 2: Perform Tests using cURL

You can use `curl` from another terminal or a REST client (like Postman or Insomnia) to send commands to the CoordinatorAgent.

### A. Verify Agents are Running and Serving `agent.json`

*   **Coordinator:**
    ```bash
    curl http://localhost:8000/.well-known/agent.json
    ```
*   **EchoAgent:**
    ```bash
    curl http://localhost:8081/.well-known/agent.json
    ```
*   **SimpleMathAgent:**
    ```bash
    curl http://localhost:8082/.well-known/agent.json
    ```
*   **Expected Result (for each):** A JSON response representing the agent's `AgentCard`. Ensure the name, description, and URL are correct.

### B. Register Specialized Agents with the Coordinator

*   **Register EchoAgent:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "REGISTER_AGENT http://localhost:8081", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
*   **Register SimpleMathAgent:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "REGISTER_AGENT http://localhost:8082", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
*   **Expected Result (for each):** The Coordinator should respond with a success message, e.g.,
    `{"role":"agent","parts":[{"root":{"text":"Coordinator: Successfully registered agent 'EchoAgent' from http://localhost:8081.","kind":"text"}}],"context_id":null,"task_id":null}`

### C. List Registered Agents

*   **Command:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "LIST_AGENTS", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
*   **Expected Result:** A message from the coordinator listing "EchoAgent (http://localhost:8081)" and "SimpleMathAgent (http://localhost:8082)".

### D. Delegate Task to EchoAgent

*   **Command:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "DELEGATE EchoAgent Hello from test guide", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
*   **Expected Result:** A response like:
    `{"role":"agent","parts":[{"root":{"text":"Task <TASK_ID> completed. Response from EchoAgent: Echo: Hello from test guide","kind":"text"}}],"context_id":null,"task_id":"<TASK_ID>"}`
    (where `<TASK_ID>` is a UUID).
    Also, check the EchoAgent's terminal output for logs showing it received and processed the message.

### E. Delegate Tasks to SimpleMathAgent

*   **Addition:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "DELEGATE SimpleMathAgent add 100 23", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
    *Expected Result:* `"...Response from SimpleMathAgent: MathAgent: Result of add 100 23 is 123.0"`
*   **Multiplication:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "DELEGATE SimpleMathAgent multiply 5 8", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
    *Expected Result:* `"...Response from SimpleMathAgent: MathAgent: Result of multiply 5 8 is 40.0"`
*   **Division by Zero (Error Handling):**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "DELEGATE SimpleMathAgent divide 9 0", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
    *Expected Result:* `"...Response from SimpleMathAgent: MathAgent: Error - Division by zero."`
*   Check the SimpleMathAgent's terminal output for logs.

### F. List Tasks

*   **Command:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "LIST_TASKS", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
*   **Expected Result:** A list of all tasks delegated so far, showing their IDs, status (e.g., `COMPLETED`, `FAILED`), and a brief detail.

### G. Cancel a Task (Simulated Cancellation)

1.  Delegate a new task to EchoAgent (or any agent) and note the `Task ID` from the response.
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "DELEGATE EchoAgent Task to be cancelled", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
    (Note the `Task ID` from this response, let's say it's `abc-123`)

2.  Attempt to cancel this task using its ID:
    ```bash
    # Replace <TASK_ID_TO_CANCEL> with the actual Task ID from the previous step
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "CANCEL_TASK <TASK_ID_TO_CANCEL>", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
*   **Expected Result:** Coordinator responds with a message like `Coordinator: Task <TASK_ID_TO_CANCEL> marked as cancelled.`

3.  List tasks again to see the updated status:
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "LIST_TASKS", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
*   **Expected Result:** The task you cancelled should now have its status as `CANCELLED` (or `FAILED` with a cancellation note, depending on final implementation in `coordinator.py`).

### H. Coordinator Error Handling Tests

*   **Delegate to a Non-Existent Agent:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "DELEGATE NonExistentAgent test message", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
    *Expected Result:* `"...Coordinator: Agent 'NonExistentAgent' not recognized."`

*   **Register Agent with a Bad URL:**
    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "REGISTER_AGENT http://thisurldoesnotexistforsure123.com:9999", "kind": "text"}}]}' http://localhost:8000/invoke
    ```
    *Expected Result:* A message indicating connection failure or inability to fetch `agent.json`.

*   **Send Malformed JSON to Coordinator's `/invoke` endpoint:**
    ```bash
    # Note the intentionally missing closing brace for the parts array
    curl -X POST -H "Content-Type: application/json" -d '{"role": "user", "parts": [{"root": {"text": "LIST_AGENTS", "kind": "text"}]' http://localhost:8000/invoke
    ```
    *Expected Result:* An HTTP 400 Bad Request error from the server (this might be shown by `curl` as an error, or the response body might indicate it). The Coordinator's terminal might log a JSON decoding error.

## Step 3: Stop the Agents

Press `Ctrl+C` in each terminal window where the agents are running to stop them.

This concludes the manual testing guide.
```
