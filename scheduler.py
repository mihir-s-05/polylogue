"""
Scheduler and orchestration logic for the LLM Council.
"""

import uuid
import logging
from datetime import datetime
from typing import List, Optional
from models import (
    ConversationState, ConversationMode, ConversationPhase,
    TranscriptMessage, Speaker, AgentState, IdeaNode
)
import storage
from llm_helpers import call_llm
from agents import (
    build_agent_prompt_opening,
    build_agent_prompt_debate,
    parse_council_footer
)
from dag_manager import (
    create_node_from_opening,
    create_nodes_from_branch_proposals,
    process_votes,
    print_dag_structure,
    get_priority_nodes
)
from overseer import init_overseer, overseer_update, overseer_synthesis


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Constants
OVERSEER_UPDATE_INTERVAL = 3  # Update overseer every N turns


def get_recent_messages(conversation_id: str, k: int = 5) -> List[TranscriptMessage]:
    """
    Get the k most recent messages for a conversation.

    Args:
        conversation_id: The conversation ID
        k: Number of recent messages to retrieve

    Returns:
        List of recent messages, sorted by timestamp
    """
    messages = storage.get_messages_for_conversation(conversation_id)
    return messages[-k:] if messages else []


def get_relevant_nodes(
    conversation: ConversationState,
    agent_state: AgentState
) -> List[IdeaNode]:
    """
    Get nodes relevant to the current agent's turn.

    Args:
        conversation: The conversation
        agent_state: The agent making the turn

    Returns:
        List of relevant nodes
    """
    # For MVP, return priority nodes plus agent's current node
    relevant = get_priority_nodes(conversation)

    # Add agent's current node if not already included
    if agent_state.current_node_id:
        current_node = storage.get_node(agent_state.current_node_id)
        if current_node and current_node not in relevant:
            relevant.append(current_node)

    return relevant


def select_next_agent(conversation: ConversationState) -> AgentState:
    """
    Select the next agent to speak based on scheduling heuristics.

    Considers:
    - Recency (favor agents who haven't spoken recently)
    - Pending objections (agents with strong objections speak sooner)
    - Node priority (agents working on priority nodes speak more)

    Args:
        conversation: The conversation

    Returns:
        The selected AgentState
    """
    agents = [storage.get_agent(aid) for aid in conversation.agent_ids]
    agents = [a for a in agents if a and a.is_active]

    if not agents:
        raise ValueError("No active agents available")

    # Simple heuristic for MVP: rotate by last spoke time
    # Sort by last_spoke_at ascending (least recent first)
    agents.sort(key=lambda a: a.last_spoke_at)

    # TODO: Add more sophisticated scheduling:
    # - Check for pending objections in recent messages
    # - Prioritize agents working on priority nodes
    # - Add some randomness to avoid strictly round-robin

    return agents[0]


def run_opening_phase(conversation_id: str) -> None:
    """
    Run the opening phase where each agent gives their initial stance.

    Args:
        conversation_id: The conversation ID
    """
    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found")

    logger.info(f"=== Starting OPENING phase for conversation {conversation_id} ===")

    # Get all agents
    agents = [storage.get_agent(aid) for aid in conversation.agent_ids]

    # Each agent provides opening statement
    for i, agent in enumerate(agents):
        logger.info(f"Agent {agent.agent_id} providing opening statement ({i+1}/4)...")

        # Build opening prompt
        prompt = build_agent_prompt_opening(agent, conversation, i)

        # Call LLM
        role = f"agent_opening_{i+1}"
        response = call_llm(role=role, prompt=prompt, max_tokens=400)

        # Parse footer
        footer = parse_council_footer(response)

        # Create transcript message
        message = TranscriptMessage(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            conversation_id=conversation.id,
            speaker=Speaker.AGENT,
            agent_id=agent.agent_id,
            content=response,
            timestamp=datetime.now(),
            footer=footer
        )
        storage.save_message(message)

        # Create node from opening
        node = create_node_from_opening(agent, conversation, response, footer)
        logger.info(f"  Created node: {node.id}")

        # Update agent state
        agent.last_spoke_at = datetime.now()
        storage.save_agent(agent)

        # Track tokens (rough estimate: 1 token ≈ 0.75 words)
        conversation.used_tokens += len(response.split()) * 4 // 3

    # After all openings, update overseer
    logger.info("All openings complete. Updating overseer...")
    overseer_update(conversation)

    # Transition to debate phase
    conversation.phase = ConversationPhase.DEBATE
    storage.save_conversation(conversation)

    logger.info("=== OPENING phase complete ===\n")


