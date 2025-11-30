"""
Agent logic and persona definitions for the LLM Council.
"""

import json
import re
from typing import List, Dict, Optional
from datetime import datetime
from models import AgentState, ConversationState, TranscriptMessage, IdeaNode
import storage


# Define agent personas
AGENT_PERSONAS = [
    {
        "agent_id": "agent_bold_innovator",
        "persona_description": (
            "Bold Innovator: You are a creative, risk-taking thinker who prioritizes "
            "novel solutions and paradigm shifts. You challenge conventional wisdom and "
            "push for ambitious, transformative approaches. You value innovation over "
            "incremental improvements."
        )
    },
    {
        "agent_id": "agent_risk_critic",
        "persona_description": (
            "Risk-Averse Critic: You are a careful, analytical thinker who identifies "
            "potential problems, edge cases, and failure modes. You prioritize stability, "
            "reliability, and proven approaches. You challenge ideas by stress-testing "
            "assumptions and highlighting risks."
        )
    },
    {
        "agent_id": "agent_pragmatic_builder",
        "persona_description": (
            "Pragmatic Builder: You are a practical, implementation-focused thinker who "
            "considers feasibility, resource constraints, and real-world execution. You "
            "balance idealism with pragmatism and focus on actionable, achievable solutions. "
            "You value simplicity and incremental progress."
        )
    },
    {
        "agent_id": "agent_systems_thinker",
        "persona_description": (
            "Systems Thinker: You are a holistic, interconnected thinker who considers "
            "broader context, second-order effects, and long-term implications. You identify "
            "feedback loops, unintended consequences, and systemic patterns. You challenge "
            "narrow thinking and advocate for comprehensive analysis."
        )
    }
]


def initialize_agents() -> List[AgentState]:
    """
    Initialize all council agents with their personas.

    Returns:
        List of initialized AgentState objects
    """
    agents = []
    for persona in AGENT_PERSONAS:
        agent = AgentState(
            agent_id=persona["agent_id"],
            persona_description=persona["persona_description"],
            last_spoke_at=datetime.now(),
            is_active=True,
            current_node_id=None
        )
        storage.save_agent(agent)
        agents.append(agent)

    return agents


def build_agent_prompt_opening(
    agent_state: AgentState,
    conversation: ConversationState,
    opening_index: int
) -> str:
    """
    Build the prompt for an agent's opening statement.

    Args:
        agent_state: The agent making the opening
        conversation: The conversation state
        opening_index: Index of this opening (0-3)

    Returns:
        Formatted prompt string
    """
    prompt = f"""You are participating in a council deliberation as one of several expert agents.

YOUR PERSONA:
{agent_state.persona_description}

USER'S QUESTION:
{conversation.user_prompt}

OVERSEER'S INITIAL ANALYSIS:
{conversation.overseer_summary}

INSTRUCTIONS:
This is the opening phase of deliberation. You are agent #{opening_index + 1} of 4 to speak.
Provide your initial stance on the user's question in 150-250 tokens.

Your response should:
1. Reflect your unique perspective based on your persona
2. Identify key considerations or angles relevant to the question
3. Propose an initial direction or framework for thinking about this
4. Be concise but substantive

IMPORTANT: You must append a [COUNCIL_STATE] footer with the following JSON structure:
[COUNCIL_STATE]
{{
  "current_node_id": "<unique_id_for_your_opening_idea>",
  "status": "ACTIVE",
  "new_branch_proposals": [],
  "votes": {{}},
  "raise_objection_to": null
}}
[/COUNCIL_STATE]

Provide your opening statement now:"""

    return prompt


