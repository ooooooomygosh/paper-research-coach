"""Synthetic response evaluation in a logged-in Codex CLI; no model override."""

import argparse, json, subprocess, tempfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--codex", default="codex")
p.add_argument("--ids", default="")
p.add_argument("--output", default=".prc/codex-evaluation.json")
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
skill = root / "skills/paper-research-coach"
source = "\n\n".join(
    path.read_text()
    for path in [skill / "SKILL.md", *sorted((skill / "references").glob("*.md"))]
)
cases = json.loads((root / "evals/scenarios.json").read_text())
results = []
executable = str(Path(args.codex).resolve()) if "/" in args.codex else args.codex
with tempfile.TemporaryDirectory(prefix="prc-codex-eval-") as directory:
    for case in cases:
        if args.ids and case["id"] not in args.ids.split(","):
            continue
        out = Path(directory) / "reply.txt"
        prompt = (
            "这是独立的纯文本带读行为评测。只使用下面提供的材料，不调用工具，不读取其他文件，不保存笔记，也不执行代码。下面的skill是本轮要应用的协议。按随后给出的学生消息直接进行这一轮带读，不解释评测本身。\n\n"
            + source
            + "\n\n学生消息：\n"
            + case["prompt"]
        )
        try:
            run = subprocess.run(
                [
                    executable,
                    "exec",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "--color",
                    "never",
                    "--output-last-message",
                    str(out),
                    "-",
                ],
                input=prompt,
                text=True,
                capture_output=True,
                cwd=directory,
                timeout=240,
            )
            response = out.read_text() if out.is_file() else "No final response"
            results.append(
                {
                    "id": case["id"],
                    "exit_code": run.returncode,
                    "response": response,
                    "checks": case["checks"],
                }
            )
            print(case["id"], run.returncode, flush=True)
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "id": case["id"],
                    "exit_code": -1,
                    "response": "Host timeout",
                    "checks": case["checks"],
                }
            )
            print(case["id"], "timeout", flush=True)
        if out.exists():
            out.unlink()
        target = root / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(results, ensure_ascii=False, indent=2))
