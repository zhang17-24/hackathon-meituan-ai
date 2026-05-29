"""创建 NailFlow 三端测试账号（idempotent，可重复运行）"""
import asyncio
import sys
from pathlib import Path

# 确保 backend 目录在 Python path 中
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "harness"))

USERS = [
    {"email": "user@nailflow.dev", "password": "nail123456", "nail_role": "user"},
    {"email": "ops@nailflow.dev",  "password": "nail123456", "nail_role": "ops"},
    {"email": "dev@nailflow.dev",  "password": "nail123456", "nail_role": "dev"},
]


async def main():
    from deerflow.persistence import init_engine, get_session_factory
    from app.gateway.auth.repositories.sqlite import SQLiteUserRepository
    from app.gateway.auth.password import hash_password
    from app.gateway.auth.models import User

    # Load config to find the SQLite path
    import os
    sqlite_dir = os.getenv("SQLITE_DIR", ".")
    db_url = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{sqlite_dir}/deer-flow.db")

    await init_engine("sqlite", url=db_url, sqlite_dir=sqlite_dir)
    sf = get_session_factory()
    if sf is None:
        print("ERROR: session factory is None — engine not initialized")
        sys.exit(1)

    repo = SQLiteUserRepository(sf)

    for u in USERS:
        try:
            existing = await repo.get_user_by_email(u["email"])
            if existing:
                print(f"Already exists: {u['email']} (nail_role={getattr(existing, 'nail_role', 'unknown')})")
                continue
            user = User(
                email=u["email"],
                password_hash=hash_password(u["password"]),
                nail_role=u["nail_role"],
            )
            await repo.create_user(user)
            print(f"Created: {u['email']} (nail_role={u['nail_role']})")
        except Exception as e:
            print(f"Error creating {u['email']}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
