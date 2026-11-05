"""Only the final protected-directory swap runs with Windows elevation."""
import contextlib
import io
import json
import traceback
from pathlib import Path

from install_builtin import ROOT, activate

result = ROOT / "install-result.json"
try:
    state = json.loads((ROOT / ".install-state.json").read_text(encoding="utf-8"))
    with contextlib.redirect_stdout(io.StringIO()):
        activate(Path(state["profile"]))
    value = {"ok": True, "archive": state["archive"], "sha256": state["pending_sha256"], "backup": state["backup"]}
except Exception as error:
    value = {"ok": False, "error": str(error), "details": traceback.format_exc()}
result.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
