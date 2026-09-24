"""Read-only technical learning plans; human mentoring remains mandatory."""
from __future__ import annotations
import ast
import hashlib
import heapq
import json
import re
from types import MappingProxyType

VERSION = "0.1.2a1"
SKILL_LEVELS = ("beginner", "intermediate", "advanced")
MAX_FILES = 1000
MAX_FILE_BYTES = 1024 * 1024
MAX_BYTES = 16 * 1024 * 1024
MAX_EDGES = 10000

def _snapshot(value):
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(text.encode("utf-8")) > MAX_BYTES:
            raise ValueError()
        return json.loads(text)
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise ValueError("artifact must be bounded finite JSON") from None

def _digest(value):
    text = json.dumps(_snapshot(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

def _text(value, limit=512):
    if type(value) is not str or not value.strip() or len(value) > limit or any(ord(c)<32 for c in value):
        raise ValueError("required text must be a nonempty bounded string")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("invalid Unicode text") from None
    return value

def _verified(value, field):
    value = _snapshot(value)
    if type(value) is not dict:
        raise ValueError("artifact must be an object")
    digest = value.pop(field, None)
    if digest != _digest(value):
        raise ValueError("artifact digest missing or mismatched")
    value[field] = digest
    return value

def capture_learner_profile(raw):
    raw = _snapshot(raw)
    if type(raw) is not dict:
        raise ValueError("learner profile must be an object")
    name, goal = _text(raw.get("name_or_handle")), _text(raw.get("goal"), 4096)
    if type(raw.get("skill_level")) is not str or raw["skill_level"] not in SKILL_LEVELS:
        raise ValueError("invalid skill level")
    constraints = raw.get("constraints", [])
    if type(constraints) is not list or len(constraints)>100:
        raise ValueError("constraints must be a bounded list")
    constraints = [_text(item) for item in constraints]
    result = {"name_or_handle": name, "goal": goal, "skill_level": raw["skill_level"],
              "constraints": constraints}
    result["profile_digest"] = _digest(result)
    return result

def _profile(value):
    value = _verified(value, "profile_digest")
    if capture_learner_profile(value) != value:
        raise ValueError("profile contains unsupported fields")
    return value

def analyze_codebase(py_files):
    if type(py_files) is not dict or len(py_files)>MAX_FILES:
        raise ValueError("py_files must be a bounded mapping")
    sources, names, errors, total = {}, {}, [], 0
    for path, source in py_files.items():
        _text(path, 1024)
        canonical = path.replace("\\", "/")
        parts = canonical.split("/")
        if canonical.startswith("/") or ":" in canonical or any(part in ("", ".", "..") for part in parts) or not canonical.endswith(".py"):
            raise ValueError("paths must be relative Python file labels without traversal")
        if canonical in sources:
            raise ValueError("duplicate normalized path")
        if type(source) is not str:
            raise ValueError("source must be text")
        try:
            data = source.encode("utf-8")
        except UnicodeError:
            raise ValueError("source must be valid UTF-8") from None
        total += len(data)
        if len(data)>MAX_FILE_BYTES or total>MAX_BYTES:
            raise ValueError("source size limit exceeded")
        sources[canonical] = source
        segments = parts[:-1] if parts[-1]=="__init__.py" else parts[:-1]+[parts[-1][:-3]]
        names[canonical] = ".".join(segments) or "__root__"
    by_name = {}
    for path, name in names.items():
        by_name.setdefault(name, []).append(path)
    ambiguous = sorted(name for name, paths in by_name.items() if len(paths)>1)
    modules, trees = {}, {}
    for path, source in sorted(sources.items()):
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError, RecursionError):
            errors.append({"path": path, "error": "Python source cannot be parsed"})
            continue
        trees[path] = tree
        public = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                  and not node.name.startswith("_")]
        doc = ast.get_docstring(tree)
        modules[path] = {"module": names[path], "internal_imports": [], "dependency_paths": [],
            "unresolved_imports": [], "public_symbols": [node.name for node in public],
            "symbol_lines": {node.name: node.lineno for node in public},
            "summary": doc.splitlines()[0] if doc else None, "loc": len(source.splitlines()),
            "source_digest": "sha256:"+hashlib.sha256(source.encode("utf-8")).hexdigest()}
    edge_count = 0
    for path, tree in trees.items():
        name = names[path]
        package = name if path.endswith("/__init__.py") else name.rpartition(".")[0]
        dependencies, unresolved = set(), set()
        def candidate(module):
            if not module:
                return
            if module in by_name:
                if len(by_name[module]) == 1 and by_name[module][0] in modules:
                    dependencies.add(by_name[module][0])
                else:
                    unresolved.add(module)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pieces = alias.name.split(".")
                    matched = False
                    for size in range(1, len(pieces)+1):
                        part = ".".join(pieces[:size])
                        if part in by_name:
                            matched = True
                            candidate(part)
                    if not matched:
                        unresolved.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    pieces = package.split(".") if package else []
                    if node.level > len(pieces):
                        unresolved.add("relative import above supplied root")
                        continue
                    base = ".".join(pieces[:len(pieces)-node.level+1])
                    base = ".".join(part for part in (base, node.module) if part)
                else:
                    base = node.module or ""
                candidate(base)
                matched = base in by_name
                for alias in node.names:
                    full = base+"."+alias.name if base else alias.name
                    if full in by_name:
                        matched = True
                        candidate(full)
                if not matched:
                    unresolved.add(base or "unresolved relative import")
        # Importing the current package from within its own __init__ is not a prerequisite.
        if path.endswith("/__init__.py"):
            dependencies.discard(path)
        edge_count += len(dependencies)
        if edge_count>MAX_EDGES:
            raise ValueError("dependency edge limit exceeded")
        modules[path]["dependency_paths"] = sorted(dependencies)
        modules[path]["internal_imports"] = sorted({names[item] for item in dependencies})
        modules[path]["unresolved_imports"] = sorted(unresolved)
    result = {"modules": modules, "parse_errors": errors, "ambiguous_modules": ambiguous}
    result["codebase_digest"] = _digest(result)
    return result

