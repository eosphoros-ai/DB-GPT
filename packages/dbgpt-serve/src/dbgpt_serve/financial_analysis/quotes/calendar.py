"""Dynamic CN (SSE/SZSE/BJ) and HK (HKEX) trading calendar with caching."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from time import monotonic
from time import time as wall_time
from typing import Any, Optional
from weakref import WeakValueDictionary

import httpx

logger = logging.getLogger(__name__)

SZSE_CALENDAR_API = (
    "https://www.szse.cn/api/report/exchange/onepersistenthour/monthList"
)
GOVHK_HOLIDAYS_ICS = "https://www.1823.gov.hk/common/ical/en.ics"

_SUCCESS_TTL = 24 * 3600.0
_FAILURE_TTL = 300.0

# Offline fallback seed for 2026 only; all years dynamically sync from SZSE / GovHK
# or an optional user-configured JSON file (DBGPT_TRADING_CALENDAR_PATH).
_SEED_CLOSURES: dict[tuple[str, int], set[str]] = {
    ("cn", 2026): set(
        "01-01 01-02 02-16 02-17 02-18 02-19 02-20 02-23 04-06 "
        "05-01 05-04 05-05 06-19 09-25 10-01 10-02 10-05 10-06 10-07".split()
    ),
    ("hk", 2026): set(
        "01-01 02-17 02-18 02-19 04-03 04-06 04-07 05-01 05-25 "
        "06-19 07-01 10-01 10-19 12-25".split()
    ),
}
_SEED_HK_HALF_DAYS: dict[int, set[date]] = {
    2026: {date(2026, 2, 16), date(2026, 12, 24), date(2026, 12, 31)},
}


def _norm_market(market: str) -> str:
    return "hk" if market == "hk" else "cn"


def _parse_date_entry(raw: str, year: int) -> Optional[date]:
    text = raw.strip()
    try:
        if len(text) == 10 and text[4] == "-":
            return date.fromisoformat(text)
        if len(text) == 5 and text[2] == "-":
            return date(year, int(text[:2]), int(text[3:]))
    except ValueError:
        return None
    return None


def parse_szse_month_calendar(payload: Any) -> dict[date, bool]:
    """Parse SZSE monthList JSON into a {date: is_trading_day} mapping."""
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("data")
    if not isinstance(rows, list):
        return {}
    result: dict[date, bool] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_day = str(row.get("jyrq") or "").strip()
        flag = str(row.get("jybz") or "").strip()
        if flag not in {"0", "1"}:
            continue
        try:
            day = date.fromisoformat(raw_day)
        except ValueError:
            continue
        result[day] = flag == "1"
    return result


def parse_govhk_ics(text: str) -> tuple[dict[int, set[date]], dict[int, set[date]]]:
    """Parse GovHK public-holiday iCal into (closures_by_year, half_days_by_year).

    Derives HKEX half-day trading sessions dynamically per year:
    Christmas Eve (Dec 24), New Year's Eve (Dec 31), and Lunar New Year's Eve
    (the calendar day immediately before Lunar New Year's Day), whenever they
    fall on a weekday and are not themselves a public holiday.
    """
    unfolded = re.sub(r"\r?\n[ \t]", "", text)
    closures: dict[int, set[date]] = {}
    lny_first_days: dict[int, date] = {}

    in_event = False
    ev_day: Optional[date] = None
    ev_summary = ""

    for line in unfolded.splitlines():
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            in_event, ev_day, ev_summary = True, None, ""
        elif stripped == "END:VEVENT" and in_event:
            if ev_day is not None:
                closures.setdefault(ev_day.year, set()).add(ev_day)
                low = ev_summary.lower()
                if "lunar new year" in low and (
                    "lunar new year's day" in low
                    or "first day" in low
                    or (
                        "second" not in low
                        and "third" not in low
                        and "fourth" not in low
                    )
                ):
                    prev = lny_first_days.get(ev_day.year)
                    if prev is None or ev_day < prev:
                        lny_first_days[ev_day.year] = ev_day
            in_event = False
        elif in_event:
            if stripped.startswith("DTSTART"):
                _, _, val = stripped.partition(":")
                m = re.match(r"(\d{4})(\d{2})(\d{2})", val.strip())
                if m:
                    try:
                        ev_day = date(int(m[1]), int(m[2]), int(m[3]))
                    except ValueError:
                        ev_day = None
            elif stripped.startswith("SUMMARY"):
                _, _, val = stripped.partition(":")
                ev_summary = val.strip()

    half_days: dict[int, set[date]] = {}
    for year, hols in closures.items():
        candidates = [date(year, 12, 24), date(year, 12, 31)]
        if year in lny_first_days:
            eve = lny_first_days[year] - timedelta(days=1)
            if eve.year == year:
                candidates.append(eve)
        year_halves = {d for d in candidates if d.weekday() < 5 and d not in hols}
        half_days[year] = year_halves
    return closures, half_days


class TradingCalendar:
    """Dynamically synced CN/HK trading calendar with config override and disk cache."""

    def __init__(
        self,
        *,
        override_path: Optional[Path | str] = None,
        cache_path: Optional[Path | str] = None,
        enable_disk_cache: bool = True,
    ) -> None:
        self._override_path = Path(override_path) if override_path is not None else None
        self._cache_path = Path(cache_path) if cache_path is not None else None
        self._enable_disk_cache = enable_disk_cache
        self._disk_loaded = False
        self._override_mtime: Optional[float] = None
        self._override_closures: dict[tuple[str, int], set[date]] = {}
        self._override_open_days: dict[tuple[str, int], set[date]] = {}
        self._override_hk_halves: dict[int, set[date]] = {}

        # Dynamic remote data
        self._cn_months: dict[tuple[int, int], tuple[float, dict[date, bool]]] = {}
        self._cn_wall_fetched_at: dict[tuple[int, int], float] = {}
        self._hk_fetched_at: Optional[float] = None
        self._hk_wall_fetched_at: Optional[float] = None
        self._hk_ok: bool = False
        self._hk_closures: dict[int, set[date]] = {}
        self._hk_half_days: dict[int, set[date]] = {}
        self._locks: WeakValueDictionary = WeakValueDictionary()

    def _resolve_override_path(self) -> Optional[Path]:
        if self._override_path is not None:
            return self._override_path
        env = os.environ.get("DBGPT_TRADING_CALENDAR_PATH", "").strip()
        return Path(env) if env else None

    def _resolve_cache_path(self) -> Optional[Path]:
        if not self._enable_disk_cache:
            return None
        if self._cache_path is not None:
            return self._cache_path
        env = os.environ.get("DBGPT_TRADING_CALENDAR_CACHE", "").strip()
        if env:
            return Path(env)
        return Path(tempfile.gettempdir()) / "dbgpt_trading_calendar_cache.json"

    def _reload_override_if_needed(self) -> None:
        path = self._resolve_override_path()
        if path is None:
            if self._override_mtime is not None:
                self._override_mtime = None
                self._override_closures.clear()
                self._override_open_days.clear()
                self._override_hk_halves.clear()
            return
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if mtime == self._override_mtime:
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            closures: dict[tuple[str, int], set[date]] = {}
            open_days: dict[tuple[str, int], set[date]] = {}
            hk_halves: dict[int, set[date]] = {}
            for mkt in ("cn", "hk"):
                section = raw.get(mkt)
                if not isinstance(section, dict):
                    continue
                for yr_str, items in (section.get("closures") or {}).items():
                    if not str(yr_str).isdigit() or not isinstance(items, list):
                        continue
                    yr = int(yr_str)
                    parsed = {
                        d
                        for s in items
                        if isinstance(s, str) and (d := _parse_date_entry(s, yr))
                    }
                    closures[(mkt, yr)] = parsed
                for yr_str, items in (section.get("open_days") or {}).items():
                    if not str(yr_str).isdigit() or not isinstance(items, list):
                        continue
                    yr = int(yr_str)
                    parsed = {
                        d
                        for s in items
                        if isinstance(s, str) and (d := _parse_date_entry(s, yr))
                    }
                    open_days[(mkt, yr)] = parsed
                if mkt == "hk":
                    for yr_str, items in (section.get("half_days") or {}).items():
                        if not str(yr_str).isdigit() or not isinstance(items, list):
                            continue
                        yr = int(yr_str)
                        parsed = {
                            d
                            for s in items
                            if isinstance(s, str) and (d := _parse_date_entry(s, yr))
                        }
                        hk_halves[yr] = parsed
            self._override_closures = closures
            self._override_open_days = open_days
            self._override_hk_halves = hk_halves
            self._override_mtime = mtime
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Failed to load trading calendar override %s: %s", path, exc)

    def _load_disk_cache_once(self) -> None:
        if self._disk_loaded:
            return
        self._disk_loaded = True
        path = self._resolve_cache_path()
        if path is None or not path.is_file():
            return
        try:
            file_mtime = path.stat().st_mtime
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            now_mono = monotonic()
            now_wall = wall_time()
            cn_fetched_map = data.get("cn_fetched_at")
            if not isinstance(cn_fetched_map, dict):
                cn_fetched_map = {}
            for ym, days_map in (data.get("cn_months") or {}).items():
                if not isinstance(ym, str) or not isinstance(days_map, dict):
                    continue
                parts = ym.split("-")
                if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
                    continue
                parsed_month: dict[date, bool] = {}
                for d_str, is_open in days_map.items():
                    try:
                        parsed_month[date.fromisoformat(d_str)] = bool(is_open)
                    except ValueError:
                        continue
                if parsed_month:
                    raw_ts = cn_fetched_map.get(ym)
                    fetched_wall = (
                        float(raw_ts)
                        if isinstance(raw_ts, (int, float)) and raw_ts > 0
                        else file_mtime
                    )
                    age = max(0.0, now_wall - fetched_wall)
                    key = (int(parts[0]), int(parts[1]))
                    self._cn_months[key] = (now_mono - age, parsed_month)
                    self._cn_wall_fetched_at[key] = fetched_wall
            hk_loaded = False
            for yr_str, yr_data in (data.get("hk_years") or {}).items():
                if not str(yr_str).isdigit() or not isinstance(yr_data, dict):
                    continue
                yr = int(yr_str)
                hols = set()
                for d_str in yr_data.get("closures") or []:
                    if isinstance(d_str, str) and (d := _parse_date_entry(d_str, yr)):
                        hols.add(d)
                halves = set()
                for d_str in yr_data.get("half_days") or []:
                    if isinstance(d_str, str) and (d := _parse_date_entry(d_str, yr)):
                        halves.add(d)
                if hols:
                    self._hk_closures[yr] = hols
                    self._hk_half_days[yr] = halves
                    hk_loaded = True
            if hk_loaded:
                hk_raw_ts = data.get("hk_fetched_at")
                hk_wall = (
                    float(hk_raw_ts)
                    if isinstance(hk_raw_ts, (int, float)) and hk_raw_ts > 0
                    else file_mtime
                )
                self._hk_fetched_at = now_mono - max(0.0, now_wall - hk_wall)
                self._hk_wall_fetched_at = hk_wall
                self._hk_ok = True
        except (OSError, ValueError, TypeError) as exc:
            logger.debug("Ignoring unreadable trading calendar cache %s: %s", path, exc)

    def _save_disk_cache(self) -> None:
        path = self._resolve_cache_path()
        if path is None:
            return
        try:
            payload: dict[str, Any] = {
                "cn_months": {
                    f"{y:04d}-{m:02d}": {
                        d.isoformat(): is_open for d, is_open in sorted(days.items())
                    }
                    for (y, m), (_, days) in self._cn_months.items()
                    if days
                },
                "cn_fetched_at": {
                    f"{y:04d}-{m:02d}": ts
                    for (y, m), ts in self._cn_wall_fetched_at.items()
                    if (y, m) in self._cn_months and self._cn_months[(y, m)][1]
                },
                "hk_years": {
                    str(yr): {
                        "closures": sorted(d.isoformat() for d in hols),
                        "half_days": sorted(
                            d.isoformat() for d in self._hk_half_days.get(yr, set())
                        ),
                    }
                    for yr, hols in self._hk_closures.items()
                },
            }
            if self._hk_wall_fetched_at is not None and self._hk_closures:
                payload["hk_fetched_at"] = self._hk_wall_fetched_at
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            logger.debug("Skipping trading calendar cache write (%s): %s", path, exc)

    def _get_lock(self, key: tuple) -> asyncio.Lock:
        loop_key = (asyncio.get_running_loop(), key)
        lock = self._locks.get(loop_key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[loop_key] = lock
        return lock

    async def _ensure_cn_month(
        self, client: httpx.AsyncClient, year: int, month: int
    ) -> None:
        key = (year, month)
        entry = self._cn_months.get(key)
        now = monotonic()
        if entry is not None:
            ttl = _SUCCESS_TTL if entry[1] else _FAILURE_TTL
            if now - entry[0] < ttl:
                return
        async with self._get_lock(("cn", year, month)):
            entry = self._cn_months.get(key)
            now = monotonic()
            if entry is not None:
                ttl = _SUCCESS_TTL if entry[1] else _FAILURE_TTL
                if now - entry[0] < ttl:
                    return
            try:
                resp = await client.get(
                    SZSE_CALENDAR_API,
                    params={"month": f"{year:04d}-{month:02d}"},
                    timeout=3.0,
                )
                resp.raise_for_status()
                parsed = parse_szse_month_calendar(resp.json())
                if parsed:
                    self._cn_months[key] = (monotonic(), parsed)
                    self._cn_wall_fetched_at[key] = wall_time()
                    self._save_disk_cache()
                elif key in self._cn_months and self._cn_months[key][1]:
                    self._cn_months[key] = (
                        monotonic() - _SUCCESS_TTL + _FAILURE_TTL,
                        self._cn_months[key][1],
                    )
                else:
                    self._cn_months[key] = (monotonic(), {})
            except (
                httpx.HTTPError,
                ValueError,
                TypeError,
                KeyError,
                IndexError,
                AttributeError,
            ) as exc:
                logger.debug(
                    "CN calendar fetch failed for %04d-%02d: %s", year, month, exc
                )
                if key in self._cn_months and self._cn_months[key][1]:
                    self._cn_months[key] = (
                        monotonic() - _SUCCESS_TTL + _FAILURE_TTL,
                        self._cn_months[key][1],
                    )
                else:
                    self._cn_months[key] = (monotonic(), {})

    async def _ensure_hk(self, client: httpx.AsyncClient, year: int) -> None:
        now = monotonic()
        if self._hk_fetched_at is not None:
            ttl = (
                _SUCCESS_TTL
                if (self._hk_ok and year in self._hk_closures)
                else _FAILURE_TTL
            )
            if now - self._hk_fetched_at < ttl:
                return
        async with self._get_lock(("hk",)):
            now = monotonic()
            if self._hk_fetched_at is not None:
                ttl = (
                    _SUCCESS_TTL
                    if (self._hk_ok and year in self._hk_closures)
                    else _FAILURE_TTL
                )
                if now - self._hk_fetched_at < ttl:
                    return
            try:
                resp = await client.get(GOVHK_HOLIDAYS_ICS, timeout=3.0)
                resp.raise_for_status()
                closures, half_days = parse_govhk_ics(resp.text)
                if closures:
                    self._hk_closures.update(closures)
                    self._hk_half_days.update(half_days)
                    self._hk_ok = True
                    self._hk_fetched_at = monotonic()
                    self._hk_wall_fetched_at = wall_time()
                    self._save_disk_cache()
                else:
                    self._hk_fetched_at = (
                        monotonic() - _SUCCESS_TTL + _FAILURE_TTL
                        if self._hk_ok
                        else monotonic()
                    )
            except (
                httpx.HTTPError,
                ValueError,
                TypeError,
                KeyError,
                IndexError,
                AttributeError,
            ) as exc:
                logger.debug("HK calendar fetch failed: %s", exc)
                self._hk_fetched_at = (
                    monotonic() - _SUCCESS_TTL + _FAILURE_TTL
                    if self._hk_ok
                    else monotonic()
                )

    async def ensure(self, client: httpx.AsyncClient, market: str, day: date) -> None:
        """Best-effort dynamic refresh of the trading calendar for market/day."""
        self._load_disk_cache_once()
        self._reload_override_if_needed()
        mkt = _norm_market(market)
        if mkt == "hk":
            await self._ensure_hk(client, day.year)
            return
        months = [(day.year, day.month)]
        if day.day <= 10:
            prev_month_end = day.replace(day=1) - timedelta(days=1)
            months.append((prev_month_end.year, prev_month_end.month))
        await asyncio.gather(*(self._ensure_cn_month(client, y, m) for y, m in months))

    def is_trading_day(self, market: str, day: date) -> bool:
        self._load_disk_cache_once()
        self._reload_override_if_needed()
        if day.weekday() >= 5:
            return False
        mkt = _norm_market(market)
        override_open = self._override_open_days.get((mkt, day.year))
        if override_open and day in override_open:
            return True
        override_closed = self._override_closures.get((mkt, day.year))
        if override_closed is not None:
            return day not in override_closed

        if mkt == "cn":
            month_entry = self._cn_months.get((day.year, day.month))
            if month_entry and day in month_entry[1]:
                return month_entry[1][day]
        else:
            hk_closed = self._hk_closures.get(day.year)
            if hk_closed is not None:
                return day not in hk_closed

        seed = _SEED_CLOSURES.get((mkt, day.year))
        return True if seed is None else day.strftime("%m-%d") not in seed

    def is_hk_half_day(self, day: date) -> bool:
        if not self.is_trading_day("hk", day):
            return False
        override_halves = self._override_hk_halves.get(day.year)
        if override_halves is not None:
            return day in override_halves
        dynamic_halves = self._hk_half_days.get(day.year)
        if dynamic_halves is not None:
            return day in dynamic_halves
        seed_halves = _SEED_HK_HALF_DAYS.get(day.year)
        if seed_halves is not None:
            return day in seed_halves
        return (day.month, day.day) in {(12, 24), (12, 31)}

    def expected_day(self, market: str, day: date) -> date:
        for _ in range(30):
            if self.is_trading_day(market, day):
                return day
            day -= timedelta(days=1)
        return day

    def latest_expected_day(self, market: str, now: datetime) -> date:
        """Latest trading day expected to have quotes at Beijing timestamp ``now``."""
        day = now.date()
        if self.is_trading_day(market, day):
            open_cutoff = time(9, 0) if market == "hk" else time(9, 30)
            if now.time() < open_cutoff:
                return self.expected_day(market, day - timedelta(days=1))
            return day
        return self.expected_day(market, day)

    def session(self, market: str, now: datetime) -> str:
        """Return the exchange session phase at a Beijing timestamp."""
        if not self.is_trading_day(market, now.date()):
            return "holiday"
        t = now.time()
        if market == "hk":
            half = self.is_hk_half_day(now.date())
            end = time(12) if half else time(16)
            bounds = (
                (time(9), "preopen"),
                (time(9, 30), "opening_auction"),
                (time(12), "trading"),
                (time(13) if not half else end, "lunch"),
                (end, "trading"),
                (time(end.hour, 8), "closing_auction"),
                (time(end.hour, 10), "random_close"),
            )
        else:
            bounds = (
                (time(9, 15), "preopen"),
                (time(9, 25), "opening_auction"),
                (time(9, 30), "preopen"),
                (time(11, 30), "trading"),
                (time(13), "lunch"),
                (time(14, 57), "trading"),
                (time(15), "closing_auction"),
                (time(15, 5), "auction_ended"),
                (time(15, 30), "after_hours"),
            )
        for cutoff, phase in bounds:
            if t < cutoff:
                return phase
        return "closed"


TRADING_CALENDAR = TradingCalendar()
