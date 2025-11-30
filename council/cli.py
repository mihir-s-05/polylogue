"""
CLI entrypoint for the LLM Council system.
Allows running council conversations without HTTP.
"""

import argparse
import sys
import json
from council.scheduler import run_council_conversation


def main():
    """
    CLI entrypoint for running council conversations.
    
    TODO 3: Add simple CLI entrypoint to call run_council_conversation(user_prompt) without HTTP
    """
    parser = argparse.ArgumentParser(
        description="Run an LLM Council deliberation on a prompt"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt to deliberate on"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode, prompting for input"
    )
    
    args = parser.parse_args()
    
    # Get the prompt
    if args.interactive:
        print("LLM Council - Interactive Mode")
        print("Enter your prompt (or 'quit' to exit):")
        prompt = input("> ").strip()
        if prompt.lower() == "quit":
            print("Goodbye!")
            sys.exit(0)
    elif args.prompt:
        prompt = args.prompt
    else:
        # Read from stdin if no prompt provided
        print("Enter your prompt (Ctrl+D to submit):")
        prompt = sys.stdin.read().strip()
    
    if not prompt:
        print("Error: No prompt provided", file=sys.stderr)
        sys.exit(1)
    
    print(f"\nStarting council deliberation on: {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n")
    
    # Run the council conversation
    result = run_council_conversation(prompt)
    
    # Output result
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "=" * 60)
        print("COUNCIL DELIBERATION COMPLETE")
        print("=" * 60)
        print("\nFINAL ANSWER:")
        print("-" * 40)
        print(result.get("final_answer", "No answer generated"))
        print("\nCOUNCIL SUMMARY:")
        print("-" * 40)
        print(result.get("council_summary", "No summary available"))


if __name__ == "__main__":
    main()
