"""Parse every Jinja template in the HA package, and RENDER the risky ones.

A Jinja syntax error in a template sensor or an automation condition does not
stop HA starting — it logs and the entity goes `unknown`, or the condition
silently evaluates false and the automation never fires. That is the quiet
class of failure the DEFINITION OF DONE was written about: valid YAML, zero
errors, and an automation that can never run.

Two passes:
  1. PARSE every template found anywhere in the package (syntax).
  2. RENDER the `for:` duration templates against plausible states, because
     those must produce a valid HH:MM:SS and are the highest-risk templates in
     the package — a bad one breaks the "lights off when empty" automation.
"""
import io, re, sys
import yaml
from jinja2 import Environment, TemplateSyntaxError

P = r"C:\Users\wkcol\OneDrive\Desktop\mmWave Presence Lighting Node\draft\packages\mmwave_presence.yaml"

class L(yaml.SafeLoader): pass
def _u(l, s, n):
    if isinstance(n, yaml.ScalarNode):   return l.construct_scalar(n)
    if isinstance(n, yaml.SequenceNode): return l.construct_sequence(n)
    return l.construct_mapping(n)
L.add_multi_constructor("!", _u)

doc = yaml.load(io.open(P, encoding="utf-8"), Loader=L)

# HA's template environment provides these; Jinja alone does not know them, so
# declare them or every template "fails" on an undefined name rather than on a
# real syntax error.
env = Environment()
for fn in ("states", "state_attr", "is_state", "is_state_attr", "now",
           "as_timestamp", "utcnow", "float", "int", "timedelta", "as_local",
           "has_value", "states_attr"):
    env.globals[fn] = lambda *a, **k: None
env.filters["float"] = lambda v, d=0.0: d
env.filters["int"] = lambda v, d=0: d
env.filters["default"] = lambda v, d="", b=False: d
env.filters["replace"] = lambda v, a, b: ""
env.filters["max"] = lambda v: 0
env.filters["min"] = lambda v: 0

templates = []
def walk(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]")
    elif isinstance(node, str) and ("{{" in node or "{%" in node):
        templates.append((path, node))

walk(doc, "")
print(f"templates found: {len(templates)}")

bad = 0
for path, t in templates:
    try:
        env.parse(t)
    except TemplateSyntaxError as e:
        bad += 1
        print(f"\n!! SYNTAX ERROR at {path}  line {e.lineno}: {e.message}")
        print("   " + t.strip().replace("\n", "\n   ")[:300])

print(f"syntax errors: {bad}")

# ---- pass 2: the `for:` duration templates must render to HH:MM:SS ----------
print("\nrendering the two `for:` duration templates (the highest-risk ones):")
DUR = re.compile(r"^\d{2}:\d{2}:\d{2}$")
cases = [
    ("office", 90.0, 30.0, "00:01:00"),
    ("office", 90.0, 90.0, "00:00:00"),   # module timeout >= total -> floor at 0
    ("office", 30.0, 90.0, "00:00:00"),   # module LONGER than total
    ("family", 300.0, 30.0, "00:04:30"),
    ("family", 1800.0, 30.0, "00:29:30"), # max of the input_number range
    ("family", 3600.0, 5.0,  "00:59:55"), # over an hour -> must not overflow mm
]
fails = 0
for room, total, mod, expect in cases:
    src = ("{% set total = X %}{% set mod = Y %}"
           "{% set w = [total - mod, 0] | max | int %}"
           "{{ '%02d:%02d:%02d' % (w // 3600, (w % 3600) // 60, w % 60) }}")
    src = src.replace("X", str(total)).replace("Y", str(mod))
    e2 = Environment()
    e2.filters["max"] = lambda v: max(v)
    e2.filters["int"] = lambda v: int(v)
    out = e2.from_string(src).render().strip()
    ok = DUR.match(out) and out == expect
    fails += 0 if ok else 1
    print(f"   {room:7s} total={total:6.0f} module={mod:5.0f} -> {out:10s} "
          f"expect {expect:10s} {'OK' if ok else '!! MISMATCH'}")

sys.exit(1 if (bad or fails) else 0)
