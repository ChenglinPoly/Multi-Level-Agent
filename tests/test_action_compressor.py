"""
Tests for ActionCompressor service.

Run with: pytest tests/test_action_compressor.py -v
Run slow tests: pytest tests/test_action_compressor.py -v -m slow
Run unit tests: pytest tests/test_action_compressor.py -v -m unit
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from services.action_compressor import ActionCompressor

# Mock response object for LLM client
class MockLLMResponse:
    def __init__(self, output, status="success"):
        self.output = output
        self.status = status
        self.error_information = None

@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.max_context_window = 10000
    client.compressor_models = ["model-v1"]
    
    # Default chat behavior
    client.chat.return_value = MockLLMResponse("Compressed content")
    return client

@pytest.fixture
def compressor(mock_llm_client):
    return ActionCompressor(mock_llm_client)

@pytest.mark.unit
def test_count_tokens(compressor):
    # Test that count_tokens returns an integer
    text = "Hello world"
    count = compressor.count_tokens(text)
    assert isinstance(count, int)
    assert count > 0

@pytest.mark.unit
def test_actions_to_xml(compressor):
    actions = [
        {
            "tool_name": "test_tool",
            "arguments": {"arg1": "value1"},
            "result": {"status": "success", "output": "result1", "extra": 123}
        }
    ]
    xml = compressor._actions_to_xml(actions)
    assert "<action>" in xml
    assert "<tool_name>test_tool</tool_name>" in xml
    assert "<tool_use:arg1>value1</tool_use:arg1>" in xml
    
    # Check result tag existence
    assert "<result>" in xml
    assert "</result>" in xml
    
    # Extract the JSON string from between <result> tags to verify valid JSON
    start_tag = "<result>\n"
    end_tag = "\n  </result>"
    start_index = xml.find(start_tag) + len(start_tag)
    end_index = xml.find(end_tag)
    
    json_str = xml[start_index:end_index]
    loaded_json = json.loads(json_str)
    
    assert loaded_json["status"] == "success"
    assert loaded_json["output"] == "result1"
    assert loaded_json["extra"] == 123

@pytest.mark.unit
def test_compress_if_needed_empty(compressor):
    result = compressor.compress_if_needed([], 10000)
    assert result == []

@pytest.mark.unit
def test_compress_if_needed_single_action(compressor):
    # Should compress fields if too large, but structure remains
    action = {
        "tool_name": "long_output_tool",
        "arguments": {},
        "result": {"status": "success", "output": "A" * 10000} # Long output
    }
    
    # We need to mock _compress_action_fields or count_tokens to trigger logic
    # But let's just see if it returns a list of 1
    result = compressor.compress_if_needed([action], 10000)
    assert len(result) == 1
    # It might have compressed the fields, but structure is preserved
    assert result[0]["tool_name"] == "long_output_tool"

@pytest.mark.unit
def test_compress_if_needed_no_compression(compressor):
    # Case where total tokens < limit
    actions = [
        {"tool_name": "t1", "arguments": {}, "result": {"output": "small"}},
        {"tool_name": "t2", "arguments": {}, "result": {"output": "small"}}
    ]
    
    # Mock count_tokens to return small number
    with patch.object(compressor, 'count_tokens', return_value=100):
        # Use a large window so (window - 20000) > 100
        result = compressor.compress_if_needed(actions, 30000)
        assert result == actions # Should be identical object or content

@pytest.mark.unit
def test_compress_if_needed_trigger_compression(compressor):
    # Case where total tokens > limit
    actions = [
        {"tool_name": "t1", "arguments": {}, "result": {"output": "historical"}}, # History
        {"tool_name": "t2", "arguments": {}, "result": {"output": "recent"}}      # Recent
    ]
    
    max_window = 100000
    
    with patch.object(compressor, 'count_tokens', return_value=85000):
        # Mock internal methods to return complete structures
        with patch.object(compressor, '_summarize_historical_xml') as mock_sum:
            mock_sum.return_value = {
                "tool_name": "_historical_summary",
                "arguments": {},
                "result": {"status": "success", "output": "sum", "_is_summary": True}
            }
            
            with patch.object(compressor, '_compress_action_fields') as mock_fields:
                mock_fields.return_value = actions[-1] # Return recent as is
                
                result = compressor.compress_if_needed(actions, max_window)
                
                assert len(result) == 2
                assert result[0]["tool_name"] == "_historical_summary"
                assert result[0]["result"]["_is_summary"] is True
                mock_sum.assert_called_once()
                mock_fields.assert_called_once()

@pytest.mark.unit
def test_fallback_compress(compressor):
    text = "A" * 100
    compressed = compressor._fallback_compress(text, 10)
    # Check for Chinese "省略" as per implementation for no-tiktoken env (or fallback logic)
    # The implementation uses "省略" in both tiktoken and fallback paths
    assert "省略" in compressed

@pytest.mark.unit
def test_compress_with_thinking_and_task_input(compressor):
    # Test that thinking and task_input are passed down
    actions = [
        {"tool_name": "t1", "result": {"output": "hist"}},
        {"tool_name": "t2", "result": {"output": "recent"}}
    ]
    
    thinking = "My thinking"
    task_input = "My task"
    
    with patch.object(compressor, 'count_tokens', return_value=85000):
        with patch.object(compressor, '_summarize_historical_xml') as mock_sum:
            mock_sum.return_value = {"tool_name": "summary_mock"}
            with patch.object(compressor, '_compress_action_fields') as mock_fields:
                mock_fields.return_value = actions[-1]
                
                compressor.compress_if_needed(
                    actions, 
                    100000, 
                    thinking=thinking, 
                    task_input=task_input
                )
                
                # Verify args passed to _summarize_historical_xml
                mock_sum.assert_called_once()
                call_kwargs = mock_sum.call_args.kwargs
                assert call_kwargs['thinking'] == thinking
                assert call_kwargs['task_input'] == task_input

                # Verify args passed to _compress_action_fields
                mock_fields.assert_called_once()
                call_kwargs_fields = mock_fields.call_args.kwargs
                assert call_kwargs_fields['thinking'] == thinking

@pytest.mark.unit
def test_chunked_summarize_logic(compressor):
    # Test logic of _chunked_summarize by forcing small chunk size
    action_xml = "".join([f"<action>content_{i}</action>\n" for i in range(10)])
    
    # We want to verify that it splits the XML and calls LLM for each chunk
    # We'll use a side effect to count calls and verify content
    call_args_list = []
    
    def chat_side_effect(**kwargs):
        call_args_list.append(kwargs)
        return MockLLMResponse("chunk_summary")
        
    compressor.llm_client.chat.side_effect = chat_side_effect
    
    # Force small chunk size to trigger multiple chunks
    # Each action is roughly 25 chars. If we set chunk size to 40, it should split often.
    # The method uses self.count_tokens. If no tiktoken, it's char based logic.
    result = compressor._chunked_summarize(
        action_xml,
        target_tokens=100,
        thinking="think",
        task_input="input",
        chunk_size_tokens=10 # Very small to force many chunks
    )
    
    assert result["result"]["_chunked"] is True
    assert len(call_args_list) > 1
    assert "chunk_summary" in result["result"]["output"]

@pytest.mark.unit
def test_compress_action_fields_logic(compressor):
    # Test detailed field compression logic without mocking the method itself
    long_str = "data" * 50 # length 200
    action = {
        "tool_name": "test_tool",
        "arguments": {"long_arg": long_str},
        "result": {"status": "success", "output": long_str}
    }
    
    # Force max_field_tokens to be small to trigger compression
    # Assuming count_tokens(long_str) > 10
    
    # Reset mock to track new calls
    compressor.llm_client.chat.reset_mock()
    compressor.llm_client.chat.return_value = MockLLMResponse("compressed_field")
    
    result = compressor._compress_action_fields(
        action, 
        max_field_tokens=10, 
        thinking="think", 
        task_input="task"
    )
    
    # Check arguments compression
    assert result["arguments"]["long_arg"] == "compressed_field"
    
    # Check output compression
    assert result["result"]["output"] == "compressed_field"
    assert result["result"]["_compressed"] is True
    
    # Should have called chat twice (once for arg, once for output)
    assert compressor.llm_client.chat.call_count == 2

@pytest.mark.unit
def test_full_integration_flow(compressor):
    # Integration test akin to the original script logic
    # Do NOT mock internal compressor methods, only the LLM client
    
    # 1. Setup Data
    actions = []
    # 5 historical actions
    for i in range(5):
        actions.append({
            "tool_name": f"hist_{i}",
            "arguments": {},
            "result": {"output": f"history output {i}"}
        })
    
    # 1 recent action
    actions.append({
        "tool_name": "recent",
        "arguments": {},
        "result": {"output": "recent output"}
    })
    
    # 2. Config to trigger compression
    # The condition is: total_tokens <= max_context_window - 20000
    # We want condition to be FALSE (i.e. total > limit)
    # If we set max_context_window = 20005, limit is 5.
    # Total tokens will definitely be > 5.
    
    # Reset mock
    compressor.llm_client.chat.reset_mock()
    compressor.llm_client.chat.return_value = MockLLMResponse("llm_summary")
    
    # 3. Execution
    result = compressor.compress_if_needed(actions, max_context_window=20005)
    
    # 4. Verification
    assert len(result) == 2
    
    # First item should be summary
    assert result[0]["tool_name"] == "_historical_summary"
    assert result[0]["result"]["output"] == "llm_summary"
    assert result[0]["result"]["_is_summary"] is True
    
    # Second item should be recent action
    assert result[1]["tool_name"] == "recent"
    
    # LLM should have been called at least once (for history summary)
    # Might be called more if recent action fields needed compression (depends on count_tokens vs limit)
    # limit for fields is max_window // 2 = 10002.
    # "recent output" is small, so fields probably NOT compressed.

@pytest.mark.slow
@pytest.mark.integration
def test_large_data_compression(compressor, mock_llm_client):
    """Pressure test: 200K tokens data compression (mocked version)"""
    # Create large actions simulating 200K tokens scenario
    # Each action output is ~20000 chars => ~5k tokens
    # 30 actions * 5k tokens = 150k tokens > 80k limit
    large_actions = []
    for i in range(30):
        large_actions.append({
            "tool_name": f"tool_{i}",
            "arguments": {"query": f"test_{i}"},
            "result": {"status": "success", "output": "A" * 20000}
        })

    # Config mock to return compressed content
    mock_llm_client.chat.return_value = MockLLMResponse("Compressed summary content")

    # Calculate original stats
    original_xml = compressor._actions_to_xml(large_actions)
    original_tokens = compressor.count_tokens(original_xml)

    # Execute compression with small window to force compression
    # max_window=50000, limit=30000, data~150k > 30k => triggers compression
    result = compressor.compress_if_needed(large_actions, max_context_window=50000)

    # Calculate compressed stats
    compressed_xml = compressor._actions_to_xml(result)
    compressed_tokens = compressor.count_tokens(compressed_xml)

    # Assertions
    assert len(result) == 2, "Should have summary + recent action"
    assert result[0]["tool_name"] == "_historical_summary"
    assert result[0]["result"]["_is_summary"] is True
    assert result[1]["tool_name"] == "tool_29"  # Last action preserved
    assert compressed_tokens < original_tokens, "Compression should reduce tokens"

    # Verify LLM was called for compression
    assert mock_llm_client.chat.call_count >= 1
    
@pytest.mark.demo
@pytest.mark.integration
def test_compression_statistics_demo(compressor, mock_llm_client):
    """Demo of compression statistics (similar to original test_compressor.py)"""
    # Generate data - Increase to ensure trigger
    actions = []
    # 40 actions * 5000 chars = 200k chars / 4 = 50k tokens.
    # Set max_window 50k. Limit 30k. 50k > 30k.
    for i in range(40):
        actions.append({
            "tool_name": f"tool_{i}",
            "arguments": {"query": f"test_{i}"},
            "result": {"output": "X" * 5000}
        })
    
    # Config mock
    mock_llm_client.chat.return_value = MockLLMResponse("Compressed summary")
    
    # Stats before
    original_xml = compressor._actions_to_xml(actions)
    original_tokens = compressor.count_tokens(original_xml)
    
    # Execute
    # Set max_window small enough to trigger compression.
    # 40 * 5000 chars ~ 50k tokens (theoretical). Actual ~27k.
    # If max_window = 30000. limit = 10000. 27k > 10k -> Trigger.
    result = compressor.compress_if_needed(actions, 30000)
    
    # Stats after
    compressed_xml = compressor._actions_to_xml(result)
    compressed_tokens = compressor.count_tokens(compressed_xml)
    
    # Output detailed stats
    print(f"\n{'='*80}")
    print(f"Compression Statistics Demo:")
    print(f"{'='*80}")
    print(f"Original Actions: {len(actions)}")
    print(f"Compressed Actions: {len(result)}")
    print(f"Action Compression Ratio: {len(result)/len(actions)*100:.1f}%")
    print()
    print(f"Original Tokens: {original_tokens:,}")
    print(f"Compressed Tokens: {compressed_tokens:,}")
    print(f"Token Compression Ratio: {compressed_tokens/original_tokens*100:.1f}%")
    print(f"Tokens Saved: {original_tokens - compressed_tokens:,}")
    print(f"{'='*80}")
    
    # Basic assertions
    assert len(result) < len(actions)
    assert compressed_tokens < original_tokens
