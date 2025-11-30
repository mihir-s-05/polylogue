"""
Agent logic for the LLM Council system.
Defines council agents and their prompt building functions.
"""

import re
import json
import uuid
from datetime import datetime
from council.models import AgentState, ConversationState, TranscriptMessage, IdeaNode
from council import registries


# Agent persona definitions
AGENT_PERSONAS = [
    {
        "id": "agent_bold_innovator",
        "persona_description": "bold innovator - You push boundaries and propose creative, unconventional solutions. You're not afraid to challenge the status quo and advocate for transformative ideas."
    },
    {
        "id": "agent_risk_averse_critic",
        "persona_description": "risk-averse critic - You carefully analyze proposals for potential risks, downsides, and unintended consequences. You advocate for caution and thorough evaluation before action."
    },
    {
        "id": "agent_pragmatic_synthesizer",
        "persona_description": "pragmatic synthesizer - You focus on finding practical, implementable solutions that balance different viewpoints. You excel at combining ideas into coherent, actionable plans."
    },
    {
        "id": "agent_devils_advocate",
        "persona_description": "devil's advocate - You deliberately challenge prevailing opinions and assumptions. You probe weaknesses in arguments and ensure all perspectives are thoroughly examined."
    }
]


def create_default_agents(conversation_id: str) -> list[AgentState]:
    """
    Create the default set of 4 council agents.
    
    Args:
        conversation_id: The conversation these agents will participate in
        
    Returns:
        List of created AgentState objects
    """
    created_agents = []
    
    for persona in AGENT_PERSONAS:
        agent = AgentState(
            agent_id=persona["id"],
            persona_description=persona["persona_description"],
            current_node_id=None,
            last_spoke_at=datetime.now(),
            is_active=True
        )
        registries.agents[agent.agent_id] = agent
        created_agents.append(agent)
    
    return created_agents


def build_agent_prompt_opening(
    agent_state: AgentState, 
    conversation: ConversationState, 
    opening_index: int
) -> str:
    """
    Build the prompt for an agent's opening statement.
    
    Args:
        agent_state: The agent generating the opening
        conversation: The conversation context
        opening_index: The order of this opening (0-3)
        
    Returns:
        The prompt string for the agent
    """
    prompt = f"""You are a council member with the following persona: {agent_state.persona_description}

USER'S REQUEST:
{conversation.user_prompt}

OVERSEER'S FRAMING:
{conversation.overseer_summary}

YOUR TASK:
Provide your opening stance on this topic. Your opening should:
- Be 150-250 tokens in length
- Reflect your persona's perspective
- Propose initial ideas or concerns
- Be constructive and contribute to the deliberation

You are speaker #{opening_index + 1} of 4 in the opening phase.

At the end of your response, you MUST include a [COUNCIL_STATE] JSON footer with the following structure:
[COUNCIL_STATE]
{{
    "current_node_id": null,
    "status": "proposing",
    "new_branch_proposals": [{{"summary": "Brief summary of your proposal", "parent_id": null}}],
    "votes": {{}},
    "raise_objection_to": null
}}
[/COUNCIL_STATE]

Now provide your opening statement:"""
    
    return prompt


def build_agent_prompt_debate(
    agent_state: AgentState,
    conversation: ConversationState,
    recent_messages: list[TranscriptMessage],
    relevant_nodes: list[IdeaNode],
    retrieved_snippets: list[str] | None = None
) -> str:
    """
    Build the prompt for an agent's debate contribution.
    
    Args:
        agent_state: The agent contributing
        conversation: The conversation context
        recent_messages: Last 5 council messages
        relevant_nodes: Relevant idea nodes
        retrieved_snippets: Optional RAG-retrieved snippets
        
    Returns:
        The prompt string for the agent
    """
    # Format recent messages
    message_text = []
    for msg in recent_messages[-5:]:  # Last 5 messages
        speaker = msg.agent_id if msg.speaker == "agent" else msg.speaker
        message_text.append(f"[{speaker}]: {msg.content[:300]}...")
    
    # Format priority nodes
    priority_nodes_text = []
    for node_id in conversation.priority_node_ids:
        node = registries.get_node(node_id)
        if node:
            priority_nodes_text.append(f"- {node.id}: {node.summary} (score: {node.score})")
    
    # Format agent's current node if any
    current_node_text = "None"
    if agent_state.current_node_id:
        current_node = registries.get_node(agent_state.current_node_id)
        if current_node:
            current_node_text = f"{current_node.id}: {current_node.summary}"
    
    # Format retrieved snippets if any
    snippets_text = ""
    if retrieved_snippets:
        snippets_text = f"\n\nRELEVANT RETRIEVED INFORMATION:\n" + "\n".join(retrieved_snippets)
    
    prompt = f"""You are a council member with the following persona: {agent_state.persona_description}

USER'S REQUEST:
{conversation.user_prompt}

OVERSEER'S CURRENT SUMMARY:
{conversation.overseer_summary}

RECENT COUNCIL DISCUSSION:
{chr(10).join(message_text) if message_text else "No recent messages"}

PRIORITY IDEAS BEING EXPLORED:
{chr(10).join(priority_nodes_text) if priority_nodes_text else "No priority nodes yet"}

YOUR CURRENT FOCUS NODE:
{current_node_text}
{snippets_text}

YOUR TASK:
Contribute to the debate. Your contribution should:
- Be <=150 tokens
- Reflect your persona's perspective
- Engage with recent discussion points
- Build on, challenge, or refine existing ideas

Round {conversation.current_round} of {conversation.max_debate_rounds}

At the end of your response, you MUST include a [COUNCIL_STATE] JSON footer:
[COUNCIL_STATE]
{{
    "current_node_id": "<node_id you're focusing on or null>",
    "status": "contributing",
    "new_branch_proposals": [],
    "votes": {{}},
    "raise_objection_to": null
}}
[/COUNCIL_STATE]

If you want to propose a new branch, add it to new_branch_proposals.
If you want to vote on a node, add to votes: {{"<node_id>": <score 1-5>}}
If you strongly object to something, set raise_objection_to with node_id and strength.

Now provide your contribution:"""
    
    return prompt


def parse_council_footer(text: str) -> dict:
    """
    Extract the JSON footer from an agent's response.
    
    Args:
        text: The full agent response text
        
    Returns:
        Dict with fields: current_node_id, status, new_branch_proposals, votes, raise_objection_to
    """
    default_footer = {
        "current_node_id": None,
        "status": "unknown",
        "new_branch_proposals": [],
        "votes": {},
        "raise_objection_to": None
    }
    
    # Try to extract JSON between [COUNCIL_STATE] and [/COUNCIL_STATE]
    pattern = r'\[COUNCIL_STATE\](.*?)\[/COUNCIL_STATE\]'
    match = re.search(pattern, text, re.DOTALL)
    
    if not match:
        return default_footer
    
    json_str = match.group(1).strip()
    
    try:
        footer_data = json.loads(json_str)
        # Merge with defaults to ensure all keys exist
        return {**default_footer, **footer_data}
    except json.JSONDecodeError:
        return default_footer


def get_content_without_footer(text: str) -> str:
    """
    Extract the content portion of an agent's response without the footer.
    
    Args:
        text: The full agent response text
        
    Returns:
        The content without the [COUNCIL_STATE] footer
    """
    # Remove everything from [COUNCIL_STATE] onwards
    pattern = r'\[COUNCIL_STATE\].*?\[/COUNCIL_STATE\]'
    content = re.sub(pattern, '', text, flags=re.DOTALL).strip()
    return content
