#!/usr/bin/env python3
"""
Simple test script to verify the LLM Council system works end-to-end.

This script runs a minimal council deliberation and checks that all components work.
"""

import sys
from scheduler import run_council_conversation
from agents import initialize_agents
import storage


def test_basic_deliberation():
    """Test a basic council deliberation."""
    print("="*70)
    print("LLM COUNCIL SYSTEM TEST")
    print("="*70)
    print()

    # Clear any existing data
    print("1. Clearing existing data...")
    storage.clear_all_data()
    print("   ✓ Data cleared")
    print()

    # Initialize agents
    print("2. Initializing agents...")
    agents = initialize_agents()
    print(f"   ✓ Initialized {len(agents)} agents:")
    for agent in agents:
        print(f"     - {agent.agent_id}")
    print()

    # Run a test deliberation
    print("3. Running test deliberation...")
    test_prompt = "What are the most important factors to consider when designing a simple web API?"

    try:
        result = run_council_conversation(test_prompt)
        print("   ✓ Deliberation completed successfully")
        print()

        # Verify result structure
        print("4. Verifying results...")
        assert "final_answer" in result, "Missing final_answer"
        assert "council_summary" in result, "Missing council_summary"
        assert "conversation_id" in result, "Missing conversation_id"
        assert "total_messages" in result, "Missing total_messages"
        assert "total_nodes" in result, "Missing total_nodes"
        print("   ✓ Result structure valid")
        print()

        # Print summary
        print("5. Test Results:")
        print(f"   Conversation ID: {result['conversation_id']}")
        print(f"   Total messages: {result['total_messages']}")
        print(f"   Total nodes: {result['total_nodes']}")
        print(f"   Tokens used: {result['tokens_used']}")
        print()

        print("   Final Answer (first 200 chars):")
        print(f"   {result['final_answer'][:200]}...")
        print()

        # Verify data persistence
        print("6. Verifying data persistence...")
        conv = storage.get_conversation(result['conversation_id'])
        assert conv is not None, "Conversation not found in storage"

        messages = storage.get_messages_for_conversation(result['conversation_id'])
        assert len(messages) > 0, "No messages found"

        nodes = storage.get_nodes_for_conversation(result['conversation_id'])
        assert len(nodes) > 0, "No nodes found"

        print(f"   ✓ Found {len(messages)} messages in storage")
        print(f"   ✓ Found {len(nodes)} nodes in storage")
        print()

        print("="*70)
        print("ALL TESTS PASSED ✓")
        print("="*70)
        print()
        print("The LLM Council system is working correctly!")
        print("You can now:")
        print("  - Run CLI: python cli.py \"Your question\"")
        print("  - Start API: python main.py")
        print()

        return True

    except Exception as e:
        print(f"\n   ✗ ERROR: {str(e)}")
        print()
        print("="*70)
        print("TEST FAILED ✗")
        print("="*70)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_basic_deliberation()
    sys.exit(0 if success else 1)
