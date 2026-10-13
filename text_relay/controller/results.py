"""Results and job history endpoints."""

import asyncio
from typing import cast

from fastapi import Query, Request

from text_relay.controller.payloads import job_payload, result_payload


async def recent_results(
    request: Request,
    after: str | None = Query(default=None),
    wait: bool = Query(default=False),
) -> dict[str, list[dict[str, str | dict[str, str] | None]] | str | None]:
    app = request.app
    if wait:
        try:
            await asyncio.to_thread(
                app.state.store.wait_for_change,
                after,
                app.state.settings.long_poll_timeout_seconds,
            )
        except asyncio.CancelledError:
            app.state.store.interrupt_waiters()
            raise
    payload: dict[str, list[dict[str, str | dict[str, str] | None]] | str | None] = {
        "results": [
            cast(dict[str, str | dict[str, str] | None], result_payload(result))
            for result in app.state.store.recent()
        ],
        "jobs": [job_payload(job) for job in app.state.store.jobs()],
        "cursor": app.state.store.change_id(),
        "active_profile": app.state.ocr_profiles.active_profile_id,
    }
    if app.state.is_shutting_down:
        payload["server_status"] = "stopping"
    return payload
