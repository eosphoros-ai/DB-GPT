"""Quote data models, decimal calculations, and CN/HK trading calendar."""

from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .calendar import (
    _SEED_CLOSURES,
    _SEED_HK_HALF_DAYS,
    TRADING_CALENDAR,
    TradingCalendar,
)

BEIJING = timezone(timedelta(hours=8))
CENT = Decimal("0.01")
CLOCK_SKEW_TOLERANCE = timedelta(minutes=2)
CLOSURES = _SEED_CLOSURES
HK_HALF_DAYS = _SEED_HK_HALF_DAYS[2026]


def number(value: object, *, positive: bool = False) -> Optional[Decimal]:
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (ValueError, InvalidOperation):
        return None
    if not amount.is_finite() or (positive and amount <= 0):
        return None
    return amount


def trading_day(
    market: str, day: date, *, calendar: TradingCalendar = TRADING_CALENDAR
) -> bool:
    return calendar.is_trading_day(market, day)


def expected_day(
    market: str, day: date, *, calendar: TradingCalendar = TRADING_CALENDAR
) -> date:
    return calendar.expected_day(market, day)


def latest_expected_day(
    market: str, now: datetime, *, calendar: TradingCalendar = TRADING_CALENDAR
) -> date:
    return calendar.latest_expected_day(market, now)


def session(
    market: str, now: datetime, *, calendar: TradingCalendar = TRADING_CALENDAR
) -> str:
    """Return the exchange session phase at a Beijing timestamp."""
    return calendar.session(market, now)


class Listing(BaseModel):
    market: Literal["sh", "sz", "bj", "hk"]
    code: str
    name: str
    currency: str = ""
    asset_type: Literal["stock", "index", "etf"] = "stock"
    lookup_alias: str = Field(default="", exclude=True)

    @property
    def symbol(self) -> str:
        return self.market + self.code

    @property
    def label(self) -> str:
        return f"{self.code}.{self.market.upper()}"


class Quote(BaseModel):
    listing: Listing
    day: date
    as_of: Optional[datetime] = None
    source: str
    url: str
    last: Optional[Decimal] = None
    previous: Optional[Decimal] = None
    opening: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    turnover: Optional[Decimal] = None
    pe: Optional[Decimal] = None
    pb: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    turnover_rate: Optional[Decimal] = None
    suspended: bool = False
    change: Optional[Decimal] = None
    percent: Optional[Decimal] = None
    amplitude: Optional[Decimal] = None
    gaps: dict[str, str] = Field(default_factory=dict)

    def calculate(
        self,
        source_change: Optional[Decimal] = None,
        source_percent: Optional[Decimal] = None,
    ) -> None:
        for key in ("last", "previous", "opening", "high", "low", "turnover"):
            if getattr(self, key) is None:
                self.gaps[key] = "missing"
        if self.previous is None or self.previous <= 0:
            return
        if self.high is not None and self.low is not None:
            if self.high >= self.low:
                self.amplitude = (self.high - self.low) * 100 / self.previous
            else:
                self.gaps["amplitude"] = "conflict"
        if self.last is None:
            return
        change = self.last - self.previous
        percent = change * 100 / self.previous
        for calc, reported in ((change, source_change), (percent, source_percent)):
            if reported is not None:
                tick = Decimal(1).scaleb(reported.as_tuple().exponent)
                rounded = calc.quantize(tick, rounding=ROUND_HALF_UP)
                if abs(rounded - reported) > tick:
                    self.gaps["change"] = "reference_conflict"
                    return
        self.change, self.percent = change, percent


class Verification(BaseModel):
    status: Literal["pending", "confirmed"] = "pending"
    source: Optional[str] = None
    url: Optional[str] = None
    day: Optional[date] = None
    fields: list[str] = Field(default_factory=list)
    reason: str = ""
    other_price: Optional[Decimal] = None
    other_source: Optional[str] = None
    other_url: Optional[str] = None
    other_as_of: Optional[datetime] = None


class Sector(BaseModel):
    code: str = Field(pattern=r"^BK[0-9]{4}$")
    name: str

    @property
    def url(self) -> str:
        return f"https://quote.eastmoney.com/bk/90.{self.code}.html"


class SectorMover(BaseModel):
    code: str
    name: str
    percent: Decimal
    as_of: datetime


class SectorQuote(BaseModel):
    day: date
    as_of: Optional[datetime] = None
    percent: Optional[Decimal] = None
    rising: Optional[int] = None
    falling: Optional[int] = None
    flat: Optional[int] = None
    gainers: Optional[list[SectorMover]] = None
    losers: Optional[list[SectorMover]] = None
    ranked_members: Optional[int] = None
    total_members: Optional[int] = None


class QuoteRow(BaseModel):
    requested: str
    kind: Literal["stock", "index", "etf", "sector"] = "stock"
    outcome: Literal["quoted", "choose", "unavailable"] = "unavailable"
    candidates: list[Listing] = Field(default_factory=list)
    quote: Optional[Quote] = None
    sector_candidates: list[Sector] = Field(default_factory=list)
    sector: Optional[Sector] = None
    sector_quote: Optional[SectorQuote] = None
    phase: str = "unknown"
    verification: Verification = Field(default_factory=Verification)
    reason: str = ""


class Snapshot(BaseModel):
    version: Literal[1] = 1
    queried_at: datetime
    rows: list[QuoteRow]
    display_mode: Literal["full", "compact"] = "full"
    recall_detail: Optional[str] = None
    recall_indices: Optional[list[int]] = None
