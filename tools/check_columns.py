#!/usr/bin/env python3
"""Fail the build if a record function's params do not match its column list.

Every write in launchpad.oee now hands launchpad.store a column list and a
`params` list, positionally. If the two lengths disagree the store raises, which
is fine. If they AGREE but the order has drifted, nothing raises: values land in
the wrong columns, and SQL accepts that silently whenever the types happen to
line up. A shift's reject count showing up as its idle seconds is not a crash,
it is a plausible number on a chart.

This cannot check the ORDER - only a human reading the appends can - but it can
check the count, which is what catches the common edit: a column added to the
list, or a params.append inserted, without its partner.

    python3 tools/check_columns.py final/OEE
"""
import os
import re
import sys

# record function -> the constant naming the columns it writes
PAIRS = {
    "recordHourStart": "HOUR_START_COLUMNS",
    "recordHourEnd": "HOUR_END_COLUMNS",
    "recordShiftStart": "SHIFT_START_COLUMNS",
    "recordShiftEnd": "SHIFT_END_COLUMNS",
    "makeHistory": "SHIFT_HISTORY_COLUMNS",
    "makeHourlyHistory": "HOUR_HISTORY_COLUMNS",
}


def check(project):
    path = os.path.join(project, "ignition/script-python/launchpad/oee/code.py")
    if not os.path.exists(path):
        return ["%s: no launchpad.oee module" % project]
    src = open(path).read()

    constants = {}
    for m in re.finditer(r"^(\w+_COLUMNS) = \[(.*?)^\]", src, re.S | re.M):
        constants[m.group(1)] = len(re.findall(r'"(\w+)"', m.group(2)))

    problems = []
    for fn, const in sorted(PAIRS.items()):
        if const not in constants:
            problems.append("%s: %s is not defined" % (project, const))
            continue
        i = src.find("def %s(" % fn)
        if i < 0:
            problems.append("%s: no function %s" % (project, fn))
            continue
        j = src.find("\ndef ", i + 5)
        body = src[i:j if j > 0 else len(src)]
        # both spellings the module uses: one value at a time, or a run of them
        appends = len(re.findall(r"\n\t+params\.append\(", body))
        extends = re.findall(r"\n\t+params\.extend\(\[(.*?)\]\)", body, re.S)
        extended = 0
        for run in extends:
            # count top-level commas, so a nested call or list stays one value
            depth, n = 0, 1
            for ch in run:
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                elif ch == "," and depth == 0:
                    n += 1
            extended += n
        values = appends + extended
        if values != constants[const]:
            problems.append(
                "%s: %s writes %d values into %s, which has %d columns"
                % (project, fn, values, const, constants[const]))
    return problems


def main(argv):
    projects = argv[1:] or ["final/OEE"]
    problems = []
    for p in projects:
        problems.extend(check(p))
    if problems:
        print("column check FAILED:", file=sys.stderr)
        for p in problems:
            print("    " + p, file=sys.stderr)
        return 1
    print("column check passed: every record function matches its column list")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
