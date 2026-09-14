import time
import uuid
import logging
from datetime import datetime, timezone
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

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def trace_run(
        self,
        session_id: str,
        incident_id: str | None,
        model: str,
        input_text: str,
        output_text: str,
        latency_ms: int,
        metadata: dict | None = None,
        spans: list[dict] | None = None,
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
        trace_id = None
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.host}/api/traces",
                    json=payload,
                    headers={"X-PRISMtrace-Key": self.api_key, "Content-Type": "application/json"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    trace_id = data.get("trace_id") or data.get("id")
                    logger.info(f"PRISM trace sent: {session_id} -> {trace_id}")
                else:
                    logger.warning(f"PRISM trace failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"PRISM trace error: {e}")

        if spans and trace_id:
            await self._send_spans(trace_id, session_id, spans)

    async def _send_spans(self, trace_id: str, session_id: str, spans: list[dict]):
        import httpx
        payload = {
            "trace_id": trace_id,
            "project_id": self.project_id,
            "session_id": session_id,
            "spans": spans,
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.host}/api/spans/ingest",
                    json=payload,
                    headers={"X-PRISMtrace-Key": self.api_key, "Content-Type": "application/json"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    logger.info(f"PRISM spans sent: {len(spans)} spans for {trace_id}")
                else:
                    logger.warning(f"PRISM spans failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.error(f"PRISM spans error: {e}")

    def create_span(
        self,
        name: str,
        span_type: str,
        input_text: str = "",
        output_text: str = "",
        model: str | None = None,
        parent_span_id: str | None = None,
        status: str = "ok",
        error_message: str | None = None,
        token_count_input: int | None = None,
        token_count_output: int | None = None,
        metadata: dict | None = None,
    ) -> dict:
        now = self._now_iso()
        return {
            "span_id": str(uuid.uuid4()),
            "parent_span_id": parent_span_id,
            "name": name,
            "span_type": span_type,
            "input_text": input_text[:2000] if input_text else "",
            "output_text": output_text[:2000] if output_text else "",
            "start_time": now,
            "end_time": now,
            "duration_ms": 0,
            "status": status,
            "error_message": error_message,
            "model": model,
            "token_count_input": token_count_input,
            "token_count_output": token_count_output,
            "metadata": metadata or {},
        }

    def finish_span(self, span: dict, start_time: float, status: str = "ok", error_message: str | None = None):
        duration_ms = int((time.time() - start_time) * 1000)
        span["end_time"] = self._now_iso()
        span["duration_ms"] = duration_ms
        span["status"] = status
        if error_message:
            span["error_message"] = error_message


prism = PRISMAdapter()
