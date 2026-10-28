"""Run a unittest directory, rejecting empty discovery rather than reporting success."""

import argparse
import os
import sys
import unittest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    args = parser.parse_args()
    # -B affects this interpreter only. Descendant CLI/import tests inherit the
    # environment flag, keeping ignored bytecode from outliving branch changes.
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    suite = unittest.defaultTestLoader.discover(args.directory, pattern="test_*.py")
    count = suite.countTestCases()
    if not count:
        print(f"No tests collected from {args.directory}", file=sys.stderr)
        return 2
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
