import secrets
from pathlib import Path


root = Path(__file__).resolve().parents[1]
path = root / ".env"
with path.open("x", encoding="utf-8") as stream:
    stream.write(
        f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
        f"ADMIN_TOKEN={secrets.token_urlsafe(32)}\n"
        f"DRIVER_TOKEN={secrets.token_urlsafe(32)}\n"
        "APP_PORT=8080\n"
    )
print("Created .env with generated credentials")
