"""Auditable demand forecasting and rolling-origin backtest.

This service is deliberately separate from the legacy analytics facade.  The
legacy facade still contains demo fallbacks for the old dashboard; this module
is the Phase 4 contract and never substitutes synthetic data for live data.
"""

from __future__ import annotations

import datetime as dt
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from app.repositories import supabase as db


CALCULATION_VERSION = "forecast_backtest_v2"
METHODS = (
    "NAIVE_LAST",
    "MA7",
    "SEASONAL_NAIVE_7",
    "LINEAR_TREND",
    "RIDGE_LAG_7",
)
MODEL_TYPES = {
    "NAIVE_LAST": "baseline",
    "MA7": "baseline",
    "SEASONAL_NAIVE_7": "baseline",
    "LINEAR_TREND": "statistical",
    "RIDGE_LAG_7": "ml",
}


class ForecastUnavailable(RuntimeError):
    """Live forecast cannot be produced without inventing data."""


def _validate_dependency_metadata(
    metadata: Any, *, require_dates: bool = True, require_quality: bool = False
) -> dict[str, Any]:
    """Validate live paid-order provenance without filling missing fields."""
    if not isinstance(metadata, dict):
        raise ForecastUnavailable(
            "Metadata dependency forecast tidak tersedia; forecast live ditahan."
        )
    validated: dict[str, Any] = {}
    for field in ("paid_order_count", "paid_order_item_count"):
        if field not in metadata:
            raise ForecastUnavailable(
                "Metadata dependency forecast tidak lengkap; forecast live ditahan."
            )
        value = metadata.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ForecastUnavailable(
                f"Metadata {field} forecast tidak valid; forecast live ditahan."
            )
        validated[field] = value
    # These fields were added to the live query so a NULL/negative quantity or
    # blank unit cannot disappear inside SUM()/GROUP BY aggregation. They are
    # optional for old in-memory fixtures, but mandatory in build_live_forecast_report.
    for field in (
        "invalid_quantity_item_count",
        "missing_unit_item_count",
        "missing_menu_id_item_count",
    ):
        if field not in metadata:
            if require_quality:
                raise ForecastUnavailable(
                    "Metadata quality quantity/unit forecast tidak lengkap; forecast live ditahan."
                )
            continue
        value = metadata.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ForecastUnavailable(
                f"Metadata {field} forecast tidak valid; forecast live ditahan."
            )
        validated[field] = value
    for field in ("latest_paid_date", "latest_non_cancelled_date"):
        if field not in metadata:
            raise ForecastUnavailable(
                "Metadata dependency forecast tidak lengkap; forecast live ditahan."
            )
        value = metadata.get(field)
        if require_dates and not value:
            raise ForecastUnavailable(
                f"Metadata {field} forecast tidak tersedia; forecast live ditahan."
            )
        if value is not None:
            if isinstance(value, (dt.date, dt.datetime)):
                pass
            elif isinstance(value, str):
                try:
                    dt.date.fromisoformat(value)
                except ValueError as exc:
                    raise ForecastUnavailable(
                        f"Metadata {field} forecast tidak valid; forecast live ditahan."
                    ) from exc
            else:
                raise ForecastUnavailable(
                    f"Metadata {field} forecast tidak valid; forecast live ditahan."
                )
        validated[field] = value
    return validated


def _validate_live_quality_metadata(metadata: dict[str, Any]) -> None:
    """Require item-level quality evidence before accepting a live report."""
    for field in (
        "invalid_quantity_item_count",
        "missing_unit_item_count",
        "missing_menu_id_item_count",
    ):
        value = metadata.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ForecastUnavailable(
                f"Metadata {field} forecast tidak tersedia atau invalid; forecast live ditahan."
            )
        if value:
            raise ForecastUnavailable(
                f"Data paid memiliki {value} item dengan {field}; forecast live ditahan."
            )


def _as_date(value: Any) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value or "").strip()
    if not text:
        raise ForecastUnavailable(
            "Observasi forecast tidak memiliki tanggal; forecast ditahan."
        )
    try:
        return dt.date.fromisoformat(text[:10])
    except (TypeError, ValueError) as exc:
        raise ForecastUnavailable(
            "Observasi forecast memiliki tanggal invalid; forecast ditahan."
        ) from exc


