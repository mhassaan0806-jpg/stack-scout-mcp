"""Offline tests: no network. Run with  python -m unittest discover tests"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stack_scout_mcp.tools.format_report import format_report  # noqa: E402
from stack_scout_mcp.tools.license_check import classify, classify_text  # noqa: E402
from stack_scout_mcp.tools.plan_components import plan_components  # noqa: E402
from stack_scout_mcp.tools.rank_tools import rank  # noqa: E402
from stack_scout_mcp.tools.repo_health import assess  # noqa: E402
from stack_scout_mcp.tools.research_tool import readme_signals  # noqa: E402
from stack_scout_mcp.tools.scout_stack import search_terms  # noqa: E402

NOW = datetime(2026, 11, 22, tzinfo=timezone.utc)
MIT_BODY = ("Permission is hereby granted, free of charge, to any person obtaining a copy of this software "
            "and associated documentation files")


def repo(name="acme/widget", stars=5000, days_ago=10, license="MIT", archived=False, **extra):
    pushed = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"full_name": name, "url": f"https://github.com/{name}", "description": "A widget",
            "stars": stars, "license": license, "pushed_at": pushed, "archived": archived,
            "fork": False, "open_issues": 3, "homepage": None, **extra}


class LicenseTests(unittest.TestCase):
    def test_spdx_categories(self):
        self.assertEqual(classify("MIT")["category"], "permissive")
        self.assertEqual(classify("MPL-2.0")["category"], "weak-copyleft")
        self.assertEqual(classify("AGPL-3.0")["category"], "copyleft")
        self.assertEqual(classify("BUSL-1.1")["category"], "not-free")
        self.assertEqual(classify("NOASSERTION")["category"], "unknown")
        self.assertEqual(classify(None)["category"], "unknown")

    def test_text_plain_mit(self):
        self.assertEqual(classify_text("MIT License\n\n" + MIT_BODY)["category"], "permissive")

    def test_text_open_core(self):
        text = ("Except for the Enterprise Edition materials identified in ENTERPRISE-LICENSE.md, the repository "
                "is licensed under the MIT License below.\n" + MIT_BODY)
        result = classify_text(text)
        self.assertEqual(result["category"], "open-core")
        self.assertEqual(result["spdx"], "MIT")

    def test_text_restrictive_wins(self):
        text = "Business Source License 1.1\nLicensor: Acme\n" + MIT_BODY
        self.assertEqual(classify_text(text)["category"], "not-free")
        self.assertEqual(classify_text('"Commons Clause" License Condition v1.0\n' + MIT_BODY)["category"], "not-free")

    def test_text_open_core_with_busl_enterprise_part(self):  # Meilisearch-style
        text = ("Part of this work fall under the Enterprise Edition (EE) and are licensed under the Business "
                "Source License 1.1. The other parts of this work are licensed under the MIT license.")
        self.assertEqual(classify_text(text)["category"], "open-core")

    def test_text_delayed_free_license_is_still_not_free(self):  # Sentry-style FSL
        text = ("# Functional Source License, Version 1.1, Apache 2.0 Future License\n"
                "...except for the Competing Use restriction... Apache License, Version 2.0")
        result = classify_text(text)
        self.assertEqual(result["category"], "not-free")
        self.assertIn("after a delay", result["note"])

    def test_text_choice_of_licenses_uses_free_option(self):  # Elasticsearch-style
        text = ('covered by a triple license under the "GNU Affero General Public License v3.0 only", '
                '"the Server Side Public License, v 1", and the "Elastic License 2.0"')
        result = classify_text(text)
        self.assertEqual((result["spdx"], result["category"]), ("AGPL-3.0", "copyleft"))

    def test_text_unrecognised(self):
        self.assertEqual(classify_text("All rights reserved.")["category"], "unknown")

    def test_gpl_mentioning_proprietary_is_not_open_core(self):
        text = "GNU General Public License ... incorporating your program into proprietary programs"
        self.assertEqual(classify_text(text)["category"], "copyleft")


class HealthTests(unittest.TestCase):
    def test_healthy(self):
        h = assess(repo(), now=NOW)
        self.assertEqual(h["status"], "ok")
        self.assertGreater(h["score"], 80)

    def test_rejections(self):
        self.assertEqual(assess(repo(archived=True), now=NOW)["status"], "rejected")
        self.assertEqual(assess(repo(days_ago=800), now=NOW)["status"], "rejected")
        self.assertEqual(assess(repo(license="SSPL-1.0"), now=NOW)["status"], "rejected")
        self.assertEqual(assess(repo(name="someone/awesome-widgets"), now=NOW)["status"], "rejected")
        self.assertEqual(assess(repo(name="someone/30-days-of-code"), now=NOW)["status"], "rejected")

    def test_cautions(self):
        self.assertEqual(assess(repo(days_ago=400), now=NOW)["status"], "caution")
        self.assertEqual(assess(repo(license=None), now=NOW)["status"], "caution")
        self.assertEqual(assess(repo(stars=40), now=NOW)["status"], "caution")

    def test_license_info_overrides_github_label(self):
        info = classify_text("Enterprise license applies to /ee/ directory.\n" + MIT_BODY)
        h = assess(repo(license="NOASSERTION", license_info=info), now=NOW)
        self.assertEqual(h["license"]["category"], "open-core")
        self.assertTrue(any("Open core" in w for w in h["warnings"]))

    def test_rank_drops_rejected_and_sorts(self):
        cands = [repo("a/small", stars=60), repo("b/big", stars=90000), repo("c/dead", archived=True)]
        out = rank(cands, top_n=3)
        self.assertEqual([r["full_name"] for r in out["top"]][0], "b/big")
        self.assertEqual([r["full_name"] for r in out["rejected"]], ["c/dead"])


class PlanningTests(unittest.TestCase):
    def test_store_archetype(self):
        ids = [c["id"] for c in plan_components("I want to build an online shoe store")["components"]]
        self.assertIn("ecommerce", ids)
        self.assertIn("payments", ids)

    def test_unknown_request_is_searched_as_typed(self):
        comps = plan_components("a 2D game engine")["components"]
        self.assertEqual(comps[0]["id"], "a 2D game engine")
        self.assertEqual(len(comps), 1)  # not an app, so no generic app blocks

    def test_unknown_app_gets_common_blocks(self):
        ids = [c["id"] for c in plan_components("an app for dog walkers")["components"]]
        self.assertIn("auth", ids)

    def test_whole_word_matching(self):
        ids = [c["id"] for c in plan_components("a cartoon drawing tool")["components"]]
        self.assertNotIn("ecommerce", ids)  # 'cart' must not match 'cartoon'

    def test_search_terms(self):
        self.assertEqual(search_terms("extract text from PDF files in python"),
                         (["extract", "text", "pdf"], "Python"))
        self.assertEqual(search_terms("I want a 2D game engine"), (["2d", "game", "engine"], None))


class ReadmeAndReportTests(unittest.TestCase):
    README = """# Widget
