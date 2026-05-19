"""AI Image Analysis for Condition Grading"""
import base64
import json
import logging
from typing import Optional
from pathlib import Path
import httpx
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

logger = logging.getLogger("facebook_marketplace")


class ImageAnalyzer:
    """Analyzes listing images using AI vision models."""

    VISION_PROMPT = """You are an expert appraiser analyzing a second-hand item for sale on Facebook Marketplace.
Analyze these listing photos and return a JSON object with:
{
  'condition_grade': 'Excellent | Good | Fair | Poor',
  'condition_score': 0-100,
  'visible_damage': ['list any scratches, dents, stains, missing parts, etc.'],
  'completeness': 'Complete | Missing accessories | Parts only',
  'estimated_age': 'approximate age based on visual cues',
  'authenticity_flags': ['any signs of counterfeit, heavy wear beyond stated condition, etc.'],
  'condition_summary': 'one sentence plain-English summary for use in offer message',
  'recommended_offer_adjustment': -30 to +10 (percentage adjustment based on condition vs. typical listing)
}"""

    def __init__(self, provider: str = "openai", **kwargs):
        """Initialize analyzer with specified provider.

        Args:
            provider: "openai" or "anthropic"
            **kwargs: API keys and configuration
        """
        self.provider = provider.lower()
        self.openai_api_key = kwargs.get("openai_api_key")
        self.anthropic_api_key = kwargs.get("anthropic_api_key")

        if self.provider == "openai" and self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        elif self.provider == "anthropic" and self.anthropic_api_key:
            self.anthropic_client = AsyncAnthropic(api_key=self.anthropic_api_key)
        else:
            raise ValueError(f"Invalid provider or missing API key: {provider}")

    async def analyze_images(self, image_paths: list[str]) -> dict:
        """Analyze listing images and return condition assessment.

        Args:
            image_paths: List of local image file paths

        Returns:
            Dictionary with analysis results
        """
        if not image_paths:
            return self._default_analysis()

        try:
            # Encode images to base64
            encoded_images = []
            for path in image_paths[:5]:  # Limit to 5 images
                try:
                    encoded = await self._encode_image(path)
                    if encoded:
                        encoded_images.append(encoded)
                except Exception as e:
                    logger.warning(f"Failed to encode image {path}: {e}")
                    continue

            if not encoded_images:
                return self._default_analysis()

            # Call appropriate provider
            if self.provider == "openai":
                result = await self._analyze_openai(encoded_images)
            else:
                result = await self._analyze_anthropic(encoded_images)

            result["images_analyzed"] = len(encoded_images)
            return result

        except Exception as e:
            logger.error(f"Error analyzing images: {e}")
            return self._default_analysis()

    async def _analyze_openai(self, encoded_images: list[str]) -> dict:
        """Analyze images using OpenAI GPT-4 Vision.

        Args:
            encoded_images: List of base64 encoded images

        Returns:
            Analysis results
        """
        # Build content with images
        content = [{"type": "text", "text": self.VISION_PROMPT}]

        for encoded_image in encoded_images:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
            })

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
                max_tokens=1000,
            )

            response_text = response.choices[0].message.content
            analysis = self._parse_json_response(response_text)
            analysis["ai_provider"] = "openai"
            return analysis

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self._default_analysis()

    async def _analyze_anthropic(self, encoded_images: list[str]) -> dict:
        """Analyze images using Anthropic Claude Vision.

        Args:
            encoded_images: List of base64 encoded images

        Returns:
            Analysis results
        """
        # Build content with images
        content = [{"type": "text", "text": self.VISION_PROMPT}]

        for encoded_image in encoded_images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": encoded_image,
                },
            })

        try:
            response = await self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
            )

            response_text = response.content[0].text
            analysis = self._parse_json_response(response_text)
            analysis["ai_provider"] = "anthropic"
            return analysis

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return self._default_analysis()

    async def _encode_image(self, image_path: str) -> Optional[str]:
        """Encode image to base64.

        Args:
            image_path: Path to image file

        Returns:
            Base64 encoded string or None
        """
        try:
            path = Path(image_path)
            if not path.exists():
                logger.warning(f"Image not found: {image_path}")
                return None

            with open(path, "rb") as f:
                image_data = f.read()
            return base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
            logger.error(f"Error encoding image: {e}")
            return None

    def _parse_json_response(self, response_text: str) -> dict:
        """Parse JSON from LLM response.

        Args:
            response_text: LLM response text

        Returns:
            Parsed JSON or default analysis
        """
        try:
            # Try to extract JSON from response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                analysis = json.loads(json_str)

                # Validate required fields
                required = [
                    "condition_grade",
                    "condition_score",
                    "visible_damage",
                    "completeness",
                    "estimated_age",
                    "authenticity_flags",
                    "condition_summary",
                    "recommended_offer_adjustment",
                ]
                for field in required:
                    if field not in analysis:
                        analysis[field] = None

                return analysis
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON response")

        return self._default_analysis()

    def _default_analysis(self) -> dict:
        """Return default analysis when processing fails.

        Returns:
            Default analysis dictionary
        """
        return {
            "condition_grade": "Fair",
            "condition_score": 50,
            "visible_damage": [],
            "completeness": "Complete",
            "estimated_age": "Unknown",
            "authenticity_flags": [],
            "condition_summary": "Unable to analyze images; default assessment applied.",
            "recommended_offer_adjustment": 0,
            "ai_provider": "default",
        }
