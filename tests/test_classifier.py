import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from src.classifier.classifier import classify_complexity, get_tier_for_score


class TestClassifier:
    @pytest.mark.asyncio
    async def test_classify_simple(self, mock_bedrock_runtime):
        mock_response = {
            "content": [
                {
                    "text": json.dumps(
                        {
                            "classification": "SIMPLE",
                            "confidence": 0.95,
                            "reasoning": "Simple classification task",
                        }
                    )
                }
            ]
        }

        mock_bedrock_runtime.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        result = await classify_complexity("Classify this sentiment: I love this!")

        assert result["tier"] == "simple"
        assert result["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_classify_medium(self, mock_bedrock_runtime):
        mock_response = {
            "content": [
                {
                    "text": json.dumps(
                        {
                            "classification": "MEDIUM",
                            "confidence": 0.85,
                            "reasoning": "Code generation task",
                        }
                    )
                }
            ]
        }

        mock_bedrock_runtime.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        result = await classify_complexity("Write a Python function to sort a list")

        assert result["tier"] == "medium"
        assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_classify_complex(self, mock_bedrock_runtime):
        mock_response = {
            "content": [
                {
                    "text": json.dumps(
                        {
                            "classification": "COMPLEX",
                            "confidence": 0.90,
                            "reasoning": "Architecture design task",
                        }
                    )
                }
            ]
        }

        mock_bedrock_runtime.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        result = await classify_complexity("Design a distributed system for real-time analytics")

        assert result["tier"] == "complex"
        assert result["confidence"] == 0.90

    @pytest.mark.asyncio
    async def test_classify_fallback_on_error(self, mock_bedrock_runtime):
        mock_bedrock_runtime.invoke_model.side_effect = Exception("Bedrock error")
        result = await classify_complexity("Some prompt")

        assert result["tier"] == "medium"
        assert result["confidence"] == 0.5

    def test_get_tier_for_score(self):
        assert get_tier_for_score(0.1) == "simple"
        assert get_tier_for_score(0.33) == "simple"
        assert get_tier_for_score(0.5) == "medium"
        assert get_tier_for_score(0.66) == "medium"
        assert get_tier_for_score(0.9) == "complex"