![badge](https://img.shields.io/x)
Widget is a fast, self-hostable widget server for your apps.

## Cloud
Prefer not to self-host? Try Widget Cloud, our managed cloud service with a free tier.

## Install
```
docker compose up   # starts postgres and redis
```
Requires PostgreSQL 14+ and Redis. This project is in beta and has breaking changes between versions.
"""

    def test_readme_signals(self):
        s = readme_signals(self.README)
        self.assertTrue(s["summary"].startswith("Widget is a fast"))
        self.assertTrue(any("managed cloud service" in m for m in s["paid_mentions"]))
        self.assertTrue(any("beta" in m for m in s["maturity_flags"]))
        for need in ("Docker", "PostgreSQL", "Redis"):
            self.assertIn(need, s["mentions_needing"])

    def test_report_renders(self):
        r = repo()
        r["health"] = assess(r, now=NOW)
        r["research"] = {"readme": readme_signals(self.README), "latest_release": {"title": "v1.2", "date": "2026-11-01"},
                         "scorecard": {"score": 6.1, "checks": {"Fuzzing": 0, "Maintained": 10}},
                         "package": {"system": "NPM", "name": "widget", "downloads": {"count": 123456, "period": "last month"},
                                     "advisories": {"version": "1.2.0", "count": 0, "ids": []}},
                         "hacker_news": {"stories": 1, "top": [{"title": "Show HN: Widget", "points": 120, "comments": 40,
                                                               "year": "2025", "url": "https://news.ycombinator.com/item?id=1"}]},
                         "unavailable": []}
        md = format_report({"idea": "test", "generated_at": "now", "components": [
            {"id": "x", "name": "Widgets", "query": "topic:x", "top": [r], "rejected": [], "considered": 1}]})
        for expected in ("acme/widget", "123.5k downloads last month", "6.1/10", "Fuzzing 0/10",
                         "Show HN: Widget", "managed cloud service", "For the AI presenting this"):
            self.assertIn(expected, md)


if __name__ == "__main__":
    unittest.main()
