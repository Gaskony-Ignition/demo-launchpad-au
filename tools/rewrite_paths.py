#!/usr/bin/env python3
"""Rewrite OEE/KPI project tag references from the old [Launchpad]Launchpad/...
(and stale [default]Launchpad/...) layout to the new flat layout:
  Oee/...            -> [Launchpad]OEE/...
  everything else    -> [Launchpad]KPI/...
Also fixes the two SafeGroup binding typos. Dry-run by default; --apply to write.
"""
import re, sys, os, json

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/../mirror"
APPLY = "--apply" in sys.argv

# provider-qualified refs
REF = re.compile(r"\[(?:Launchpad|default)\]Exchange/Launchpad(/[A-Za-z0-9_ /.]*|(?=[\"'\s]))")
# bare typeId refs (browse calls / typeIds inside project files)
TYPEID = re.compile(r"(?<!\])Launchpad/Oee/(LineConfig|OEE|Schedule|Shift)")

def map_ref(m):
    rest = m.group(1) or ""
    rest = rest.lstrip("/")
    if rest == "Oee" or rest.startswith("Oee/"):
        return "[Launchpad]OEE" + ("/" + rest[4:] if len(rest) > 4 else "")
    if rest == "":
        return "[Launchpad]"  # bare Exchange/Launchpad root -> provider root
    return "[Launchpad]KPI/" + rest

TYPO_FIXES = [
    ("OEE/Demo/Line1/ShiftOee/Shift_O", "OEE/Demo/Line 1/ShiftOee/O"),
    ("OEE/Demo/Line3/Schedule/1/StartTime", "OEE/Demo/Line 3/Schedule/1/StartTime"),
]

changed = {}
for dirpath, _, files in os.walk(ROOT):
    for fn in files:
        if not (fn.endswith(".json") or fn.endswith(".py") or fn.endswith(".sql")):
            continue
        p = os.path.join(dirpath, fn)
        with open(p, encoding="utf-8") as f:
            src = f.read()
        out = REF.sub(map_ref, src)
        out = TYPEID.sub(r"OEE/\1", out)
        for a, b in TYPO_FIXES:
            out = out.replace(a, b)
        if out != src:
            rel = os.path.relpath(p, ROOT)
            n = sum(1 for _ in re.finditer(r"\[Launchpad\](OEE|KPI/)", out))
            changed[rel] = n
            if APPLY:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(out)

for rel in sorted(changed):
    print(f"{changed[rel]:4d}  {rel}")
print(f"\n{'APPLIED' if APPLY else 'DRY RUN'}: {len(changed)} files")

# safety: report any survivors of the old scheme
if APPLY:
    leftovers = []
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            p = os.path.join(dirpath, fn)
            if not (fn.endswith(".json") or fn.endswith(".py") or fn.endswith(".sql")):
                continue
            with open(p, encoding="utf-8") as f:
                s = f.read()
            if "]Exchange/Launchpad" in s or "Shift_O" in s:
                leftovers.append(os.path.relpath(p, ROOT))
    print("leftover old refs:", leftovers if leftovers else "none")
