#!/usr/bin/env python3
"""Generate Designer-importable tag exports from the gateway config resources.

On 8.3 the tags live on disk as config resources, one tags.json per folder. A
Designer tag import wants the opposite shape: a single root node with a nested
tags[] array. This rebuilds that shape so the Setup payload carries an export
anyone can bring in through the Designer, whether or not they can reach the
gateway filesystem.

    python3 tools/build_tag_exports.py <output-root>
"""
import json, os, shutil, sys

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/.."
CFG = f"{ROOT}/live-config"
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/dist/Tags"


def load(p):
    d = json.load(open(p))
    return d if isinstance(d, list) else [d]


def folder(name, tags):
    return {"name": name, "tagType": "Folder", "tags": tags}


def leaves(node):
    if "tags" in node:
        return sum(leaves(c) for c in node["tags"])
    return 1


def build_oee(dest):
    os.makedirs(dest, exist_ok=True)
    types = load(f"{CFG}/tag-type-definition/launchpad/OEE/udts.json")
    # UDT types import under a _types_ folder; Ignition resolves the typeId of an
    # instance against the type's path, so the OEE/ prefix has to be preserved
    json.dump(folder("OEE", [folder("_types_", types)]),
              open(f"{dest}/launchpad-oee-udts.json", "w"), indent=2)

    demo = load(f"{CFG}/tag-definition/launchpad/OEE/Demo/udts.json")
    sim = load(f"{CFG}/tag-definition/launchpad/OEE/Demo/Sim/tags.json")
    root = load(f"{CFG}/tag-definition/launchpad/OEE/tags.json")
    tree = folder("OEE", root + [folder("Demo", demo + [folder("Sim", sim)])])
    json.dump(tree, open(f"{dest}/launchpad-oee-tags.json", "w"), indent=2)
    return leaves(tree), leaves(folder("x", types))


def build_kpi(dest):
    os.makedirs(dest, exist_ok=True)
    root = load(f"{CFG}/tag-definition/launchpad/KPI/tags.json")
    lines = [folder(f"Line{n}", load(f"{CFG}/tag-definition/launchpad/KPI/Lines/Line{n}/tags.json"))
             for n in range(1, 8)]
    tree = folder("KPI", root + [folder("Lines", lines)])
    json.dump(tree, open(f"{dest}/launchpad-kpi-tags.json", "w"), indent=2)
    # the simulator programme is what gives every KPI tag a value
    shutil.copy(f"{CFG}/device/Launchpad/instructions.csv", f"{dest}/launchpad-simulator.csv")
    return leaves(tree)


if __name__ == "__main__":
    n_oee, n_types = build_oee(f"{OUT}/oee")
    n_kpi = build_kpi(f"{OUT}/kpi")
    print(f"  OEE: {n_oee} tags + {n_types} UDT members")
    print(f"  KPI: {n_kpi} tags + simulator programme")
