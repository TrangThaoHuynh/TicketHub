from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import joblib
import pandas as pd


@dataclass(frozen=True)
class TicketPriceSuggestion:
    suggested_price: int
    source: str  # "ml" | "fallback"


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _round_vnd(value: float | int | None) -> int:
    if value is None:
        return 0
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0

    if n < 0:
        n = 0
    return int(round(n / 1000.0) * 1000)


def _compute_derived_features(
    *,
    start_time: datetime | None,
    end_time: datetime | None,
    sale_start: datetime | None,
    sale_end: datetime | None,
) -> dict[str, Any]:
    derived: dict[str, Any] = {
        "start_month": None,
        "start_dayofweek": None,
        "start_hour": None,
        "event_duration_hours": None,
        "sale_window_days": None,
        "days_to_event_from_saleStart": None,
    }

    if start_time:
        derived["start_month"] = start_time.month
        derived["start_dayofweek"] = start_time.weekday()
        derived["start_hour"] = start_time.hour

    if start_time and end_time:
        delta = end_time - start_time
        derived["event_duration_hours"] = delta.total_seconds() / 3600.0

    if sale_start and sale_end:
        delta = sale_end - sale_start
        derived["sale_window_days"] = delta.total_seconds() / 86400.0

    if start_time and sale_start:
        delta = start_time - sale_start
        derived["days_to_event_from_saleStart"] = delta.total_seconds() / 86400.0

    return derived


class TicketPriceSuggester:
    def __init__(self, model_path: str | None = None):
        self._model_path = model_path
        self._artifact: dict[str, Any] | None = None

    def _default_model_path(self) -> str:
        # app/services -> app
        app_dir = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(app_dir, "models", "price_suggester.joblib")

    def _load(self) -> dict[str, Any]:
        if self._artifact is not None:
            return self._artifact

        model_path = self._model_path or os.getenv("PRICE_SUGGESTER_MODEL_PATH") or self._default_model_path()
        artifact = joblib.load(model_path)
        if not isinstance(artifact, dict) or "pipeline" not in artifact or "metadata" not in artifact:
            raise ValueError("Unsupported model artifact format")

        self._artifact = artifact
        return artifact

    def suggest_price(
        self,
        *,
        organizer_id: int,
        event_type_id: int,
        event_type_name: str,
        location: str,
        has_face_reg: bool,
        limit_quantity: int | None,
        start_time: datetime | str | None,
        end_time: datetime | str | None,
        sale_start: datetime | str | None,
        sale_end: datetime | str | None,
        ticket_type_name: str,
        ticket_quantity: int,
    ) -> TicketPriceSuggestion:
        try:
            artifact = self._load()
            pipeline = artifact["pipeline"]
            metadata = artifact["metadata"]
            features = metadata.get("features") or {}

            numeric_cols: list[str] = list((features.get("numeric") or []))
            categorical_cols: list[str] = list((features.get("categorical") or []))

            start_dt = _parse_dt(start_time)
            end_dt = _parse_dt(end_time)
            sale_start_dt = _parse_dt(sale_start)
            sale_end_dt = _parse_dt(sale_end)

            row: dict[str, Any] = {
                "ticketQuantity": int(ticket_quantity),
                "hasFaceReg": 1 if bool(has_face_reg) else 0,
                "limitQuantity": _safe_int(limit_quantity),
                "eventTypeId": int(event_type_id),
                "organizerId": int(organizer_id),
                "ticketTypeName": (ticket_type_name or "").strip(),
                "eventTypeName": (event_type_name or "").strip(),
                "location": (location or "").strip(),
            }

            row.update(
                _compute_derived_features(
                    start_time=start_dt,
                    end_time=end_dt,
                    sale_start=sale_start_dt,
                    sale_end=sale_end_dt,
                )
            )

            # Make sure all expected columns exist for the ColumnTransformer.
            all_cols = list(dict.fromkeys([*numeric_cols, *categorical_cols]))
            for col in all_cols:
                row.setdefault(col, None)

            df = pd.DataFrame([row], columns=all_cols)
            y_pred = pipeline.predict(df)
            value = float(y_pred[0]) if hasattr(y_pred, "__len__") else float(y_pred)
            return TicketPriceSuggestion(suggested_price=_round_vnd(value), source="ml")
        except Exception:
            return TicketPriceSuggestion(
                suggested_price=_fallback_price(ticket_type_name=ticket_type_name, ticket_quantity=ticket_quantity),
                source="fallback",
            )


def _fallback_price(*, ticket_type_name: str, ticket_quantity: int) -> int:
    name = (ticket_type_name or "").strip().lower()
    base = 50000

    if any(key in name for key in ["vip", "v.i.p", "premium"]):
        base = 200000
    elif any(key in name for key in ["standard", "thuong", "thường"]):
        base = 80000
    elif any(key in name for key in ["student", "sinh viên", "sv"]):
        base = 40000

    qty = max(int(ticket_quantity or 0), 0)
    if qty >= 500:
        base = int(base * 0.9)
    elif qty <= 50:
        base = int(base * 1.05)

    return _round_vnd(base)
