from __future__ import annotations

import argparse
import asyncio

from app.db.models.camera import Camera
from app.db.session import async_session_factory
from app.core.exceptions import NotFoundError
from app.vision.pipeline import process_frame


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--camera", default="cam-001")
    p.add_argument("--arrive", default=None, help="plate arriving")
    p.add_argument("--depart", action="store_true")
    args = p.parse_args()
    async with async_session_factory() as db:
        camera = await db.get(Camera, args.camera)
        if camera is None:
            raise NotFoundError(f"camera {args.camera} not found - run python -m scripts.seed first")
        if args.depart:
            from app.core.config import get_settings

            camera.consecutive_empty_frames = max(0, get_settings().DEPARTURE_EMPTY_FRAMES - 1)
            await db.commit()
            result = await process_frame(db, camera, None, False, None)
        else:
            result = await process_frame(db, camera, None, True, args.arrive)
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
