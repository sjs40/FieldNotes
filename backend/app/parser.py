"""Deterministic lightweight syntax parsing; deliberately no LLM dependency."""
import re

TYPE_MAP = {"o": "observation", "i": "idea", "th": "thesis", "q": "question", "t": "task", "d": "decision", "n": "note"}


def parse_note(body: str, note_type: str = "note") -> dict:
    clean = body.strip()
    command = re.match(r"^/(o|i|th|q|t|d|n)\b\s*", clean, re.I)
    if command:
        note_type = TYPE_MAP[command.group(1).lower()]
        clean = clean[command.end():]
    tickers = list(dict.fromkeys(m.upper() for m in re.findall(r"\$([A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z])?)", clean)))
    tags = list(dict.fromkeys(re.findall(r"#(?!longshort\b)([\w-]+)", clean, re.I)))
    warnings, calls = [], []
    pair = re.search(r"#longshort\s+\$([\w.]+)\s*>\s*\$([\w.]+)", clean, re.I)
    if pair:
        long, short = pair.group(1).upper(), pair.group(2).upper()
        if long == short:
            warnings.append("A long-short pair needs two different tickers.")
        else:
            calls.append({"type": "long_short", "long": long, "short": short})
    elif re.search(r"#longshort\b", clean, re.I):
        warnings.append("Long-short syntax needs two tickers: #LongShort $AAPL > $GOOGL")
    stances = []
    for line in clean.splitlines():
        stance = re.search(r"@(bull|bear)\b", line, re.I)
        line_symbols = re.findall(r"\$([\w.]+)", line)
        if stance and len(line_symbols) == 1:
            stances.append({"type": stance.group(1).lower(), "symbol": line_symbols[0].upper()})
    if not pair and not stances:
        stance = re.search(r"@(bull|bear)\b", clean, re.I)
        if stance and len(tickers) == 1:
            stances.append({"type": stance.group(1).lower(), "symbol": tickers[0]})
        elif stance and len(tickers) > 1:
            warnings.append("Multiple tickers make the stance ambiguous. Put each stance on the same line as its ticker.")
    calls.extend(stances)
    return {"note_type": note_type, "clean_body": clean, "tags": tags, "ticker_mentions": tickers, "tracked_calls": calls, "warnings": warnings, "errors": [] if clean else ["Note body is required."]}
