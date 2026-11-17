"""Create the pqa settings profiles phase2_all and phase2_off (one time).

Both are copies of claude_cheap (made by team_setup.ps1), using the E2 test papers
(test_papers/e2_trust) and OpenAlex for paper details:

    phase2_all  all three Phase 2 enhancements on (E1 year filter, E2 trust score,
                E3 source diversity)
    phase2_off  all three off, i.e. the original behavior on the same papers

Then ask like in Phase 1:   pqa -s phase2_all ask "your question"

Existing profiles are kept; use --force to overwrite them.
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SETTINGS_DIR = Path.home() / ".pqa" / "settings"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="overwrite existing profiles")
    args = parser.parse_args()

    base_path = SETTINGS_DIR / "claude_cheap.json"
    if not base_path.exists():
        sys.exit(f"{base_path} not found: run .\\team_setup.ps1 first (Step 5).")
    base = json.loads(base_path.read_text(encoding="utf-8"))
    base.pop("md5", None)

    for name, on in (("phase2_all", True), ("phase2_off", False)):
        target = SETTINGS_DIR / f"{name}.json"
        if target.exists() and not args.force:
            print(f"kept     {target} (use --force to overwrite)")
            continue
        profile = json.loads(json.dumps(base))  # deep copy
        profile["parsing"]["use_doc_details"] = True
        profile["parsing"]["metadata_clients"] = ["openalex", "journal_quality"]
        profile["agent"]["apply_year_filter"] = on
        profile["answer"]["use_trust_score"] = on
        profile["agent"]["show_source_diversity"] = on
        profile["agent"]["index"]["paper_directory"] = str(REPO / "test_papers" / "e2_trust")
        profile["agent"]["index"]["name"] = f"pqa_{name}"
        target.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        print(f"written  {target}")


if __name__ == "__main__":
    main()
