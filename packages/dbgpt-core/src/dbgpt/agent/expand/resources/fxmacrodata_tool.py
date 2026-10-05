"""FXMacroData tools for the agent.

Official macroeconomic releases, release calendars and indicator catalogues for 22
currencies from the FXMacroData REST API (https://fxmacrodata.com/documentation).

The API key is read from the `FXMACRODATA_API_KEY` environment variable at call
time and is optional: without a key, USD releases (most recent 90 days, 15 minute
delay), the USD release calendar and the indicator catalogue of every currency are
available. Other currencies need a key, see https://fxmacrodata.com/subscribe.
"""

import os
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from typing_extensions import Annotated, Doc

from ...resource.tool.base import tool

FXMACRODATA_BASE_URL = "https://api.fxmacrodata.com/v1"
FXMACRODATA_API_KEY_ENV = "FXMACRODATA_API_KEY"
SUPPORTED_CURRENCIES = (
    "AUD BRL CAD CHF CNH CNY DKK EUR GBP HUF ILS JPY "
    "KRW MYR NGN NOK NZD PEN SEK THB TWD USD"
).split()
MAX_LIMIT = 100
REQUEST_TIMEOUT_SECONDS = 10
MAX_ERROR_DETAIL_LENGTH = 300
# Top level catalogue keys that are notices, not indicators.
_CATALOGUE_NOTICE_KEYS = {"freemium_window", "freemium_delay", "pagination"}

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INDICATOR_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]*$")
# Printable ASCII without spaces: anything else is not a valid header value.
_API_KEY_PATTERN = re.compile(r"^[\x21-\x7e]+$")


class FXMacroDataError(ValueError):
    """Raised when an FXMacroData request or response is not usable."""


def _read_api_key() -> Optional[str]:
    """Read the optional API key from the environment, validated and stripped."""
    api_key = os.getenv(FXMACRODATA_API_KEY_ENV, "").strip()
    if not api_key:
        return None
    if not _API_KEY_PATTERN.match(api_key):
        # Never echo the value, it is a secret.
        raise FXMacroDataError(
            f"`{FXMACRODATA_API_KEY_ENV}` contains whitespace or non printable "
            "characters, please check the value."
        )
    return api_key


def _scrub(text: str, api_key: Optional[str]) -> str:
    """Remove the API key from any text that leaves this module."""
    if api_key:
        return text.replace(api_key, "***")
    return text


def _validate_currency(currency: str) -> str:
    code = str(currency or "").strip().upper()
    if code not in SUPPORTED_CURRENCIES:
        raise FXMacroDataError(
            "currency must be one of the 3-letter codes "
            f"{', '.join(SUPPORTED_CURRENCIES)}."
        )
    return code.lower()


def _validate_indicator(indicator: str) -> str:
    slug = str(indicator or "").strip().lower()
    if not _INDICATOR_PATTERN.match(slug):
        raise FXMacroDataError(
            "indicator must be a slug such as `inflation` or `policy_rate`, "
            "use fxmacrodata_data_catalogue to list the slugs for a currency."
        )
    return slug


