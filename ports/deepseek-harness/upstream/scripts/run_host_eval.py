"""Run bounded synthetic dialogue tests in an installed Claude Code host.
Outputs are candidates for human scoring, never automatic claims of learning gains.
No tools, MCP, personal files, or session persistence are used.
"""

import argparse, json, subprocess, tempfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--ids", default="")
p.add_argument("--output", default=".prc/host-evaluation.json")
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
skill = root / "skills/paper-research-coach"
source = "\n\n".join(
    path.read_text()
    for path in [skill / "SKILL.md", *sorted((skill / "references").glob("*.md"))]
)
cases = json.loads((root / "evals/scenarios.json").read_text())
selected = args.ids.split(",") if args.ids else []
results = []
with tempfile.TemporaryDirectory(prefix="prc-host-eval-") as directory:
    for case in cases:
        if selected and case["id"] not in selected:
            continue
        command = [
            "claude",
            "-p",
            "--no-session-persistence",
            "--strict-mcp-config",
            "--setting-sources",
            "user",
            "--tools",
            "",
            "--output-format",
            "json",
            "--append-system-prompt",
            source,
        ]
        try:
            run = subprocess.run(
                command,
                input=case["prompt"],
                text=True,
                capture_output=True,
                cwd=directory,
                timeout=150,
            )
            parsed = (
                json.loads(run.stdout)
                if run.stdout.strip().startswith("{")
                else {"result": run.stdout}
            )
            results.append(
                {
                    "id": case["id"],
                    "exit_code": run.returncode,
                    "is_error": parsed.get("is_error", False),
                    "response": parsed.get("result", ""),
                    "models": list(parsed.get("modelUsage", {})),
                    "checks": case["checks"],
                }
            )
            print(case["id"], run.returncode, flush=True)
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "id": case["id"],
                    "is_error": True,
                    "response": "Host timeout",
                    "checks": case["checks"],
                }
            )
            print(case["id"], "timeout", flush=True)
        out = root / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
