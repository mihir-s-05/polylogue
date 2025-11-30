"""
Scheduler for the LLM Council system.
Manages turn-taking, message retrieval, and phase orchestration.
"""

import uuid
import logging
from datetime import datetime
from council.models import (
    ConversationState, AgentState, TranscriptMessage, IdeaNode
)
from council import registries
from council.llm_helpers import call_llm
from council.agents import (
    create_default_agents,
    build_agent_prompt_opening,
    build_agent_prompt_debate,
    parse_council_footer,
    get_content_without_footer
)
from council.dag import (
    create_node_from_opening,
    create_nodes_from_branch_proposals,
    update_node_from_vote,
    log_dag_structure
)
from council.overseer import init_overseer, overseer_update, overseer_synthesis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_recent_messages(conversation_id: str, k: int = 5) -> list[TranscriptMessage]:
    """
    Get the k most recent messages for a conversation.
    
    Args:
        conversation_id: The conversation to get messages for
        k: Number of messages to retrieve
        
    Returns:
        List of the k most recent TranscriptMessages
    """
    all_messages = registries.get_conversation_messages(conversation_id)
    sorted_messages = sorted(all_messages, key=lambda m: m.timestamp, reverse=True)
    return sorted_messages[:k]


def get_relevant_nodes(
    conversation: ConversationState, 
    agent_state: AgentState
) -> list[IdeaNode]:
    """
    Get nodes relevant to the current agent and conversation state.
    
    Args:
        conversation: The conversation context
        agent_state: The agent requesting relevant nodes
        
    Returns:
        List of relevant IdeaNodes
    """
    relevant = []
    
    # Include priority nodes
    for node_id in conversation.priority_node_ids:
        node = registries.get_node(node_id)
        if node and node.status == "ACTIVE":
            relevant.append(node)
    
    # Include agent's current node if not already included
    if agent_state.current_node_id:
        node = registries.get_node(agent_state.current_node_id)
        if node and node not in relevant:
            relevant.append(node)
    
    return relevant


def select_next_agent(conversation: ConversationState) -> AgentState | None:
    """
    Select the next agent to speak based on various factors.
    
    Uses:
    - Recency (favor agents who haven't spoken recently)
    - Pending strong objections
    - Whether agent's current_node_id is in priority_node_ids
    
    Args:
        conversation: The conversation context
        
    Returns:
        The selected AgentState, or None if no agents available
    """
    agents = registries.get_conversation_agents(conversation.id)
    if not agents:
        return None
    
    # Filter to active agents
    active_agents = [a for a in agents if a.is_active]
    if not active_agents:
        return None
    
    # Score each agent
    agent_scores = []
    for agent in active_agents:
        score = 0.0
        
        # Recency factor - favor agents who haven't spoken
        time_since_spoke = (datetime.now() - agent.last_spoke_at).total_seconds()
        score += min(time_since_spoke / 60.0, 10.0)  # Cap at 10 minutes worth
        
        # Priority node factor - favor agents working on priority nodes
        if agent.current_node_id in conversation.priority_node_ids:
            score += 5.0
        
        agent_scores.append((agent, score))
    
    # Sort by score and return highest
    agent_scores.sort(key=lambda x: x[1], reverse=True)
    return agent_scores[0][0]


def store_message(
    conversation_id: str,
    speaker: str,
    content: str,
    agent_id: str | None = None,
    footer: dict | None = None
) -> TranscriptMessage:
    """
    Store a new transcript message.
    
    Args:
        conversation_id: The conversation this message belongs to
        speaker: One of "user", "overseer", "agent"
        content: The message content
        agent_id: Optional agent ID if speaker is "agent"
        footer: Optional parsed footer dict
        
    Returns:
        The created TranscriptMessage
    """
    message = TranscriptMessage(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        conversation_id=conversation_id,
        speaker=speaker,
        content=content,
        agent_id=agent_id,
        footer=footer,
        timestamp=datetime.now()
    )
    registries.messages[message.id] = message
    return message


def run_opening_phase(conversation_id: str) -> None:
    """
    Run the opening phase where each agent provides their initial stance.
    
    Args:
        conversation_id: The conversation to run opening phase for
    """
    conversation = registries.get_conversation(conversation_id)
    if not conversation:
        logger.error(f"Conversation {conversation_id} not found")
        return
    
    logger.info(f"Starting opening phase for conversation {conversation_id}")
    
    agents = registries.get_conversation_agents(conversation_id)
    
    for i, agent in enumerate(agents):
        logger.info(f"Agent {agent.agent_id} providing opening statement ({i+1}/4)")
        
        # Build the opening prompt
        prompt = build_agent_prompt_opening(agent, conversation, i)
        
        # Call LLM
        response = call_llm(
            role="agent_opening",
            prompt=prompt,
            max_tokens=300
        )
        
        # Parse the response
        footer = parse_council_footer(response)
        content = get_content_without_footer(response)
        
        # Store the message
        store_message(
            conversation_id=conversation_id,
            speaker="agent",
            content=content,
            agent_id=agent.agent_id,
            footer=footer
        )
        
        # Create the idea node
        node = create_node_from_opening(agent, conversation, content, footer)
        logger.info(f"Created node {node.id} from {agent.agent_id}'s opening")
        
        # Update agent state
        agent.last_spoke_at = datetime.now()
        registries.agents[agent.agent_id] = agent
        
        # Track token usage (rough estimate for MVP)
        conversation.used_tokens += len(content.split()) * 1.3
        registries.conversations[conversation_id] = conversation
    
    # After all openings, update overseer
    logger.info("Updating overseer after opening phase")
    overseer_update(conversation)
    
    # Log DAG structure
    logger.info(log_dag_structure(conversation_id))
    
    # Transition to debate phase
    conversation.phase = "DEBATE"
    registries.conversations[conversation_id] = conversation
    logger.info("Opening phase complete, transitioning to DEBATE")


