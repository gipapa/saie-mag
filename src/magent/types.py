from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field
import uuid

class Role(str, Enum):
    USER = "user"
    AGENT = "agent"
    MODEL = "model" # As seen in ADKHostManager conversion
    SYSTEM = "system" # Common role

class Provider(BaseModel):
    organization: Optional[str] = None

class Capabilities(BaseModel):
    streaming: bool = False
    push_notifications: bool = False # from AgentState

class AgentCard(BaseModel):
    url: Optional[str] = None # The address of the agent
    name: str
    description: Optional[str] = None
    provider: Optional[Provider] = None
    default_input_modes: List[str] = Field(default_factory=list) # Renamed from defaultInputModes
    default_output_modes: List[str] = Field(default_factory=list) # Renamed from defaultOutputModes
    capabilities: Capabilities = Field(default_factory=Capabilities)
    # id: str = Field(default_factory=lambda: str(uuid.uuid4())) # Optional: if agents need unique IDs beyond URL

class TextPart(BaseModel):
    text: str
    kind: str = "text"

class DataPart(BaseModel):
    data: Dict[str, Any]
    kind: str = "data"

class FileWithUri(BaseModel):
    uri: str
    mime_type: str # Renamed from mimeType
    name: Optional[str] = None

class FileWithBytes(BaseModel):
    bytes_content: str # Field name changed from 'bytes' which is a reserved keyword
    mime_type: str # Renamed from mimeType
    name: Optional[str] = None

class FilePart(BaseModel):
    file: Union[FileWithUri, FileWithBytes]
    kind: str = "file"

PartContent = Union[TextPart, DataPart, FilePart]

class Part(BaseModel):
    root: PartContent

    class Config:
        # For Pydantic v1, use this for discriminated union
        # smart_union = True
        # For Pydantic v2, type is automatically inferred in many cases,
        # but explicit discriminator can be useful if issues arise.
        # To handle the Union PartContent, Pydantic usually infers by shape,
        # or you can add a literal 'kind' field to each model in the Union
        # and use it as a discriminator.
        # For now, relying on Pydantic's default behavior for Union.
        pass


class Message(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4())) # Renamed from messageId
    context_id: Optional[str] = None # Renamed from contextId
    task_id: Optional[str] = None # Renamed from taskId
    role: Role
    parts: List[Part]
    # metadata: Optional[Dict[str, Any]] = None # As seen in get_message_id, but optional

class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled" # New state

class TaskStatus(BaseModel):
    state: TaskState
    message: Optional[Message] = None # A message associated with the current status

class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4())) # Renamed from artifactId
    parts: List[Part]
    # description: Optional[str] = None # Common for artifacts

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus
    artifacts: List[Artifact] = Field(default_factory=list)
    context_id: Optional[str] = None # Renamed from contextId
    history: List[Message] = Field(default_factory=list) # History of messages related to this task
    # name: Optional[str] = None
    # description: Optional[str] = None

# For events like TaskStatusUpdateEvent, TaskArtifactUpdateEvent
# These are not strictly types to be stored but represent data in transit.
# We can define them if direct interaction with a system like ADKHostManager's callback is needed,
# or handle their data payload directly.

class TaskStatusUpdateEvent(BaseModel):
    task_id: str # Renamed from taskId
    context_id: Optional[str] = None # Renamed from contextId
    status: TaskStatus

class TaskArtifactUpdateEvent(BaseModel):
    task_id: str # Renamed from taskId
    context_id: Optional[str] = None # Renamed from contextId
    artifact: Artifact
    append: bool = True # Whether to append to existing artifact data or replace
    last_chunk: Optional[bool] = None # Renamed from lastChunk


# Example of how AgentCard might be structured for .well-known/agent.json
# This is not a class to be instantiated directly in Python code often,
# but a representation of the JSON structure.
class AgentWellKnownInfo(AgentCard):
    # Usually, the .well-known/agent.json directly reflects the AgentCard structure.
    # No extra fields needed here unless the spec diverges.
    pass
