#!/usr/bin/env python3
"""Currency calculator that fetches live exchange rates on every run."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

API_URL = "https://open.er-api.com/v6/latest/{base}"
TIMEOUT_SECONDS = 10

# Common currencies shown in the help list (API supports 160+)
POPULAR_CURRENCIES = [
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CNY",
    "AUD",
    "CAD",
    "CHF",
    "HKD",
    "SGD",
    "INR",
    "PHP",
    "KRW",
    "THB",
    "NZD",
]


class RateFetchError(Exception):
    """Raised when live rates cannot be retrieved."""


def fetch_rates(base: str) -> dict[str, Any]:
    """Fetch the latest rates for a base currency. Refreshed on every run."""
    url = API_URL.format(base=base.upper())
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")
        data = json.loads(payload)
    except urllib.error.HTTPError as exc:
        raise RateFetchError(f"API HTTP error: {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RateFetchError(f"Could not reach the exchange-rate API: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RateFetchError("Request timed out while fetching rates.") from exc
    except json.JSONDecodeError as exc:
        raise RateFetchError("API returned invalid JSON.") from exc

    if data.get("result") != "success":
        raise RateFetchError(data.get("error-type", "Unknown API error."))

    rates = data.get("rates")
    if not isinstance(rates, dict) or not rates:
        raise RateFetchError("API response did not include rates.")

    return {
        "base": data.get("base_code", base.upper()),
        "rates": {code.upper(): float(rate) for code, rate in rates.items()},
        "updated": data.get("time_last_update_utc", "unknown"),
        "provider": data.get("provider", "https://www.exchangerate-api.com"),
    }


def convert(amount: float, from_code: str, to_code: str, rates: dict[str, float]) -> float:
    """Convert amount using rates quoted against the fetched base currency."""
    from_code = from_code.upper()
    to_code = to_code.upper()

    if from_code not in rates:
        raise KeyError(from_code)
    if to_code not in rates:
        raise KeyError(to_code)

    # rates are all relative to the same base, so convert via base units
    amount_in_base = amount / rates[from_code]
    return amount_in_base * rates[to_code]


def prompt_float(label: str) -> float:
    while True:
        raw = input(label).strip().replace(",", "")
        try:
            amount = float(raw)
        except ValueError:
            print("Please enter a valid number.")
            continue
        if amount < 0:
            print("Amount cannot be negative.")
            continue
        return amount


def prompt_currency(label: str, rates: dict[str, float]) -> str:
    while True:
        code = input(label).strip().upper()
        if code in rates:
            return code
        print(f"Unsupported currency '{code}'. Try again, or type 'list' to see popular codes.")
        if code == "LIST":
            print_currency_help(rates)


def print_currency_help(rates: dict[str, float]) -> None:
    available_popular = [c for c in POPULAR_CURRENCIES if c in rates]
    print("\nPopular currencies:")
    print("  " + ", ".join(available_popular))
    print(f"  ({len(rates)} currencies available in total)\n")


def run_interactive() -> int:
    print("=" * 48)
    print("  Currency Calculator")
    print("  Live rates fetched on every run")
    print("=" * 48)

    try:
        # Fetch against USD so all codes are available for any pair
        print("\nFetching latest exchange rates...")
        data = fetch_rates("USD")
    except RateFetchError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1

    rates = data["rates"]
    print(f"Rates updated: {data['updated']}")
    print(f"Source: {data['provider']}")
    print_currency_help(rates)

    while True:
        amount = prompt_float("Amount: ")
        from_code = prompt_currency("From currency (e.g. USD): ", rates)
        to_code = prompt_currency("To currency (e.g. EUR): ", rates)

        try:
            result = convert(amount, from_code, to_code, rates)
            rate = convert(1.0, from_code, to_code, rates)
        except KeyError as missing:
            print(f"Unsupported currency: {missing}")
            continue

        print()
        print(f"  {amount:,.4f} {from_code} = {result:,.4f} {to_code}")
        print(f"  Rate: 1 {from_code} = {rate:,.6f} {to_code}")
        print()

        again = input("Convert another amount? [Y/n]: ").strip().lower()
        if again in {"n", "no", "q", "quit", "exit"}:
            break

    print("Goodbye.")
    return 0


def run_once(amount: float, from_code: str, to_code: str) -> int:
    try:
        data = fetch_rates("USD")
    except RateFetchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    rates = data["rates"]
    from_code = from_code.upper()
    to_code = to_code.upper()

    try:
        result = convert(amount, from_code, to_code, rates)
        rate = convert(1.0, from_code, to_code, rates)
    except KeyError as missing:
        print(f"Error: unsupported currency '{missing}'", file=sys.stderr)
        return 1

    print(f"{amount:,.4f} {from_code} = {result:,.4f} {to_code}")
    print(f"Rate: 1 {from_code} = {rate:,.6f} {to_code}")
    print(f"Updated: {data['updated']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        return run_interactive()

    if len(argv) == 1 and argv[0] in {"-h", "--help", "help"}:
        print("Usage:")
        print("  python currency_calculator.py")
        print("  python currency_calculator.py <amount> <from> <to>")
        print()
        print("Examples:")
        print("  python currency_calculator.py")
        print("  python currency_calculator.py 100 USD EUR")
        return 0

    if len(argv) != 3:
        print("Usage: python currency_calculator.py [amount from to]", file=sys.stderr)
        return 1

    try:
        amount = float(argv[0].replace(",", ""))
    except ValueError:
        print("Error: amount must be a number.", file=sys.stderr)
        return 1

    if amount < 0:
        print("Error: amount cannot be negative.", file=sys.stderr)
        return 1

    return run_once(amount, argv[1], argv[2])


if __name__ == "__main__":
    raise SystemExit(main())
