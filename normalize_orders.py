#!/usr/bin/env python3
"""Normalize a small, known order-export schema. Author: x0Lazarus.

Copyright (c) 2026 x0Lazarus. AI-assisted; see README.md.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


COLUMNS = ("order_id", "customer_ref", "order_date", "amount", "currency")
SUPPORTED_CURRENCIES = frozenset({"USD", "EUR", "GBP", "CAD", "AUD"})
AMOUNT_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,2})?\Z")
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class InputError(ValueError):
    """The source does not satisfy the agreed import contract."""


def parse_date(value: str) -> str:
    """Accept ISO dates or explicitly US month/day/year dates."""
    for pattern, date_format in (
        (r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z", "%Y-%m-%d"),
        (r"[0-9]{2}/[0-9]{2}/[0-9]{4}\Z", "%m/%d/%Y"),
    ):
        if re.fullmatch(pattern, value):
            try:
                return datetime.strptime(value, date_format).date().isoformat()
            except ValueError:
                break
    raise InputError("order_date must be a real date in YYYY-MM-DD or US MM/DD/YYYY format")


def parse_amount(value: str) -> int:
    """Return cents using integer arithmetic, never binary floating point."""
    if not AMOUNT_PATTERN.fullmatch(value):
        raise InputError(
            "amount must be a plain positive number with at most two decimal places "
            "and at most nine whole-number digits (no symbols, separators or exponent)"
        )
    whole, _, fraction = value.partition(".")
    minor = int(whole) * 100 + int(fraction.ljust(2, "0"))
    if minor == 0:
        raise InputError("amount must be greater than zero; refunds and zero-value orders are unsupported")
    return minor


def normalize_row(values: dict[str, str]) -> dict[str, str | int]:
    if not ID_PATTERN.fullmatch(values["order_id"]):
        raise InputError("order_id must contain 1-64 ASCII letters, digits, dots, underscores or hyphens, starting with a letter or digit")
    customer = values["customer_ref"]
    if not customer or len(customer) > 200 or not customer.isprintable():
        raise InputError("customer_ref must contain 1-200 printable characters")
    currency = values["currency"].upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise InputError("currency must be one of AUD, CAD, EUR, GBP, USD")
    return {
        "order_id": values["order_id"],
        "customer_ref": customer,
        "order_date": parse_date(values["order_date"]),
        "amount_minor": parse_amount(values["amount"]),
        "currency": currency,
    }


def read_orders(source: Path) -> dict[str, Any]:
    """Read and validate the entire CSV before anything is written."""
    orders: list[dict[str, str | int]] = []
    totals: dict[str, int] = {}
    seen_ids: dict[str, int] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        try:
            header = next(reader, None)
            if header is None:
                raise InputError("input is empty; a header and at least one order are required")
            header = [column.strip() for column in header]
            if len(header) != len(set(header)):
                raise InputError("header contains duplicate column names")
            if set(header) != set(COLUMNS):
                missing = sorted(set(COLUMNS) - set(header))
                extra = sorted(set(header) - set(COLUMNS))
                raise InputError(f"header mismatch: missing={missing}; unexpected={extra}")
            for row in reader:
                line_number = reader.line_num
                if not row:  # Ignore physically empty lines, not incomplete records.
                    continue
                if len(row) != len(header):
                    raise InputError(f"line {line_number}: expected {len(header)} fields, got {len(row)}")
                values = dict(zip(header, (value.strip() for value in row)))
                try:
                    order = normalize_row(values)
                except InputError as error:
                    raise InputError(f"line {line_number}: {error}") from error
                order_id = str(order["order_id"])
                if order_id in seen_ids:
                    raise InputError(f"line {line_number}: duplicate order_id {order_id!r}; first seen on line {seen_ids[order_id]}")
                seen_ids[order_id] = line_number
                orders.append(order)
                currency = str(order["currency"])
                totals[currency] = totals.get(currency, 0) + int(order["amount_minor"])
        except csv.Error as error:
            raise InputError(f"CSV syntax error near line {reader.line_num}: {error}") from error
    if not orders:
        raise InputError("input contains no orders")
    return {
        "schema_version": 1,
        "order_count": len(orders),
        "totals_minor_by_currency": dict(sorted(totals.items())),
        "orders": orders,
    }


def write_atomic(destination: Path, payload: dict[str, Any]) -> None:
    """Replace output only after a complete temporary file has been flushed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=destination.parent,
            prefix=f".{destination.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def normalize(source: Path, destination: Path) -> dict[str, Any]:
    if source.resolve() == destination.resolve() or (
        source.exists() and destination.exists() and os.path.samefile(source, destination)
    ):
        raise InputError("input and output must be different files")
    payload = read_orders(source)
    write_atomic(destination, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="UTF-8 CSV export with the documented order schema")
    parser.add_argument("--output", type=Path, required=True, help="JSON destination; replaced only after successful validation")
    args = parser.parse_args(argv)
    try:
        result = normalize(args.input, args.output)
    except (InputError, OSError, UnicodeError) as error:
        print(f"Import failed: {error}", file=sys.stderr)
        return 1
    print(f"Normalized {result['order_count']} orders to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
