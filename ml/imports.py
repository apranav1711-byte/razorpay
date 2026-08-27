"""Strict CSV validation for pseudonymous ChargebackShield merchant imports."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Any


MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 5_000
REQUIRED_HEADERS = {"transaction_id", "amount_cents"}
BOOLEAN_HEADERS = {"geo_mismatch", "customer_is_first_time", "odd_hour", "new_device", "velocity_spike", "high_amount", "dispute_flag"}
INTEGER_HEADERS = {"amount_cents", "velocity_1h", "velocity_24h", "velocity_7d", "communication_count"}
FLOAT_HEADERS = {"amount_zscore", "payment_method_risk", "merchant_category_risk"}
ALLOWED_HEADERS = REQUIRED_HEADERS | BOOLEAN_HEADERS | INTEGER_HEADERS | FLOAT_HEADERS | {"customer_id", "merchant_id", "payment_method", "currency", "occurred_at", "dispute_reason", "delivery_status"}
SENSITIVE_MARKERS = ("card_number", "card number", "pan", "cvv", "cvc", "expiry", "expiration", "upi_pin", "upi pin", "email", "phone", "mobile", "address", "postal", "pin_code")


@dataclass(frozen=True)
class CsvIssue:
    code: str
    message: str
    row: int | None = None
    field: str | None = None


class CsvValidationError(ValueError):
    def __init__(self, messages: list[str], *, code: str = "invalid_csv"):
        super().__init__("; ".join(messages))
        self.messages = messages
        self.issues = [self._issue(message, code) for message in messages]

    @staticmethod
    def _issue(message: str, fallback_code: str) -> CsvIssue:
        match = re.match(r"^Row (\d+): ([^ ]+) (.*)$", message.rstrip("."))
        if match:
            return CsvIssue(code="invalid_field", message=message, row=int(match.group(1)), field=match.group(2))
        if "Sensitive field" in message or "Sensitive column" in message:
            return CsvIssue(code="sensitive_field", message=message)
        if "Missing required" in message:
            return CsvIssue(code="missing_required_header", message=message)
        if "Unsupported header" in message:
            return CsvIssue(code="unsupported_header", message=message)
        if "limit" in message or "exceeds" in message:
            return CsvIssue(code="size_or_row_limit", message=message)
        return CsvIssue(code=fallback_code, message=message)


def normalize_header(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def safe_error(row: int, field: str, message: str) -> str:
    return f"Row {row}: {field} {message}."


def parse_bool(value: str, row: int, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no", ""}:
        return False
    raise CsvValidationError([safe_error(row, field, "must be true or false")])


def parse_int(value: str, row: int, field: str, *, minimum: int = 0) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as error:
        raise CsvValidationError([safe_error(row, field, "must be an integer")]) from error
    if parsed < minimum:
        raise CsvValidationError([safe_error(row, field, f"must be at least {minimum}")])
    return parsed


def parse_float(value: str, row: int, field: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        parsed = float(value.strip())
    except ValueError as error:
        raise CsvValidationError([safe_error(row, field, "must be numeric")]) from error
    if minimum is not None and parsed < minimum:
        raise CsvValidationError([safe_error(row, field, f"must be at least {minimum}")])
    if maximum is not None and parsed > maximum:
        raise CsvValidationError([safe_error(row, field, f"must be at most {maximum}")])
    return parsed


def validate_csv_bytes(content: bytes) -> list[dict[str, Any]]:
    if not content:
        raise CsvValidationError(["The CSV file is empty."])
    if len(content) > MAX_CSV_BYTES:
        raise CsvValidationError([f"The CSV exceeds the {MAX_CSV_BYTES // (1024 * 1024)} MB limit."])
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvValidationError(["The file must be UTF-8 encoded CSV."]) from error
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise CsvValidationError(["The CSV must include a header row."])
    headers = [normalize_header(header) for header in reader.fieldnames]
    if len(headers) != len(set(headers)):
        raise CsvValidationError(["CSV headers must be unique after normalization."])
    sensitive = [header for header in headers if any(marker in header for marker in SENSITIVE_MARKERS)]
    if sensitive:
        raise CsvValidationError([f"Sensitive field not accepted: {header}." for header in sensitive])
    missing = sorted(REQUIRED_HEADERS - set(headers))
    if missing:
        raise CsvValidationError([f"Missing required header: {header}." for header in missing])
    unknown = sorted(set(headers) - ALLOWED_HEADERS)
    if unknown:
        raise CsvValidationError([f"Unsupported header: {header}. Remove it to minimize data collection." for header in unknown])

    records: list[dict[str, Any]] = []
    seen_transactions: set[str] = set()
    errors: list[str] = []
    for row_number, raw in enumerate(reader, start=2):
        if len(records) >= MAX_CSV_ROWS:
            errors.append(f"The CSV exceeds the {MAX_CSV_ROWS:,}-row limit.")
            break
        row = {normalize_header(key): (value or "").strip() for key, value in raw.items() if key is not None}
        try:
            transaction_id = row.get("transaction_id", "")
            if len(transaction_id) < 3 or len(transaction_id) > 64:
                raise CsvValidationError([safe_error(row_number, "transaction_id", "must be 3–64 characters")])
            if transaction_id[0] in {"=", "+", "-", "@"}:
                raise CsvValidationError([safe_error(row_number, "transaction_id", "cannot begin with a spreadsheet formula character")])
            if transaction_id in seen_transactions:
                raise CsvValidationError([safe_error(row_number, "transaction_id", "is duplicated in the file")])
            seen_transactions.add(transaction_id)
            record: dict[str, Any] = {"transaction_id": transaction_id}
            for header in INTEGER_HEADERS:
                if header in row and row[header] != "":
                    record[header] = parse_int(row[header], row_number, header, minimum=1 if header == "amount_cents" else 0)
            for header in FLOAT_HEADERS:
                if header in row and row[header] != "":
                    bounds = {"payment_method_risk": (0.0, 1.0), "merchant_category_risk": (0.0, 1.0)}.get(header, (None, None))
                    record[header] = parse_float(row[header], row_number, header, minimum=bounds[0], maximum=bounds[1])
            for header in BOOLEAN_HEADERS:
                if header in row:
                    record[header] = parse_bool(row[header], row_number, header)
            for header in {"customer_id", "merchant_id", "payment_method", "currency", "occurred_at", "dispute_reason", "delivery_status"}:
                if row.get(header):
                    record[header] = row[header]
            records.append(record)
        except CsvValidationError as error:
            errors.extend(error.messages)
            if len(errors) >= 50:
                break
    if not records and not errors:
        errors.append("The CSV has no data rows.")
    if errors:
        raise CsvValidationError(errors[:50])
    return records


def preview_records(records: list[dict[str, Any]], maximum_rows: int = 5) -> list[dict[str, Any]]:
    """Return a limited, minimized preview rather than raw CSV content."""
    allowed = ["transaction_id", "amount_cents", "amount_zscore", "velocity_1h", "velocity_24h", "velocity_7d", "geo_mismatch", "customer_is_first_time", "new_device", "payment_method_risk", "merchant_category_risk", "velocity_spike", "high_amount", "currency", "payment_method"]
    return [{key: record[key] for key in allowed if key in record} for record in records[:maximum_rows]]
