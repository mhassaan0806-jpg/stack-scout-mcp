"""Classify a repo's license: is it really free to build with?

Categories (and points toward the 0-100 health score):
    permissive     20  MIT, Apache, BSD... use anywhere, even commercially
    weak-copyleft  15  MPL, LGPL... free; changes to the library itself must be shared
    open-core      14  free license plus some paid "enterprise" parts (found from LICENSE text)
    copyleft        8  GPL/AGPL... free, but your app may have to be open-sourced too
    unknown         0  no license detected: legally, no permission to use. Warn.
    not-free       --  source-available with use restrictions (BUSL, SSPL...). Reject.

CLI:
    python tools/license_check.py MIT AGPL-3.0 BUSL-1.1 NOASSERTION
"""
from __future__ import annotations

import json
import re
import sys

PERMISSIVE = {
    "MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD", "Unlicense",
    "Zlib", "BSL-1.0", "CC0-1.0", "PostgreSQL", "Python-2.0", "UPL-1.0", "Artistic-2.0", "WTFPL",
}
WEAK_COPYLEFT = {"MPL-2.0", "LGPL-2.1", "LGPL-3.0", "EPL-1.0", "EPL-2.0", "CDDL-1.0"}
COPYLEFT = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "EUPL-1.2", "OSL-3.0"}
NOT_FREE = {
    "BUSL-1.1", "SSPL-1.0", "Elastic-2.0", "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0",
    "PolyForm-Noncommercial-1.0.0", "PolyForm-Small-Business-1.0.0",
}

POINTS = {"permissive": 20, "open-core": 14, "weak-copyleft": 15, "copyleft": 8, "unknown": 0, "not-free": 0}

# For repos GitHub labels "Other": recognise the license from the LICENSE file text.
# Restrictive licenses come first so a "Commons Clause on top of MIT" file counts as not free.
_TEXT_RULES = [
    ("Commons-Clause", r"commons clause"),
    ("BUSL-1.1", r"business source license"),
    ("SSPL-1.0", r"server side public license"),
    ("Elastic-2.0", r"elastic license"),
    ("FSL-1.1", r"functional source license"),
    ("PolyForm-Noncommercial-1.0.0", r"polyform noncommercial"),
    ("AGPL-3.0", r"gnu affero general public license"),
    ("LGPL-3.0", r"gnu lesser general public license"),
    ("GPL-3.0", r"gnu general public license"),
    ("MPL-2.0", r"mozilla public license"),
    ("Apache-2.0", r"apache license,?\s+version 2\.0"),
    ("MIT", r"permission is hereby granted,\s+free of charge|\bmit licen[cs]e\b"),
    ("ISC", r"permission to use, copy, modify,? and/or distribute this software for any purpose"),
    ("BSD-3-Clause", r"redistribution and use in source and binary forms"),
]
# Free license + paid extras. Phrases that only appear when a file splits the code into parts.
_OPEN_CORE = r"enterprise edition|enterprise license|commercial license|proprietary license|\bee/|\(ee\)"
_PARTS = r"part(?:s)? of this (?:work|software|repository|project)|portions of this software|other parts|enterprise edition|\bee/|\(ee\)"
# User may pick any one of several licenses (e.g. Elasticsearch: AGPL or SSPL or Elastic).
_CHOICE = r"dual[- ]licen|triple[- ]licen|at your (?:option|election)|your choice of"
# BUSL / FSL: each version turns into a free license after a delay.
_DELAYED = r"future license|change license|change date"
NOT_FREE.update({"Commons-Clause", "FSL-1.1"})
_FREE_CATEGORIES = ("permissive", "weak-copyleft", "copyleft")


def classify(spdx_id: str | None) -> dict:
    spdx = (spdx_id or "").strip()
    if spdx in PERMISSIVE:
        category, note = "permissive", "Free to use, even commercially. Keep the copyright notice."
    elif spdx in WEAK_COPYLEFT:
        category, note = "weak-copyleft", "Free to use. If you modify this library's own files, share those changes."
    elif spdx == "AGPL-3.0":
        category, note = "copyleft", (
            "Free, but if you modify it and run it as a web service, you must publish your changes. "
            "Fine to self-host unmodified."
        )
    elif spdx in COPYLEFT:
        category, note = "copyleft", "Free, but if you distribute an app that includes it, your app must be GPL too."
    elif spdx in NOT_FREE:
        category, note = "not-free", "Source-available, not open source: restricts commercial or SaaS use."
    else:
        category = "unknown"
        note = (
            "License not recognised by GitHub ('Other' or missing). Read the LICENSE file before using it: "
            "no license means no permission."
        )
    return {"spdx": spdx or None, "category": category, "points": POINTS[category], "note": note}


def _open_core(free_spdx: str, paid: str) -> dict:
    return {
        "spdx": free_spdx, "category": "open-core", "points": POINTS["open-core"],
        "note": (f"Open core: mostly {free_spdx}, but some parts (usually 'enterprise' features) are under "
                 f"{paid}. The free core is fine to use; check that the features you need are in it."),
    }


def classify_text(text: str) -> dict:
    """Classify a LICENSE file's text.

    - only a restrictive license (BUSL, SSPL...)          -> not-free
    - a free license + a restrictive one for some parts   -> open-core (e.g. MIT core, BUSL enterprise)
    - a free license + 'enterprise edition' / ee/ folder  -> open-core
    - a free license alone                                -> its normal category
    """
    lowered = " ".join(text.lower().split())
    found = [spdx for spdx, pattern in _TEXT_RULES if re.search(pattern, lowered)]
    if not found:
        return classify(None)
    restrictive = [s for s in found if s in NOT_FREE]
    free = [s for s in found if classify(s)["category"] in _FREE_CATEGORIES]
    if restrictive and free and re.search(_CHOICE, lowered):
        result = classify(free[0])
        result["note"] = (f"You can choose {free[0]} (free) instead of the restrictive options "
                          f"({', '.join(restrictive)}). {result['note']}")
    elif restrictive and free and re.search(_PARTS, lowered):
        result = _open_core(free[-1], f"a restrictive license ({restrictive[0]})")
    elif restrictive:
        result = classify(restrictive[0])
        if free and re.search(_DELAYED, lowered):
            result["note"] += (f" Each version becomes {free[-1]} after a delay (FSL: 2 years, BUSL: up to 4); "
                               "until then, competing or commercial use is restricted.")
    else:
        result = classify(found[0])
        if result["category"] in ("permissive", "weak-copyleft") and re.search(_OPEN_CORE, lowered):
            result = _open_core(found[0], "a paid or proprietary license")
    result["detected_from"] = "LICENSE file"
    return result


if __name__ == "__main__":
    print(json.dumps([classify(a) for a in sys.argv[1:]] or classify(None), indent=2))
