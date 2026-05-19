"""Offer Price Calculation with Tiered Logic"""
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("facebook_marketplace")


class OfferCalculator:
    """Calculates offer prices using tiered logic and adjustments."""

    # Price tiers with offer ranges (percentages of fair value)
    PRICE_TIERS = [
        {"min": 0, "max": 50, "offer_min": 0.80, "offer_max": 0.88, "label": "Low-stakes"},
        {"min": 51, "max": 200, "offer_min": 0.72, "offer_max": 0.80, "label": "Mid-range"},
        {"min": 201, "max": 500, "offer_min": 0.65, "offer_max": 0.74, "label": "Larger ticket"},
        {"min": 501, "max": 2000, "offer_min": 0.58, "offer_max": 0.67, "label": "High-value"},
        {"min": 2001, "max": 10000, "offer_min": 0.50, "offer_max": 0.60, "label": "Major purchase"},
        {"min": 10001, "max": float("inf"), "offer_min": 0.42, "offer_max": 0.55, "label": "Premium"},
    ]

    def __init__(
        self,
        aggressiveness_multiplier: float = 1.0,
        min_floor_percentage: float = 40,
        absolute_minimum_dollars: float = 5,
        condition_threshold: int = 50,
        listing_age_motivated_days: int = 14,
    ):
        """Initialize offer calculator.

        Args:
            aggressiveness_multiplier: Global multiplier for offer aggressiveness (0.5-1.5)
            min_floor_percentage: Minimum percentage of asking price
            absolute_minimum_dollars: Absolute minimum offer in dollars
            condition_threshold: Condition score threshold for poor condition (0-100)
            listing_age_motivated_days: Days after which listing is considered motivated
        """
        self.aggressiveness_multiplier = max(0.5, min(1.5, aggressiveness_multiplier))  # Clamp 0.5-1.5
        self.min_floor_percentage = min_floor_percentage / 100
        self.absolute_minimum_dollars = absolute_minimum_dollars
        self.condition_threshold = condition_threshold
        self.listing_age_motivated_days = listing_age_motivated_days

    def calculate_offer(
        self,
        asking_price: float,
        fair_value: float,
        condition_score: int,
        listing_age_days: int,
        price_assessment: str,
    ) -> dict:
        """Calculate final offer price with all adjustments.

        Args:
            asking_price: Original asking price
            fair_value: Condition-adjusted fair value
            condition_score: AI condition score (0-100)
            listing_age_days: Days listing has been active
            price_assessment: Price assessment label ("Steal", "Good Deal", "Fair", "Overpriced")

        Returns:
            Dictionary with offer calculation breakdown
        """
        logger.info(f"Calculating offer for fair value ${fair_value:.2f}")

        # Get tier range
        tier = self._get_price_tier(fair_value)
        offer_min = tier["offer_min"]
        offer_max = tier["offer_max"]
        base_offer_percentage = (offer_min + offer_max) / 2  # Use midpoint as base

        logger.info(f"Tier: {tier['label']}, Base range: {offer_min:.0%} - {offer_max:.0%}")

        # Initialize adjustments
        adjustments = {}
        total_adjustment = 0.0

        # Adjustment 1: Poor condition (score < 50)
        if condition_score < self.condition_threshold:
            adjustment = -0.075  # -7.5% (mid-range of -5% to -10%)
            adjustments["poor_condition"] = adjustment
            total_adjustment += adjustment
            logger.info(f"Poor condition adjustment: {adjustment:.1%}")

        # Adjustment 2: Listing age (14-30 days)
        if listing_age_days >= self.listing_age_motivated_days:
            if listing_age_days >= 30:
                adjustment = -0.10  # -10% for 30+ days
                adjustments["listing_age_30+"] = adjustment
            else:
                adjustment = -0.05  # -5% for 14-30 days
                adjustments["listing_age_14-30"] = adjustment
            total_adjustment += adjustment
            logger.info(f"Listing age adjustment: {adjustment:.1%}")

        # Adjustment 3: Asking price above fair value
        if asking_price > fair_value:
            adjustment = -0.05  # -5%
            adjustments["asking_above_fair"] = adjustment
            total_adjustment += adjustment
            logger.info(f"Asking price above fair value adjustment: {adjustment:.1%}")

        # Adjustment 4: Good deal (don't lowball too hard)
        if price_assessment == "Steal":
            adjustment = -0.05  # -5%
            adjustments["steal_classification"] = adjustment
            total_adjustment += adjustment
            logger.info(f"Steal classification adjustment: {adjustment:.1%}")

        # Apply aggressiveness multiplier to adjustments
        logger.info(f"Aggressiveness multiplier: {self.aggressiveness_multiplier}")
        adjusted_adjustments = {k: v * self.aggressiveness_multiplier for k, v in adjustments.items()}
        final_adjustment = sum(adjusted_adjustments.values())

        # Calculate offer percentage
        offer_percentage = base_offer_percentage + final_adjustment

        # Apply hard floors
        # Floor 1: Minimum percentage of asking price
        asking_price_floor = asking_price * self.min_floor_percentage
        # Floor 2: Absolute minimum
        absolute_floor = max(self.absolute_minimum_dollars, asking_price_floor)

        # Calculate offer price
        offer_price = fair_value * offer_percentage
        final_offer_price = max(offer_price, absolute_floor)

        # Recalculate final percentage if floor was hit
        final_offer_percentage = (final_offer_price / fair_value) if fair_value > 0 else offer_percentage

        logger.info(
            f"Final offer: ${final_offer_price:.2f} ({final_offer_percentage:.1%} of fair value)"
        )

        return {
            "fair_value": fair_value,
            "asking_price": asking_price,
            "tier_label": tier["label"],
            "tier_range_min": tier["offer_min"],
            "tier_range_max": tier["offer_max"],
            "base_offer_price": fair_value * base_offer_percentage,
            "base_offer_percentage": base_offer_percentage,
            "adjustments": adjustments,
            "adjusted_adjustments": adjusted_adjustments,
            "total_adjustment": final_adjustment,
            "aggressiveness_multiplier": self.aggressiveness_multiplier,
            "final_offer_price": round(final_offer_price, 2),
            "final_offer_percentage": round(final_offer_percentage, 4),
            "floor_applied": "Yes" if final_offer_price == absolute_floor else "No",
            "calculation_timestamp": datetime.utcnow(),
        }

    def _get_price_tier(self, fair_value: float) -> dict:
        """Get price tier for a fair value.

        Args:
            fair_value: Fair value in dollars

        Returns:
            Tier dictionary
        """
        for tier in self.PRICE_TIERS:
            if tier["min"] <= fair_value <= tier["max"]:
                return tier
        return self.PRICE_TIERS[-1]  # Return highest tier as fallback
