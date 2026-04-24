"""SQLAlchemy models for multi-seller Arc marketplace."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agents_market.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Seller(Base):
    __tablename__ = "sellers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner_wallet_address: Mapped[str] = mapped_column(String(66), nullable=False, index=True)
    validator_wallet_address: Mapped[str] = mapped_column(String(66), default="", nullable=False)
    wallet_set_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_wallet_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validator_wallet_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    agents: Mapped[list["Agent"]] = relationship(back_populates="seller", cascade="all, delete-orphan")


class Buyer(Base):
    __tablename__ = "buyers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    organization: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(66), nullable=False, index=True)
    validator_wallet_address: Mapped[str] = mapped_column(String(66), default="", nullable=False)
    owner_wallet_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validator_wallet_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    arc_agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    identity_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_uri: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    icon_data_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="General", nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    http_method: Mapped[str] = mapped_column(String(12), default="POST", nullable=False)
    api_docs_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arc_agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    identity_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    seller: Mapped[Seller] = relationship(back_populates="agents")
    tools: Mapped[list["Tool"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    tool_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price_usdc: Mapped[float] = mapped_column(Float, nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    http_method: Mapped[str] = mapped_column(String(12), default="POST", nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="General", nullable=False)
    runtime_price_usdc: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    runtime_unit: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    capability_type: Mapped[str] = mapped_column(String(32), default="tool", nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    agent: Mapped[Agent] = relationship(back_populates="tools")
    skills: Mapped[list["Skill"]] = relationship(back_populates="tool", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id"), index=True)
    skill_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price_usdc: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tool: Mapped[Tool] = relationship(back_populates="skills")


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    seller_id: Mapped[int | None] = mapped_column(ForeignKey("sellers.id"), nullable=True, index=True)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    tool_id: Mapped[int | None] = mapped_column(ForeignKey("tools.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    buyer_address: Mapped[str | None] = mapped_column(String(66), nullable=True, index=True)
    transaction_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount_usdc: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    validator_wallet_address: Mapped[str] = mapped_column(String(66), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    tag: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    feedback_hash: Mapped[str] = mapped_column(String(130), default="", nullable=False)
    tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ValidationRequest(Base):
    __tablename__ = "validation_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    validator_wallet_address: Mapped[str] = mapped_column(String(66), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(130), unique=True, nullable=False)
    request_uri: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_tag: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    request_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    response_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class GatewayAccount(Base):
    __tablename__ = "gateway_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), unique=True, index=True)
    chain: Mapped[str] = mapped_column(String(64), default="arcTestnet", nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(66), nullable=False)
    wallet_balance_usdc: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    gateway_available_usdc: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BridgeTransfer(Base):
    __tablename__ = "bridge_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), index=True)
    source_chain: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_chain: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_usdc: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    transfer_ref: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    transfer_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ExternalFundingAttempt(Base):
    __tablename__ = "external_funding_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"), index=True)
    source_chain: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_chain: Mapped[str] = mapped_column(String(64), default="Arc_Testnet", nullable=False)
    amount_usdc: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    transfer_ref: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    bridge_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    steps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tx_hashes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    explorer_urls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class BuyerInvocation(Base):
    __tablename__ = "buyer_invocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id"), index=True)
    payment_event_id: Mapped[int | None] = mapped_column(ForeignKey("payment_events.id"), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    output_preview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    amount_usdc: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    transaction_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(64), default="completed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        back_populates="buyer_invocation",
        cascade="all, delete-orphan",
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    buyer_invocation_id: Mapped[int | None] = mapped_column(ForeignKey("buyer_invocations.id"), nullable=True, index=True)
    payment_event_id: Mapped[int | None] = mapped_column(ForeignKey("payment_events.id"), nullable=True, index=True)
    tool_id: Mapped[int | None] = mapped_column(ForeignKey("tools.id"), nullable=True, index=True)
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"), nullable=True, index=True)
    component_type: Mapped[str] = mapped_column(String(32), nullable=False)
    component_key: Mapped[str] = mapped_column(String(64), nullable=False)
    component_name: Mapped[str] = mapped_column(String(120), nullable=False)
    units: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    unit_price_usdc: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    subtotal_usdc: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    buyer_invocation: Mapped[BuyerInvocation | None] = relationship(back_populates="usage_records")
