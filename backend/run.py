from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from backend.app.config import get_settings
from backend.app.main import create_app
from backend.app.seed import seed_database


def load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def get_int_env(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def make_parser(default_host: str):
    parser = argparse.ArgumentParser(description="Run A2 安心留样后端服务")
    parser.add_argument("--host", default=os.environ.get("APP_HOST", default_host))
    parser.add_argument("--port", default=os.environ.get("APP_PORT", "8000"))
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--seed", action="store_true", help="启动前先执行数据库种子")
    return parser


def main(argv=None):
    root_dir = Path(__file__).resolve().parents[1]
    load_dotenv_file(root_dir / ".env")

    settings = get_settings()
    default_host = "0.0.0.0" if settings.app_env == "production" else "127.0.0.1"
    parser = make_parser(default_host=default_host)
    args = parser.parse_args(argv)

    if args.seed:
        seed_database(settings)

    app = create_app(settings)
    port = get_int_env("APP_PORT", int(args.port))
    if args.port and str(args.port).isdigit():
        port = int(args.port)

    reload = args.reload or settings.app_env != "production"
    uvicorn.run(
        app,
        host=args.host,
        port=port,
        reload=reload,
        reload_dirs=[str(Path(__file__).resolve().parent)],
        log_level="info",
    )


if __name__ == "__main__":
    main()
