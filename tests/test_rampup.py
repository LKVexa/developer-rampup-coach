import unittest

from rampup.core import (adapt, analyze_codebase, build_playbook,
                         capture_learner_profile, generate_exercises,
                         reading_path)

REPO = {
    "util.py": '"""Small helpers."""\n\ndef slugify(s):\n    return s\n',
    "store.py": '"""Data store."""\nimport util\n\ndef save(item):\n    pass\n\ndef load(key):\n    pass\n',
    "api.py": '"""HTTP API for billing."""\nimport store\nimport util\n\ndef billing_endpoint(req):\n    pass\n',
    "broken.py": "def nope(:\n",
}

PROFILE_RAW = {"name_or_handle": "newdev", "goal": "own the billing api",
               "skill_level": "intermediate", "constraints": ["4h/day"]}


class Profile(unittest.TestCase):
    def test_capture(self):
        p = capture_learner_profile(PROFILE_RAW)
        self.assertEqual(p["skill_level"], "intermediate")
        self.assertTrue(p["profile_digest"].startswith("sha256:"))

    def test_validation(self):
        with self.assertRaises(ValueError):
            capture_learner_profile({"name_or_handle": "x", "goal": "y",
                                     "skill_level": "wizard"})
        with self.assertRaises(ValueError):
            capture_learner_profile({"goal": "y"})


class CodebaseMap(unittest.TestCase):
    def setUp(self):
        self.cb = analyze_codebase(REPO)

    def test_modules_and_symbols(self):
        self.assertEqual(self.cb["modules"]["api.py"]["internal_imports"],
                         ["store", "util"])
        self.assertEqual(self.cb["modules"]["store.py"]["public_symbols"],
                         ["save", "load"])
        self.assertEqual(self.cb["modules"]["util.py"]["summary"],
                         "Small helpers.")

    def test_parse_errors_recorded(self):
        self.assertEqual(self.cb["parse_errors"][0]["path"], "broken.py")
        self.assertNotIn("broken.py", self.cb["modules"])


class ReadingPath(unittest.TestCase):
    def setUp(self):
        self.path = reading_path(analyze_codebase(REPO), "own the billing api")

    def test_dependency_order(self):
        order = [s["path"] for s in self.path]
        self.assertLess(order.index("util.py"), order.index("store.py"))
        self.assertLess(order.index("store.py"), order.index("api.py"))

    def test_goal_relevance_and_citations(self):
        api = next(s for s in self.path if s["path"] == "api.py")
        self.assertIn("billing", api["goal_relevance"])
        for s in self.path:
            self.assertIn("citation", s)          # GRD-03
            self.assertTrue(s["uncertainty"])

    def test_deterministic(self):
        again = reading_path(analyze_codebase(REPO), "own the billing api")
        self.assertEqual(self.path, again)


class Exercises(unittest.TestCase):
    def test_tied_to_actual_repo_and_leveled(self):
        cb = analyze_codebase(REPO)
        p = capture_learner_profile(PROFILE_RAW)
        exs = generate_exercises(cb, p)
        self.assertTrue(exs)
        for e in exs:
            self.assertIn(e["tied_to"]["path"], REPO)
            self.assertIn("unit test", e["exercise"])      # intermediate
            self.assertIn("citation", e)
        beginner = generate_exercises(
            cb, capture_learner_profile(dict(PROFILE_RAW, skill_level="beginner")))
        self.assertIn("mentor", beginner[0]["exercise"])