def run_debate_phase(conversation_id: str) -> None:
    """
    Run the debate phase where agents discuss and refine ideas.
    
    Args:
        conversation_id: The conversation to run debate phase for
    """
    conversation = registries.get_conversation(conversation_id)
    if not conversation:
        logger.error(f"Conversation {conversation_id} not found")
        return
    
    logger.info(f"Starting debate phase for conversation {conversation_id}")
    
    # Debate loop
    overseer_update_interval = 3  # Update overseer every N turns
    
    while (conversation.used_tokens < conversation.global_token_budget and 
           conversation.current_round < conversation.max_debate_rounds):
        
        # Select next agent
        agent = select_next_agent(conversation)
        if not agent:
            logger.warning("No agent available, ending debate")
            break
        
        logger.info(f"Round {conversation.current_round + 1}: {agent.agent_id} speaking")
        
        # Gather context
        recent_messages = get_recent_messages(conversation_id, k=5)
        relevant_nodes = get_relevant_nodes(conversation, agent)
        
        # TODO: Implement RAG retrieval here
        # retrieved_snippets = search_relevant_context(conversation.user_prompt, conversation_id)
        retrieved_snippets = None  # MVP: skip RAG
        
        # Build debate prompt
        prompt = build_agent_prompt_debate(
            agent,
            conversation,
            recent_messages,
            relevant_nodes,
            retrieved_snippets
        )
        
        # Call LLM
        response = call_llm(
            role="agent_debate",
            prompt=prompt,
            max_tokens=200
        )
        
        # Parse the response
        footer = parse_council_footer(response)
        content = get_content_without_footer(response)
        
        # Store the message
        store_message(
            conversation_id=conversation_id,
            speaker="agent",
            content=content,
            agent_id=agent.agent_id,
            footer=footer
        )
        
        # Process footer actions
        
        # Update agent's current node if specified
        if footer.get("current_node_id"):
            agent.current_node_id = footer["current_node_id"]
        
        # Create nodes from branch proposals
        if footer.get("new_branch_proposals"):
            new_nodes = create_nodes_from_branch_proposals(agent, conversation, footer)
            for node in new_nodes:
                logger.info(f"Created branch node {node.id} from {agent.agent_id}")
        
        # Process votes
        if footer.get("votes"):
            for node_id, score in footer["votes"].items():
                update_node_from_vote(node_id, score)
                logger.info(f"{agent.agent_id} voted {score} on node {node_id}")
        
        # Update agent state
        agent.last_spoke_at = datetime.now()
        registries.agents[agent.agent_id] = agent
        
        # Track token usage
        conversation.used_tokens += len(content.split()) * 1.3
        conversation.current_round += 1
        registries.conversations[conversation_id] = conversation
        
        # Periodic overseer update
        if conversation.current_round % overseer_update_interval == 0:
            logger.info("Updating overseer mid-debate")
            overseer_update(conversation)
            logger.info(log_dag_structure(conversation_id))
    
    # Transition to synthesis phase
    conversation.phase = "SYNTHESIS"
    registries.conversations[conversation_id] = conversation
    logger.info(f"Debate phase complete after {conversation.current_round} rounds")


def run_council_conversation(user_prompt: str) -> dict:
    """
    Run a complete council conversation from start to finish.
    
    TODO 3: This function serves as CLI entrypoint to run council without HTTP.
    
    Args:
        user_prompt: The user's initial prompt/question
        
    Returns:
        Dict with 'final_answer' and 'council_summary'
    """
    logger.info(f"Starting new council conversation for: {user_prompt[:50]}...")
    
    # Create conversation
    conversation_id = f"conv_{uuid.uuid4().hex[:8]}"
    conversation = ConversationState(
        id=conversation_id,
        user_prompt=user_prompt,
        mode="council",
        phase="OPENING",
        global_token_budget=4000,
        max_branches=4,
        max_depth=3,
        max_debate_rounds=8
    )
    registries.conversations[conversation_id] = conversation
    
    # Store user message
    store_message(
        conversation_id=conversation_id,
        speaker="user",
        content=user_prompt
    )
    
    # Create default agents
    agents = create_default_agents(conversation_id)
    conversation.agent_ids = [a.agent_id for a in agents]
    registries.conversations[conversation_id] = conversation
    
    # Initialize overseer
    init_overseer(conversation)
    
    # Run opening phase
    run_opening_phase(conversation_id)
    
    # Run debate phase
    run_debate_phase(conversation_id)
    
    # Run synthesis
    logger.info("Running overseer synthesis")
    result = overseer_synthesis(conversation)
    
    # TODO 1: Verify single POST /council_chat runs end-to-end
    # This function should print logs of:
    # - Opening statements
    # - Nodes created
    # - A few debate turns
    # - Final synthesized answer
    logger.info(f"Council conversation complete. Final answer: {result['final_answer'][:100]}...")
    
    return result
