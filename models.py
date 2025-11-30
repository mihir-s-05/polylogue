"""
Data models for the LLM Council system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum


class Speaker(str, Enum):
    """Speaker type in transcript."""
    USER = "user"
    OVERSEER = "overseer"
    AGENT = "agent"


class NodeStatus(str, Enum):
    """Status of an idea node in the DAG."""
    ACTIVE = "ACTIVE"
    COMPLETE = "COMPLETE"
    PRUNED = "PRUNED"


class ConversationMode(str, Enum):
    """Conversation mode."""
    FAST = "fast"
    COUNCIL = "council"


class ConversationPhase(str, Enum):
    """Phase of council deliberation."""
    OPENING = "OPENING"
    DEBATE = "DEBATE"
    SYNTHESIS = "SYNTHESIS"
    DONE = "DONE"


@dataclass
class TranscriptMessage:
    """A message in the conversation transcript."""
    id: str
    conversation_id: str
    speaker: Speaker
    content: str
    timestamp: datetime
    agent_id: Optional[str] = None
    footer: Optional[Dict] = None


@dataclass
class IdeaNode:
    """A node in the ideas DAG."""
    id: str
    conversation_id: str
    summary: str
    artifact: str
    parents: List[str]
    status: NodeStatus
    score: float
    tags: List[str]
    embedding: List[float]
    created_by_agent_id: Optional[str] = None
    equivalent_to: Optional[str] = None


@dataclass
class AgentState:
    """State of a council agent."""
    agent_id: str
    persona_description: str
    last_spoke_at: datetime
    is_active: bool = True
    current_node_id: Optional[str] = None


@dataclass
class ConversationState:
    """Overall state of a council conversation."""
    id: str
    user_prompt: str
    mode: ConversationMode
    phase: ConversationPhase
    overseer_summary: str
    active_node_ids: List[str]
    priority_node_ids: List[str]
    global_token_budget: int
    used_tokens: int
    max_branches: int
    max_depth: int
    max_debate_rounds: int
    current_round: int
    agent_ids: List[str]
    created_at: datetime = field(default_factory=datetime.now)
