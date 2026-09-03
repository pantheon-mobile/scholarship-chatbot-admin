from __future__ import annotations

import asyncio
import logging
import sys


logger = logging.getLogger(__name__)


async def launch_ingestion_worker() -> None:
    """Run the same queue worker used by the nightly scheduled task."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.worker",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    message = output.decode("utf-8", errors="replace").strip()
    if process.returncode == 0:
        logger.info("manually launched ingestion worker completed: %s", message)
        return
    logger.error(
        "manually launched ingestion worker failed (exit=%s): %s",
        process.returncode,
        message,
    )
