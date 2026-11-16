#!/usr/bin/env python3
"""PSST: print the `run:` script of one step of a GitHub workflow job, so that a test workflow can execute the
production step verbatim (macos-signing-dryrun.yml runs the Developer ID steps of web-desktop.yml this way).

  workflow-step.py <workflow.yml> <job> "<step name>" ['expression=value' ...]

Each 'expression=value' replaces ${{ expression }} in the script. Fails when the step does not exist, has no `run:`,
or a ${{ … }} expression is left unresolved (so a changed production step can never run half-substituted).
The production `env:` keys and working directory are printed to stderr for the log.
"""
import re
import sys

import yaml

wf, job, name, *subs = sys.argv[1:]
steps = yaml.safe_load(open(wf))["jobs"][job]["steps"]
step = next((s for s in steps if s.get("name") == name), None)
if not step or "run" not in step:
    sys.exit(f"step {name!r} with run: not found in {wf} job {job}")
script = step["run"]
for kv in subs:
    k, v = kv.split("=", 1)
    script = re.sub(r"\$\{\{\s*" + re.escape(k) + r"\s*\}\}", v, script)
left = re.findall(r"\$\{\{[^}]*\}\}", script)
if left:
    sys.exit(f"unresolved expressions in {name!r}: {left}")
print(f"# {wf} / {job} / {name!r} — production env: {sorted(step.get('env') or {})}, "
      f"working-directory: {step.get('working-directory', '.')}", file=sys.stderr)
print(script)
