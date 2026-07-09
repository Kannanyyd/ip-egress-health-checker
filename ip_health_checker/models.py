from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Target:
    name: str
    mode: str
    ip: str | None = None
    proxy: str | None = None


@dataclass
class SourceResult:
    source: str
    ok: bool
    skipped: bool = False
    data: dict[str, Any] | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    raw_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Observation:
    source: str
    ip: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    asn: str | None = None
    asn_name: str | None = None
    isp: str | None = None
    organization: str | None = None
    ip_type: str | None = None
    is_proxy: bool | None = None
    is_vpn: bool | None = None
    is_tor: bool | None = None
    is_hosting: bool | None = None
    is_datacenter: bool | None = None
    is_anonymous: bool | None = None
    is_known_abuser: bool | None = None
    is_bot: bool | None = None
    is_crawler: bool | None = None
    is_relay: bool | None = None
    is_bogon: bool | None = None
    is_anycast: bool | None = None
    timezone: str | None = None
    currency: str | None = None
    languages: list[str] = field(default_factory=list)
    fraud_score: int | None = None
    abuse_score: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionScore:
    name: str
    score: int
    max_score: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TargetReport:
    target: Target
    exit_ip: str
    observations: list[Observation]
    sources: dict[str, SourceResult]
    consistency: dict[str, Any]
    dns_leak: dict[str, Any]
    rbl: dict[str, Any]
    stability: dict[str, Any]
    scores: dict[str, Any]
    manual_review_links: list[dict[str, str]]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": asdict(self.target),
            "exit_ip": self.exit_ip,
            "observations": [item.to_dict() for item in self.observations],
            "sources": {key: value.to_dict() for key, value in self.sources.items()},
            "consistency": self.consistency,
            "dns_leak": self.dns_leak,
            "rbl": self.rbl,
            "stability": self.stability,
            "scores": self.scores,
            "manual_review_links": self.manual_review_links,
            "warnings": self.warnings,
        }
