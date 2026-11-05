import json, subprocess, sys
from pathlib import Path


def test_cli_import_context_transaction_and_resume(tmp_path, pdf):
    prefix = [
        sys.executable,
        "-m",
        "paper_research_coach.cli",
        "--data-dir",
        str(tmp_path / "cli"),
    ]

    def call(*args, stdin=None):
        result = subprocess.run(
            prefix + list(args), input=stdin, text=True, capture_output=True
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    p = call("import", str(pdf), "--title", "CLI example")
    tx = {
        "operation_id": "cli-1",
        "mutations": [
            {
                "kind": "note",
                "data": {
                    "id": "cli-note",
                    "paper_id": p["id"],
                    "content": "literal $(not a command)\n  原话  ",
                },
            }
        ],
    }
    one = call("commit", stdin=json.dumps(tx))
    two = call("commit", stdin=json.dumps(tx))
    assert one == two
    assert (
        call("resume", p["id"])["pending_thoughts"][0]["content"]
        == tx["mutations"][0]["data"]["content"]
    )
    assert call("text", p["id"], "0")["untrusted_source"] is True
    output = call("export", "paper", "--paper", p["id"])
    assert Path(output["path"]).is_file()


def test_version_flag_reports_the_release(capsys):
    import pytest
    from paper_research_coach import __version__
    from paper_research_coach.cli import parser

    with pytest.raises(SystemExit):
        parser().parse_args(["--version"])
    assert __version__ in capsys.readouterr().out