def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise ForecastUnavailable("Model forecast menghasilkan nilai non-finite.")
    return value


def _quantity(value: Any, *, field: str = "quantity") -> float:
    if isinstance(value, bool):
        raise ForecastUnavailable(f"{field} forecast tidak valid; forecast ditahan.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ForecastUnavailable(f"{field} forecast tidak valid; forecast ditahan.") from exc
    if not math.isfinite(number) or number < 0:
        raise ForecastUnavailable(f"{field} forecast harus finite dan tidak negatif; forecast ditahan.")
    return number


def _validate_snapshot_series(report: dict[str, Any]) -> None:
    """Validate every persisted forecast row before opening a write transaction."""
    series_rows = report.get("series")
    if not isinstance(series_rows, list) or not series_rows:
        raise ForecastUnavailable(
            "Snapshot tidak memiliki series forecast yang valid; snapshot ditahan."
        )
    for series in series_rows:
        if not isinstance(series, dict):
            raise ForecastUnavailable("Series snapshot tidak valid; snapshot ditahan.")
        series_key = str(series.get("series_key") or "").strip()
        series_unit = str(series.get("unit") or "").strip()
        forecast_rows = series.get("forecast")
        if not series_key or not series_unit or not isinstance(forecast_rows, list) or not forecast_rows:
            raise ForecastUnavailable(
                "Series snapshot memiliki identitas/unit/forecast yang hilang; snapshot ditahan."
            )
        for item in forecast_rows:
            if not isinstance(item, dict):
                raise ForecastUnavailable("Baris forecast snapshot tidak valid; snapshot ditahan.")
            _as_date(item.get("target_date"))
            quantity = _quantity(item.get("quantity"), field="quantity")
            unit = str(item.get("unit") or "").strip()
            if not unit or unit != series_unit:
                raise ForecastUnavailable(
                    "Snapshot memiliki unit kosong atau unit campuran; snapshot ditahan."
                )
            method = item.get("method")
            if method not in METHODS:
                raise ForecastUnavailable(
                    "Snapshot memiliki method forecast yang tidak dikenal; snapshot ditahan."
                )
            lower_bound = _quantity(item.get("lower_bound"), field="lower_bound")
            upper_bound = _quantity(item.get("upper_bound"), field="upper_bound")
            if lower_bound > quantity or quantity > upper_bound:
                raise ForecastUnavailable(
                    "Interval forecast snapshot tidak membungkus quantity; snapshot ditahan."
                )
            interval_level = item.get("interval_level")
            if isinstance(interval_level, bool):
                raise ForecastUnavailable(
                    "Interval level snapshot tidak valid; snapshot ditahan."
                )
            try:
                interval_number = float(interval_level)
            except (TypeError, ValueError) as exc:
                raise ForecastUnavailable(
                    "Interval level snapshot tidak valid; snapshot ditahan."
                ) from exc
            if not math.isfinite(interval_number) or not 0 < interval_number <= 1:
                raise ForecastUnavailable(
                    "Interval level snapshot tidak valid; snapshot ditahan."
                )


def _mae(actual: list[float], predicted: list[float]) -> float:
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual) if actual else 0.0


def _rmse(actual: list[float], predicted: list[float]) -> float:
    return math.sqrt(
        sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual)
    ) if actual else 0.0


def _smape(actual: list[float], predicted: list[float]) -> float | None:
    values = []
    for a, p in zip(actual, predicted):
        denominator = abs(a) + abs(p)
        if denominator:
            values.append(200.0 * abs(a - p) / denominator)
    return sum(values) / len(values) if values else None


def _linear_forecast(history: list[float], horizon: int) -> list[float]:
    if not history:
        raise ForecastUnavailable("Histori kosong; model linear tidak dapat dihitung.")
    if len(history) == 1:
        return [max(0.0, history[0])] * horizon
    n = len(history)
    x_mean = (n - 1) / 2
    y_mean = sum(history) / n
    denominator = sum((x - x_mean) ** 2 for x in range(n))
    slope = (
        sum((x - x_mean) * (y - y_mean) for x, y in enumerate(history)) / denominator
        if denominator
        else 0.0
    )
    intercept = y_mean - slope * x_mean
    return [max(0.0, _finite(intercept + slope * (n + offset))) for offset in range(horizon)]