def _codebase(value):
    value = _verified(value, "codebase_digest")
    if type(value.get("modules")) is not dict or len(value["modules"])>MAX_FILES:
        raise ValueError("invalid module inventory")
    for path, module in value["modules"].items():
        if type(module) is not dict or type(module.get("dependency_paths")) is not list:
            raise ValueError("invalid module dependency list")
        if any(dep not in value["modules"] for dep in module["dependency_paths"]):
            raise ValueError("dependency missing from module inventory")
    return value

def _cycle_nodes(graph):
    """Iterative strongly-connected component detection."""
    seen, finish = set(), []
    for start in graph:
        if start in seen:
            continue
        stack = [(start, False)]
        while stack:
            node, exiting = stack.pop()
            if exiting:
                finish.append(node)
            elif node not in seen:
                seen.add(node)
                stack.append((node, True))
                stack.extend((child, False) for child in graph[node] if child not in seen)
    reverse = {node: [] for node in graph}
    for node, children in graph.items():
        for child in children:
            reverse[child].append(node)
    visited, cyclic = set(), set()
    for start in reversed(finish):
        if start in visited:
            continue
        component, stack = set(), [start]
        visited.add(start)
        while stack:
            node = stack.pop()
            component.add(node)
            for child in reverse[node]:
                if child not in visited:
                    visited.add(child)
                    stack.append(child)
        if len(component)>1 or start in graph[start]:
            cyclic.update(component)
    return cyclic

def reading_path(codebase, goal):
    codebase, goal = _codebase(codebase), _text(goal, 4096)
    modules = codebase["modules"]
    graph = {path: module["dependency_paths"] for path, module in modules.items()}
    degrees = {path: len(deps) for path, deps in graph.items()}
    dependents = {path: [] for path in graph}
    for path, deps in graph.items():
        for dep in deps:
            dependents[dep].append(path)
    ready = [path for path, degree in degrees.items() if degree==0]
    heapq.heapify(ready)
    order = []
    while ready:
        path = heapq.heappop(ready)
        order.append(path)
        for child in dependents[path]:
            degrees[child] -= 1
            if degrees[child]==0:
                heapq.heappush(ready, child)
    remainder = set(modules)-set(order)
    cycles = _cycle_nodes(graph)
    goal_words = set(re.findall(r"[a-z]{3,}", goal.lower()))
    steps = []
    for index, path in enumerate(order+sorted(remainder), 1):
        module = modules[path]
        words = set(re.findall(r"[a-z]{3,}", (path+" "+(module["summary"] or "")+" "+" ".join(module["public_symbols"])).lower()))
        steps.append({"step": index, "path": path, "module": module["module"],
            "why": "no resolved internal prerequisites" if not graph[path] else "builds on "+", ".join(module["internal_imports"]),
            "goal_relevance": sorted(goal_words & words), "in_cycle": path in cycles,
            "blocked_by_cycle": path in remainder and path not in cycles,
            "citation": {"path": path, "line": 1, "loc": module["loc"], "source_digest": module["source_digest"]},
            "unresolved_imports": module["unresolved_imports"],
            "uncertainty": "static import heuristic over supplied files; external, conditional and dynamic imports need mentor review"})
    return steps

