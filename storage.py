"""
In-memory data storage for the LLM Council system.
"""

from typing import Dict, List, Optional
from models import ConversationState, TranscriptMessage, IdeaNode, AgentState


# Global in-memory registries
conversations: Dict[str, ConversationState] = {}
messages: Dict[str, TranscriptMessage] = {}
nodes: Dict[str, IdeaNode] = {}
agents: Dict[str, AgentState] = {}


def get_conversation(conversation_id: str) -> Optional[ConversationState]:
    """Retrieve a conversation by ID."""
    return conversations.get(conversation_id)


def save_conversation(conversation: ConversationState) -> None:
    """Save or update a conversation."""
    conversations[conversation.id] = conversation


def get_message(message_id: str) -> Optional[TranscriptMessage]:
    """Retrieve a message by ID."""
    return messages.get(message_id)


def save_message(message: TranscriptMessage) -> None:
    """Save a message to the transcript."""
    messages[message.id] = message


def get_messages_for_conversation(conversation_id: str) -> List[TranscriptMessage]:
    """Get all messages for a conversation, sorted by timestamp."""
    conv_messages = [
        msg for msg in messages.values()
        if msg.conversation_id == conversation_id
    ]
    return sorted(conv_messages, key=lambda m: m.timestamp)


def get_node(node_id: str) -> Optional[IdeaNode]:
    """Retrieve a node by ID."""
    return nodes.get(node_id)


def save_node(node: IdeaNode) -> None:
    """Save or update a node."""
    nodes[node.id] = node


def get_nodes_for_conversation(conversation_id: str) -> List[IdeaNode]:
    """Get all nodes for a conversation."""
    return [
        node for node in nodes.values()
        if node.conversation_id == conversation_id
    ]


def get_agent(agent_id: str) -> Optional[AgentState]:
    """Retrieve an agent by ID."""
    return agents.get(agent_id)


def save_agent(agent: AgentState) -> None:
    """Save or update an agent."""
    agents[agent.agent_id] = agent


def get_all_agents() -> List[AgentState]:
    """Get all registered agents."""
    return list(agents.values())


def clear_all_data() -> None:
    """Clear all in-memory data (useful for testing)."""
    conversations.clear()
    messages.clear()
    nodes.clear()
    agents.clear()
