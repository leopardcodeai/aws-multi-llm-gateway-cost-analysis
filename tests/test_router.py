import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.router.router import route_request


class TestRouter:
    @pytest.fixture
    def mock_bedrock_response(self):
        return {
            "content": [{"text": "Test response from Bedrock"}],
            "usage": {"input_tokens": 50, "output_tokens": 100},
        }

    @pytest.fixture
    def mock_openai_response(self):
        mock = MagicMock()
        mock.choices = [MagicMock(message=MagicMock(content="Test response from OpenAI"))]
        mock.usage = MagicMock(prompt_tokens=50, completion_tokens=100, total_tokens=150)
        return mock

    @pytest.mark.asyncio
    async def test_route_simple_to_llama(
        self, mock_bedrock_response, mock_bedrock_runtime, mock_openai_client
    ):
        with patch("src.router.router.classify_complexity") as mock_classify:
            mock_classify.return_value = {
                "tier": "simple",
                "confidence": 0.9,
                "reasoning": "Simple task",
            }

            mock_bedrock_runtime.invoke_model.return_value = {
                "body": MagicMock(read=lambda: json.dumps(mock_bedrock_response).encode())
            }

            response = await route_request(
                messages=[{"role": "user", "content": "Classify: positive"}], model="auto"
            )

            assert response.provider == "bedrock"
            assert "llama" in response.model.lower()

    @pytest.mark.asyncio
    async def test_route_complex_to_gpt4o(
        self, mock_openai_response, mock_bedrock_runtime, mock_openai_client
    ):
        with patch("src.router.router.classify_complexity") as mock_classify:
            mock_classify.return_value = {
                "tier": "complex",
                "confidence": 0.95,
                "reasoning": "Complex reasoning",
            }

            mock_openai_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_response
            )

            response = await route_request(
                messages=[{"role": "user", "content": "Design a distributed system"}], model="auto"
            )

            assert response.provider == "openai"
            assert "gpt" in response.model.lower()

    @pytest.mark.asyncio
    async def test_specific_model_override(self, mock_bedrock_response, mock_bedrock_runtime):
        mock_bedrock_runtime.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_bedrock_response).encode())
        }

        response = await route_request(
            messages=[{"role": "user", "content": "Test"}], model="meta.llama3-1-8b-instruct-v1:0"
        )

        assert response.model == "meta.llama3-1-8b-instruct-v1:0"

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self, mock_bedrock_response, mock_bedrock_runtime):
        with patch("src.router.router.classify_complexity") as mock_classify:
            mock_classify.return_value = {
                "tier": "simple",
                "confidence": 0.9,
                "reasoning": "Simple",
            }

            mock_bedrock_runtime.invoke_model.side_effect = [
                Exception("Primary failed"),
                {"body": MagicMock(read=lambda: json.dumps(mock_bedrock_response).encode())},
            ]

            response = await route_request(
                messages=[{"role": "user", "content": "Test"}], model="auto"
            )

            assert response.fallback_used is True
