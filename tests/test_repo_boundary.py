"""Repository rules from AGENTS.md: no videos, no local secrets, required manifest fields."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
SECRET_FILES = {".env", ".dev.vars"}
SECRET_SUFFIXES = (".pem", ".p12", ".pfx", ".key")
MANIFEST_FIELDS = {
    "purpose",
    "tools_available",
    "prohibited_actions",
    "memory_policy",
    "context_sources",
    "model_choice",
    "prompts_or_system_instructions",
    "named_failure_modes",
    "evaluation_cases",
    "logging_policy",
    "human_override_points",
    "test_command",
    "ci_workflow_path",
}
ROLE_FIELDS = {
    "role",
    "native_artifact",
    "purpose",
    "context",
    "tools_and_permissions",
    "outputs",
    "handoff",
    "evaluation",
    "human_approval",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def test_no_video_files_tracked() -> None:
    videos = [str(p) for p in tracked_files() if p.suffix.lower() in VIDEO_SUFFIXES]
    assert not videos, f"Videos must be linked, never committed: {videos}"


def looks_like_secret(path: Path) -> bool:
    name = path.name.lower()
    if name in SECRET_FILES or name.endswith(SECRET_SUFFIXES):
        return True
    if name.startswith(".env.") and name != ".env.example":
        return True
    if path.suffix.lower() == ".json" and (ROOT / path).is_file():
        text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
        return '"private_key"' in text or '"service_account"' in text
    return False


def test_secret_detector_catches_known_shapes() -> None:
    for name in [".env", ".env.local", ".dev.vars", "key.pem", "cert.p12", "id.key"]:
        assert looks_like_secret(Path(name)), name
    assert not looks_like_secret(Path(".env.example"))
    assert not looks_like_secret(Path("README.md"))


def test_no_secret_files_tracked() -> None:
    secrets = [str(p) for p in tracked_files() if looks_like_secret(p)]
    assert not secrets, f"Secret files are tracked: {secrets}"


def test_manifest_has_course_fields() -> None:
    manifest = json.loads((ROOT / "agent-config.json").read_text(encoding="utf-8"))
    missing = MANIFEST_FIELDS - manifest.keys()
    assert not missing, f"agent-config.json is missing {sorted(missing)}"


def test_every_role_has_fields_and_an_artifact() -> None:
    manifest = json.loads((ROOT / "agent-config.json").read_text(encoding="utf-8"))
    team = manifest["agent_team"]
    assert team, "agent_team is empty"
    for role in team:
        missing = ROLE_FIELDS - role.keys()
        assert not missing, f"{role.get('role')} is missing {sorted(missing)}"
        assert (ROOT / role["native_artifact"]).is_file(), role["native_artifact"]
