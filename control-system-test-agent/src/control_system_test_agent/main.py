import argparse
import asyncio
import json
import os

import httpx

from .clients import ControlSystemClient, GenBClient
from .orchestrator import DeterministicAnswerer, TestAgent
from .settings import Settings


async def _run(session_id: str, message: str) -> int:
    settings = Settings.from_mapping(os.environ)
    timeout = httpx.Timeout(settings.http_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as http:
        agent = TestAgent(
            agent_id=settings.agent_id,
            service_credential=settings.service_credential,
            genb=GenBClient(http, settings.genb_base_url),
            control=ControlSystemClient(http, settings.control_system_base_url),
            answerer=DeterministicAnswerer(),
        )
        result = await agent.chat(
            user_token=settings.user_token,
            session_id=session_id,
            message=message,
        )
    print(
        json.dumps(
            {
                "agentId": settings.agent_id,
                "sessionId": session_id,
                "answer": result.answer,
                "contextMessageCount": result.context_message_count,
                "committed": result.committed,
                "warnings": list(result.warnings),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result.committed else 2


def main() -> None:
    parser = argparse.ArgumentParser(description="GenB Control System test agent")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--message", required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.session_id, args.message)))


if __name__ == "__main__":
    main()
