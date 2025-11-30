"""
DAG (Directed Acyclic Graph) management for idea nodes.
"""

import uuid
from typing import List, Dict, Optional
from models import IdeaNode, AgentState, ConversationState, NodeStatus
import storage
from llm_helpers import get_embedding, similarity_search_nodes


# Similarity threshold for deduplication
SIMILARITY_THRESHOLD = 0.85


def create_node_from_opening(
    agent_state: AgentState,
    conversation: ConversationState,
    opening_text: str,
    footer: Dict
) -> IdeaNode:
    """
    Create an idea node from an agent's opening statement.

    Args:
        agent_state: The agent creating the node
        conversation: The conversation
        opening_text: The agent's opening statement text
        footer: Parsed council footer

    Returns:
        The created IdeaNode
    """
    # Generate node ID (use footer's current_node_id or generate new)
    node_id = footer.get("current_node_id") or f"node_{uuid.uuid4().hex[:12]}"

    # Extract summary from opening text (first 150 chars)
    summary = opening_text[:150].strip() + ("..." if len(opening_text) > 150 else "")

    # Create node
    node = IdeaNode(
        id=node_id,
        conversation_id=conversation.id,
        summary=summary,
        artifact=opening_text,
        parents=[],  # Opening nodes have no parents
        status=NodeStatus.ACTIVE,
        score=0.5,  # Initial score
        tags=[],
        embedding=get_embedding(opening_text),
        created_by_agent_id=agent_state.agent_id,
        equivalent_to=None
    )

    # Check for similar nodes and mark as equivalent if found
    _check_and_mark_duplicate(node, conversation.id)

    # Save node
    storage.save_node(node)

    # Update agent's current node
    agent_state.current_node_id = node_id
    storage.save_agent(agent_state)

    return node


def create_nodes_from_branch_proposals(
    agent_state: AgentState,
    conversation: ConversationState,
    footer: Dict
) -> List[IdeaNode]:
    """
    Create new idea nodes from branch proposals in the footer.

    Args:
        agent_state: The agent proposing branches
        conversation: The conversation
        footer: Parsed council footer with new_branch_proposals

    Returns:
        List of created IdeaNode objects
    """
    proposals = footer.get("new_branch_proposals", [])
    created_nodes = []

    for proposal in proposals:
        summary = proposal.get("summary", "")
        parent_node_id = proposal.get("parent_node_id")

        if not summary:
            continue

        # Generate unique node ID
        node_id = f"node_{uuid.uuid4().hex[:12]}"

        # Determine parents
        parents = []
        if parent_node_id and storage.get_node(parent_node_id):
            parents = [parent_node_id]
        elif agent_state.current_node_id:
            parents = [agent_state.current_node_id]

        # Create node
        node = IdeaNode(
            id=node_id,
            conversation_id=conversation.id,
            summary=summary,
            artifact=summary,  # For branch proposals, summary is the artifact
            parents=parents,
            status=NodeStatus.ACTIVE,
            score=0.5,
            tags=[],
            embedding=get_embedding(summary),
            created_by_agent_id=agent_state.agent_id,
            equivalent_to=None
        )

        # Check for duplicates
        _check_and_mark_duplicate(node, conversation.id)

        # Save node
        storage.save_node(node)
        created_nodes.append(node)

    return created_nodes


def _check_and_mark_duplicate(node: IdeaNode, conversation_id: str) -> None:
    """
    Check if a node is similar to existing nodes and mark as equivalent.

    Args:
        node: The node to check
        conversation_id: The conversation ID
    """
    # Search for similar nodes
    similar_nodes = similarity_search_nodes(
        query_embedding=node.embedding,
        conversation_id=conversation_id,
        top_k=3,
        exclude_ids=[node.id]
    )

    # If we find a very similar node, mark as equivalent
    for similar_node, similarity in similar_nodes:
        if similarity >= SIMILARITY_THRESHOLD:
            node.equivalent_to = similar_node.id
            # Inherit parent's score
            node.score = similar_node.score * 0.9
            break


def update_node_status(node_id: str, new_status: NodeStatus) -> Optional[IdeaNode]:
    """
    Update the status of a node.

    Args:
        node_id: The node's ID
        new_status: The new status

    Returns:
        The updated node, or None if not found
    """
    node = storage.get_node(node_id)
    if node:
        node.status = new_status
        storage.save_node(node)
    return node


def process_votes(footer: Dict) -> None:
    """
    Process votes from agent footer to update node statuses.

    Args:
        footer: Parsed council footer with votes
    """
    votes = footer.get("votes", {})

    for node_id, vote in votes.items():
        if vote == "COMPLETE":
            update_node_status(node_id, NodeStatus.COMPLETE)
        elif vote == "PRUNED":
            update_node_status(node_id, NodeStatus.PRUNED)


def get_node_depth(node_id: str) -> int:
    """
    Calculate the depth of a node in the DAG (distance from root).

    Args:
        node_id: The node's ID

    Returns:
        Depth of the node (0 for root nodes)
    """
    node = storage.get_node(node_id)
    if not node or not node.parents:
        return 0

    # Recursively find max parent depth
    parent_depths = [get_node_depth(parent_id) for parent_id in node.parents]
    return max(parent_depths, default=0) + 1


def print_dag_structure(conversation_id: str) -> str:
    """
    Generate a text representation of the DAG structure.

    Args:
        conversation_id: The conversation ID

    Returns:
        Text representation of the DAG
    """
    nodes = storage.get_nodes_for_conversation(conversation_id)

    if not nodes:
        return "No nodes in DAG."

    lines = ["", "=== DAG Structure ===", ""]

    # Group nodes by depth
    nodes_by_depth: Dict[int, List[IdeaNode]] = {}
    for node in nodes:
        depth = get_node_depth(node.id)
        if depth not in nodes_by_depth:
            nodes_by_depth[depth] = []
        nodes_by_depth[depth].append(node)

    # Print level by level
    for depth in sorted(nodes_by_depth.keys()):
        lines.append(f"Level {depth}:")
        for node in nodes_by_depth[depth]:
            parent_info = f" <- {node.parents}" if node.parents else " (root)"
            equiv_info = f" [EQUIV to {node.equivalent_to}]" if node.equivalent_to else ""
            lines.append(
                f"  {node.id}: {node.summary[:60]}... "
                f"[{node.status.value}] (score: {node.score:.2f})"
                f"{parent_info}{equiv_info}"
            )
        lines.append("")

    return "\n".join(lines)


def get_active_nodes(conversation_id: str) -> List[IdeaNode]:
    """
    Get all active nodes for a conversation.

    Args:
        conversation_id: The conversation ID

    Returns:
        List of active nodes
    """
    nodes = storage.get_nodes_for_conversation(conversation_id)
    return [node for node in nodes if node.status == NodeStatus.ACTIVE]


def get_priority_nodes(conversation: ConversationState) -> List[IdeaNode]:
    """
    Get priority nodes for a conversation.

    Args:
        conversation: The conversation

    Returns:
        List of priority nodes
    """
    return [
        storage.get_node(node_id)
        for node_id in conversation.priority_node_ids
        if storage.get_node(node_id)
    ]
