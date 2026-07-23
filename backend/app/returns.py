"""Canonical, server-side investment journal return calculations."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


class ReturnCalculationError(ValueError):
    pass


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ReturnCalculationError("Price must be numeric") from exc
    if result <= 0:
        raise ReturnCalculationError("Price must be greater than zero")
    return result


def price_return(entry: object, current: object) -> Decimal:
    return _decimal(current) / _decimal(entry) - Decimal("1")


def single_call_return(call_type: str, entry: object, current: object, benchmark_entry: object, benchmark_current: object) -> dict:
    underlying = price_return(entry, current)
    benchmark = price_return(benchmark_entry, benchmark_current)
    directional = -underlying if call_type == "bear" else underlying
    relative = directional + benchmark if call_type == "bear" else directional - benchmark
    return {"underlying_return": underlying, "directional_return": directional, "benchmark_return": benchmark, "relative_return": relative}


def pair_call_return(long_entry: object, long_current: object, short_entry: object, short_current: object, benchmark_entry: object | None = None, benchmark_current: object | None = None) -> dict:
    long_return = price_return(long_entry, long_current)
    short_underlying = price_return(short_entry, short_current)
    result = {"long_return": long_return, "short_underlying_return": short_underlying, "pair_return": long_return - short_underlying}
    if benchmark_entry is not None and benchmark_current is not None:
        result["benchmark_return"] = price_return(benchmark_entry, benchmark_current)
    return result


def canonical_return_object(*, call_id: str, status: str, call_type: str, legs: list[dict], benchmark: dict, opened_at: datetime, as_of: datetime | None = None) -> dict:
    """Return the stable API contract for open, closed, and invalidated calls.

    For terminal calls the supplied ``exit`` values are mandatory: results are
    therefore frozen and never affected by later quote refreshes.
    """
    terminal = status in {"closed", "invalidated"}
    timestamp = as_of or datetime.now(timezone.utc)
    selected = []
    for leg in legs:
        price = leg.get("exit") if terminal else leg.get("current")
        if price is None:
            raise ReturnCalculationError("Terminal calls require an exit price")
        selected.append({**leg, "selected_price": price})
    benchmark_price = benchmark.get("exit") if terminal else benchmark.get("current")
    if benchmark_price is None:
        raise ReturnCalculationError("Terminal calls require a benchmark exit price")
    benchmark_return = price_return(benchmark["entry"], benchmark_price)
    quote = benchmark.get("exit_quote" if terminal else "current_quote", {})
    result = {
        "call_id": call_id, "status": status, "as_of": timestamp.isoformat(),
        "benchmark_return": float(benchmark_return),
        "elapsed_days": max(0, (timestamp - opened_at).days),
        "quote_quality": {
            "provider": quote.get("provider"), "price_type": quote.get("price_type"),
            "quote_at": quote.get("timestamp").isoformat() if isinstance(quote.get("timestamp"), datetime) else quote.get("timestamp"),
        },
    }
    if call_type == "long_short":
        long_leg, short_leg = selected
        calculation = pair_call_return(long_leg["entry"], long_leg["selected_price"], short_leg["entry"], short_leg["selected_price"], benchmark["entry"], benchmark_price)
        result.update({
            "pair_return": float(calculation["pair_return"]),
            "long_return": float(calculation["long_return"]),
            "short_underlying_return": float(calculation["short_underlying_return"]),
            "legs": [{"symbol": leg.get("symbol"), "direction": leg.get("direction"), "entry": float(_decimal(leg["entry"])), "current_or_exit": float(_decimal(leg["selected_price"])), "return": float(price_return(leg["entry"], leg["selected_price"]))} for leg in selected],
        })
        return result
    leg = selected[0]
    calculation = single_call_return(call_type, leg["entry"], leg["selected_price"], benchmark["entry"], benchmark_price)
    result.update({
        "underlying_return": float(calculation["underlying_return"]),
        "directional_return": float(calculation["directional_return"]),
        "relative_return": float(calculation["relative_return"]),
        "label": "Bear directional return" if call_type == "bear" else "Directional return",
        "legs": [{"symbol": leg.get("symbol"), "direction": leg.get("direction"), "entry": float(_decimal(leg["entry"])), "current_or_exit": float(_decimal(leg["selected_price"]))}],
    })
    return result
