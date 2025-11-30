"""
Overseer logic for managing the LLM Council deliberation.
"""

import json
import re
from typing import Dict, List
from models import ConversationState, ConversationMode, ConversationPhase, NodeStatus
import storage
from llm_helpers import call_llm


def init_overseer(conversation: ConversationState) -> None:
    """
    Initialize the overseer for a new council conversation.

    Args:
        conversation: The conversation to initialize
    """
    # Set mode and phase
    conversation.mode = ConversationMode.COUNCIL
    conversation.phase = ConversationPhase.OPENING

    # Generate initial overseer summary
    prompt = f"""You are the Overseer of a council of expert agents who will deliberate on the following question.

USER'S QUESTION:
{conversation.user_prompt}

Your task is to provide an initial analysis and framing of this question that will guide the council's deliberation.

Identify:
1. The core question or challenge
2. Key dimensions or aspects to explore
3. Potential approaches or frameworks
4. Important constraints or considerations

Provide a concise summary (200-300 tokens) that will orient the council members."""

    overseer_response = call_llm(role="overseer_init", prompt=prompt, max_tokens=500)
    conversation.overseer_summary = overseer_response

    # Save updated conversation
    storage.save_conversation(conversation)


def overseer_update(conversation: ConversationState) -> None:
    """
    Update the overseer's summary and prioritize nodes based on current deliberation.

    Args:
        conversation: The conversation to update
    """
    # Get all nodes and messages for this conversation
    nodes = storage.get_nodes_for_conversation(conversation.id)
    messages = storage.get_messages_for_conversation(conversation.id)

    # Build context for overseer
    nodes_summary = "\n".join([
        f"- Node {node.id} (by {node.created_by_agent_id}): {node.summary[:100]} | "
        f"Score: {node.score:.2f} | Status: {node.status.value}"
        for node in nodes[-10:]  # Last 10 nodes
    ])

    recent_messages = "\n".join([
        f"[{msg.speaker.value}] {msg.content[:150]}..."
        for msg in messages[-8:]  # Last 8 messages
    ])

    prompt = f"""You are the Overseer managing a council deliberation.

USER'S QUESTION:
{conversation.user_prompt}

YOUR PREVIOUS SUMMARY:
{conversation.overseer_summary}

RECENT COUNCIL ACTIVITY:
{recent_messages}

IDEA NODES EXPLORED:
{nodes_summary}

Update your summary based on the council's progress. Identify:
1. Key themes and patterns emerging
2. Most promising directions
3. Areas needing more exploration
4. Potential synthesis points

Provide an updated summary (200-300 tokens)."""

    overseer_response = call_llm(role="overseer_update", prompt=prompt, max_tokens=500)
    conversation.overseer_summary = overseer_response

    # Update node scores and priorities
    _update_node_priorities(conversation, nodes)

    # Save updated conversation
    storage.save_conversation(conversation)


def _update_node_priorities(conversation: ConversationState, nodes: List) -> None:
    """
    Update node scores and priority list.

    For MVP, use simple heuristics. In production, could use LLM to score nodes.

    Args:
        conversation: The conversation
        nodes: List of nodes to score
    """
    active_nodes = [node for node in nodes if node.status == NodeStatus.ACTIVE]

    # Simple scoring: newer nodes get higher scores, with some randomness
    import random
    for i, node in enumerate(active_nodes):
        # Base score on recency
        recency_score = i / max(len(active_nodes), 1)

        # Bonus for nodes with more children (referenced by other nodes)
        children_count = sum(1 for n in nodes if node.id in n.parents)
        children_score = min(children_count * 0.1, 0.3)

        # Combined score with some noise
        node.score = recency_score + children_score + random.uniform(0, 0.2)
        storage.save_node(node)

    # Sort by score and update priorities
    active_nodes.sort(key=lambda n: n.score, reverse=True)

    conversation.active_node_ids = [n.id for n in active_nodes]
    conversation.priority_node_ids = [n.id for n in active_nodes[:conversation.max_branches]]


def overseer_synthesis(conversation: ConversationState) -> Dict[str, str]:
    """
    Synthesize the final answer from the council's deliberation.

    Args:
        conversation: The conversation to synthesize

    Returns:
        Dictionary with 'final_answer' and 'council_summary' keys
    """
    # Get top nodes
    priority_nodes = [
        storage.get_node(node_id)
        for node_id in conversation.priority_node_ids[:5]
        if storage.get_node(node_id)
    ]

    nodes_summary = "\n\n".join([
        f"**Idea {i+1}** (Score: {node.score:.2f}):\n{node.summary}\n"
        f"Key insight: {node.artifact[:200]}..."
        for i, node in enumerate(priority_nodes)
    ])

    # Get message count and round info
    messages = storage.get_messages_for_conversation(conversation.id)
    total_messages = len(messages)

    prompt = f"""You are the Overseer concluding a council deliberation.

USER'S ORIGINAL QUESTION:
{conversation.user_prompt}

YOUR FINAL SUMMARY:
{conversation.overseer_summary}

TOP IDEAS FROM DELIBERATION:
{nodes_summary}

DELIBERATION STATS:
- Total messages: {total_messages}
- Debate rounds: {conversation.current_round}
- Ideas explored: {len(storage.get_nodes_for_conversation(conversation.id))}

Synthesize a final answer that:
1. Directly addresses the user's question
2. Integrates the best insights from the council
3. Acknowledges key trade-offs or considerations
4. Provides actionable guidance or conclusions

Also provide a brief council summary describing the deliberation process.

Format your response with a [COUNCIL_STATE] footer:
[COUNCIL_STATE]
{{
  "final_answer": "<your synthesized answer>",
  "council_summary": "<summary of the deliberation process>"
}}
[/COUNCIL_STATE]"""

    synthesis_response = call_llm(role="overseer_synthesis", prompt=prompt, max_tokens=800)

    # Parse the footer to extract final answer and summary
    result = _parse_synthesis_footer(synthesis_response)

    # Mark conversation as done
    conversation.phase = ConversationPhase.DONE
    storage.save_conversation(conversation)

    return result


def _parse_synthesis_footer(text: str) -> Dict[str, str]:
    """
    Parse the synthesis footer from overseer's final response.

    Args:
        text: The overseer's synthesis response

    Returns:
        Dictionary with final_answer and council_summary
    """
    pattern = r'\[COUNCIL_STATE\](.*?)\[/COUNCIL_STATE\]'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        try:
            footer_json = match.group(1).strip()
            footer = json.loads(footer_json)
            return {
                "final_answer": footer.get("final_answer", ""),
                "council_summary": footer.get("council_summary", "")
            }
        except json.JSONDecodeError:
            pass

    # Fallback: use the full text as final answer
    return {
        "final_answer": text,
        "council_summary": "The council completed its deliberation."
    }
