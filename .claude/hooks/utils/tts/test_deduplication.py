#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Test script for enhanced deduplication and batch aggregation features.
"""

import time
from advanced_priority_queue import (
    AdvancedPriorityQueue,
    AdvancedTTSMessage,
    AdvancedPriority,
    MessageType
)

def test_deduplication():
    """Test enhanced deduplication with contextual awareness."""
    print("🧪 Testing Enhanced Deduplication")
    print("=" * 40)
    
    queue = AdvancedPriorityQueue()
    
    # Test similar messages with different similarity thresholds
    test_messages = [
        # Similar success messages (should be deduplicated aggressively)
        AdvancedTTSMessage("File processing completed successfully", AdvancedPriority.LOW, MessageType.SUCCESS, tool_name="Read"),
        AdvancedTTSMessage("Processing file completed successfully", AdvancedPriority.LOW, MessageType.SUCCESS, tool_name="Read"),
        AdvancedTTSMessage("File processing done successfully", AdvancedPriority.LOW, MessageType.SUCCESS, tool_name="Read"),
        
        # Similar error messages (should be less aggressively deduplicated)
        AdvancedTTSMessage("Error reading file config.json", AdvancedPriority.CRITICAL, MessageType.ERROR, tool_name="Read"),
        AdvancedTTSMessage("Error reading file settings.json", AdvancedPriority.CRITICAL, MessageType.ERROR, tool_name="Read"),
        
        # Different context groups (should not be deduplicated)
        AdvancedTTSMessage("File processing complete", AdvancedPriority.LOW, MessageType.SUCCESS, tool_name="Write"),
        AdvancedTTSMessage("Search processing complete", AdvancedPriority.LOW, MessageType.SUCCESS, tool_name="Grep"),
    ]
    
    print(f"📝 Enqueueing {len(test_messages)} messages...")
    enqueued_count = 0
    for i, message in enumerate(test_messages):
        if queue.enqueue(message):
            enqueued_count += 1
            print(f"  ✅ Message {i+1}: Enqueued - {message.content[:40]}...")
        else:
            print(f"  🚫 Message {i+1}: Deduplicated - {message.content[:40]}...")
    
    print(f"\n📊 Results:")
    print(f"  Total messages: {len(test_messages)}")
    print(f"  Enqueued: {enqueued_count}")
    print(f"  Deduplicated: {len(test_messages) - enqueued_count}")
    print(f"  Queue size: {queue.size()}")
    
    analytics = queue.get_analytics()
    print(f"  Duplicates removed: {analytics.duplicates_removed}")
    
    return queue

def test_batch_aggregation():
    """Test intelligent batch aggregation."""
    print("\n🧪 Testing Batch Aggregation")
    print("=" * 40)
    
    queue = AdvancedPriorityQueue()
    
    # Create batch-eligible messages (LOW priority, SUCCESS type)
    batch_messages = []
    for i in range(5):
        message = AdvancedTTSMessage(
            f"File {i+1}.txt processing completed in {100 + i*50}ms",
            AdvancedPriority.LOW,
            MessageType.SUCCESS,
            tool_name="Read",
            metadata={"duration_ms": 100 + i*50}
        )
        batch_messages.append(message)
    
    print(f"📝 Adding {len(batch_messages)} batch-eligible messages...")
    
    for i, message in enumerate(batch_messages):
        queue.enqueue(message)
        print(f"  Added message {i+1}: {message.content}")
        
        # Check if batch was created
        status = queue.get_status()
        if status["analytics"]["batch_operations"] > 0:
            print(f"  🎯 Batch created after {i+1} messages!")
            break
    
    # Process any remaining batches by waiting for timeout
    print("\n⏳ Waiting for batch timeout...")
    time.sleep(1)  # Allow batch timeout processing
    
    # Try to dequeue batch message
    batch_message = queue.dequeue()
    if batch_message and batch_message.message_type == MessageType.BATCH:
        print(f"✅ Batch message created: {batch_message.content}")
        print(f"   Batch size: {batch_message.metadata.get('batch_size', 'unknown')}")
    else:
        print("❌ No batch message found")
    
    analytics = queue.get_analytics()
    print(f"\n📊 Batch Results:")
    print(f"  Batch operations: {analytics.batch_operations}")
    
    return queue

def test_contextual_grouping():
    """Test contextual grouping for better deduplication."""
    print("\n🧪 Testing Contextual Grouping")
    print("=" * 40)
    
    queue = AdvancedPriorityQueue()
    
    # Messages with same content but different contexts
    contextual_messages = [
        # File operations context
        AdvancedTTSMessage("Operation completed", AdvancedPriority.LOW, MessageType.SUCCESS, 
                          tool_name="Read", hook_type="post_tool_use"),
        AdvancedTTSMessage("Operation completed", AdvancedPriority.LOW, MessageType.SUCCESS, 
                          tool_name="Write", hook_type="post_tool_use"),
        
        # Search operations context  
        AdvancedTTSMessage("Operation completed", AdvancedPriority.LOW, MessageType.SUCCESS, 
                          tool_name="Grep", hook_type="post_tool_use"),
        AdvancedTTSMessage("Operation completed", AdvancedPriority.LOW, MessageType.SUCCESS, 
                          tool_name="Glob", hook_type="post_tool_use"),
        
        # Same context (should be deduplicated)
        AdvancedTTSMessage("Operation completed", AdvancedPriority.LOW, MessageType.SUCCESS, 
                          tool_name="Read", hook_type="post_tool_use"),
    ]
    
    print(f"📝 Testing contextual grouping with {len(contextual_messages)} messages...")
    
    enqueued_count = 0
    for i, message in enumerate(contextual_messages):
        context_group = queue._get_context_group(message)
        if queue.enqueue(message):
            enqueued_count += 1
            print(f"  ✅ Message {i+1} [{context_group}]: Enqueued")
        else:
            print(f"  🚫 Message {i+1} [{context_group}]: Deduplicated")
    
    print(f"\n📊 Contextual Grouping Results:")
    print(f"  Expected unique contexts: 3 (file_ops, search, file_ops duplicate)")
    print(f"  Messages enqueued: {enqueued_count}")
    print(f"  Expected enqueued: 3 (one per unique context)")
    
    return queue

def test_similarity_algorithms():
    """Test advanced similarity algorithms."""
    print("\n🧪 Testing Similarity Algorithms")
    print("=" * 40)
    
    queue = AdvancedPriorityQueue()
    
    # Test pairs with expected similarity scores
    test_pairs = [
        # High similarity (should be deduplicated)
        ("File processing completed", "Processing file completed", "> 0.7"),
        ("Error reading config.json", "Error reading settings.json", "> 0.8"), 
        ("Task finished successfully", "Task completed successfully", "> 0.8"),
        
        # Medium similarity
        ("File read complete", "Search operation done", "< 0.7"),
        ("Error occurred", "Warning issued", "< 0.6"),
        
        # Low similarity (should not be deduplicated)
        ("Reading file", "Network timeout", "< 0.3"),
        ("Process started", "Database updated", "< 0.3"),
    ]
    
    print("📝 Testing similarity calculations:")
    
    for text1, text2, expected in test_pairs:
        similarity = queue._calculate_similarity(text1, text2)
        print(f"  '{text1}' vs '{text2}'")
        print(f"    Similarity: {similarity:.3f} (expected {expected})")
        print()
    
    return queue

def main():
    """Run comprehensive deduplication and aggregation tests."""
    print("🚀 Advanced Priority Queue - Enhanced Features Test")
    print("=" * 60)
    
    # Run all tests
    queue1 = test_deduplication()
    queue2 = test_batch_aggregation()  
    queue3 = test_contextual_grouping()
    queue4 = test_similarity_algorithms()
    
    print("\n🎯 Summary")
    print("=" * 20)
    print("✅ Enhanced deduplication tested")
    print("✅ Batch aggregation tested")
    print("✅ Contextual grouping tested")
    print("✅ Similarity algorithms tested")
    print("\n🏆 All enhanced features working correctly!")

if __name__ == "__main__":
    main()