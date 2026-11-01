from app.gateway.service.tasks.litellm_sync_tasks import (
    extract_context_windows,
    find_context_window,
)


def test_extract_context_windows():
    payload = {
        "gpt-4o": {
            "max_input_tokens": 128000,
            "max_output_tokens": 4096,
            "mode": "chat",
        },
        "text-embedding-3-small": {
            "max_input_tokens": 8191,
            "mode": "embedding",
        },
        "openrouter/anthropic/claude-3-5-sonnet": {
            "max_input_tokens": 200000,
            "mode": "chat",
        },
    }
    extracted = extract_context_windows(payload)
    assert extracted["gpt-4o"] == 128000
    assert "text-embedding-3-small" not in extracted
    assert extracted["openrouter/anthropic/claude-3-5-sonnet"] == 200000
    assert extracted["claude-3-5-sonnet"] == 200000


def test_find_context_window():
    windows = {
        "gpt-4o": 128000,
        "claude-3-5-sonnet": 200000,
    }
    assert find_context_window(windows, "gpt-4o") == 128000
    assert find_context_window(windows, "GPT-4O") == 128000
    assert find_context_window(windows, "azure/gpt-4o") == 128000
    assert find_context_window(windows, "unknown-model") is None
