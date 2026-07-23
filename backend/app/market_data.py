from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile

import httpx


@dataclass
class Quote:
    symbol: str
    price: float
    timestamp: datetime
    price_type: str = "latest_available"
    provider: str = "yfinance"
    currency: str = "USD"


class YFinanceMarketDataProvider:
    """yfinance is isolated here so it can be replaced with a licensed provider later."""
    name = "yfinance"

    @staticmethod
    def _cache_dir() -> Path:
        """Return a writable cache location in both local and Vercel runtimes."""
        if os.getenv("VERCEL"):
            return Path(tempfile.gettempdir()) / "fieldnotes-yfinance-cache"
        return Path(__file__).parents[2] / ".yfinance-cache"

    @staticmethod
    def _yahoo_chart_quote(symbol: str) -> Quote:
        """Fallback that avoids yfinance's cookie and timezone-cache machinery."""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.upper()}"
        response = httpx.get(
            url,
            params={"range": "5d", "interval": "1d", "includePrePost": "false"},
            headers={"User-Agent": "Fieldnotes/1.0 (personal research journal)"},
            timeout=10.0,
        )
        response.raise_for_status()
        result = response.json().get("chart", {}).get("result") or []
        closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", []) if result else []
        price = next((float(value) for value in reversed(closes) if value is not None), None)
        if not price or price <= 0:
            raise ValueError(f"No quote found for {symbol}")
        return Quote(symbol=symbol.upper(), price=price, timestamp=datetime.now(timezone.utc), price_type="latest_available", provider="yahoo_chart")

    def get_latest_quote(self, symbol: str) -> Quote:
        try:
            import yfinance as yf

            cache_dir = self._cache_dir()
            cache_dir.mkdir(parents=True, exist_ok=True)
            yf.set_tz_cache_location(str(cache_dir))
            ticker = yf.Ticker(symbol)
            history = ticker.history(period="5d", auto_adjust=False)
            if history.empty:
                raise ValueError(f"No quote found for {symbol}")
            price = float(history["Close"].dropna().iloc[-1])
            return Quote(symbol=symbol.upper(), price=price, timestamp=datetime.now(timezone.utc), price_type="latest_available")
        except Exception:
            return self._yahoo_chart_quote(symbol)

    def validate_security(self, symbol: str) -> bool:
        try:
            return self.get_latest_quote(symbol).price > 0
        except Exception:
            return False

    def get_historical_close(self, symbol: str, date_text: str) -> Quote:
        """Return the regular-session close for a legacy entry date.

        Intraday Yahoo history is only retained for a short window, so an old
        unrecorded entry is transparently marked `historical_close` rather than
        falsely claiming an exact publication-time quote.
        """
        import yfinance as yf
        from datetime import timedelta
        cache_dir = self._cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache_dir))
        day = datetime.strptime(date_text, "%b %d, %Y").date()
        history = yf.Ticker(symbol).history(start=day.isoformat(), end=(day + timedelta(days=1)).isoformat(), auto_adjust=False)
        if history.empty:
            raise ValueError(f"No historical close found for {symbol} on {date_text}")
        return Quote(symbol=symbol.upper(), price=float(history["Close"].dropna().iloc[-1]), timestamp=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc), price_type="historical_close")