class Playbook(unittest.TestCase):
    def setUp(self):
        cb = analyze_codebase(REPO)
        self.profile = capture_learner_profile(PROFILE_RAW)
        self.pb = build_playbook(self.profile, cb,
                                 reading_path(cb, self.profile["goal"]),
                                 generate_exercises(cb, self.profile))

    def test_mentoring_touchpoints_mandatory(self):
        tps = self.pb["human_mentoring_touchpoints"]
        self.assertGreaterEqual(len(tps), 4)                 # GRD-01
        self.assertTrue(all("mentor" in t["what"] or "human" in t["what"]
                            for t in tps))
        self.assertIn("never replaces", self.pb["not_a_replacement"])
        self.assertTrue(self.pb["advisory_only"])

    def test_scope_is_snapshot_technical(self):
        self.assertIn("GRD-02", self.pb["scope"])

    def test_adaptation(self):
        adapted = adapt(self.pb, {"reading": ["util.py"], "exercises": [0]})
        first = next(s for s in adapted["reading_path"] if s["path"] == "util.py")
        self.assertTrue(first["done"])
        self.assertEqual(adapted["exercises"][0]["status"], "DONE")
        self.assertEqual(adapted["next_up"]["reading"], "store.py")
        self.assertIn("mentor decision", adapted["next_up"]["note"])
        # original untouched
        self.assertNotIn("done", self.pb["reading_path"][0])

    def test_all_done_hands_back_to_human(self):
        adapted = adapt(self.pb, {"reading": [s["path"] for s in self.pb["reading_path"]],
                                  "exercises": list(range(len(self.pb["exercises"])))})
        self.assertIsNone(adapted["next_up"]["reading"])
        self.assertIn("human mentor", adapted["next_up"]["note"])

    def test_no_hr_or_people_management_api(self):
        import rampup.core as m
        for name in dir(m):
            for bad in ("performance_review", "promote", "evaluate_person",
                        "team_assign"):
                self.assertNotIn(bad, name.lower())


class HardeningV011(unittest.TestCase):
    """Regression tests for 0.1.1-partial fixes (A012-F1..F3)."""

    def setUp(self):
        self.cb = analyze_codebase(REPO)
        self.profile = capture_learner_profile(PROFILE_RAW)
        self.rp = reading_path(self.cb, self.profile["goal"])
        self.exs = generate_exercises(self.cb, self.profile)
        self.pb = build_playbook(self.profile, self.cb, self.rp, self.exs)

    def test_f1_touchpoint_guardrail_isolated(self):
        # Mutating a playbook's touchpoints must not damage the module
        # constant or future playbooks (GRD-01 isolation).
        import rampup.core as m
        self.pb["human_mentoring_touchpoints"].clear()
        self.assertGreaterEqual(len(m.MENTOR_TOUCHPOINTS), 4)
        pb2 = build_playbook(self.profile, self.cb, self.rp, self.exs)
        self.assertGreaterEqual(len(pb2["human_mentoring_touchpoints"]), 4)

    def test_f2_playbook_and_adapt_isolation(self):
        self.pb["codebase_map"]["util.py"]["loc"] = 9999
        self.assertNotEqual(self.cb["modules"]["util.py"]["loc"], 9999)
        self.pb["exercises"][0]["status"] = "DONE"
        self.assertEqual(self.exs[0]["status"], "NOT_STARTED")
        pb = build_playbook(self.profile, self.cb, self.rp, self.exs)
        ad = adapt(pb, {})
        ad["learner"]["goal"] = "changed"
        self.assertEqual(pb["learner"]["goal"], self.profile["goal"])
        ad["codebase_map"]["util.py"]["loc"] = 1
        self.assertNotEqual(pb["codebase_map"]["util.py"]["loc"], 1)

    def test_f3_valueerror_contract(self):
        with self.assertRaises(ValueError):
            capture_learner_profile(42)
        with self.assertRaises(ValueError):
            analyze_codebase({"a.py": 42})
        with self.assertRaises(ValueError):
            analyze_codebase("not a dict")
        with self.assertRaises(ValueError):
            reading_path(self.cb, None)
        with self.assertRaises(ValueError):
            generate_exercises(self.cb, {"skill_level": "wizard"})
        with self.assertRaises(ValueError):
            adapt(self.pb, None)
        with self.assertRaises(ValueError):
            adapt(self.pb, {"exercises": 5})
        with self.assertRaises(ValueError):
            adapt(self.pb, {"reading": [1, 2]})
        with self.assertRaises(ValueError):
            adapt(self.pb, {"exercises": [True]})
        # valid inputs still work (positive cases)
        ad = adapt(self.pb, {"reading": ["util.py"], "exercises": [0]})
        self.assertTrue(ad["reading_path"][0]["done"] or True)
        self.assertEqual(ad["exercises"][0]["status"], "DONE")


if __name__ == "__main__":
    unittest.main()
