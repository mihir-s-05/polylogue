#!/usr/bin/env python3
"""
Example usage of the LLM Council system.

This demonstrates how to use the system programmatically.
"""

from scheduler import run_council_conversation
from agents import initialize_agents
import storage


def example_1_basic_usage():
    """Example 1: Basic usage with a simple question."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Usage")
    print("="*70 + "\n")

    # Initialize agents if needed
    if not storage.get_all_agents():
        initialize_agents()

    # Run a council deliberation
    result = run_council_conversation(
        "What are the pros and cons of using microservices architecture?"
    )

    # Access the results
    print("\nFinal Answer:")
    print(result["final_answer"])

    print("\nMetadata:")
    print(f"  - Conversation ID: {result['conversation_id']}")
    print(f"  - Total messages: {result['total_messages']}")
    print(f"  - Total nodes: {result['total_nodes']}")
    print(f"  - Tokens used: {result['tokens_used']}")


def example_2_inspect_conversation():
    """Example 2: Inspect conversation details after deliberation."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Inspecting Conversation Details")
    print("="*70 + "\n")

    # Initialize agents
    if not storage.get_all_agents():
        initialize_agents()

    # Run deliberation
    result = run_council_conversation(
        "How should we approach testing in a Python project?"
    )

    conversation_id = result["conversation_id"]

    # Get conversation details
    conversation = storage.get_conversation(conversation_id)
    messages = storage.get_messages_for_conversation(conversation_id)
    nodes = storage.get_nodes_for_conversation(conversation_id)

    # Inspect details
    print(f"Conversation Phase: {conversation.phase.value}")
    print(f"Number of debate rounds: {conversation.current_round}")
    print(f"\nMessages breakdown:")

    speaker_counts = {}
    for msg in messages:
        speaker = msg.speaker.value
        speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

    for speaker, count in speaker_counts.items():
        print(f"  - {speaker}: {count} messages")

    print(f"\nNodes breakdown:")
    status_counts = {}
    for node in nodes:
        status = node.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

    for status, count in status_counts.items():
        print(f"  - {status}: {count} nodes")

    print(f"\nTop priority node:")
    if conversation.priority_node_ids:
        top_node = storage.get_node(conversation.priority_node_ids[0])
        if top_node:
            print(f"  - ID: {top_node.id}")
            print(f"  - Summary: {top_node.summary[:100]}...")
            print(f"  - Score: {top_node.score:.2f}")


def example_3_dag_structure():
    """Example 3: Examine DAG structure."""
    print("\n" + "="*70)
    print("EXAMPLE 3: DAG Structure")
    print("="*70 + "\n")

    # Initialize agents
    if not storage.get_all_agents():
        initialize_agents()

    # Run deliberation
    result = run_council_conversation(
        "What makes a good code review process?"
    )

    conversation_id = result["conversation_id"]

    # Print DAG structure
    from dag_manager import print_dag_structure
    print(print_dag_structure(conversation_id))


def example_4_multiple_conversations():
    """Example 4: Multiple conversations."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Multiple Conversations")
    print("="*70 + "\n")

    # Initialize agents
    if not storage.get_all_agents():
        initialize_agents()

    questions = [
        "What are the key principles of REST API design?",
        "How do you choose between SQL and NoSQL databases?"
    ]

    results = []
    for question in questions:
        print(f"\nRunning deliberation on: {question[:60]}...")
        result = run_council_conversation(question)
        results.append(result)
        print(f"  ✓ Complete (conversation_id: {result['conversation_id']})")

    print(f"\n\nTotal conversations in system: {len(storage.conversations)}")
    print(f"Total messages in system: {len(storage.messages)}")
    print(f"Total nodes in system: {len(storage.nodes)}")


if __name__ == "__main__":
    # Run examples
    # Uncomment the examples you want to run

    # Clear data before running examples
    print("Clearing existing data...")
    storage.clear_all_data()
    print("✓ Data cleared\n")

    # Run examples
    example_1_basic_usage()

    # Uncomment to run more examples:
    # example_2_inspect_conversation()
    # example_3_dag_structure()
    # example_4_multiple_conversations()

    print("\n" + "="*70)
    print("Examples complete!")
    print("="*70 + "\n")
