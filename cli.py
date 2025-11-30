#!/usr/bin/env python3
"""
CLI entrypoint for the LLM Council system.

Usage:
    python cli.py "Your question here"
    python cli.py --interactive
"""

import sys
import argparse
from scheduler import run_council_conversation
from agents import initialize_agents
import storage


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="LLM Council - Multi-agent deliberation system"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The question or prompt for the council to deliberate on"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all data before running"
    )

    args = parser.parse_args()

    # Reset data if requested
    if args.reset:
        print("Resetting all data...")
        storage.clear_all_data()
        initialize_agents()
        print("Data reset complete.\n")

    # Initialize agents if needed
    if not storage.get_all_agents():
        print("Initializing council agents...")
        agents = initialize_agents()
        print(f"Initialized {len(agents)} agents.\n")

    # Interactive mode
    if args.interactive:
        run_interactive()
        return

    # Single prompt mode
    if args.prompt:
        run_single_prompt(args.prompt)
        return

    # No arguments - show help
    parser.print_help()
    print("\nExample usage:")
    print('  python cli.py "What are the key considerations for building a scalable web application?"')
    print("  python cli.py --interactive")


def run_single_prompt(prompt: str):
    """
    Run a single council deliberation.

    Args:
        prompt: The user's question
    """
    print(f"\n{'='*70}")
    print("LLM COUNCIL DELIBERATION")
    print(f"{'='*70}")
    print(f"\nQuestion: {prompt}\n")

    # Run council
    result = run_council_conversation(prompt)

    # Print results
    print(f"\n{'='*70}")
    print("FINAL ANSWER")
    print(f"{'='*70}")
    print(result["final_answer"])

    print(f"\n{'='*70}")
    print("COUNCIL SUMMARY")
    print(f"{'='*70}")
    print(result["council_summary"])

    print(f"\n{'='*70}")
    print("STATISTICS")
    print(f"{'='*70}")
    print(f"Conversation ID: {result['conversation_id']}")
    print(f"Total messages: {result['total_messages']}")
    print(f"Total nodes: {result['total_nodes']}")
    print(f"Tokens used: {result['tokens_used']}")
    print(f"{'='*70}\n")


def run_interactive():
    """Run in interactive mode with multiple questions."""
    print("\n" + "="*70)
    print("LLM COUNCIL - INTERACTIVE MODE")
    print("="*70)
    print("\nEnter your questions for the council to deliberate on.")
    print("Type 'quit' or 'exit' to end the session.")
    print("Type 'reset' to clear all data.")
    print("Type 'stats' to see current statistics.")
    print("="*70 + "\n")

    while True:
        try:
            # Get user input
            prompt = input("\nYour question: ").strip()

            if not prompt:
                continue

            # Check for commands
            if prompt.lower() in ["quit", "exit"]:
                print("\nGoodbye!")
                break

            if prompt.lower() == "reset":
                storage.clear_all_data()
                initialize_agents()
                print("✓ All data reset. Agents re-initialized.")
                continue

            if prompt.lower() == "stats":
                show_statistics()
                continue

            # Run council deliberation
            result = run_council_conversation(prompt)

            # Print results
            print(f"\n{'-'*70}")
            print("FINAL ANSWER:")
            print(f"{'-'*70}")
            print(result["final_answer"])

            print(f"\n{'-'*70}")
            print(f"Council Summary: {result['council_summary']}")
            print(f"Conversation ID: {result['conversation_id']}")
            print(f"{'-'*70}")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {str(e)}")
            print("Please try again or type 'quit' to exit.")


def show_statistics():
    """Show current system statistics."""
    conversations = len(storage.conversations)
    messages = len(storage.messages)
    nodes = len(storage.nodes)
    agents = len(storage.agents)

    print(f"\n{'='*70}")
    print("SYSTEM STATISTICS")
    print(f"{'='*70}")
    print(f"Total conversations: {conversations}")
    print(f"Total messages: {messages}")
    print(f"Total nodes: {nodes}")
    print(f"Active agents: {agents}")

    if conversations > 0:
        print("\nRecent conversations:")
        for conv_id, conv in list(storage.conversations.items())[-5:]:
            print(f"  - {conv_id}: {conv.user_prompt[:50]}...")

    print(f"{'='*70}")


if __name__ == "__main__":
    main()
