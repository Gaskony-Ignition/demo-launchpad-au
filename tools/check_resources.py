#!/usr/bin/env python3
"""Fail the build if a project resource folder contains files it does not declare.

Every Ignition project resource is a folder holding a resource.json whose `files`
list is the manifest for that folder. A file that is present but undeclared is not
merely untidy: it is undefined behaviour at import time, and the failure it produces
is remote from its cause -- a script package that silently does not load, and then an
AttributeError from whatever tried to call it.

This exists because a stray __pycache__/code.cpython-314.pyc was shipped inside the
payload script resource of both released packages. It was invisible to every check in
place: gitignored, so `git status` was clean, and the packages are built from the
working tree rather than from git, so it went out in a release.

    python3 tools/check_resources.py final/OEE final/KPI
"""
import json
import os
import sys

# resource.json itself is always implicit; thumbnails are written by the Designer
# and are legitimately undeclared in some resource types
ALWAYS_ALLOWED = {"resource.json"}


def check(root):
    problems = []
    for dirpath, dirnames, filenames in os.walk(root):
        if "resource.json" not in filenames:
            continue
        manifest = os.path.join(dirpath, "resource.json")
        try:
            declared = set(json.load(open(manifest)).get("files") or [])
        except Exception as exc:
            problems.append("%s: unreadable (%s)" % (manifest, exc))
            continue
        present = set(filenames) - ALWAYS_ALLOWED
        for undeclared in sorted(present - declared):
            problems.append("%s: %s is present but not in resource.json files"
                            % (dirpath, undeclared))
        # a subdirectory inside a resource folder is never part of the resource
        for sub in sorted(dirnames):
            if sub not in declared:
                problems.append("%s: %s/ is a directory inside a resource folder"
                                % (dirpath, sub))
        for missing in sorted(declared - set(filenames)):
            problems.append("%s: %s is declared but missing" % (dirpath, missing))
    return problems


def main(roots):
    problems = []
    for root in roots:
        problems.extend(check(root))
    if problems:
        print("resource check FAILED:")
        for p in problems:
            print("  " + p)
        return 1
    print("resource check passed: every resource folder matches its manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["final"]))