def _solve_ridge(features: list[list[float]], targets: list[float], alpha: float = 1.0) -> list[float] | None:
    """Small dependency-free ridge solver for the bounded demand features.

    The model is intentionally tiny and deterministic: intercept, lag-1, lag-7,
    and trailing 7-day mean. Keeping the solver here avoids silently changing
    the production result when an optional scientific Python package is absent.
    """
    if not features or len(features) != len(targets):
        return None
    width = len(features[0])
    matrix = [[0.0 for _ in range(width)] for _ in range(width)]
    vector = [0.0 for _ in range(width)]
    for row, target in zip(features, targets):
        for i in range(width):
            vector[i] += row[i] * target
            for j in range(width):
                matrix[i][j] += row[i] * row[j]
    for i in range(1, width):  # do not penalise the intercept
        matrix[i][i] += alpha

    augmented = [matrix[i] + [vector[i]] for i in range(width)]
    for column in range(width):
        pivot = max(range(column, width), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-10:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(width):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    left - factor * right
                    for left, right in zip(augmented[row], augmented[column])
                ]
    return [augmented[i][-1] for i in range(width)]


def _ridge_forecast(history: list[float], horizon: int) -> list[float]:
    if len(history) < 8:
        raise ForecastUnavailable("Histori RIDGE_LAG_7 belum cukup; model ditahan.")
    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(7, len(history)):
        features.append([
            1.0,
            history[index - 1],
            history[index - 7],
            sum(history[index - 7:index]) / 7.0,
        ])
        targets.append(history[index])
    coefficients = _solve_ridge(features, targets)
    if coefficients is None:
        raise ForecastUnavailable("Solver RIDGE_LAG_7 gagal; forecast ditahan.")
    values = list(history)
    predictions: list[float] = []
    for _ in range(horizon):
        feature = [
            1.0,
            values[-1],
            values[-7],
            sum(values[-7:]) / 7.0,
        ]
        prediction = max(0.0, _finite(sum(a * b for a, b in zip(coefficients, feature))))
        predictions.append(prediction)
        values.append(prediction)
    return predictions


def _predict(method: str, history: list[float], horizon: int = 1) -> list[float]:
    if not history:
        raise ForecastUnavailable("Histori kosong; forecast ditahan.")
    if method == "NAIVE_LAST":
        return [max(0.0, history[-1])] * horizon
    if method == "MA7":
        window = history[-7:]
        return [max(0.0, sum(window) / len(window))] * horizon
    if method == "SEASONAL_NAIVE_7":
        if len(history) < 7:
            raise ForecastUnavailable("Histori SEASONAL_NAIVE_7 belum cukup; model ditahan.")
        pattern = history[-7:]
        return [max(0.0, pattern[index % 7]) for index in range(horizon)]
    if method == "LINEAR_TREND":
        return _linear_forecast(history, horizon)
    if method == "RIDGE_LAG_7":
        return _ridge_forecast(history, horizon)
    raise ValueError(f"Unknown forecast method: {method}")


def _metrics(actual: list[float], predicted: list[float]) -> dict[str, Any]:
    actual_total = sum(abs(value) for value in actual)
    wape = (
        100.0 * sum(abs(a - p) for a, p in zip(actual, predicted)) / actual_total
        if actual_total
        else None
    )
    return {
        "mae": round(_mae(actual, predicted), 4),
        "rmse": round(_rmse(actual, predicted), 4),
        "smape_percent": round(smape, 4) if (smape := _smape(actual, predicted)) is not None else None,
        "smape_status": "DEFINED" if smape is not None else "UNDEFINED_ZERO_DENOMINATOR",
        "wape_percent": round(wape, 4) if wape is not None else None,
        "wape_status": "DEFINED" if wape is not None else "UNDEFINED_ZERO_ACTUAL",
        "holdout_points": len(actual),
    }


