"""Market Analysis and Price Comparison"""
import statistics
import logging
from typing import Optional
from datetime import datetime
from app.scraper import FacebookMarketplaceScraper
from app.image_analyzer import ImageAnalyzer

logger = logging.getLogger("facebook_marketplace")


class MarketAnalyzer:
    """Analyzes market prices and finds comparable listings."""

    CONDITION_GRADES = ["Excellent", "Good", "Fair", "Poor"]
    CONDITION_TIERS = {"Excellent": 4, "Good": 3, "Fair": 2, "Poor": 1}

    def __init__(
        self,
        scraper: FacebookMarketplaceScraper,
        image_analyzer: ImageAnalyzer,
        comparable_count: int = 18,
        condition_tier_tolerance: int = 1,
    ):
        """Initialize market analyzer.

        Args:
            scraper: FacebookMarketplaceScraper instance
            image_analyzer: ImageAnalyzer instance
            comparable_count: Number of comparables to find
            condition_tier_tolerance: How many tiers difference to allow
        """
        self.scraper = scraper
        self.image_analyzer = image_analyzer
        self.comparable_count = comparable_count
        self.condition_tier_tolerance = condition_tier_tolerance

    async def analyze_listing(
        self,
        title: str,
        description: str,
        asking_price: float,
        condition_grade: str,
    ) -> dict:
        """Analyze market for a specific listing.

        Args:
            title: Item title
            description: Item description
            asking_price: Asking price
            condition_grade: Condition grade from AI analysis

        Returns:
            Market analysis dictionary
        """
        logger.info(f"Analyzing market for: {title}")

        # Build search query from title and description
        search_keywords = self._extract_keywords(title, description)
        search_url = self._build_marketplace_search_url(search_keywords)

        # Scrape comparable listings
        comparables = await self._find_comparable_listings(search_url, condition_grade)

        if not comparables:
            logger.warning(f"No comparable listings found for {title}")
            return self._default_analysis(asking_price)

        # Calculate statistics
        prices = [c["price"] for c in comparables]
        analysis = {
            "median_price": statistics.median(prices),
            "average_price": statistics.mean(prices),
            "price_range_min": min(prices),
            "price_range_max": max(prices),
            "std_deviation": statistics.stdev(prices) if len(prices) > 1 else 0,
            "comparable_count": len(comparables),
            "comparables": comparables,
        }

        # Calculate condition-adjusted fair value
        analysis["condition_adjusted_fair_value"] = analysis["median_price"]

        # Assess price relative to comparables
        fair_value = analysis["condition_adjusted_fair_value"]
        discount_percentage = ((fair_value - asking_price) / fair_value * 100) if fair_value > 0 else 0

        if discount_percentage > 15:
            analysis["price_assessment"] = "Steal"
        elif discount_percentage > 5:
            analysis["price_assessment"] = "Good Deal"
        elif discount_percentage > -5:
            analysis["price_assessment"] = "Fair"
        else:
            analysis["price_assessment"] = "Overpriced"

        analysis["analyzed_at"] = datetime.utcnow()
        logger.info(f"Market analysis complete: {analysis['price_assessment']} at ${fair_value:.2f}")
        return analysis

    async def _find_comparable_listings(
        self, search_url: str, target_condition: str
    ) -> list[dict]:
        """Find comparable listings with condition matching.

        Args:
            search_url: Search URL for comparable listings
            target_condition: Target condition grade for matching

        Returns:
            List of comparable listing dictionaries
        """
        try:
            # Scrape search results
            listings = await self.scraper.scrape_search(search_url, max_pages=2)
            logger.info(f"Found {len(listings)} listings for market comparison")

            comparables = []
            target_tier = self.CONDITION_TIERS.get(target_condition, 2)

            for listing in listings:
                # Analyze condition from images
                if listing.get("local_image_paths"):
                    condition_analysis = await self.image_analyzer.analyze_images(
                        listing["local_image_paths"]
                    )

                    comparable_condition = condition_analysis.get("condition_grade", "Fair")
                    comparable_tier = self.CONDITION_TIERS.get(comparable_condition, 2)

                    # Check if within tolerance
                    tier_diff = abs(comparable_tier - target_tier)
                    if tier_diff <= self.condition_tier_tolerance:
                        comparables.append({
                            "marketplace_id": listing.get("marketplace_id"),
                            "title": listing.get("title"),
                            "price": listing.get("asking_price"),
                            "condition_grade": comparable_condition,
                            "condition_score": condition_analysis.get("condition_score", 50),
                            "listing_url": listing.get("listing_url"),
                            "image_url": listing.get("image_urls", [None])[0],
                            "found_at": datetime.utcnow(),
                        })

                if len(comparables) >= self.comparable_count:
                    break

            logger.info(f"Found {len(comparables)} condition-matched comparables")
            return comparables

        except Exception as e:
            logger.error(f"Error finding comparable listings: {e}")
            return []

    def _extract_keywords(self, title: str, description: str) -> str:
        """Extract search keywords from title and description.

        Args:
            title: Item title
            description: Item description

        Returns:
            Search keywords
        """
        # Simple keyword extraction - take first 3-5 words from title
        words = title.split()[:5]
        return " ".join(words)

    def _build_marketplace_search_url(self, keywords: str) -> str:
        """Build Facebook Marketplace search URL.

        Args:
            keywords: Search keywords

        Returns:
            Search URL
        """
        # This would need to be customized based on location
        encoded_keywords = keywords.replace(" ", "%20")
        return f"https://www.facebook.com/marketplace/search?query={encoded_keywords}"

    def _default_analysis(self, asking_price: float) -> dict:
        """Return default analysis when no comparables found.

        Args:
            asking_price: Asking price

        Returns:
            Default analysis dictionary
        """
        return {
            "median_price": asking_price,
            "average_price": asking_price,
            "price_range_min": asking_price * 0.8,
            "price_range_max": asking_price * 1.2,
            "std_deviation": asking_price * 0.1,
            "comparable_count": 0,
            "condition_adjusted_fair_value": asking_price,
            "price_assessment": "Fair",
            "comparables": [],
            "analyzed_at": datetime.utcnow(),
        }
