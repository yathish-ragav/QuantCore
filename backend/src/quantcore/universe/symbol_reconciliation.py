from __future__ import annotations

import re


def symbol_aliases(symbol: str) -> set[str]:
    """Return deterministic cross-provider symbol representations.

    SEC and vendor feeds use different punctuation/conventions for some
    security symbols. These aliases are formatting representations only;
    they never change the underlying issuer CIK or security type.

    The mappings cover observed conventions:
    - punctuation-insensitive representation (e.g. ABR-PD <-> ABRPD)
    - SEC unit/warrant/rights suffixes to Massive notation
    - SEC single-letter share classes to vendor dot notation
    """
    normalized = symbol.strip().upper()
    aliases = {normalized}
    compact = re.sub(r"[^A-Z0-9]", "", normalized)
    if compact:
        aliases.add(compact)

    if "-" not in normalized:
        return aliases

    base, suffix = normalized.rsplit("-", 1)
    if not base or not suffix:
        return aliases

    if suffix == "UN":
        aliases.add(f"{base}.U")
    elif suffix == "WT":
        aliases.add(f"{base}.WS")
    elif suffix == "WTA":
        aliases.add(f"{base}.WS.A")
    elif suffix == "RI":
        aliases.add(f"{base}R")
    elif len(suffix) == 1 and suffix.isalpha():
        aliases.add(f"{base}.{suffix}")

    return aliases
