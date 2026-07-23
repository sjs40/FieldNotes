from backend.app.main import bootstrap
from backend.app.parser import parse_note


def main() -> None:
    bootstrap()
    result = parse_note("/th Apple $AAPL @bull #AI")
    assert result["note_type"] == "thesis"
    assert result["ticker_mentions"] == ["AAPL"]
    assert result["tracked_calls"] == [{"type": "bull", "symbol": "AAPL"}]
    print("Parser and database bootstrap: ok")


if __name__ == "__main__":
    main()
