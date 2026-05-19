"""Facebook Marketplace Web Scraper"""
import asyncio
import random
from pathlib import Path
from datetime import datetime
from typing import Optional
from PIL import Image
import aiofiles
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import logging

logger = logging.getLogger("facebook_marketplace")


class FacebookMarketplaceScraper:
    """Scrapes Facebook Marketplace listings using Playwright."""

    def __init__(
        self,
        email: str,
        password: str,
        backup_code: Optional[str] = None,
        image_dir: Path = Path("app/images"),
        image_max_width: int = 1200,
        image_quality: int = 85,
    ):
        """Initialize the scraper.

        Args:
            email: Facebook email
            password: Facebook password
            backup_code: 2FA backup code if needed
            image_dir: Directory to save images
            image_max_width: Max width for compressed images
            image_quality: JPEG quality (0-100)
        """
        self.email = email
        self.password = password
        self.backup_code = backup_code
        self.image_dir = image_dir
        self.image_max_width = image_max_width
        self.image_quality = image_quality
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Ensure image directory exists
        self.image_dir.mkdir(parents=True, exist_ok=True)

    async def launch(self):
        """Launch browser and authenticate with Facebook."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        logger.info("Browser launched")

        await self._authenticate()

    async def _authenticate(self):
        """Authenticate with Facebook."""
        logger.info("Authenticating with Facebook...")
        await self.page.goto("https://www.facebook.com/login")
        await self._random_delay(1000, 2000)

        # Enter email
        await self.page.fill("input[name='email']", self.email)
        await self._human_like_typing_delay()

        # Enter password
        await self.page.fill("input[name='pass']", self.password)
        await self._human_like_typing_delay()

        # Click login
        await self.page.click("button[name='login']", force=True)
        await self._random_delay(2000, 3000)

        # Handle 2FA if present
        try:
            await self.page.wait_for_selector("input[aria-label*='code']", timeout=5000)
            logger.info("2FA detected, entering backup code...")
            if self.backup_code:
                await self.page.fill("input[aria-label*='code']", self.backup_code)
                await self._human_like_typing_delay()
                await self.page.press("input[aria-label*='code']", "Enter")
                await self._random_delay(2000, 3000)
        except:
            logger.info("No 2FA required")

        # Wait for redirect
        await self.page.wait_for_url("**/marketplace**", timeout=15000)
        logger.info("Successfully authenticated")

    async def scrape_search(self, search_url: str, max_pages: int = 5) -> list[dict]:
        """Scrape listings from a search URL.

        Args:
            search_url: Facebook Marketplace search URL
            max_pages: Maximum pages to scrape

        Returns:
            List of listing dictionaries
        """
        listings = []
        await self.page.goto(search_url)
        await self._random_delay(2000, 3000)

        for page_num in range(max_pages):
            logger.info(f"Scraping page {page_num + 1}")

            # Wait for listings to load
            await self.page.wait_for_selector("div[data-testid='listing_card']", timeout=10000)
            await self._random_delay(1000, 2000)

            # Scroll to load more listings
            for _ in range(3):
                await self._human_like_scroll()
                await self._random_delay(500, 1500)

            # Extract listing cards
            listing_elements = await self.page.query_selector_all("div[data-testid='listing_card']")
            logger.info(f"Found {len(listing_elements)} listings on page {page_num + 1}")

            for element in listing_elements:
                try:
                    listing = await self._extract_listing(element)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.warning(f"Error extracting listing: {e}")
                    continue

            # Try to navigate to next page
            if page_num < max_pages - 1:
                try:
                    next_button = await self.page.query_selector("a[aria-label='Next Page']")
                    if next_button:
                        await next_button.click()
                        await self._random_delay(2000, 3000)
                    else:
                        logger.info("No next page button found")
                        break
                except:
                    logger.info("Could not navigate to next page")
                    break

        logger.info(f"Scraped total {len(listings)} listings")
        return listings

    async def _extract_listing(self, element) -> Optional[dict]:
        """Extract listing data from a listing card element.

        Args:
            element: Playwright element handle

        Returns:
            Listing dictionary or None
        """
        try:
            # Extract title
            title_elem = await element.query_selector("span[role='heading']")
            title = await title_elem.inner_text() if title_elem else "Unknown"

            # Extract price
            price_elem = await element.query_selector("span.x1jyosf9")
            price_text = await price_elem.inner_text() if price_elem else "$0"
            price = float(price_text.replace("$", "").replace(",", ""))

            # Extract seller name
            seller_elem = await element.query_selector("span.x1jyosf9")
            seller_name = await seller_elem.inner_text() if seller_elem else "Unknown"

            # Extract listing URL
            link_elem = await element.query_selector("a[role='link']")
            listing_url = await link_elem.get_attribute("href") if link_elem else ""
            if not listing_url.startswith("http"):
                listing_url = f"https://www.facebook.com{listing_url}"

            # Get marketplace ID from URL
            marketplace_id = listing_url.split("/")[-2] if listing_url else None

            # Extract images
            image_urls = await self._extract_image_urls(element)
            local_image_paths = []

            if image_urls and marketplace_id:
                local_image_paths = await self._download_images(image_urls, marketplace_id)

            return {
                "marketplace_id": marketplace_id,
                "title": title,
                "asking_price": price,
                "seller_name": seller_name,
                "listing_url": listing_url,
                "image_urls": image_urls,
                "local_image_paths": local_image_paths,
                "description": "",  # Would need to visit detail page
                "scraped_at": datetime.utcnow(),
            }
        except Exception as e:
            logger.error(f"Error extracting listing: {e}")
            return None

    async def _extract_image_urls(self, element) -> list[str]:
        """Extract image URLs from a listing element.

        Args:
            element: Playwright element handle

        Returns:
            List of image URLs
        """
        image_urls = []
        try:
            img_elements = await element.query_selector_all("img[role='img']")
            for img_elem in img_elements:
                src = await img_elem.get_attribute("src")
                if src and "facebook" in src and "image" not in src.lower():
                    image_urls.append(src)
        except Exception as e:
            logger.warning(f"Error extracting image URLs: {e}")
        return image_urls[:10]  # Limit to 10 images

    async def _download_images(self, image_urls: list[str], marketplace_id: str) -> list[str]:
        """Download and compress images.

        Args:
            image_urls: List of image URLs
            marketplace_id: Marketplace listing ID

        Returns:
            List of local file paths
        """
        listing_dir = self.image_dir / marketplace_id
        listing_dir.mkdir(parents=True, exist_ok=True)

        local_paths = []
        for idx, url in enumerate(image_urls):
            try:
                # Download image
                response = await self.page.goto(url, wait_until="networkidle")
                image_data = await response.body()

                # Save and compress
                temp_path = listing_dir / f"temp_{idx}.jpg"
                compressed_path = listing_dir / f"image_{idx:02d}.jpg"

                # Write original
                async with aiofiles.open(temp_path, "wb") as f:
                    await f.write(image_data)

                # Compress with PIL
                img = Image.open(temp_path)
                if img.width > self.image_max_width:
                    ratio = self.image_max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((self.image_max_width, new_height), Image.Resampling.LANCZOS)

                img.save(compressed_path, "JPEG", quality=self.image_quality)
                temp_path.unlink()

                local_paths.append(str(compressed_path))
                logger.info(f"Downloaded and compressed image {idx + 1} for {marketplace_id}")
            except Exception as e:
                logger.warning(f"Error downloading image {idx}: {e}")
                continue

        return local_paths

    async def _human_like_scroll(self):
        """Perform human-like scrolling behavior."""
        scroll_amount = random.randint(100, 500)
        await self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")

    async def _human_like_typing_delay(self):
        """Add human-like delay between typing."""
        await self._random_delay(50, 200)

    async def _random_delay(self, min_ms: int = 500, max_ms: int = 2000):
        """Add random delay to mimic human behavior.

        Args:
            min_ms: Minimum delay in milliseconds
            max_ms: Maximum delay in milliseconds
        """
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    async def close(self):
        """Close browser and cleanup."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")
