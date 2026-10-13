"""Start the workbench again once the old service has exited.

`python -m paper_research_coach.relaunch --data-dir D --port P --wait-pid PID` is spawned by a
service that is about to restart itself after an update. It waits for that process to leave,
then replaces itself with a fresh `prc serve` that runs the newly installed code.
"""

import argparse
import os
import sys
import time


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--wait-pid", type=int, default=0)
    args = p.parse_args(argv)
    deadline = time.monotonic() + 20
    while args.wait_pid and time.monotonic() < deadline:
        try:
            os.kill(args.wait_pid, 0)
        except OSError:
            break
        time.sleep(0.2)
    time.sleep(0.5)  # let the old process release the port
    os.execv(
        sys.executable,
        [sys.executable, "-m", "paper_research_coach.cli", "--data-dir", args.data_dir, "serve", "--no-open", "--port", str(args.port)],
    )


if __name__ == "__main__":
    main()
