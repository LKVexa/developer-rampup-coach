import copy
import unittest
from unittest.mock import patch
from rampup.core import (capture_learner_profile, analyze_codebase, reading_path,
    generate_exercises, build_playbook, adapt, MENTOR_TOUCHPOINTS, _digest)
from tests.test_rampup import REPO, PROFILE_RAW

class SecurityRegressions(unittest.TestCase):
    def playbook(self):
        profile = capture_learner_profile(PROFILE_RAW)
        codebase = analyze_codebase(REPO)
        return build_playbook(profile, codebase, reading_path(codebase, profile["goal"]),
                              generate_exercises(codebase, profile))

    def test_profile_field_types(self):
        for field in ("name_or_handle", "goal"):
            for value in (None, [], True, ""):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    capture_learner_profile(dict(PROFILE_RAW, **{field: value}))

    def test_constraints_must_be_string_list(self):
        for value in ("4h/day", [1], [{}], None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                capture_learner_profile(dict(PROFILE_RAW, constraints=value))

    def test_profile_digest_is_canonical(self):
        first = capture_learner_profile(PROFILE_RAW)
        second = capture_learner_profile(dict(reversed(list(PROFILE_RAW.items()))))
        self.assertEqual(first, second)

    def test_profile_constraints_detached(self):
        raw = copy.deepcopy(PROFILE_RAW)
        profile = capture_learner_profile(raw)
        raw["constraints"].append("changed")
        self.assertEqual(profile["constraints"], ["4h/day"])

    def test_profile_tampering_rejected(self):
        profile = capture_learner_profile(PROFILE_RAW)
        profile["goal"] = "changed"
        with self.assertRaises(ValueError):
            generate_exercises(analyze_codebase(REPO), profile)

    def test_windows_paths_normalized(self):
        codebase = analyze_codebase({"pkg\\util.py": "def helper(): pass"})
        self.assertEqual(codebase["modules"]["pkg/util.py"]["module"], "pkg.util")

    def test_normalized_path_collision_rejected(self):
        with self.assertRaises(ValueError):
            analyze_codebase({"pkg\\a.py": "", "pkg/a.py": ""})

    def test_unsafe_path_labels_rejected(self):
        for path in ("../a.py", "/tmp/a.py", "D:\\a.py", "a//b.py", "a.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                analyze_codebase({path: ""})

    def test_same_basename_in_packages_is_distinct(self):
        codebase = analyze_codebase({"left/util.py": "", "right/util.py": "", "api.py": "import left.util"})
        self.assertEqual(codebase["modules"]["api.py"]["dependency_paths"], ["left/util.py"])

    def test_relative_module_import_resolves(self):
        codebase = analyze_codebase({"pkg/util.py": "", "pkg/api.py": "from . import util"})
        self.assertEqual(codebase["modules"]["pkg/api.py"]["dependency_paths"], ["pkg/util.py"])

    def test_relative_parent_import_resolves(self):
        codebase = analyze_codebase({"pkg/util.py": "", "pkg/sub/api.py": "from .. import util"})
        self.assertEqual(codebase["modules"]["pkg/sub/api.py"]["dependency_paths"], ["pkg/util.py"])

    def test_imported_attribute_resolves_containing_module(self):
        codebase = analyze_codebase({"pkg/util.py": "def f(): pass", "api.py": "from pkg.util import f"})
        self.assertEqual(codebase["modules"]["api.py"]["dependency_paths"], ["pkg/util.py"])

    def test_package_import_keeps_parent_and_submodule(self):
        codebase = analyze_codebase({"pkg/__init__.py": "", "pkg/util.py": "", "api.py": "import pkg.util"})
        self.assertEqual(codebase["modules"]["api.py"]["dependency_paths"], ["pkg/__init__.py", "pkg/util.py"])

    def test_duplicate_module_identity_is_unresolved(self):
        codebase = analyze_codebase({"pkg.py": "", "pkg/__init__.py": "", "api.py": "import pkg"})
        self.assertEqual(codebase["ambiguous_modules"], ["pkg"])
        self.assertEqual(codebase["modules"]["api.py"]["dependency_paths"], [])
        self.assertEqual(codebase["modules"]["api.py"]["unresolved_imports"], ["pkg"])

    def test_broken_dependency_not_silently_resolved(self):
        codebase = analyze_codebase({"util.py": "def broken(:", "api.py": "import util"})
        self.assertEqual(codebase["modules"]["api.py"]["unresolved_imports"], ["util"])

    def test_external_imports_explicit(self):
        codebase = analyze_codebase({"api.py": "import external_library"})
        self.assertEqual(codebase["modules"]["api.py"]["unresolved_imports"], ["external_library"])

    def test_async_public_symbols_included(self):
        module = analyze_codebase({"a.py": "async def run(): pass"})["modules"]["a.py"]
        self.assertEqual(module["public_symbols"], ["run"])
        self.assertEqual(module["symbol_lines"]["run"], 1)

    def test_cycles_distinguished_from_blocked_dependents(self):
        codebase = analyze_codebase({"a.py": "import b", "b.py": "import a", "c.py": "import a"})
        steps = {step["path"]: step for step in reading_path(codebase, "learn modules")}
        self.assertTrue(steps["a.py"]["in_cycle"])
        self.assertTrue(steps["b.py"]["in_cycle"])
        self.assertFalse(steps["c.py"]["in_cycle"])
        self.assertTrue(steps["c.py"]["blocked_by_cycle"])

    def test_self_cycle_exposed(self):
        steps = reading_path(analyze_codebase({"a.py": "import a"}), "learn modules")
        self.assertTrue(steps[0]["in_cycle"])

    def test_diamond_dependencies_are_ordered(self):
        steps = reading_path(analyze_codebase({"a.py": "", "b.py": "import a",
            "c.py": "import a", "d.py": "import b\nimport c"}), "learn modules")
        self.assertEqual([step["path"] for step in steps], ["a.py", "b.py", "c.py", "d.py"])

    def test_codebase_tampering_rejected(self):
        codebase = analyze_codebase(REPO)
        codebase["modules"]["api.py"]["dependency_paths"] = []
        with self.assertRaises(ValueError):
            reading_path(codebase, "learn modules")

    def test_zero_exercise_limit_is_empty(self):
        self.assertEqual(generate_exercises(analyze_codebase(REPO),
            capture_learner_profile(PROFILE_RAW), limit=0), [])

    def test_invalid_exercise_limits_rejected(self):
        for value in (-1, True, 1.5, 101):
            with self.subTest(value=value), self.assertRaises(ValueError):
                generate_exercises(analyze_codebase(REPO), capture_learner_profile(PROFILE_RAW), value)

    def test_exercise_citations_bind_line_and_source(self):
        for exercise in self.playbook()["exercises"]:
            self.assertGreater(exercise["citation"]["line"], 0)
            self.assertTrue(exercise["citation"]["source_digest"].startswith("sha256:"))

    def test_forged_reading_path_rejected(self):
        profile = capture_learner_profile(PROFILE_RAW)
        codebase = analyze_codebase(REPO)
        steps = reading_path(codebase, profile["goal"])
        steps[0]["citation"]["path"] = "not-real.py"
        with self.assertRaises(ValueError):
            build_playbook(profile, codebase, steps, generate_exercises(codebase, profile))

    def test_forged_exercise_rejected(self):
        profile = capture_learner_profile(PROFILE_RAW)
        codebase = analyze_codebase(REPO)
        exercises = generate_exercises(codebase, profile)
        exercises[0]["exercise"] = "unrelated work"
        with self.assertRaises(ValueError):
            build_playbook(profile, codebase, reading_path(codebase, profile["goal"]), exercises)

    def test_mentor_guardrail_immutable(self):
        with self.assertRaises(TypeError):
            MENTOR_TOUCHPOINTS[0]["what"] = "changed"

    def test_progress_updates_are_cumulative(self):
        first = adapt(self.playbook(), {"reading": ["util.py"], "exercises": [0]})
        second = adapt(first, {"reading": ["store.py"], "exercises": [1]})
        self.assertTrue(all(step["done"] for step in second["reading_path"] if step["path"] in ("util.py", "store.py")))
        self.assertEqual(second["exercises"][0]["status"], "DONE")
        self.assertEqual(len(second["progress_history"]), 2)

    def test_replayed_completion_is_idempotent(self):
        first = adapt(self.playbook(), {"reading": ["util.py"], "exercises": [0]})
        self.assertEqual(first, adapt(first, {"reading": ["util.py"], "exercises": [0]}))

    def test_empty_update_preserves_completion(self):
        first = adapt(self.playbook(), {"reading": ["util.py"], "exercises": [0]})
        self.assertEqual(first, adapt(first, {}))

    def test_unknown_progress_rejected(self):
        for completed in ({"reading": ["unknown.py"]}, {"exercises": [-1]}, {"exercises": [99]}, {"extra": 1}):
            with self.subTest(completed=completed), self.assertRaises(ValueError):
                adapt(self.playbook(), completed)

    def test_tampered_playbook_rejected(self):
        playbook = self.playbook()
        playbook["human_mentoring_touchpoints"].clear()
        with self.assertRaises(ValueError):
            adapt(playbook, {})

    def test_history_preserved_and_bound(self):
        first = adapt(self.playbook(), {"reading": ["util.py"]})
        second = adapt(first, {"reading": ["store.py"]})
        self.assertEqual(second["progress_history"][0], first["progress_history"][0])
        self.assertEqual(second["progress_history"][1]["previous_digest"], first["playbook_digest"])

    def test_source_size_and_count_limits(self):
        with patch("rampup.core.MAX_FILE_BYTES", 2), self.assertRaises(ValueError):
            analyze_codebase(REPO)
        with patch("rampup.core.MAX_FILES", 1), self.assertRaises(ValueError):
            analyze_codebase(REPO)

    def test_invalid_source_unicode_rejected(self):
        with self.assertRaises(ValueError):
            analyze_codebase({"a.py": "\ud800"})

    def test_dependency_edge_limit(self):
        with patch("rampup.core.MAX_EDGES", 1), self.assertRaises(ValueError):
            analyze_codebase({"a.py": "", "b.py": "import a", "c.py": "import a"})

    def test_playbook_digest_covers_progress(self):
        playbook = adapt(self.playbook(), {"reading": ["util.py"]})
        digest = playbook.pop("playbook_digest")
        self.assertEqual(digest, _digest(playbook))

