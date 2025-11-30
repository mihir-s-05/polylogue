"""
Data models for the LLM Council system.
Uses dataclasses for all models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal


@dataclass
class TranscriptMessage:
    """Represents a message in the council transcript."""
    id: str
    conversation_id: str
    speaker: Literal["user", "overseer", "agent"]
    content: str
    agent_id: Optional[str] = None
    footer: Optional[dict] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class IdeaNode:
    """Represents a node in the idea DAG."""
    id: str
    conversation_id: str
    summary: str
    artifact: str
    parents: list[str] = field(default_factory=list)
    status: Literal["ACTIVE", "COMPLETE", "PRUNED"] = "ACTIVE"
    score: float = 0.0
    tags: list[str] = field(default_factory=list)
    created_by_agent_id: Optional[str] = None
    equivalent_to: Optional[str] = None
    embedding: list[float] = field(default_factory=list)


@dataclass
class AgentState:
    """Represents the state of a council agent."""
    agent_id: str
    persona_description: str
    current_node_id: Optional[str] = None
    last_spoke_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class ConversationState:
    """Represents the state of a council conversation."""
    id: str
    user_prompt: str
    mode: Literal["fast", "council"] = "council"
    phase: Literal["OPENING", "DEBATE", "SYNTHESIS", "DONE"] = "OPENING"
    overseer_summary: str = ""
    active_node_ids: list[str] = field(default_factory=list)
    priority_node_ids: list[str] = field(default_factory=list)
    global_token_budget: int = 4000
    used_tokens: int = 0
    max_branches: int = 4
    max_depth: int = 3
    max_debate_rounds: int = 8
    current_round: int = 0
    agent_ids: list[str] = field(default_factory=list)
