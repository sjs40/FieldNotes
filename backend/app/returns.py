"""Canonical, server-side investment journal return calculations."""
from dataclasses import dataclass
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