def _validate_date(value: str, name: str) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    if not _DATE_PATTERN.match(text):
        raise FXMacroDataError(f"{name} must be a date in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise FXMacroDataError(f"{name} must be a real calendar date (YYYY-MM-DD).")


def _date_params(start_date: str, end_date: str) -> Dict[str, str]:
    start = _validate_date(start_date, "start_date")
    end = _validate_date(end_date, "end_date")
    if start and end and start > end:
        raise FXMacroDataError("start_date must not be after end_date.")
    params = {}
    if start:
        params["start_date"] = start.isoformat()
    if end:
        params["end_date"] = end.isoformat()
    return params


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise FXMacroDataError("limit must be an integer.")
    if limit < 1 or limit > MAX_LIMIT:
        raise FXMacroDataError(f"limit must be between 1 and {MAX_LIMIT}.")
    return limit


def _error_detail(response: Any) -> str:
    """Return the error message of an API response body, if there is one."""
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    detail = body.get("detail") or body.get("message") or body.get("error") or ""
    return str(detail)[:MAX_ERROR_DETAIL_LENGTH]


def _raise_for_status(response: Any, api_key: Optional[str]) -> None:
    status = response.status_code
    if 300 <= status < 400:
        # Redirects are not followed so the key is never sent to another URL.
        raise FXMacroDataError(f"FXMacroData answered with a redirect (HTTP {status}).")
    if status >= 400:
        message = f"FXMacroData request failed (HTTP {status})."
        detail = _error_detail(response)
        if detail:
            message += f" {detail}"
        if status in (401, 403) and not api_key:
            message += f" Set `{FXMACRODATA_API_KEY_ENV}` to use an API key."
        raise FXMacroDataError(_scrub(message, api_key))


def _parse_body(response: Any, api_key: Optional[str]) -> Dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        raise FXMacroDataError("FXMacroData returned a response that is not JSON.")
    if not isinstance(body, dict):
        raise FXMacroDataError("FXMacroData returned an unexpected response shape.")
    if "error" in body:
        detail = str(body.get("detail") or body["error"])[:MAX_ERROR_DETAIL_LENGTH]
        message = f"FXMacroData returned an error: {detail}"
        raise FXMacroDataError(_scrub(message, api_key))
    return body


def _get_json(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """GET a path of the FXMacroData API and return the JSON object body."""
    try:
        import requests
    except ImportError:
        raise ImportError(
            "`requests` is required for FXMacroData tools, please run "
            "`pip install requests` to install it."
        )

    api_key = _read_api_key()
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    try:
        response = requests.get(
            f"{FXMACRODATA_BASE_URL}{path}",
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    except requests.RequestException as error:
        # The exception text can carry request details, keep only its type.
        raise FXMacroDataError(
            f"FXMacroData request failed ({type(error).__name__})."
        ) from None
    _raise_for_status(response, api_key)
    return _parse_body(response, api_key)


def _rows(body: Dict[str, Any], key: str = "data") -> List[Dict[str, Any]]:
    rows = body.get(key)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise FXMacroDataError(f"FXMacroData response has no valid `{key}` list.")
    return rows


def _next_offset(body: Dict[str, Any], offset: int) -> Optional[int]:
    """Return the offset of the next page, or None when there is no next page."""
    pagination = body.get("pagination")
    if pagination is None:
        return None
    if not isinstance(pagination, dict):
        raise FXMacroDataError("FXMacroData returned an invalid `pagination` object.")
    has_more = pagination.get("has_more", False)
    if not isinstance(has_more, bool):
        raise FXMacroDataError("FXMacroData returned an invalid `has_more` value.")
    if not has_more:
        return None
    next_offset = pagination.get("next_offset")
    if (
        isinstance(next_offset, bool)
        or not isinstance(next_offset, int)
        or next_offset <= offset
    ):
        raise FXMacroDataError("FXMacroData returned an invalid `next_offset` value.")
    return next_offset


def _get_rows(
    path: str, params: Dict[str, Any], limit: int
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch up to `limit` rows, following pagination, and the first page body."""
    rows: List[Dict[str, Any]] = []
    first_body: Optional[Dict[str, Any]] = None
    offset: Optional[int] = 0
    while offset is not None and len(rows) < limit:
        page_params = dict(params, limit=limit - len(rows), offset=offset)
        body = _get_json(path, page_params)
        first_body = first_body or body
        page_rows = _rows(body)
        if not page_rows:
            break
        rows.extend(page_rows)
        offset = _next_offset(body, offset)
    return rows[:limit], first_body or {}


def _format_time(timestamp: Any) -> str:
    """Format an epoch seconds timestamp as UTC."""
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        return ""
    moment = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: List[str], rows: List[List[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "---|" * len(headers),
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return "\n".join(lines)


def _free_tier_notes(body: Dict[str, Any]) -> List[str]:
    """Return the free tier window and delay messages of a keyless response."""
    notes = []
    for key in ("freemium_window", "freemium_delay"):
        notice = body.get(key)
        if isinstance(notice, dict) and notice.get("applied") is not False:
            message = notice.get("message")
            if isinstance(message, str) and message:
                notes.append(f"> Note: {message}")
    delay = body.get("freemium_delay")
    if isinstance(delay, dict):
        withheld = delay.get("withheld_count")
        if isinstance(withheld, int) and not isinstance(withheld, bool) and withheld:
            notes.append(
                f"> Note: {withheld} release(s) published in the last 15 minutes "
                "are withheld on the free tier."
            )
    return notes


def _render(title: str, table: str, body: Dict[str, Any]) -> str:
    api_key = _read_api_key()
    parts = [f"### {title}", table] + _free_tier_notes(body)
    return _scrub("\n\n".join(parts), api_key)


@tool(
    description="Get the latest official macroeconomic release of every indicator "
    "for a currency (CPI, GDP, policy rate, unemployment, bond yields and more) "
    "from FXMacroData, as a markdown table. USD works without an API key.",
)
def fxmacrodata_latest_releases(
    currency: Annotated[str, Doc("3-letter currency code, e.g. USD, EUR, JPY.")],
) -> str:
    """Get the latest release of every indicator for a currency.

    Without `FXMACRODATA_API_KEY` only USD is available, on a 15 minute delay.
    """
    code = _validate_currency(currency)
    body = _get_json(f"/announcements/{code}/latest")
    table_rows = []
    for row in _rows(body):
        latest = row.get("latest") if isinstance(row.get("latest"), dict) else {}
        table_rows.append(
            [
                row.get("indicator"),
                row.get("name"),
                latest.get("date"),
                latest.get("val"),
                row.get("unit"),
                _format_time(latest.get("announcement_datetime")),
            ]
        )
    headers = ["Indicator", "Name", "Period", "Value", "Unit", "Released"]
    title = f"{code.upper()} latest releases"
    return _render(title, _table(headers, table_rows), body)


@tool(
    description="Get the release history of one macroeconomic indicator for a "
    "currency from FXMacroData, as a markdown table of period, value and release "
    "time. Use fxmacrodata_data_catalogue to find indicator slugs.",
)
def fxmacrodata_indicator_history(
    currency: Annotated[str, Doc("3-letter currency code, e.g. USD, EUR, JPY.")],
    indicator: Annotated[str, Doc("Indicator slug, e.g. inflation, policy_rate.")],
    start_date: Annotated[str, Doc("Optional start date, YYYY-MM-DD.")] = "",
    end_date: Annotated[str, Doc("Optional end date, YYYY-MM-DD.")] = "",
    limit: Annotated[int, Doc("Maximum number of releases, 1 to 100.")] = 20,
) -> str:
    """Get the release history of one indicator for a currency.

    Without `FXMACRODATA_API_KEY` only USD is available, for the last 90 days.
    """
    code = _validate_currency(currency)
    slug = _validate_indicator(indicator)
    params = _date_params(start_date, end_date)
    rows, body = _get_rows(
        f"/announcements/{code}/{slug}", params, _validate_limit(limit)
    )
    table_rows = [
        [
            row.get("date"),
            row.get("val"),
            row.get("previous_value"),
            _format_time(row.get("announcement_datetime")),
        ]
        for row in rows
    ]
    headers = ["Period", "Value", "Previous", "Released"]
    name = body.get("name") or slug
    title = f"{code.upper()} {name} ({slug})"
    return _render(title, _table(headers, table_rows), body)


@tool(
    description="Get the upcoming official release calendar for a currency from "
    "FXMacroData, as a markdown table of release time (UTC), indicator and "
    "importance. USD works without an API key.",
)
def fxmacrodata_release_calendar(
    currency: Annotated[str, Doc("3-letter currency code, e.g. USD, EUR, JPY.")],
    start_date: Annotated[str, Doc("Optional start date, YYYY-MM-DD.")] = "",
    end_date: Annotated[str, Doc("Optional end date, YYYY-MM-DD.")] = "",
    limit: Annotated[int, Doc("Maximum number of events, 1 to 100.")] = 20,
) -> str:
    """Get the release calendar for a currency.

    The release time is `announcement_datetime`. A calendar row's `date`, when
    present, is the reference period the release covers, not the release day.
    """
    code = _validate_currency(currency)
    params = _date_params(start_date, end_date)
    rows, body = _get_rows(f"/calendar/{code}", params, _validate_limit(limit))
    table_rows = [
        [
            _format_time(row.get("announcement_datetime")),
            row.get("release"),
            row.get("name"),
            row.get("date"),
            row.get("event_importance"),
        ]
        for row in rows
    ]
    headers = ["Release time", "Indicator", "Name", "Reference period", "Importance"]
    title = f"{code.upper()} release calendar"
    return _render(title, _table(headers, table_rows), body)


@tool(
    description="List the macroeconomic indicators FXMacroData publishes for a "
    "currency, with their slugs, units and frequency, as a markdown table. Works "
    "without an API key for every currency.",
)
def fxmacrodata_data_catalogue(
    currency: Annotated[str, Doc("3-letter currency code, e.g. USD, EUR, JPY.")],
) -> str:
    """List the indicator slugs, names, units and frequency for a currency."""
    code = _validate_currency(currency)
    body = _get_json(f"/data_catalogue/{code}")
    table_rows = [
        [slug, entry.get("name"), entry.get("unit"), entry.get("frequency")]
        for slug, entry in body.items()
        if isinstance(entry, dict) and slug not in _CATALOGUE_NOTICE_KEYS
    ]
    if not table_rows:
        raise FXMacroDataError("FXMacroData returned an empty data catalogue.")
    headers = ["Indicator", "Name", "Unit", "Frequency"]
    title = f"{code.upper()} data catalogue"
    return _render(title, _table(headers, table_rows), body)
