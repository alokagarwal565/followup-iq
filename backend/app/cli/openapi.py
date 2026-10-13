"""Writes the API's OpenAPI schema to backend/openapi.json for frontend type generation.

    python -m app.cli.openapi

Runs without a database or keys, so the frontend's generated types never depend on a live server.
"""

import json
from pathlib import Path

from app.config import Settings
from app.main import create_app

OUTPUT = Path(__file__).resolve().parents[2] / "openapi.json"


def main() -> None:
    settings = Settings(database_url="postgresql://schema-export/none")
    schema = create_app(settings, pool=None).openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
