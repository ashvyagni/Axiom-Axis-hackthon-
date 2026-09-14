import time
import logging
from axiom.config import get_settings

logger = logging.getLogger(__name__)


class PRISMAdapter:
    def __init__(self):
        settings = get_settings()
        self.host = settings.PRISMTRACE_HOST
        self.project_id = settings.PRISMTRACE_PROJECT_ID
        self.api_key = settings.PRISMTRACE_API_KEY
        self._client = None

        if self.api_key and self.project_id:
            try:
                from prismtrace import PRISMtrace
                self._client = PRISMtrace(
                    api_key=self.api_key,
                    host=self.host,
                    project_id=self.project_id,
                )
                logger.info("PRISM SDK initialized")
            except Exception as e:
                logger.warning(f"PRISM SDK init failed, using HTTP fallback: {e}")

    async def trace_run(
        self,
        session_id: str,
        incident_id: str | None,
        model: str,
        input_text: str,
        output_text: str,
        latency_ms: int,
        metadata: dict | None = None,
    ):
        import httpx
        payload = {
            "project_id": self.project_id,
            "model": model,
            "input_messages": [{"role": "user", "content": input_text}],
            "output_message": output_text,
            "latency_ms": latency_ms,
            "session_id": session_id,
            "agent_id": "axiom-orchestrator",
            "agent_name": "AXIOM",
            "metadata": {
                "incident_id": incident_id,
                **(metadata or {}),
            },
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.host}/api/traces",
                    json=payload,
                    headers={"X-PRISMtrace-Key": self.api_key, "Content-Type": "application/json"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    logger.info(f"PRISM trace sent: {session_id}")
                else:
                    logger.warning(f"PRISM trace failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"PRISM trace error: {e}")


prism = PRISMAdapter()
