"""AI Message Generation for Offers"""
import logging
import random
from typing import Optional
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

logger = logging.getLogger("facebook_marketplace")


class MessageGenerator:
    """Generates natural, human-like offer messages using AI."""

    FALLBACK_TEMPLATES = [
        "Hey, I'm interested in your {item}. Would you consider {price}? Let me know!",
        "Hi! Your {item} looks great. I'd love to offer {price} if that works for you.",
        "Hi there! Interested in your {item}. Could you do {price}?",
        "Hey! I'm looking for a {item}. Would {price} work for you?",
    ]

    def __init__(
        self,
        provider: str = "openai",
        tone: str = "casual",
        mention_comps: bool = True,
        mention_condition: bool = True,
        **kwargs,
    ):
        """Initialize message generator.

        Args:
            provider: "openai" or "anthropic"
            tone: "casual" or "semi-formal"
            mention_comps: Whether to mention market comparables
            mention_condition: Whether to mention condition issues
            **kwargs: API keys
        """
        self.provider = provider.lower()
        self.tone = tone
        self.mention_comps = mention_comps
        self.mention_condition = mention_condition

        if self.provider == "openai" and kwargs.get("openai_api_key"):
            self.openai_client = AsyncOpenAI(api_key=kwargs["openai_api_key"])
        elif self.provider == "anthropic" and kwargs.get("anthropic_api_key"):
            self.anthropic_client = AsyncAnthropic(api_key=kwargs["anthropic_api_key"])
        else:
            logger.warning(f"No valid API key for provider {provider}, will use fallback templates")
            self.openai_client = None
            self.anthropic_client = None

    async def generate_message(
        self,
        item_name: str,
        asking_price: float,
        offer_price: float,
        condition_grade: str,
        condition_summary: str,
        visible_damage: list[str],
        listing_age_days: int,
        comparable_price: Optional[float] = None,
        price_assessment: Optional[str] = None,
    ) -> str:
        """Generate an offer message.

        Args:
            item_name: Name of the item
            asking_price: Original asking price
            offer_price: Generated offer price
            condition_grade: Condition grade (Excellent, Good, Fair, Poor)
            condition_summary: One-sentence condition summary
            visible_damage: List of visible damage items
            listing_age_days: How old the listing is
            comparable_price: Market comparable price (optional)
            price_assessment: Price assessment label (optional)

        Returns:
            Generated message text
        """
        logger.info(f"Generating message for {item_name}")

        # Try LLM if available
        if self.openai_client or self.anthropic_client:
            try:
                message = await self._generate_with_llm(
                    item_name,
                    asking_price,
                    offer_price,
                    condition_grade,
                    condition_summary,
                    visible_damage,
                    listing_age_days,
                    comparable_price,
                    price_assessment,
                )
                if message:
                    return message
            except Exception as e:
                logger.warning(f"LLM generation failed, using fallback: {e}")

        # Fall back to template
        return self._generate_fallback_message(item_name, offer_price)

    async def _generate_with_llm(
        self,
        item_name: str,
        asking_price: float,
        offer_price: float,
        condition_grade: str,
        condition_summary: str,
        visible_damage: list[str],
        listing_age_days: int,
        comparable_price: Optional[float],
        price_assessment: Optional[str],
    ) -> Optional[str]:
        """Generate message using LLM.

        Args:
            item_name: Item name
            asking_price: Asking price
            offer_price: Offer price
            condition_grade: Condition grade
            condition_summary: Condition summary
            visible_damage: List of visible damage
            listing_age_days: Listing age
            comparable_price: Market comparable
            price_assessment: Price assessment

        Returns:
            Generated message or None
        """
        # Build context
        context = f"""
Generate a natural, friendly Facebook Marketplace offer message for the following item:

Item: {item_name}
Asking Price: ${asking_price:.2f}
Offer Price: ${offer_price:.2f}
Condition: {condition_grade} ({condition_summary})
Listing Age: {listing_age_days} days
Tone: {self.tone}
"""

        if visible_damage and self.mention_condition:
            context += f"\nVisible Issues: {', '.join(visible_damage)}"

        if comparable_price and self.mention_comps:
            context += f"\nMarket Comparable Price: ${comparable_price:.2f}"

        if price_assessment:
            context += f"\nMarket Assessment: {price_assessment}"

        context += """

Write a 2-4 sentence message that:
- Sounds like a real, friendly buyer (not a bot)
- References specific details from the listing to seem genuine
- States the exact offer price (don't say "around" or use ranges)
- If condition issues exist, subtly mention one as reason for lower offer
- If listing is old (14+ days), mention readiness for quick pickup
- Ends with an open question to invite negotiation
- Does NOT mention this is AI-generated or automated

Return ONLY the message text, no other content.
"""

        try:
            if self.provider == "openai":
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": context}],
                    max_tokens=200,
                    temperature=0.7,
                )
                return response.choices[0].message.content.strip()

            elif self.provider == "anthropic":
                response = await self.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=200,
                    messages=[{"role": "user", "content": context}],
                )
                return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return None

    def _generate_fallback_message(self, item_name: str, offer_price: float) -> str:
        """Generate message from fallback template.

        Args:
            item_name: Item name
            offer_price: Offer price

        Returns:
            Generated message
        """
        template = random.choice(self.FALLBACK_TEMPLATES)
        return template.format(item=item_name, price=f"${offer_price:.2f}")
