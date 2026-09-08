"""Resolve EVERY entity id referenced by the three dashboards, against all three
sources that can actually supply one:

  1. the ESPHome firmwares      -> slugify(friendly_name + " " + entity name)
  2. the HA package             -> helper keys, template names, history_stats
  3. the live entity registry   -> everything pre-existing (plugs, thermostats)

A reference that matches none of the three is broken. This is the closest thing
to ENTITIES.md's rule ("this file, then the registry, never from a pattern")
that can be run before the hardware exists.
"""
import io, json, re, sys, unicodedata
import yaml

DRAFT = r"C:\Users\wkcol\OneDrive\Desktop\mmWave Presence Lighting Node\draft"

class L(yaml.SafeLoader): pass
def _u(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):   return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode): return loader.construct_sequence(node)
    return loader.construct_mapping(node)
L.add_multi_constructor("!", _u)

def load(p):
    return yaml.load(io.open(p, encoding="utf-8"), Loader=L)

def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", t.lower())).strip("_")

available = {}          # entity_id -> where it comes from

# ---------------------------------------------------------------- firmware --
EH2HA = {"binary_sensor": "binary_sensor", "sensor": "sensor",
         "text_sensor": "sensor", "switch": "switch", "button": "button",
         "number": "number", "select": "select"}
SKIP = ("filters", "pin", "on_value", "on_press", "on_release", "then",
        "lambda", "project", "condition")

def names(node, out):
    if isinstance(node, dict):
        if isinstance(node.get("name"), str):
            out.append(node["name"])
        for k, v in node.items():
            if k not in SKIP:
                names(v, out)
    elif isinstance(node, list):
        for v in node:
            names(v, out)

def firmware(dev_file, common=None):
    fw = load(dev_file)
    if common:
        base = load(common)
        subs = dict(base.get("substitutions", {}))
        subs.update(fw.get("substitutions", {}))
        merged = base
        merged["esphome"] = {**base.get("esphome", {}), **fw.get("esphome", {})}
    else:
        subs = fw.get("substitutions", {})
        merged = fw
    def ex(v):
        if not isinstance(v, str): return v
        for k, sv in subs.items():
            v = v.replace("${%s}" % k, str(sv))
        return v
    dev = ex(merged["esphome"].get("friendly_name") or merged["esphome"]["name"])
    got = {}
    for ehd, had in EH2HA.items():
        if ehd not in merged: continue
        ns = []
        names(merged[ehd], ns)
        for n in ns:
            got[f"{had}.{slug(dev + ' ' + ex(n))}"] = f"firmware({dev})"
    return got

available.update(firmware(DRAFT + r"\esphome\mmwave-bench.yaml"))
available.update(firmware(DRAFT + r"\esphome\mmwave-office-node.yaml",
                          DRAFT + r"\esphome\mmwave-node-common.yaml"))
available.update(firmware(DRAFT + r"\esphome\mmwave-family-node.yaml",
                          DRAFT + r"\esphome\mmwave-node-common.yaml"))
print(f"firmware entities        : {len(available)}")

# ----------------------------------------------------------------- package --
pkg = load(DRAFT + r"\packages\mmwave_presence.yaml")
n0 = len(available)
for dom in ("input_boolean", "input_select", "input_number", "input_datetime"):
    for k in (pkg.get(dom) or {}):
        available[f"{dom}.{k}"] = "package helper"
for k in (pkg.get("script") or {}):
    available[f"script.{k}"] = "package script"
for blk in (pkg.get("template") or []):
    for dom in ("sensor", "binary_sensor"):
        for e in (blk.get(dom) or []):
            if e.get("name"):
                available[f"{dom}.{slug(e['name'])}"] = "package template"
for e in (pkg.get("sensor") or []):
    if e.get("name"):
        available[f"sensor.{slug(e['name'])}"] = f"package {e.get('platform')}"
print(f"package entities         : {len(available)-n0}")

# ---------------------------------------------------------------- registry --
reg = json.load(io.open("H:/.storage/core.entity_registry", encoding="utf-8"))
n1 = len(available)
for e in reg["data"]["entities"]:
    available.setdefault(e["entity_id"], "registry (live)")
print(f"live registry entities   : {len(available)-n1}")

# -------------------------------------------------------------- dashboards --
def refs_of(path):
    d = load(path); found = set()
    def walk(n):
        if isinstance(n, dict):
            for k, v in n.items():
                if k in ("entity", "entity_id"):
                    if isinstance(v, str): found.add(v)
                    elif isinstance(v, list): found.update(x for x in v if isinstance(x, str))
                elif k == "entities" and isinstance(v, list):
                    for it in v:
                        if isinstance(it, str): found.add(it)
                        else: walk(it)
                else: walk(v)
        elif isinstance(n, list):
            for v in n: walk(v)
    walk(d)
    return {f for f in found if "." in f}

print()
bad = 0
for name in ("mmwave-bench", "mmwave-office", "mmwave-family"):
    p = DRAFT + rf"\dashboards\{name}.yaml"
    rs = refs_of(p)
    missing = sorted(r for r in rs if r not in available)
    status = "OK" if not missing else f"{len(missing)} BROKEN"
    print(f"{name:16s} {len(rs):3d} refs   {status}")
    for m in missing:
        bad += 1
        near = [a for a in available
                if a.split(".")[0] == m.split(".")[0]
                and slug(m.split(".",1)[1])[:12] in a]
        print(f"      !! {m}")
        for nn in near[:2]:
            print(f"           near -> {nn}  [{available[nn]}]")

# also: does the PACKAGE reference anything that does not exist?
print()
pkg_txt = io.open(DRAFT + r"\packages\mmwave_presence.yaml", encoding="utf-8").read()
cited = set(re.findall(r"\b((?:binary_sensor|sensor|switch|number|select|button|"
                       r"input_boolean|input_select|input_number|input_datetime|"
                       r"climate|light|script)\.[a-z0-9_]+)", pkg_txt))
# Exclude SERVICE names — `input_boolean.turn_on`, `script.turn_off` etc. are
# services, not entities, and the regex cannot tell them apart by shape.
SERVICES = {"turn_on", "turn_off", "toggle", "set_datetime", "select_option",
            "set_value", "reload", "create", "dismiss", "log", "press"}
cited = {c for c in cited if c.split(".", 1)[1] not in SERVICES}
cited = {c for c in cited if not c.endswith("_")}   # template fragments
pmiss = sorted(c for c in cited if c not in available)
print(f"package cites {len(cited)} entity ids; {len(pmiss)} unresolved")
for m in pmiss:
    bad += 1
    print(f"      !! {m}")

sys.exit(1 if bad else 0)
