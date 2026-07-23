from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


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

    def get_latest_quote(self, symbol: str) -> Quote:
        import yfinance as yf
        # yfinance otherwise writes its timezone cache to the user home. Keep
        # it inside this application so local installs work in restricted shells.
        cache_dir = Path(__file__).parents[2] / ".yfinance-cache"
        cache_dir.mkdir(exist_ok=True)
        yf.set_tz_cache_location(str(cache_dir))
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="5d", auto_adjust=False)
        if history.empty:
            raise ValueError(f"No quote found for {symbol}")
        price = float(history["Close"].dropna().iloc[-1])
        return Quote(symbol=symbol.upper(), price=price, timestamp=datetime.now(timezone.utc), price_type="latest_available")

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
        cache_dir = Path(__file__).parents[2] / ".yfinance-cache"
        cache_dir.mkdir(exist_ok=True)
        yf.set_tz_cache_location(str(cache_dir))
        day = datetime.strptime(date_text, "%b %d, %Y").date()
        history = yf.Ticker(symbol).history(start=day.isoformat(), end=(day + timedelta(days=1)).isoformat(), auto_adjust=False)
        if history.empty:
            raise ValueError(f"No historical close found for {symbol} on {date_text}")
        return Quote(symbol=symbol.upper(), price=float(history["Close"].dropna().iloc[-1]), timestamp=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc), price_type="historical_close")
