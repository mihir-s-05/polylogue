"""
DAG / Node management for the LLM Council system.
Handles creation, linking, and similarity checking of idea nodes.
"""

import uuid
from council.models import IdeaNode, AgentState, ConversationState
from council.llm_helpers import get_embedding, cosine_similarity
from council import registries


# Similarity threshold for considering nodes equivalent
SIMILARITY_THRESHOLD = 0.95


def check_node_similarity(
    new_embedding: list[float], 
    conversation_id: str
) -> tuple[bool, str | None]:
    """
    Check if a new node embedding is similar to existing nodes.
    
    Args:
        new_embedding: The embedding of the new node
        conversation_id: The conversation to check within
        
    Returns:
        Tuple of (is_similar, equivalent_node_id or None)
    """
    existing_nodes = registries.get_conversation_nodes(conversation_id)
    
    for node in existing_nodes:
        if node.embedding:
            similarity = cosine_similarity(new_embedding, node.embedding)
            if similarity > SIMILARITY_THRESHOLD:
                return True, node.id
    
    return False, None


def create_node_from_opening(
    agent_state: AgentState,
    conversation: ConversationState,
    opening_text: str,
    footer: dict
) -> IdeaNode:
    """
    Create an IdeaNode from an agent's opening statement.
    
    Args:
        agent_state: The agent who created the opening
        conversation: The conversation context
        opening_text: The opening statement content
        footer: The parsed [COUNCIL_STATE] footer
        
    Returns:
        The created IdeaNode
    """
    node_id = f"node_{uuid.uuid4().hex[:8]}"
    
    # Generate summary from the opening text (first 100 chars for MVP)
    summary = opening_text[:100] + "..." if len(opening_text) > 100 else opening_text
    
    # Check for proposals in footer
    if footer.get("new_branch_proposals"):
        proposal = footer["new_branch_proposals"][0]
        if proposal.get("summary"):
            summary = proposal["summary"]
    
    # Generate embedding
    embedding = get_embedding(opening_text)
    
    # Check for similarity with existing nodes
    is_similar, equivalent_id = check_node_similarity(embedding, conversation.id)
    
    node = IdeaNode(
        id=node_id,
        conversation_id=conversation.id,
        summary=summary,
        artifact=opening_text,
        parents=[],  # Opening nodes have no parents
        status="ACTIVE",
        score=1.0,  # Initial score
        tags=["opening"],
        created_by_agent_id=agent_state.agent_id,
        equivalent_to=equivalent_id if is_similar else None,
        embedding=embedding
    )
    
    # Store the node
    registries.nodes[node.id] = node
    
    # Update agent's current node
    agent_state.current_node_id = node.id
    registries.agents[agent_state.agent_id] = agent_state
    
    # Update conversation's active nodes
    if node.id not in conversation.active_node_ids:
        conversation.active_node_ids.append(node.id)
    registries.conversations[conversation.id] = conversation
    
    return node


def create_nodes_from_branch_proposals(
    agent_state: AgentState,
    conversation: ConversationState,
    footer: dict
) -> list[IdeaNode]:
    """
    Create IdeaNodes from branch proposals in an agent's footer.
    
    Args:
        agent_state: The agent proposing branches
        conversation: The conversation context
        footer: The parsed [COUNCIL_STATE] footer
        
    Returns:
        List of created IdeaNodes
    """
    created_nodes = []
    proposals = footer.get("new_branch_proposals", [])
    
    for proposal in proposals:
        summary = proposal.get("summary", "Unnamed proposal")
        parent_id = proposal.get("parent_id")
        
        # Validate parent exists if specified
        parents = []
        if parent_id and registries.get_node(parent_id):
            parents = [parent_id]
        elif agent_state.current_node_id:
            # Default to agent's current node as parent
            parents = [agent_state.current_node_id]
        
        node_id = f"node_{uuid.uuid4().hex[:8]}"
        
        # Generate embedding
        embedding = get_embedding(summary)
        
        # Check for similarity
        is_similar, equivalent_id = check_node_similarity(embedding, conversation.id)
        
        # For MVP: if similar, just mark equivalent_to but still create node
        node = IdeaNode(
            id=node_id,
            conversation_id=conversation.id,
            summary=summary,
            artifact=summary,  # For branch proposals, summary is the artifact
            parents=parents,
            status="ACTIVE",
            score=0.5,  # New branches start with lower score
            tags=["branch"],
            created_by_agent_id=agent_state.agent_id,
            equivalent_to=equivalent_id if is_similar else None,
            embedding=embedding
        )
        
        # Store the node
        registries.nodes[node.id] = node
        created_nodes.append(node)
        
        # Update conversation's active nodes
        if node.id not in conversation.active_node_ids:
            conversation.active_node_ids.append(node.id)
    
    # Update conversation
    registries.conversations[conversation.id] = conversation
    
    return created_nodes


def update_node_from_vote(node_id: str, vote_score: int) -> None:
    """
    Update a node's score based on a vote.
    
    Args:
        node_id: The node being voted on
        vote_score: The vote score (1-5)
    """
    node = registries.get_node(node_id)
    if node:
        # Simple additive scoring for MVP
        node.score += (vote_score - 3) * 0.2  # Votes above 3 increase, below 3 decrease
        registries.nodes[node.id] = node


def prune_node(node_id: str) -> None:
    """
    Mark a node as pruned.
    
    Args:
        node_id: The node to prune
    """
    node = registries.get_node(node_id)
    if node:
        node.status = "PRUNED"
        registries.nodes[node.id] = node
        
        # Also remove from active_node_ids
        for conv in registries.conversations.values():
            if node_id in conv.active_node_ids:
                conv.active_node_ids.remove(node_id)
            if node_id in conv.priority_node_ids:
                conv.priority_node_ids.remove(node_id)


def log_dag_structure(conversation_id: str) -> str:
    """
    Generate a text representation of the DAG structure for logging.
    
    TODO 2: Add basic logging of DAG structure per conversation (nodes + parents)
    
    Args:
        conversation_id: The conversation to log
        
    Returns:
        String representation of the DAG
    """
    nodes = registries.get_conversation_nodes(conversation_id)
    
    lines = [f"DAG Structure for Conversation {conversation_id}:"]
    lines.append("-" * 50)
    
    for node in nodes:
        parent_info = f" -> parents: {node.parents}" if node.parents else " (root)"
        equiv_info = f" [equiv to: {node.equivalent_to}]" if node.equivalent_to else ""
        lines.append(
            f"  {node.id} ({node.status}, score={node.score:.2f}){parent_info}{equiv_info}"
        )
        lines.append(f"    Summary: {node.summary[:60]}...")
        lines.append(f"    Created by: {node.created_by_agent_id}")
    
    return "\n".join(lines)