def run_debate_phase(conversation_id: str) -> None:
    """
    Run the debate phase where agents iteratively contribute.

    Args:
        conversation_id: The conversation ID
    """
    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found")

    logger.info(f"=== Starting DEBATE phase for conversation {conversation_id} ===")

    turn_count = 0

    # Main debate loop
    while (
        conversation.used_tokens < conversation.global_token_budget
        and conversation.current_round < conversation.max_debate_rounds
    ):
        turn_count += 1
        logger.info(f"\n--- Debate Turn {turn_count} (Round {conversation.current_round + 1}) ---")

        # Select next agent
        agent = select_next_agent(conversation)
        logger.info(f"Selected agent: {agent.agent_id}")

        # Get recent messages and relevant nodes
        recent_messages = get_recent_messages(conversation.id, k=5)
        relevant_nodes = get_relevant_nodes(conversation, agent)

        # TODO: RAG - Retrieve relevant snippets based on agent's context
        # This would involve:
        # 1. Extracting keywords from agent's last message or current node
        # 2. Searching transcript and nodes for relevant context
        # 3. Passing retrieved snippets to the prompt
        # Example:
        # if agent.current_node_id:
        #     current_node = storage.get_node(agent.current_node_id)
        #     if current_node:
        #         retrieved_nodes = search_nodes(current_node.summary, conversation.id, k=3)
        #         retrieved_messages = search_transcript(current_node.summary, conversation.id, k=3)
        #         retrieved_snippets = [...]
        retrieved_snippets = None  # Placeholder for RAG

        # Build debate prompt
        prompt = build_agent_prompt_debate(
            agent, conversation, recent_messages, relevant_nodes, retrieved_snippets
        )

        # Call LLM
        role = f"agent_debate_{agent.agent_id.split('_')[-1]}"
        response = call_llm(role=role, prompt=prompt, max_tokens=250)

        # Parse footer
        footer = parse_council_footer(response)

        # Create transcript message
        message = TranscriptMessage(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            conversation_id=conversation.id,
            speaker=Speaker.AGENT,
            agent_id=agent.agent_id,
            content=response,
            timestamp=datetime.now(),
            footer=footer
        )
        storage.save_message(message)

        # Update agent state
        agent.current_node_id = footer.get("current_node_id") or agent.current_node_id
        agent.last_spoke_at = datetime.now()
        storage.save_agent(agent)

        # Process new branch proposals
        new_nodes = create_nodes_from_branch_proposals(agent, conversation, footer)
        if new_nodes:
            logger.info(f"  Created {len(new_nodes)} new branch node(s)")

        # Process votes
        process_votes(footer)

        # Track tokens
        conversation.used_tokens += len(response.split()) * 4 // 3

        # Periodically update overseer
        if turn_count % OVERSEER_UPDATE_INTERVAL == 0:
            logger.info("  Updating overseer...")
            overseer_update(conversation)
            conversation.current_round += 1

        storage.save_conversation(conversation)

        # Check for early termination conditions
        # (e.g., all priority nodes marked complete)
        priority_nodes = get_priority_nodes(conversation)
        if not any(node.status.value == "ACTIVE" for node in priority_nodes):
            logger.info("All priority nodes resolved. Ending debate early.")
            break

    # Final overseer update before synthesis
    logger.info("\nFinal overseer update before synthesis...")
    overseer_update(conversation)

    # Transition to synthesis phase
    conversation.phase = ConversationPhase.SYNTHESIS
    storage.save_conversation(conversation)

    logger.info(f"=== DEBATE phase complete after {turn_count} turns ===\n")


def run_council_conversation(user_prompt: str) -> dict:
    """
    Run a complete council conversation from start to finish.

    Args:
        user_prompt: The user's question/prompt

    Returns:
        Dictionary with final_answer and council_summary
    """
    # Create conversation
    conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

    # Get or initialize agents
    agents = storage.get_all_agents()
    if not agents:
        from agents import initialize_agents
        agents = initialize_agents()

    conversation = ConversationState(
        id=conversation_id,
        user_prompt=user_prompt,
        mode=ConversationMode.COUNCIL,
        phase=ConversationPhase.OPENING,
        overseer_summary="",
        active_node_ids=[],
        priority_node_ids=[],
        global_token_budget=5000,  # MVP budget
        used_tokens=0,
        max_branches=5,
        max_depth=4,
        max_debate_rounds=3,  # MVP: keep it short
        current_round=0,
        agent_ids=[a.agent_id for a in agents]
    )
    storage.save_conversation(conversation)

    logger.info(f"\n{'='*60}")
    logger.info(f"NEW COUNCIL CONVERSATION: {conversation_id}")
    logger.info(f"User prompt: {user_prompt}")
    logger.info(f"{'='*60}\n")

    # Initialize overseer
    init_overseer(conversation)
    logger.info(f"Overseer initialized. Summary:\n{conversation.overseer_summary}\n")

    # Run opening phase
    run_opening_phase(conversation_id)

    # Print DAG after opening
    logger.info(print_dag_structure(conversation_id))

    # Run debate phase
    run_debate_phase(conversation_id)

    # Print final DAG
    logger.info(print_dag_structure(conversation_id))

    # Run synthesis
    logger.info("=== Running SYNTHESIS ===")
    conversation = storage.get_conversation(conversation_id)
    result = overseer_synthesis(conversation)

    logger.info(f"\n{'='*60}")
    logger.info("FINAL ANSWER:")
    logger.info(result["final_answer"])
    logger.info(f"\n{'-'*60}")
    logger.info("COUNCIL SUMMARY:")
    logger.info(result["council_summary"])
    logger.info(f"{'='*60}\n")

    # Add metadata
    result["conversation_id"] = conversation_id
    result["total_messages"] = len(storage.get_messages_for_conversation(conversation_id))
    result["total_nodes"] = len(storage.get_nodes_for_conversation(conversation_id))
    result["tokens_used"] = conversation.used_tokens

    return result
