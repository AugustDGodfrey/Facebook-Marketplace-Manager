"""Database Models"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class SearchQuery(Base):
    """Saved search configurations."""

    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    search_url = Column(String(2000), nullable=False)
    keywords = Column(String(500))
    location = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    last_scraped_at = Column(DateTime, nullable=True)

    listings = relationship("Listing", back_populates="search_query")


class Listing(Base):
    """Facebook Marketplace listings."""

    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    search_query_id = Column(Integer, ForeignKey("search_queries.id"), nullable=False)
    marketplace_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    asking_price = Column(Float, nullable=False)
    seller_name = Column(String(255))
    seller_id = Column(String(255))
    listing_url = Column(String(2000), nullable=False)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    search_query = relationship("SearchQuery", back_populates="listings")
    images = relationship("ListingImage", back_populates="listing", cascade="all, delete-orphan")
    image_analysis = relationship("ImageAnalysis", back_populates="listing", uselist=False, cascade="all, delete-orphan")
    market_analysis = relationship("MarketAnalysis", back_populates="listing", uselist=False, cascade="all, delete-orphan")
    offer = relationship("Offer", back_populates="listing", uselist=False, cascade="all, delete-orphan")
    messages = relationship("MessageLog", back_populates="listing", cascade="all, delete-orphan")


class ListingImage(Base):
    """Downloaded listing images."""

    __tablename__ = "listing_images"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    image_url = Column(String(2000), nullable=False)
    local_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer)
    image_order = Column(Integer, default=0)  # Order in the listing
    downloaded_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="images")


class ImageAnalysis(Base):
    """AI vision analysis results for a listing."""

    __tablename__ = "image_analysis"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), unique=True, nullable=False)
    condition_grade = Column(String(20), nullable=False)  # Excellent, Good, Fair, Poor
    condition_score = Column(Integer, nullable=False)  # 0-100
    visible_damage = Column(JSON)  # List of damage items
    completeness = Column(String(100))  # Complete, Missing accessories, Parts only
    estimated_age = Column(String(255))
    authenticity_flags = Column(JSON)  # List of potential authenticity issues
    condition_summary = Column(Text)  # One-sentence plain English summary
    recommended_offer_adjustment = Column(Float)  # -30 to +10 percentage
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    ai_provider = Column(String(50))  # openai or anthropic
    images_analyzed_count = Column(Integer, default=0)

    listing = relationship("Listing", back_populates="image_analysis")


class ComparableListing(Base):
    """Comparable listings found during market analysis."""

    __tablename__ = "comparable_listings"

    id = Column(Integer, primary_key=True, index=True)
    market_analysis_id = Column(Integer, ForeignKey("market_analysis.id"), nullable=False)
    marketplace_id = Column(String(255), unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    price = Column(Float, nullable=False)
    condition_grade = Column(String(20))  # From AI analysis
    condition_score = Column(Integer)
    listing_url = Column(String(2000))
    image_url = Column(String(2000))
    condition_tier_match = Column(Boolean, default=True)  # Within tolerance of target
    found_at = Column(DateTime, default=datetime.utcnow)

    market_analysis = relationship("MarketAnalysis", back_populates="comparables")


class MarketAnalysis(Base):
    """Market analysis and price statistics."""

    __tablename__ = "market_analysis"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), unique=True, nullable=False)
    median_price = Column(Float, nullable=False)
    average_price = Column(Float, nullable=False)
    price_range_min = Column(Float)
    price_range_max = Column(Float)
    std_deviation = Column(Float)
    comparable_count = Column(Integer)
    condition_adjusted_fair_value = Column(Float, nullable=False)
    price_assessment = Column(String(50))  # Steal, Good Deal, Fair, Overpriced
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="market_analysis")
    comparables = relationship("ComparableListing", back_populates="market_analysis", cascade="all, delete-orphan")


class Offer(Base):
    """Generated offer for a listing."""

    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), unique=True, nullable=False)
    final_offer_price = Column(Float, nullable=False)
    final_offer_percentage = Column(Float, nullable=False)  # of fair value
    tier_range_min = Column(Float)  # Tier base range
    tier_range_max = Column(Float)
    base_offer_price = Column(Float)  # Before adjustments
    adjustments = Column(JSON)  # Breakdown of all adjustments applied
    aggressiveness_multiplier = Column(Float)  # Applied multiplier
    ai_generated_message = Column(Text)
    is_approved = Column(Boolean, default=False)
    approval_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)

    listing = relationship("Listing", back_populates="offer")
    messages = relationship("MessageLog", back_populates="offer")


class MessageLog(Base):
    """Message history with sellers."""

    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    offer_id = Column(Integer, ForeignKey("offers.id"), nullable=True)
    message_text = Column(Text, nullable=False)
    message_type = Column(String(50))  # "offer", "follow_up", "counter_offer"
    sender = Column(String(50))  # "bot", "seller"
    sent_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    status = Column(String(50))  # "pending", "sent", "delivered", "read", "failed"
    seller_reply = Column(Text, nullable=True)
    outcome = Column(String(50))  # "accepted", "countered", "ignored", "declined"

    listing = relationship("Listing", back_populates="messages")
    offer = relationship("Offer", back_populates="messages")
