"""Local development server.

    python -m app.cli.serve [--port 8000]

On Windows, psycopg's async mode needs a selector event loop, which plain `uvicorn` does not
use; this runner provides one. Production (Linux on Render) runs uvicorn directly.
"""

import argparse

import uvicorn

from app.main import build_app
from app.runtime import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    # access_log=False: the app logs its own access lines without query strings.
    config = uvicorn.Config(
        build_app(), host="127.0.0.1", port=args.port, log_level="info", access_log=False
    )
    run(uvicorn.Server(config).serve())


if __name__ == "__main__":
    main()
