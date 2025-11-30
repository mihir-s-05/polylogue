"""
In-memory registries for storing conversation state, messages, nodes, and agents.
"""

from council.models import ConversationState, TranscriptMessage, IdeaNode, AgentState

# In-Memory Registries
conversations: dict[str, ConversationState] = {}
messages: dict[str, TranscriptMessage] = {}
nodes: dict[str, IdeaNode] = {}
agents: dict[str, AgentState] = {}


def clear_all_registries() -> None:
    """Clear all registries. Useful for testing."""
    conversations.clear()
    messages.clear()
    nodes.clear()
    agents.clear()


def get_conversation(conversation_id: str) -> ConversationState | None:
    """Get a conversation by ID."""
    return conversations.get(conversation_id)


def get_message(message_id: str) -> TranscriptMessage | None:
    """Get a message by ID."""
    return messages.get(message_id)


def get_node(node_id: str) -> IdeaNode | None:
    """Get a node by ID."""
    return nodes.get(node_id)


def get_agent(agent_id: str) -> AgentState | None:
    """Get an agent by ID."""
    return agents.get(agent_id)


def get_conversation_messages(conversation_id: str) -> list[TranscriptMessage]:
    """Get all messages for a conversation."""
    return [m for m in messages.values() if m.conversation_id == conversation_id]


def get_conversation_nodes(conversation_id: str) -> list[IdeaNode]:
    """Get all nodes for a conversation."""
    return [n for n in nodes.values() if n.conversation_id == conversation_id]


def get_conversation_agents(conversation_id: str) -> list[AgentState]:
    """Get all agents for a conversation by looking up agent_ids in the conversation."""
    conv = get_conversation(conversation_id)
    if not conv:
        return []
    return [agents[aid] for aid in conv.agent_ids if aid in agents]
