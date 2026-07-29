"""Deterministic lightweight syntax parsing; deliberately no LLM dependency."""
import re

TYPE_MAP = {
    "o": "observation", "obs": "observation", "observation": "observation",
    "i": "idea", "idea": "idea",
    "th": "thesis", "thesis": "thesis",
    "q": "question", "question": "question",
    "t": "task", "task": "task",
    "d": "decision", "decision": "decision",
    "n": "note", "note": "note", "news": "news",
}


def parse_note(body: str, note_type: str = "note") -> dict:
    clean = body.strip()
    command = re.match(r"^/(observation|obs|idea|thesis|question|decision|task|news|note|th|o|i|q|t|d|n)\b\s*", clean, re.I)
    if command:
        note_type = TYPE_MAP[command.group(1).lower()]
        clean = clean[command.end():]
    # A dollar number beside @target is money, never a security token.
    tickers = list(dict.fromkeys(m.upper() for m in re.findall(r"\$([A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z])?)", clean)))
    tags = list(dict.fromkeys(re.findall(r"#(?!longshort\b)([\w-]+)", clean, re.I)))
    warnings, calls = [], []
    pair = re.search(r"#longshort\s+\$([A-Za-z][\w.]*)\s*>\s*\$([A-Za-z][\w.]*)", clean, re.I)
    if pair:
        long, short = pair.group(1).upper(), pair.group(2).upper()
        if long == short:
            warnings.append("A long-short pair needs two different tickers.")
        else:
            target = _target_on_line(pair.group(0))
            # The target may appear after the pair syntax on the same line.
            pair_line = next((line for line in clean.splitlines() if pair.group(0) in line), pair.group(0))
            target = _target_on_line(pair_line)
            calls.append({"type": "long_short", "long": long, "short": short, **({"target": target, "target_type": "pair_return", "target_unit": "percent"} if target is not None else {})})
    elif re.search(r"#longshort\b", clean, re.I):
        warnings.append("Long-short syntax needs two tickers: #LongShort $AAPL > $GOOGL")
    stances = []
    for line in clean.splitlines():
        stance = re.search(r"@(bull|bear)\b", line, re.I)
        line_symbols = re.findall(r"\$([A-Za-z][\w.]*)", line)
        if stance and len(line_symbols) == 1:
            target = _target_on_line(line)
            item = {"type": stance.group(1).lower(), "symbol": line_symbols[0].upper()}
            if target is not None:
                item.update(target=target, target_type="security_price", target_unit="USD")
            stances.append(item)
    if not pair and not stances:
        stance = re.search(r"@(bull|bear)\b", clean, re.I)
        if stance and len(tickers) == 1:
            stances.append({"type": stance.group(1).lower(), "symbol": tickers[0]})
        elif stance and len(tickers) > 1:
            warnings.append("Multiple tickers make the stance ambiguous. Put each stance on the same line as its ticker.")
    calls.extend(stances)
    # Targets not tied to a call are retained in metadata so original prose is preserved.
    targets = [_target_on_line(line) for line in clean.splitlines()]
    orphan_targets = [value for value in targets if value is not None] if not calls else []
    if orphan_targets:
        warnings.append("Target syntax without a tracked call was stored as note metadata.")
    return {"note_type": note_type, "clean_body": clean, "tags": tags, "ticker_mentions": tickers, "tracked_calls": calls, "note_targets": orphan_targets, "warnings": warnings, "errors": [] if clean else ["Note body is required."]}


def capture_title(parsed: dict) -> str:
    """Derive a human-readable title from the first line of a quick capture."""
    first_line = (parsed.get("clean_body") or "").splitlines()[0] if parsed.get("clean_body") else ""
    without_metadata = re.sub(r"https?://[^\s)\]}>,]+", "", first_line, flags=re.I)
    without_metadata = re.sub(r"\$[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z])?", "", without_metadata)
    without_metadata = re.sub(r"#[\w-]+", "", without_metadata)
    without_metadata = re.sub(r"\s+", " ", without_metadata).strip(" -–—|·")
    return without_metadata[:500]


def _target_on_line(line: str) -> float | None:
    """Return one deterministic @target number (price or percentage) from a line."""
    number = r"([+-]?\$?[0-9][0-9,]*(?:\.[0-9]+)?%?)"
    match = re.search(number + r"\s*@target\b|@target\s*" + number, line, re.I)
    if not match:
        return None
    raw = next(value for value in match.groups() if value is not None)
    percent = raw.endswith("%")
    value = float(raw.replace("$", "").replace("%", "").replace(",", ""))
    if (not percent and value <= 0) or (percent and value == 0):
        return None
    return value / 100 if percent else value
