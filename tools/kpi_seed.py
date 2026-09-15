#!/usr/bin/env python3
"""Read the KPI dashboard schema and emit - or check - the file store's seed.

launchpad.init.initDashboard holds the whole dashboard schema as one SQL script:
six CREATE TABLEs and the rows that come with them. On a gateway with no
database that script cannot run, so launchpad.store has to carry the same rows
as data.

Two copies of a seed is one copy that goes stale, so the SQL script stays the
authority and this parses it:

    python3 tools/kpi_seed.py --emit     print the Python literal to paste
    python3 tools/kpi_seed.py            check the committed literal matches

The check runs in package.sh. It is the same bargain as tools/check_columns.py:
the thing that can silently drift is compared against the thing that defines it.
"""
import ast
import re
import sys

INIT = "final/KPI/ignition/script-python/launchpad/init/code.py"
STORE = "final/KPI/ignition/script-python/launchpad/store/code.py"


def sql_script():
    """The DDL text out of initDashboard, without running any of it."""
    src = open(INIT).read()
    i = src.index("def initDashboard():")
    start = src.index('query = """', i) + len('query = """')
    return src[start:src.index('"""', start)]


def split_values(text):
    """Top-level commas only: the JSON in `configuration` is full of them."""
    out, depth, quote, cur = [], 0, None, ""
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                cur += ch + (text[i + 1] if i + 1 < len(text) else "")
                i += 2
                continue
            if ch == quote:
                # '' inside a single-quoted SQL string is one literal quote
                if ch == "'" and i + 1 < len(text) and text[i + 1] == "'":
                    cur += "''"
                    i += 2
                    continue
                quote = None
            cur += ch
        elif ch in "'\"":
            quote = ch
            cur += ch
        elif ch in "([":
            depth += 1
            cur += ch
        elif ch in ")]":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip():
        out.append(cur.strip())
    return out


def literal(token):
    token = token.strip()
    if token.upper() == "NULL":
        return None
    if token.startswith("'") and token.endswith("'"):
        # SQL escapes a quote by doubling it; the script also carries \" from
        # having been written inside a Python string
        return token[1:-1].replace("''", "'").replace('\\"', '"')
    try:
        return int(token)
    except ValueError:
        return float(token)


def parse():
    sql = sql_script()
    columns = {}
    for m in re.finditer(r"CREATE TABLE (\w+)\s*\((.*?)\n\);", sql, re.S):
        cols = []
        for line in m.group(2).split("\n"):
            line = line.strip().rstrip(",")
            if not line or line.upper().startswith(("FOREIGN KEY", "PRIMARY KEY",
                                                    "UNIQUE", "CHECK")):
                continue
            cols.append(line.split()[0])
        columns[m.group(1)] = cols

    rows = {}
    for m in re.finditer(r"INSERT INTO (\w+)(?:\s*\(([^)]*)\))?\s*VALUES\s*\((.*)\)\s*;",
                         sql):
        table = m.group(1)
        cols = ([c.strip() for c in m.group(2).split(",")] if m.group(2)
                else columns[table])
        values = [literal(v) for v in split_values(m.group(3))]
        if len(cols) != len(values):
            raise SystemExit("%s: %d columns, %d values in %s"
                             % (table, len(cols), len(values), m.group(0)[:80]))
        rows.setdefault(table, []).append(dict(zip(cols, values)))
    return columns, rows


def emit(columns, rows):
    out = ["SEED = {"]
    for table in sorted(rows):
        out.append('\t"%s": [' % table)
        for row in rows[table]:
            fields = ", ".join('"%s": %r' % (c, row[c]) for c in columns[table]
                               if c in row)
            out.append("\t\t{%s}," % fields)
        out.append("\t],")
    out.append("}")
    return "\n".join(out)


def main(argv):
    columns, rows = parse()
    text = emit(columns, rows)
    if "--emit" in argv:
        print(text)
        return 0
    src = open(STORE).read()
    i = src.find("SEED = {")
    if i < 0:
        print("kpi_seed: launchpad.store carries no SEED", file=sys.stderr)
        return 1
    j = src.index("\n}\n", i) + 3
    have = src[i:j].rstrip()
    if have != text.rstrip():
        print("kpi_seed: the seed in launchpad.store no longer matches the "
              "schema in launchpad.init.initDashboard.", file=sys.stderr)
        print("          Run: python3 tools/kpi_seed.py --emit", file=sys.stderr)
        return 1
    counts = ", ".join("%s=%d" % (t, len(rows[t])) for t in sorted(rows))
    print("kpi seed check passed: %s" % counts)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