def backtest_series(
    values: Iterable[float],
    *,
    min_history_days: int = 14,
    min_backtest_points: int = 7,
) -> dict[str, Any]:
    """Run one-step rolling-origin backtests for all baseline methods."""
    if not isinstance(min_history_days, int) or min_history_days < 1:
        raise ValueError("min_history_days harus integer positif.")
    if not isinstance(min_backtest_points, int) or min_backtest_points < 1:
        raise ValueError("min_backtest_points harus integer positif.")
    series = [_quantity(value) for value in values]
    validation_start = max(min_history_days, 8)
    if len(series) <= validation_start:
        return {
            "status": "INSUFFICIENT_HISTORY",
            "history_days": len(series),
            "holdout_points": 0,
            "validation_start": validation_start,
            "methods": {},
            "selected_method": None,
        }

    actual_by_method: dict[str, list[float]] = {method: [] for method in METHODS}
    predicted_by_method: dict[str, list[float]] = {method: [] for method in METHODS}
    for origin in range(validation_start, len(series)):
        history = series[:origin]
        actual = series[origin]
        for method in METHODS:
            actual_by_method[method].append(actual)
            predicted_by_method[method].append(_predict(method, history)[0])

    results = {
        method: _metrics(actual_by_method[method], predicted_by_method[method])
        for method in METHODS
    }
    selected = min(
        METHODS,
        key=lambda method: (
            results[method]["mae"],
            results[method]["rmse"],
            METHODS.index(method),
        ),
    )
    return {
        "status": "OK" if len(series) - validation_start >= min_backtest_points else "LOW_VALIDATION",
        "history_days": len(series),
        "holdout_points": len(series) - validation_start,
        "validation_start": validation_start,
        "methods": results,
        "selected_method": selected,
    }


