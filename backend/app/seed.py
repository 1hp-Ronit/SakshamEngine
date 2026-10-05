"""`make seed` / `make reset`: wipe the database. Personas are fixtures in personas.yaml (applications are created via the API/UI)."""
import asyncio

from app.core import database
from app.core.config import get_settings


async def main() -> None:
    await database.drop_and_create_all()
    print(f"Database reset. {len(get_settings().personas)} demo personas available (see personas.yaml).")


if __name__ == "__main__":
    asyncio.run(main())
