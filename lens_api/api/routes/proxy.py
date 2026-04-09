from __future__ import annotations

from fastapi import FastAPI


def register(app: FastAPI, service_module) -> None:
    app.add_api_route("/v1/chat/completions", service_module.proxy_openai_chat, methods=["POST"])
    app.add_api_route("/v1/responses", service_module.proxy_openai_responses, methods=["POST"])
    app.add_api_route("/v1/messages", service_module.proxy_anthropic_messages, methods=["POST"])
    app.add_api_route("/v1/models", service_module.list_gateway_models, methods=["GET"])
    app.add_api_route(
        "/v1beta/models/{model_name}:generateContent",
        service_module.proxy_gemini_generate_content,
        methods=["POST"],
    )
    app.add_api_route(
        "/v1beta/models/{model_name}:streamGenerateContent",
        service_module.proxy_gemini_stream_generate_content,
        methods=["POST"],
    )