def _normalise_rows(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ForecastUnavailable(
                "Observasi forecast tidak berbentuk object; forecast ditahan."
            )
        key = str(row.get("series_key") or "").strip()
        if not key:
            raise ForecastUnavailable("Observasi forecast tidak memiliki series_key; forecast ditahan.")
        target_date = _as_date(row.get("target_date"))
        quantity = _quantity(row.get("quantity"))
        unit = str(row.get("unit") or "").strip()
        if not unit:
            raise ForecastUnavailable(
                f"Series {key} tidak memiliki unit demand; forecast ditahan."
            )
        # Label is display metadata only; the canonical series_key remains
        # mandatory and is never used as a demand value or identity fallback.
        label = str(row.get("label") or key).strip()
        item = grouped.setdefault(
            key,
            {
                "series_key": key,
                "label": label,
                "unit": unit,
                "values": defaultdict(float),
            },
        )
        row_unit = unit
        if item["unit"] != row_unit:
            raise ForecastUnavailable(
                f"Series {key} memiliki unit campuran ({item['unit']} dan {row_unit}); forecast ditahan."
            )
        item["values"][target_date] += quantity
    return grouped


def build_forecast_report(
    rows: Iterable[dict[str, Any]],
    *,
    horizon_days: int = 7,
    min_history_days: int = 14,
    min_backtest_points: int = 7,
    stale_after_days: int = 3,
    as_of: dt.date | None = None,
    data_mode: str = "fixture",
    source: str = "fixture",
    dependency_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a bounded, provenance-labelled forecast report from observed rows."""
    if not 1 <= horizon_days <= 30:
        raise ValueError("horizon_days harus berada di antara 1 dan 30.")
    if data_mode == "live" and source != "supabase_postgres":
        raise ForecastUnavailable(
            "Forecast live hanya boleh berasal dari source supabase_postgres."
        )
    grouped = _normalise_rows(rows)
    if not grouped:
        metadata = dependency_metadata if dependency_metadata is not None else {}
        if data_mode == "live":
            # NO_DATA is still a live report.  Counts may legitimately be zero
            # and dates may be null, but the dependency contract must exist.
            metadata = _validate_dependency_metadata(
                metadata, require_dates=False, require_quality=True
            )
        return {
            "status": "NO_DATA",
            "data_mode": data_mode,
            "source": source,
            "calculation_version": CALCULATION_VERSION,
            "paid_order_count": metadata.get("paid_order_count"),
            "paid_order_item_count": metadata.get("paid_order_item_count"),
            "invalid_quantity_item_count": metadata.get("invalid_quantity_item_count"),
            "missing_unit_item_count": metadata.get("missing_unit_item_count"),
            "missing_menu_id_item_count": metadata.get("missing_menu_id_item_count"),
            "latest_paid_date": metadata.get("latest_paid_date"),
            "latest_non_cancelled_date": metadata.get("latest_non_cancelled_date"),
            "dependency_metadata": metadata,
            "series": [],
            "model_comparison": {},
            "warnings": ["Tidak ada observasi demand yang dapat dihitung."],
        }

    observed_dates = [date for item in grouped.values() for date in item["values"]]
    latest_observation = max(observed_dates)
    evidence_date = as_of or dt.date.today()
    if evidence_date < latest_observation:
        if data_mode == "live":
            raise ForecastUnavailable(
                "Observasi forecast live berada di masa depan; forecast ditahan."
            )
        raise ValueError("as_of tidak boleh lebih awal dari observasi terakhir.")
    forecast_origin = latest_observation
    data_age_days = max(0, (evidence_date - latest_observation).days)
    series_reports: list[dict[str, Any]] = []
    aggregate_actual: dict[str, list[float]] = {method: [] for method in METHODS}
    aggregate_predicted: dict[str, list[float]] = {method: [] for method in METHODS}
    warnings: list[str] = []
    stale_series_count = 0
    weekday_unit_series: dict[int, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)

    for key, item in sorted(grouped.items(), key=lambda pair: pair[0]):
        first_date = min(item["values"])
        series_latest_observation = max(item["values"])
        series_data_age_days = max(0, (evidence_date - series_latest_observation).days)
        if series_data_age_days > stale_after_days:
            stale_series_count += 1
            warnings.append(
                f"{item['label']}: observasi terakhir {series_latest_observation.isoformat()} "
                f"berjarak {series_data_age_days} hari; forecast berstatus stale."
            )
        # Do not pad a series with synthetic zero-demand days after its own
        # last observation merely because another series is newer. Missing
        # dates inside the observed span remain zero demand; the tail after
        # series_latest_observation is unknown and must stay outside training.
        dates = [
            first_date + dt.timedelta(days=offset)
            for offset in range((series_latest_observation - first_date).days + 1)
        ]
        values = [float(item["values"].get(day, 0.0)) for day in dates]
        for day, quantity in zip(dates, values):
            bucket = weekday_unit_series[day.weekday()].setdefault(
                (key, item["unit"]),
                {"series_key": key, "label": item["label"], "unit": item["unit"], "total": 0.0, "days": 0},
            )
            bucket["total"] += quantity
            bucket["days"] += 1
        backtest = backtest_series(
            values,
            min_history_days=min_history_days,
            min_backtest_points=min_backtest_points,
        )
        active_days = sum(1 for value in values if value > 0)
        series_report: dict[str, Any] = {
            "series_key": key,
            "label": item["label"],
            "unit": item["unit"],
            "observed_from": first_date.isoformat(),
            "observed_to": series_latest_observation.isoformat(),
            "latest_observation_date": series_latest_observation.isoformat(),
            "data_age_days": series_data_age_days,
            "history_days": len(values),
            "active_days": active_days,
            "total_observed": round(sum(values), 4),
            "backtest": backtest,
            "forecast": [],
        }
        if backtest["selected_method"] and backtest["status"] == "OK":
            selected = str(backtest["selected_method"])
            predictions = _predict(selected, values, horizon_days)
            selected_metrics = backtest["methods"].get(selected)
            if not isinstance(selected_metrics, dict) or "rmse" not in selected_metrics:
                raise ForecastUnavailable(
                    f"Metric RMSE untuk {item['label']} hilang; interval forecast ditahan."
                )
            interval_rmse = _quantity(selected_metrics["rmse"], field="interval RMSE")
            interval_half_width = 1.28 * interval_rmse  # central 80% empirical-style band
            series_report["forecast"] = [
                {
                    "target_date": (
                        series_latest_observation + dt.timedelta(days=offset + 1)
                    ).isoformat(),
                    "quantity": round(prediction, 4),
                    "lower_bound": round(max(0.0, prediction - interval_half_width), 4),
                    "upper_bound": round(max(0.0, prediction + interval_half_width), 4),
                    "interval_level": 0.80,
                    "unit": item["unit"],
                    "method": selected,
                    "model_type": MODEL_TYPES[selected],
                }
                for offset, prediction in enumerate(predictions)
            ]
            if "validation_start" not in backtest:
                raise ForecastUnavailable(
                    f"Validation boundary untuk {item['label']} hilang; agregasi backtest ditahan."
                )
            holdout_start = int(backtest["validation_start"])
            if len(values) > holdout_start:
                actual = values[holdout_start:]
                for method in METHODS:
                    aggregate_actual[method].extend(actual)
                    aggregate_predicted[method].extend(
                        _predict(method, values[:holdout_start + index])[0]
                        for index in range(len(actual))
                    )
        elif backtest["selected_method"]:
            warnings.append(
                f"{item['label']}: holdout backtest masih pendek; forecast operasional ditahan."
            )
        else:
            warnings.append(f"{item['label']}: histori belum cukup untuk forecast.")
        series_reports.append(series_report)

    model_comparison = {
        method: _metrics(aggregate_actual[method], aggregate_predicted[method])
        for method in METHODS
        if aggregate_actual[method]
    }
    weekday_names = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
    weekday_demand_summary = [
        {
            "weekday": weekday_names[weekday],
            "weekday_index": weekday,
            "unit": unit,
            "menus": sorted(
                (
                    {
                        "series_key": menu["series_key"],
                        "label": menu["label"],
                        "average_quantity": round(menu["total"] / menu["days"], 2),
                        "total_observed": round(menu["total"], 2),
                        "observed_days": menu["days"],
                    }
                    for (series_key, series_unit), menu in weekday_unit_series[weekday].items()
                    if series_unit == unit
                ),
                key=lambda menu: (-menu["average_quantity"], menu["label"]),
            ),
        }
        for weekday in sorted(weekday_unit_series)
        for unit in sorted({series_unit for _, series_unit in weekday_unit_series[weekday]})
    ]
    eligible = sum(1 for item in series_reports if item["backtest"]["status"] == "OK")
    has_low_validation = any(
        item["backtest"]["status"] == "LOW_VALIDATION" for item in series_reports
    )
    has_insufficient_history = any(
        item["backtest"]["status"] == "INSUFFICIENT_HISTORY"
        for item in series_reports
    )
    if stale_series_count:
        status = "STALE_DATA"
    elif has_low_validation:
        status = "LOW_VALIDATION"
    elif has_insufficient_history or not eligible:
        status = "INSUFFICIENT_HISTORY"
    else:
        status = "OK"
    metadata = dependency_metadata if dependency_metadata is not None else {}
    if data_mode == "live":
        # Stale/low-validation reports are not operational outputs, but they
        # must still carry structurally valid provenance.  Only an OK report
        # requires non-null latest dates.
        metadata = _validate_dependency_metadata(
            metadata, require_dates=status == "OK", require_quality=True
        )
    return {
        "status": status,
        "data_mode": data_mode,
        "source": source,
        "calculation_version": CALCULATION_VERSION,
        "as_of": evidence_date.isoformat(),
        "forecast_origin_date": forecast_origin.isoformat(),
        "latest_observation_date": latest_observation.isoformat(),
        "data_age_days": data_age_days,
        "paid_order_count": metadata.get("paid_order_count"),
        "paid_order_item_count": metadata.get("paid_order_item_count"),
        "invalid_quantity_item_count": metadata.get("invalid_quantity_item_count"),
        "missing_unit_item_count": metadata.get("missing_unit_item_count"),
        "missing_menu_id_item_count": metadata.get("missing_menu_id_item_count"),
        "latest_paid_date": metadata.get("latest_paid_date"),
        "latest_non_cancelled_date": metadata.get("latest_non_cancelled_date"),
        "dependency_metadata": metadata,
        "freshness_threshold_days": stale_after_days,
        "stale_series_count": stale_series_count,
        "horizon_days": horizon_days,
        "min_history_days": min_history_days,
        "series_count": len(series_reports),
        "eligible_series_count": eligible,
        "series": series_reports,
        "weekday_demand_summary": weekday_demand_summary,
        "model_comparison": model_comparison,
        "warnings": sorted(set(warnings)),
        "quantity_contract": "order_items.quantity + explicit unit; no mixed units per series",
    }


def build_live_forecast_report(
    *,
    horizon_days: int = 7,
    history_days: int = 90,
    min_history_days: int = 14,
    min_backtest_points: int = 7,
) -> dict[str, Any]:
    """Read order-item observations from Supabase; never fall back to demo data."""
    if not db.is_connected():
        raise ForecastUnavailable("Supabase tidak terhubung; forecast live ditahan.")
    if not db.check_migrations():
        raise ForecastUnavailable("Migration aplikasi belum lengkap; forecast live ditahan.")
    if not 30 <= history_days <= 365:
        raise ValueError("history_days harus berada di antara 30 dan 365.")
    try:
        rows = db.execute(
            """
            SELECT oi.menu_id AS series_key,
                   m.nama_menu AS label,
                   o.created_at::DATE AS target_date,
                   SUM(oi.quantity)::NUMERIC AS quantity,
                   oi.unit AS unit
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            JOIN menus m ON m.menu_id = oi.menu_id
            WHERE oi.menu_id IS NOT NULL
              AND o.status <> 'CANCELLED'
              AND o.payment_status = 'PAID'
              AND o.created_at >= CURRENT_DATE - (%s * INTERVAL '1 day')
            GROUP BY oi.menu_id, m.nama_menu, o.created_at::DATE, oi.unit
            ORDER BY target_date, series_key
            """,
            (history_days,),
        )
        metadata_rows = db.execute(
            """
            SELECT COUNT(DISTINCT o.order_id)::INTEGER AS paid_order_count,
                   COUNT(oi.id)::INTEGER AS paid_order_item_count,
                   COUNT(*) FILTER (
                       WHERE oi.id IS NOT NULL
                         AND (oi.quantity IS NULL OR oi.quantity <= 0)
                   )::INTEGER AS invalid_quantity_item_count,
                   COUNT(*) FILTER (
                       WHERE oi.id IS NOT NULL
                         AND (oi.unit IS NULL OR BTRIM(oi.unit) = '')
                   )::INTEGER AS missing_unit_item_count,
                   COUNT(*) FILTER (
                       WHERE oi.id IS NOT NULL
                         AND oi.menu_id IS NULL
                   )::INTEGER AS missing_menu_id_item_count,
                   MAX(o.created_at)::DATE AS latest_paid_date,
                   MAX(o.created_at)::DATE AS latest_non_cancelled_date
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.status <> 'CANCELLED'
              AND o.payment_status = 'PAID'
              AND o.created_at >= CURRENT_DATE - (%s * INTERVAL '1 day')
            """,
            (history_days,),
        )
        if len(metadata_rows) != 1:
            raise ForecastUnavailable(
                "Metadata dependency forecast tidak lengkap; forecast live ditahan."
            )
        metadata = metadata_rows[0]
        dependency_metadata: dict[str, Any] = {}
        for field in ("paid_order_count", "paid_order_item_count"):
            value = metadata.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ForecastUnavailable(
                    f"Metadata {field} forecast tidak valid; forecast live ditahan."
                )
            dependency_metadata[field] = value
        for field in (
            "invalid_quantity_item_count",
            "missing_unit_item_count",
            "missing_menu_id_item_count",
        ):
            value = metadata.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ForecastUnavailable(
                    f"Metadata {field} forecast tidak valid; forecast live ditahan."
                )
            dependency_metadata[field] = value
        _validate_live_quality_metadata(dependency_metadata)
        for field in ("latest_paid_date", "latest_non_cancelled_date"):
            value = metadata.get(field)
            dependency_metadata[field] = value.isoformat() if isinstance(value, (dt.date, dt.datetime)) else value
    except Exception as exc:
        if isinstance(exc, ForecastUnavailable):
            raise
        raise ForecastUnavailable(
            "Kolom order_items.quantity/unit belum tersedia atau query forecast gagal; forecast live ditahan."
        ) from exc
    return build_forecast_report(
        rows,
        horizon_days=horizon_days,
        min_history_days=min_history_days,
        min_backtest_points=min_backtest_points,
        data_mode="live",
        source="supabase_postgres",
        dependency_metadata=dependency_metadata,
    )


def build_seeded_demo_forecast_report(*, horizon_days: int = 7) -> dict[str, Any]:
    """Create a deterministic in-memory demo forecast; never writes to Supabase."""
    as_of = dt.date.today()
    seed_path = Path(__file__).resolve().parents[2] / "data" / "forecast_seed_observations.csv"
    rows: list[dict[str, Any]] = []
    try:
        with seed_path.open("r", newline="", encoding="utf-8") as seed_file:
            for item in csv.DictReader(seed_file):
                day_offset = int(item["day_offset"])
                if not 0 <= day_offset < 120:
                    raise ValueError("day_offset seed forecast di luar rentang.")
                rows.append({
                    "series_key": item["series_key"],
                    "label": item["label"],
                    "target_date": as_of - dt.timedelta(days=119 - day_offset),
                    "quantity": float(item["quantity"]),
                    "unit": item["unit"],
                })
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ForecastUnavailable("Dataset seed forecast tidak terbaca; preview tidak tersedia.") from exc
    if len(rows) < 120:
        raise ForecastUnavailable("Dataset seed forecast tidak lengkap; preview tidak tersedia.")
    report = build_forecast_report(
        rows,
        horizon_days=horizon_days,
        min_history_days=28,
        min_backtest_points=7,
        as_of=as_of,
        data_mode="simulated",
        source="seeded_demo_dataset",
    )
    report["status"] = "SIMULATED"
    report["seed_notice"] = (
        "Data seed tersedia untuk preview; tidak berasal dari transaksi aktual dan tidak boleh dipakai untuk keputusan operasi."
    )
    report["paid_order_count"] = None
    report["paid_order_item_count"] = None
    report["quantity_contract"] = "Dataset seed porsi/menu/hari; bukan order_items live"
    return report


def persist_forecast_report(report: dict[str, Any], *, target_type: str = "MENU") -> int:
    """Persist only a fresh, live report; never persist stale/simulated output."""
    if not isinstance(report, dict):
        raise ForecastUnavailable("Snapshot forecast harus berupa object; snapshot ditahan.")
    if report.get("data_mode") != "live":
        raise ForecastUnavailable("Hanya forecast live yang boleh dipersistenkan.")
    if report.get("status") != "OK":
        raise ForecastUnavailable(
            f"Forecast berstatus {report.get('status')}; snapshot tidak ditulis."
        )
    if report.get("source") != "supabase_postgres":
        raise ForecastUnavailable("Snapshot hanya boleh berasal dari Supabase live.")
    if report.get("calculation_version") != CALCULATION_VERSION:
        raise ForecastUnavailable(
            "Snapshot hanya boleh memakai calculation_version forecast_backtest_v2."
        )
    _validate_dependency_metadata(report.get("dependency_metadata"), require_quality=True)
    _validate_snapshot_series(report)
    if target_type not in {"MENU", "INGREDIENT", "SUPPLIER"}:
        raise ValueError("target_type tidak valid.")

    persisted = 0
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for series in report.get("series", []):
                for item in series.get("forecast", []):
                    cur.execute(
                        """
                        INSERT INTO forecast_snapshots (
                            series_key, target_type, target_date, forecast_quantity,
                            unit, method, lower_bound, upper_bound, data_mode,
                            source, calculation_version
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (series_key, target_type, target_date, method, calculation_version)
                        DO UPDATE SET forecast_quantity = EXCLUDED.forecast_quantity,
                                      unit = EXCLUDED.unit,
                                      lower_bound = EXCLUDED.lower_bound,
                                      upper_bound = EXCLUDED.upper_bound,
                                      data_mode = EXCLUDED.data_mode,
                                      source = EXCLUDED.source
                        """,
                        (
                            series["series_key"],
                            target_type,
                            item["target_date"],
                            item["quantity"],
                            item["unit"],
                            item["method"],
                            item.get("lower_bound"),
                            item.get("upper_bound"),
                            report["data_mode"],
                            report["source"],
                            report["calculation_version"],
                        ),
                    )
                    persisted += 1
    return persisted
