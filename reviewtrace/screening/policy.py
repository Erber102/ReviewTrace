"""Source policy — defines which source types are allowed, flagged, or blocked."""

import json
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_POLICY_PATH = Path(__file__).parent.parent / "config" / "default_policy.json"


@dataclass
class SourcePolicy:
    allow: list[str] = field(default_factory=lambda: ["peer_reviewed", "preprint"])
    flag: list[str] = field(default_factory=lambda: ["workshop", "unknown"])
    block: list[str] = field(default_factory=lambda: ["blog", "grey_literature"])

    def verdict(self, source_type: str) -> str:
        """Return 'allow', 'flag', or 'block' for a given source type."""
        if source_type in self.block:
            return "block"
        if source_type in self.flag:
            return "flag"
        return "allow"

    def is_blocked(self, source_type: str) -> bool:
        return self.verdict(source_type) == "block"


def load_policy(path: Path | None = None) -> SourcePolicy:
    """Load policy from a JSON file. Falls back to default policy."""
    p = path or _DEFAULT_POLICY_PATH
    try:
        data = json.loads(p.read_text())
        return SourcePolicy(
            allow=data.get("allow", []),
            flag=data.get("flag", []),
            block=data.get("block", []),
        )
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[policy] Could not load {p}: {e} — using defaults")
        return SourcePolicy()
