from app.core.model_catalog import build_catalog_context_index


def test_catalog_alias_uses_exact_entry_and_ignores_output_limit() -> None:
    index = build_catalog_context_index(
        {
            "gpt-4o": {"max_input_tokens": 128_000},
            "provider/gpt-4o": {"max_input_tokens": 32_000},
            "provider/output-only": {"max_tokens": 16_384},
        }
    )

    assert index["gpt-4o"] == 128_000
    assert index["provider/gpt-4o"] == 32_000
    assert "output-only" not in index


def test_catalog_alias_uses_smallest_prefixed_window_without_exact_entry() -> None:
    index = build_catalog_context_index(
        {
            "a/claude": {"max_input_tokens": 128_000},
            "b/claude": {"max_input_tokens": 64_000},
        }
    )

    assert index["claude"] == 64_000
