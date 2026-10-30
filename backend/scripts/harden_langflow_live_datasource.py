"""Remove implicit environment defaults from the LIVE FastAPI data source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FLOW_PATH = ROOT / "langflow" / "Dova_Kitchen_Chef_BOB_LIVE.json"


def _node(payload: dict[str, Any]) -> dict[str, Any]:
    matches = [
        node
        for node in payload["data"]["nodes"]
        if "Live FastAPI Context"
        in str(node.get("data", {}).get("node", {}).get("display_name", ""))
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one LIVE FastAPI Context node, found {len(matches)}.")
    return matches[0]["data"]["node"]


def _replace_once(code: str, old: str, new: str, label: str) -> str:
    count = code.count(old)
    if count == 0 and new in code:
        return code
    if count != 1:
        raise RuntimeError(f"Expected one replacement for {label}, found {count}.")
    return code.replace(old, new, 1)


def main() -> None:
    payload = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    node = _node(payload)
    code = node["template"]["code"]["value"]
    code = _replace_once(
        code,
        "import json\nimport os\n",
        "import json\nimport math\nimport os\n",
        "math import",
    )
    old_backend = (
        '        backend_url = os.getenv(\n'
        '            "DOVAGENOME_BACKEND_URL", "http://127.0.0.1:8000"\n'
        '        ).strip().rstrip("/")\n'
    )
    new_backend = (
        '        backend_url = os.getenv("DOVAGENOME_BACKEND_URL", "").strip().rstrip("/")\n'
        '        if not backend_url:\n'
        '            raise ValueError(\n'
        '                "DOVAGENOME_BACKEND_URL belum dikonfigurasi pada proses Langflow."\n'
        '            )\n'
    )
    code = _replace_once(code, old_backend, new_backend, "backend URL default")
    old_timeout = (
        '        try:\n'
        '            timeout = float(os.getenv("DOVAGENOME_LIVE_TIMEOUT_SECONDS", "15"))\n'
        '        except ValueError:\n'
        '            timeout = 15.0\n'
    )
    new_timeout = (
        '        raw_timeout = (\n'
        '            os.getenv("DOVAGENOME_LIVE_TIMEOUT_SECONDS")\n'
        '            or os.getenv("LANGFLOW_TIMEOUT_SECONDS")\n'
        '            or ""\n'
        '        ).strip()\n'
        '        if not raw_timeout:\n'
        '            raise ValueError(\n'
        '                "DOVAGENOME_LIVE_TIMEOUT_SECONDS atau LANGFLOW_TIMEOUT_SECONDS belum dikonfigurasi pada proses Langflow."\n'
        '            )\n'
        '        try:\n'
        '            timeout = float(raw_timeout)\n'
        '        except ValueError as exc:\n'
        '            raise ValueError("DOVAGENOME_LIVE_TIMEOUT_SECONDS invalid.") from exc\n'
        '        if not math.isfinite(timeout) or timeout <= 0:\n'
        '            raise ValueError("DOVAGENOME_LIVE_TIMEOUT_SECONDS harus positif.")\n'
    )
    current_timeout = (
        '        raw_timeout = os.getenv("DOVAGENOME_LIVE_TIMEOUT_SECONDS", "").strip()\n'
        '        if not raw_timeout:\n'
        '            raise ValueError(\n'
        '                "DOVAGENOME_LIVE_TIMEOUT_SECONDS belum dikonfigurasi pada proses Langflow."\n'
        '            )\n'
        '        try:\n'
        '            timeout = float(raw_timeout)\n'
        '        except ValueError as exc:\n'
        '            raise ValueError("DOVAGENOME_LIVE_TIMEOUT_SECONDS invalid.") from exc\n'
        '        if not math.isfinite(timeout) or timeout <= 0:\n'
        '            raise ValueError("DOVAGENOME_LIVE_TIMEOUT_SECONDS harus positif.")\n'
    )
    if current_timeout in code:
        code = code.replace(current_timeout, new_timeout, 1)
    else:
        code = _replace_once(code, old_timeout, new_timeout, "timeout default")
    node["template"]["code"]["value"] = code
    node.setdefault("metadata", {})["code_hash"] = (
        "dova-live-config-fail-closed-"
        + hashlib.sha256(code.encode()).hexdigest()[:12]
    )
    FLOW_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"hardened={FLOW_PATH}")


if __name__ == "__main__":
    main()
