from fastapi import FastAPI

from ...gateway.service.proxy_routes import (
    list_gateway_models,
    list_gemini_models,
    proxy_anthropic_messages,
    proxy_gemini_generate_content,
    proxy_gemini_stream_generate_content,
    proxy_openai_chat,
    proxy_openai_embeddings,
    proxy_openai_image_edits,
    proxy_openai_image_generations,
    proxy_openai_responses,
    proxy_rerank,
)


def register(app: FastAPI) -> None:
    app.add_api_route("/v1/chat/completions", proxy_openai_chat, methods=["POST"])
    app.add_api_route("/v1/responses", proxy_openai_responses, methods=["POST"])
    app.add_api_route("/v1/embeddings", proxy_openai_embeddings, methods=["POST"])
    app.add_api_route(
        "/v1/images/generations",
        proxy_openai_image_generations,
        methods=["POST"],
    )
    app.add_api_route("/v1/images/edits", proxy_openai_image_edits, methods=["POST"])
    app.add_api_route("/v1/rerank", proxy_rerank, methods=["POST"])
    app.add_api_route("/v1/messages", proxy_anthropic_messages, methods=["POST"])
    app.add_api_route("/v1/models", list_gateway_models, methods=["GET"])
    app.add_api_route("/v1beta/models", list_gemini_models, methods=["GET"])
    app.add_api_route(
        "/v1beta/models/{model_name}:generateContent",
        proxy_gemini_generate_content,
        methods=["POST"],
    )
    app.add_api_route(
        "/v1beta/models/{model_name}:streamGenerateContent",
        proxy_gemini_stream_generate_content,
        methods=["POST"],
    )
