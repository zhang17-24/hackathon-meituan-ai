"""创建 nailflow 三端测试账号（idempotent，可重复运行）"""
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
    from nailflow.persistence import init_engine, get_session_factory
    from app.gateway.auth.repositories.sqlite import SQLiteUserRepository
    from app.gateway.auth.password import hash_password
    from app.gateway.auth.models import User

    # Use the same persistence config as the app runtime (config.yaml
    # database section). Previously this defaulted to ./nail-flow.db while
    # the app read {sqlite_dir}/nailflow.db — seeded users were invisible.
    from nailflow.config import get_app_config
    from nailflow.persistence.engine import init_engine_from_config

    cfg = get_app_config()
    await init_engine_from_config(cfg.database)
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
