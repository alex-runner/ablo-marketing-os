#!/usr/bin/env python3
"""Coverage Reconciler tests (stdlib only — no deps).

Run:  python3 tests/test_coverage.py

Covers the spec's required cases:
  - reconcile_coverage (pure): blind appears, ignored doesn't, stale detected,
    threshold filters low-volume noise.
  - registry write discipline: a no-op leaves the file byte-identical (no write);
    a real change writes once with stable key + member order.
  - v1 never auto-wires: an experiment-looking task + an event cluster both land in
    blindSpots with status 'escalated', autowired stays [], content.json untouched.
  - regression fixtures (the two real misses): tbs_* surfaces as an escalated events
    blind spot; a synthetic 'Experiment: X — A/B test' ClickUp task surfaces as
    escalated (NOT auto-stubbed).
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Import build.py from the repo root (this file lives in tests/).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402


# A small, fixed registry the pure-differ tests diff against.
def base_registry():
    return {
        "version": 1,
        "updated": "2026-06-04",
        "dimensions": {
            "events": {
                "modeled": ["$pageview", "cta_clicked", "signup_completed"],
                "ignore": ["$web_vitals", "$autocapture"],
                "ignoreReasons": {"$web_vitals": "noise", "$autocapture": "noise"},
                "minUsers30d": 10,
            },
            "experiments": {
                "modeled": ["PH-374260", "OS-TRY-VS-HOME"],
                "clickupMapped": {"OS-TRY-VS-HOME": "86ba9n6my"},
                "ignore": ["86zzignore1"],
                "ignoreReasons": {"86zzignore1": "not an experiment"},
            },
        },
        "clickupTasks": {
            "modeled": ["86referenced1"],
            "ignore": ["86ignored1"],
            "ignoreReasons": {"86ignored1": "ops task"},
            "list": "901415977874",
        },
    }


def task(tid, name, status="to do"):
    """Shape a ClickUp 'open' feed row the way fetch_clickup emits it."""
    return {"id": tid, "name": name, "status": status,
            "url": f"https://app.clickup.com/t/{tid}", "due": ""}


class ReconcilePure(unittest.TestCase):
    def test_blind_ignored_stale_and_threshold(self):
        reg = base_registry()
        scans = {
            "events": {
                "$pageview": {"users": 900, "count": 5000},     # modeled -> not blind
                "cta_clicked": {"users": 196, "count": 400},     # modeled
                "$web_vitals": {"users": 591, "count": 9000},    # ignored -> not blind
                "onboarding_started": {"users": 40, "count": 80},   # blind cluster (>= threshold)
                "onboarding_step_viewed": {"users": 30, "count": 60},
                "low_volume_thing": {"users": 3, "count": 4},    # below threshold -> filtered
                "signup_completed": {"users": 80, "count": 120}, # modeled
            },
            "experiments": None,  # skipped
            "clickup": None,      # skipped
        }
        diff = build.reconcile_coverage(reg, scans)
        keys = {b["key"] for b in diff["blindSpots"]}
        # The onboarding_* cluster appears as one ranked blind spot.
        self.assertIn("onboarding_*", keys)
        # Known-ignored and modeled events do NOT appear.
        self.assertNotIn("$web_vitals", keys)
        self.assertNotIn("$pageview", keys)
        # Threshold filters the low-volume single.
        self.assertNotIn("low_volume_thing", keys)
        # Every blind item is escalated in v1.
        for b in diff["blindSpots"]:
            self.assertEqual(b["status"], "escalated")

    def test_stale_only_for_succeeded_dimension(self):
        reg = base_registry()
        # cta_clicked is modeled but missing from the live scan -> stale.
        scans = {"events": {"$pageview": {"users": 900, "count": 5000},
                            "signup_completed": {"users": 80, "count": 120}},
                 "experiments": None, "clickup": None}
        diff = build.reconcile_coverage(reg, scans)
        stale_keys = {s["key"] for s in diff["stale"]}
        self.assertIn("cta_clicked", stale_keys)

    def test_failed_pull_emits_no_false_stale(self):
        reg = base_registry()
        # events scan failed (None) -> NO stale entries for events at all.
        scans = {"events": None, "experiments": None, "clickup": None}
        diff = build.reconcile_coverage(reg, scans)
        self.assertEqual(diff["stale"], [])
        self.assertEqual(diff["blindSpots"], [])

    def test_blind_ranked_by_volume(self):
        reg = base_registry()
        scans = {"events": {
            "alpha_one": {"users": 20, "count": 30},
            "beta_one": {"users": 60, "count": 90},
        }, "experiments": None, "clickup": None}
        diff = build.reconcile_coverage(reg, scans)
        vols = [b["volume"] for b in diff["blindSpots"]]
        self.assertEqual(vols, sorted(vols, reverse=True))


class WriteDiscipline(unittest.TestCase):
    def _with_temp_registry(self, fn):
        with tempfile.TemporaryDirectory() as d:
            old = build.REGISTRY
            build.REGISTRY = Path(d) / "coverage-registry.json"
            try:
                fn(build.REGISTRY)
            finally:
                build.REGISTRY = old

    def test_noop_is_byte_identical(self):
        def go(path):
            reg = base_registry()
            self.assertTrue(build.write_registry_if_changed(reg, "2026-06-04"))
            first = path.read_bytes()
            # Re-running with identical structural content must NOT rewrite.
            wrote = build.write_registry_if_changed(reg, "2026-06-05")  # different date
            self.assertFalse(wrote, "a no-op build must not write the registry")
            self.assertEqual(path.read_bytes(), first, "no-op left the file changed")
        self._with_temp_registry(go)

    def test_real_change_writes_once_with_stable_order(self):
        def go(path):
            reg = base_registry()
            build.write_registry_if_changed(reg, "2026-06-04")
            # A genuine change: add a modeled event.
            reg2 = base_registry()
            reg2["dimensions"]["events"]["modeled"].append("aaa_new_event")
            wrote = build.write_registry_if_changed(reg2, "2026-06-10")
            self.assertTrue(wrote, "a real change must write")
            on_disk = json.loads(path.read_bytes())
            # updated bumped to the change date.
            self.assertEqual(on_disk["updated"], "2026-06-10")
            # Members are sorted (stable order) regardless of append position.
            modeled = on_disk["dimensions"]["events"]["modeled"]
            self.assertEqual(modeled, sorted(modeled))
            self.assertIn("aaa_new_event", modeled)
        self._with_temp_registry(go)

    def test_noop_does_not_bump_updated(self):
        def go(path):
            reg = base_registry()
            reg["updated"] = "2026-01-01"
            build.write_registry_if_changed(reg, "2026-01-01")
            before = path.read_bytes()
            # Same content, later run date -> must stay byte-identical, updated unchanged.
            build.write_registry_if_changed(base_registry(), "2026-12-31")
            self.assertEqual(path.read_bytes(), before)
        self._with_temp_registry(go)


class NoAutowireV1(unittest.TestCase):
    def test_autowire_is_noop(self):
        reg = base_registry()
        diff = {"blindSpots": [{"key": "x", "dimension": "events", "status": "escalated"}],
                "stale": []}
        out_reg, autowired = build.autowire_coverage(reg, diff, {})
        self.assertEqual(autowired, [])
        self.assertEqual(out_reg, reg)

    def test_experiment_task_and_event_cluster_both_escalate(self):
        reg = base_registry()
        scans = {
            "events": {"newflow_a": {"users": 50, "count": 90},
                       "newflow_b": {"users": 30, "count": 40}},
            "experiments": {"posthog": [],
                            "clickupCandidates": [
                                {"id": "86newexp", "name": "Experiment: pricing A/B test",
                                 "url": "https://app.clickup.com/t/86newexp"}]},
            "clickup": [],
        }
        diff = build.reconcile_coverage(reg, scans)
        statuses = {b["key"]: b["status"] for b in diff["blindSpots"]}
        self.assertEqual(statuses.get("newflow_*"), "escalated")
        self.assertEqual(statuses.get("86newexp"), "escalated")
        # And v1 auto-wires nothing.
        _, autowired = build.autowire_coverage(reg, diff, {})
        self.assertEqual(autowired, [])

    def test_build_coverage_never_writes_content_json(self):
        """build_coverage must only ever touch the registry, never content.json."""
        content_path = build.CONTENT
        before = content_path.read_bytes()
        # Run the full orchestrator against a throwaway registry path so it can
        # write the registry without disturbing the repo file.
        with tempfile.TemporaryDirectory() as d:
            old = build.REGISTRY
            build.REGISTRY = Path(d) / "coverage-registry.json"
            try:
                clickup = {"open": [task("86newexp", "Experiment: foo — A/B test")]}
                cov = build.build_coverage({}, [], clickup, "2026-06-04")
            finally:
                build.REGISTRY = old
        self.assertEqual(content_path.read_bytes(), before, "content.json must never change")
        self.assertEqual(cov["autowired"], [])


class RegressionTwoMisses(unittest.TestCase):
    """The two real 2026-06-04 misses must surface as escalated blind spots."""

    def test_tbs_cluster_surfaces_as_escalated_events_blind_spot(self):
        reg = base_registry()
        # Real-ish tbs_* taxonomy from PostHog; tbs is deliberately NOT modeled.
        scans = {"events": {
            "tbs_page_viewed": {"users": 89, "count": 200},
            "tbs_category_selected": {"users": 54, "count": 120},
            "tbs_garment_added": {"users": 43, "count": 80},
            "tbs_generate_clicked": {"users": 25, "count": 40},
            "tbs_signup_wall_shown": {"users": 24, "count": 30},
            "$pageview": {"users": 900, "count": 5000},  # modeled
        }, "experiments": None, "clickup": None}
        diff = build.reconcile_coverage(reg, scans)
        tbs = next((b for b in diff["blindSpots"] if b["key"] == "tbs_*"), None)
        self.assertIsNotNone(tbs, "tbs_* must surface as a blind spot")
        self.assertEqual(tbs["dimension"], "events")
        self.assertEqual(tbs["status"], "escalated")
        self.assertTrue(tbs["cluster"])
        self.assertEqual(tbs["volume"], 89)  # cluster reach = busiest tbs_ event

    def test_synthetic_experiment_task_escalates_not_autostubbed(self):
        reg = base_registry()
        scans = {
            "events": None,
            "experiments": {"posthog": [],
                            "clickupCandidates": [
                                {"id": "86synthxp",
                                 "name": "Experiment: X — A/B test",
                                 "url": "https://app.clickup.com/t/86synthxp"}]},
            "clickup": None,
        }
        diff = build.reconcile_coverage(reg, scans)
        b = next((x for x in diff["blindSpots"] if x["key"] == "86synthxp"), None)
        self.assertIsNotNone(b, "synthetic experiment task must surface")
        self.assertEqual(b["dimension"], "experiments")
        self.assertEqual(b["status"], "escalated")
        # Not auto-stubbed: nothing auto-wired.
        _, autowired = build.autowire_coverage(reg, diff, {})
        self.assertEqual(autowired, [])

    def test_mapped_experiment_task_does_not_resurface(self):
        """The already-mapped /try task (86ba9n6my) must NOT escalate again."""
        reg = base_registry()
        scans = {
            "events": None,
            "experiments": {"posthog": ["PH-374260", "OS-TRY-VS-HOME"],
                            "clickupCandidates": [
                                {"id": "86ba9n6my",
                                 "name": "Experiment: /try landing vs homepage — paid A/B test",
                                 "url": "https://app.clickup.com/t/86ba9n6my"}]},
            "clickup": None,
        }
        diff = build.reconcile_coverage(reg, scans)
        keys = {b["key"] for b in diff["blindSpots"]}
        self.assertNotIn("86ba9n6my", keys)
        self.assertNotIn("PH-374260", keys)
        self.assertNotIn("OS-TRY-VS-HOME", keys)


class ClickupDimension(unittest.TestCase):
    def test_unreferenced_open_task_surfaces(self):
        reg = base_registry()
        scans = {"events": None, "experiments": None,
                 "clickup": [{"id": "86unref", "name": "Some marketing task",
                              "url": "https://app.clickup.com/t/86unref", "status": "to do"}]}
        diff = build.reconcile_coverage(reg, scans)
        keys = {b["key"]: b for b in diff["blindSpots"]}
        self.assertIn("86unref", keys)
        self.assertEqual(keys["86unref"]["dimension"], "clickup")
        self.assertEqual(keys["86unref"]["status"], "escalated")

    def test_ignored_clickup_task_does_not_surface(self):
        reg = base_registry()
        scans = {"events": None, "experiments": None,
                 "clickup": [{"id": "86ignored1", "name": "Ops task",
                              "url": "https://app.clickup.com/t/86ignored1", "status": "to do"}]}
        diff = build.reconcile_coverage(reg, scans)
        self.assertNotIn("86ignored1", {b["key"] for b in diff["blindSpots"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
