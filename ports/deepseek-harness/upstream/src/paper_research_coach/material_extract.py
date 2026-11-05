"""Run the upstream extraction pipeline with PRC's packaged PDF engine."""
from pathlib import Path
import os
import sys


def main():
    for index, argument in enumerate(sys.argv[1:], 1):
        if argument == "--output-dir" and index + 1 < len(sys.argv):
            os.environ["LEARNING_SKILL_WORKDIR"] = str(Path(sys.argv[index + 1]).resolve())
            break
    from .workspaces import INTEGRATIONS
    sys.path.insert(0, str(INTEGRATIONS / "learn-from-materials/scripts"))
    from cli_output import configure_output
    from extractor.prc_utils import main as extract
    configure_output()
    extract()


if __name__ == "__main__":
    main()
