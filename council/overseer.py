"""
Overseer logic for the LLM Council system.
The overseer orchestrates the council deliberation process.
"""

import json
from council.models import ConversationState
from council.llm_helpers import call_llm
from council import registries


def init_overseer(conversation: ConversationState) -> None:
    """
    Initialize the overseer for a new council conversation.
    
    Args:
        conversation: The conversation state to initialize
    """
    conversation.mode = "council"
    conversation.phase = "OPENING"
    
    # Create initial overseer summary from user prompt
    init_prompt = f"""You are the overseer of an LLM Council deliberation.
    
User's request: {conversation.user_prompt}

Create an initial summary that frames this topic for the council members to discuss.
Identify key aspects that should be explored."""
    
    conversation.overseer_summary = call_llm(
        role="overseer_init",
        prompt=init_prompt,
        max_tokens=300
    )
    
    # Save updated conversation
    registries.conversations[conversation.id] = conversation


def overseer_update(conversation: ConversationState) -> None:
    """
    Update the overseer's summary and node priorities based on current state.
    
    Args:
        conversation: The conversation state to update
    """
    # Get current nodes for this conversation
    current_nodes = registries.get_conversation_nodes(conversation.id)
    
    # Get recent messages
    recent_messages = registries.get_conversation_messages(conversation.id)
    recent_messages = sorted(recent_messages, key=lambda m: m.timestamp, reverse=True)[:10]
    
    # Build node summaries
    node_summaries = []
    for node in current_nodes:
        if node.status == "ACTIVE":
            node_summaries.append(f"- Node {node.id}: {node.summary} (score: {node.score})")
    
    # Build message summaries
    message_summaries = []
    for msg in recent_messages:
        speaker_info = msg.agent_id if msg.speaker == "agent" else msg.speaker
        message_summaries.append(f"- {speaker_info}: {msg.content[:100]}...")
    
    update_prompt = f"""You are the overseer of an LLM Council deliberation.

User's request: {conversation.user_prompt}

Current phase: {conversation.phase}
Current round: {conversation.current_round}

Current idea nodes:
{chr(10).join(node_summaries) if node_summaries else "No nodes yet"}

Recent messages:
{chr(10).join(message_summaries) if message_summaries else "No messages yet"}

Update your summary of the deliberation progress and identify priority areas to explore."""
    
    conversation.overseer_summary = call_llm(
        role="overseer_update",
        prompt=update_prompt,
        max_tokens=400
    )
    
    # Update node scores (simple heuristic for MVP)
    for node in current_nodes:
        if node.status == "ACTIVE":
            # Base score on recency and connections
            node.score = 1.0 + len(node.parents) * 0.2
            registries.nodes[node.id] = node
    
    # Update priority_node_ids (top N by score)
    active_nodes = [n for n in current_nodes if n.status == "ACTIVE"]
    sorted_nodes = sorted(active_nodes, key=lambda n: n.score, reverse=True)
    conversation.priority_node_ids = [n.id for n in sorted_nodes[:conversation.max_branches]]
    
    # Update active_node_ids
    conversation.active_node_ids = [n.id for n in active_nodes]
    
    # Save updated conversation
    registries.conversations[conversation.id] = conversation


def overseer_synthesis(conversation: ConversationState) -> dict:
    """
    Generate the final synthesis from the council deliberation.
    
    Args:
        conversation: The conversation state to synthesize
        
    Returns:
        Dict with 'final_answer' and 'council_summary' keys
    """
    # Get top nodes by score
    current_nodes = registries.get_conversation_nodes(conversation.id)
    active_nodes = [n for n in current_nodes if n.status == "ACTIVE"]
    sorted_nodes = sorted(active_nodes, key=lambda n: n.score, reverse=True)[:5]
    
    # Build node representation
    node_text = []
    for node in sorted_nodes:
        node_text.append(f"Node {node.id} (score: {node.score}):")
        node_text.append(f"  Summary: {node.summary}")
        node_text.append(f"  Artifact: {node.artifact[:200]}..." if len(node.artifact) > 200 else f"  Artifact: {node.artifact}")
        node_text.append("")
    
    synthesis_prompt = f"""You are the overseer synthesizing the final output of an LLM Council deliberation.

User's original request: {conversation.user_prompt}

Overseer summary: {conversation.overseer_summary}

Top idea nodes explored:
{chr(10).join(node_text) if node_text else "No nodes available"}

Provide a final synthesized answer that addresses the user's request, incorporating the best insights from the council deliberation.
Return your response as JSON with 'final_answer' and 'council_summary' keys."""
    
    response = call_llm(
        role="overseer_synthesis",
        prompt=synthesis_prompt,
        max_tokens=600
    )
    
    # Parse the response
    try:
        result = json.loads(response)
    except json.JSONDecodeError:
        # If parsing fails, create a structured response
        result = {
            "final_answer": response,
            "council_summary": f"Council deliberation completed with {len(sorted_nodes)} idea nodes explored."
        }
    
    # Update conversation phase
    conversation.phase = "DONE"
    registries.conversations[conversation.id] = conversation
    
    return result