def generate_exercises(codebase, profile, limit=3):
    codebase, profile = _codebase(codebase), _profile(profile)
    if type(limit) is not int or not 0 <= limit <= 100:
        raise ValueError("exercise limit must be an integer from 0 to 100")
    if limit==0:
        return []
    templates = {
        "beginner": "Read {path} and write a note explaining {symbol}; confirm it with your mentor.",
        "intermediate": "Write a unit test for {symbol} in {path}, covering normal and edge cases; run the existing suite first.",
        "advanced": "Trace {symbol} in {path} and propose, without applying, one refactor with trade-offs."}
    result = []
    for path, module in sorted(codebase["modules"].items(), key=lambda item: (-len(item[1]["public_symbols"]), item[0])):
        if not module["public_symbols"]:
            continue
        symbol = module["public_symbols"][0]
        result.append({"exercise": templates[profile["skill_level"]].format(path=path, symbol=symbol),
            "tied_to": {"path": path, "symbol": symbol},
            "citation": {"path": path, "line": module["symbol_lines"][symbol], "source_digest": module["source_digest"]},
            "uncertainty": "verify this source snapshot with a human mentor before assigning work", "status": "NOT_STARTED"})
        if len(result)==limit:
            break
    return result

MENTOR_TOUCHPOINTS = tuple(MappingProxyType(item) for item in (
    {"when": "day 1", "what": "kickoff with a human mentor: goals, team norms and pairing"},
    {"when": "end of week 1", "what": "human mentor reviews reading notes and questions"},
    {"when": "first exercise done", "what": "human mentor reviews the exercise with the learner"},
    {"when": "week 2", "what": "human-led team integration and mentor follow-up"},
))

def build_playbook(profile, codebase, goal_path, exercises):
    profile, codebase = _profile(profile), _codebase(codebase)
    goal_path, exercises = _snapshot(goal_path), _snapshot(exercises)
    if type(exercises) is not list or len(exercises)>100:
        raise ValueError("invalid exercise list")
    if goal_path != reading_path(codebase, profile["goal"]) or exercises != generate_exercises(codebase, profile, len(exercises)):
        raise ValueError("guidance does not match the profile and source snapshot")
    result = {"schema": "rampup/playbook/v1", "coach_version": VERSION, "learner": profile,
        "scope": "technical ramp-up over the supplied repository snapshot (GRD-02)",
        "codebase_map": codebase["modules"], "codebase_digest": codebase["codebase_digest"],
        "parse_errors": codebase["parse_errors"], "ambiguous_modules": codebase["ambiguous_modules"],
        "reading_path": goal_path, "exercises": exercises,
        "human_mentoring_touchpoints": [dict(item) for item in MENTOR_TOUCHPOINTS],
        "not_a_replacement": "this playbook supplements and never replaces human-led mentoring and team integration",
        "advisory_only": True, "progress_history": []}
    result["playbook_digest"] = _digest(result)
    return result

def adapt(playbook, completed):
    playbook = _verified(playbook, "playbook_digest")
    if type(completed) is not dict or set(completed)-{"reading", "exercises"}:
        raise ValueError("completed must contain reading paths and exercise indices")
    reading, indices = completed.get("reading", []), completed.get("exercises", [])
    if type(reading) not in (list, tuple, set) or len(reading)>MAX_FILES or any(type(path) is not str for path in reading):
        raise ValueError("completed reading must contain path strings")
    if type(indices) not in (list, tuple, set) or len(indices)>100 or any(type(index) is not int for index in indices):
        raise ValueError("completed exercises must contain integer indices")
    known_paths = {step["path"] for step in playbook["reading_path"]}
    if set(reading)-known_paths or any(index<0 or index>=len(playbook["exercises"]) for index in indices):
        raise ValueError("completion references unknown work")
    prior_paths = {step["path"] for step in playbook["reading_path"] if step.get("done")}
    prior_indices = {index for index, item in enumerate(playbook["exercises"]) if item["status"]=="DONE"}
    new_paths, new_indices = set(reading)-prior_paths, set(indices)-prior_indices
    all_paths, all_indices = prior_paths | set(reading), prior_indices | set(indices)
    for step in playbook["reading_path"]:
        step["done"] = step["path"] in all_paths
    for index, exercise in enumerate(playbook["exercises"]):
        if index in all_indices:
            exercise["status"] = "DONE"
    if new_paths or new_indices:
        playbook["progress_history"].append({"sequence": len(playbook["progress_history"])+1,
            "reading": sorted(new_paths), "exercises": sorted(new_indices),
            "previous_digest": playbook["playbook_digest"]})
    next_read = next((step for step in playbook["reading_path"] if not step["done"]), None)
    next_exercise = next((item for item in playbook["exercises"] if item["status"]!="DONE"), None)
    playbook["next_up"] = {"reading": next_read["path"] if next_read else None,
        "exercise": next_exercise["exercise"] if next_exercise else None,
        "note": "all items complete — schedule the closing human mentor session" if not next_read and not next_exercise
                else "progress recorded; pace adjustments are a mentor decision"}
    playbook.pop("playbook_digest")
    playbook["playbook_digest"] = _digest(playbook)
    return playbook