def build_agent_prompt_debate(
    agent_state: AgentState,
    conversation: ConversationState,
    recent_messages: List[TranscriptMessage],
    relevant_nodes: List[IdeaNode],
    retrieved_snippets: Optional[List[str]] = None
) -> str:
    """
    Build the prompt for an agent's debate turn.

    Args:
        agent_state: The agent making the statement
        conversation: The conversation state
        recent_messages: Last N messages from the debate
        relevant_nodes: Priority nodes relevant to this turn
        retrieved_snippets: Optional RAG-retrieved context (TODO)

    Returns:
        Formatted prompt string
    """
    # Format recent messages
    messages_text = "\n\n".join([
        f"[{msg.speaker.value.upper()}] {msg.agent_id or 'Overseer'}: {msg.content[:200]}..."
        for msg in recent_messages[-5:]
    ])

    # Format priority nodes
    priority_nodes = [
        storage.get_node(node_id)
        for node_id in conversation.priority_node_ids
        if storage.get_node(node_id)
    ]
    nodes_text = "\n".join([
        f"- Node {node.id}: {node.summary} (score: {node.score:.2f})"
        for node in priority_nodes[:5]
    ])

    # Current node context
    current_node_text = ""
    if agent_state.current_node_id:
        current_node = storage.get_node(agent_state.current_node_id)
        if current_node:
            current_node_text = f"\n\nYOUR CURRENT NODE:\n{current_node.summary}"

    # RAG context (TODO)
    rag_text = ""
    if retrieved_snippets:
        rag_text = "\n\nRETRIEVED CONTEXT:\n" + "\n".join(retrieved_snippets)

    prompt = f"""You are continuing your participation in the council deliberation.

YOUR PERSONA:
{agent_state.persona_description}

USER'S QUESTION:
{conversation.user_prompt}

OVERSEER'S CURRENT SUMMARY:
{conversation.overseer_summary}

RECENT DISCUSSION:
{messages_text}

PRIORITY IDEAS UNDER CONSIDERATION:
{nodes_text}
{current_node_text}
{rag_text}

INSTRUCTIONS:
Contribute to the deliberation in <=150 tokens. You may:
- Build on existing ideas
- Raise objections or identify flaws
- Propose new branches or perspectives
- Vote to mark certain ideas as complete or ready to prune
- Challenge assumptions or redirect the discussion

Stay true to your persona and add value to the council's exploration.

IMPORTANT: Append a [COUNCIL_STATE] footer:
[COUNCIL_STATE]
{{
  "current_node_id": "<your_current_or_new_node_id>",
  "status": "ACTIVE" | "COMPLETE" | "PRUNED",
  "new_branch_proposals": [
    {{"summary": "...", "parent_node_id": "..."}}, ...
  ],
  "votes": {{"node_id": "COMPLETE" | "PRUNED"}},
  "raise_objection_to": {{"node_id": "...", "strength": 0.0-1.0, "reason": "..."}}
}}
[/COUNCIL_STATE]

Provide your contribution now:"""

    return prompt


def parse_council_footer(text: str) -> Dict:
    """
    Parse the [COUNCIL_STATE] JSON footer from an agent's response.

    Args:
        text: The agent's response text

    Returns:
        Dictionary with parsed footer fields, or empty dict if parsing fails
    """
    # Extract JSON between [COUNCIL_STATE] tags
    pattern = r'\[COUNCIL_STATE\](.*?)\[/COUNCIL_STATE\]'
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        # Return default footer if not found
        return {
            "current_node_id": None,
            "status": "ACTIVE",
            "new_branch_proposals": [],
            "votes": {},
            "raise_objection_to": None
        }

    try:
        footer_json = match.group(1).strip()
        footer = json.loads(footer_json)

        # Ensure all expected fields are present
        return {
            "current_node_id": footer.get("current_node_id"),
            "status": footer.get("status", "ACTIVE"),
            "new_branch_proposals": footer.get("new_branch_proposals", []),
            "votes": footer.get("votes", {}),
            "raise_objection_to": footer.get("raise_objection_to")
        }
    except json.JSONDecodeError:
        # Return default footer if JSON is invalid
        return {
            "current_node_id": None,
            "status": "ACTIVE",
            "new_branch_proposals": [],
            "votes": {},
            "raise_objection_to": None
        }


def get_agent_by_id(agent_id: str) -> Optional[AgentState]:
    """
    Retrieve an agent by ID.

    Args:
        agent_id: The agent's ID

    Returns:
        AgentState or None if not found
    """
    return storage.get_agent(agent_id)
