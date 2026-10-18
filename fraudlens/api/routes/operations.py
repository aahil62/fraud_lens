"""Authenticated authoritative operational interface."""
import asyncio
import json
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, StreamingResponse

from fraudlens.api.deps import get_current_analyst
from fraudlens.api.state import state
from fraudlens.core.auth.security import decode_access_token
from fraudlens.models.schemas import AnalystProfile
from fraudlens.operations.guidance import guidance_response
from fraudlens.operations.models import (Channel, ControlInput, DecisionInput, ScenarioInput, TransactionInput,
                                         ClaimInput, AssignInput, ApprovalRequestInput, ApprovalDecisionInput, PresenceInput, ComplaintInput)
from fraudlens.operations.team import OperationError
from fraudlens.operations.reports import markdown, pdf, report
from fraudlens.operations.service import NotFoundError


class OperationsRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request):
            try:
                response = await handler(request)
                response.headers["Cache-Control"] = "no-store"
                return response
            except OperationError as exc:
                return JSONResponse(exc.payload, status_code=exc.status_code, headers={"Cache-Control": "no-store"})
            except NotFoundError as exc:
                raise HTTPException(404, str(exc)) from exc
            except httpx.HTTPError as exc:
                raise HTTPException(503, "Bank simulator unavailable. The request was not confirmed.") from exc
        return guarded


router = APIRouter(prefix="/ops", tags=["live operations"], route_class=OperationsRoute,
                   dependencies=[Depends(get_current_analyst)])


def service():
    if state.operations is None:
        raise HTTPException(503, "Operational service is starting")
    return state.operations


@router.get("/snapshot")
def snapshot():
    return service().snapshot()


@router.post("/transactions")
def ingest(payload: TransactionInput, response: Response, current: AnalystProfile = Depends(get_current_analyst)):
    result = service().ingest(payload, current.display_name)
    response.status_code = 200 if result["duplicate"] else 201
    return result


@router.get("/transactions")
def transactions(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), channel: Channel | None = None):
    return service().listing("transactions", limit, offset, channel)


@router.get("/cases")
def cases(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), channel: Channel | None = None,
          status: Literal["new", "investigating", "escalated", "resolved"] | None = None):
    return service().listing("cases", limit, offset, channel, status)


@router.get("/cases/{case_id}")
def case_detail(case_id: str):
    return service().get_case(case_id)


@router.post("/cases/{case_id}/decision")
def decide(case_id: str, payload: DecisionInput, current: AnalystProfile = Depends(get_current_analyst)):
    return service().decide(case_id, payload, current)


@router.post("/cases/{case_id}/claim")
def claim(case_id: str, payload: ClaimInput, current: AnalystProfile = Depends(get_current_analyst)):
    return service().claim(case_id, payload, current)


@router.post("/cases/{case_id}/assign")
def assign(case_id: str, payload: AssignInput, current: AnalystProfile = Depends(get_current_analyst)):
    return service().assign(case_id, payload, current)


@router.post("/cases/{case_id}/approval-request")
def request_approval(case_id: str, payload: ApprovalRequestInput, current: AnalystProfile = Depends(get_current_analyst)):
    return service().request_approval(case_id, payload, current)


@router.post("/cases/{case_id}/approval")
def decide_approval(case_id: str, payload: ApprovalDecisionInput, current: AnalystProfile = Depends(get_current_analyst)):
    return service().decide_approval(case_id, payload, current)


@router.post("/complaints")
def complaint(payload: ComplaintInput, current: AnalystProfile = Depends(get_current_analyst)):
    return service().file_complaint(payload, current)


@router.post("/presence/heartbeat")
def heartbeat(payload: PresenceInput, current: AnalystProfile = Depends(get_current_analyst)):
    service().heartbeat(current, payload.current_case_id)
    return {"ok": True}


@router.post("/actions/{action_id}/retry")
def retry(action_id: str, current: AnalystProfile = Depends(get_current_analyst)):
    return service().retry_action(action_id, current)


@router.get("/cases/{case_id}/report")
def case_report(case_id: str, format: Literal["json", "markdown", "pdf"] = "json"):
    value = report(service().get_case(case_id))
    if format == "json":
        return value
    headers = {"Content-Disposition": f'attachment; filename="{value["case_id"]}.{ "pdf" if format == "pdf" else "md"}"'}
    if format == "pdf":
        return Response(pdf(value), media_type="application/pdf", headers=headers)
    return Response(markdown(value), media_type="text/markdown; charset=utf-8", headers=headers)


@router.get("/guidance")
def guidance():
    return guidance_response()


@router.post("/simulation/scenario")
def scenario(payload: ScenarioInput, current: AnalystProfile = Depends(get_current_analyst)):
    return service().run_scenario(payload.channel, payload.scenario, current.display_name)


@router.post("/simulation/control")
def control(payload: ControlInput, current: AnalystProfile = Depends(get_current_analyst)):
    return service().control(payload, current.display_name)


@router.post("/process")
def process():
    service().process_jobs()
    return service().snapshot()


@router.get("/events")
async def events(request: Request, after: int = Query(0, ge=0)):
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()

    async def stream():
        cursor = after
        heartbeat = 0
        while not await request.is_disconnected():
            if decode_access_token(token) is None:
                yield 'event: auth_expired\ndata: {}\n\n'
                return
            current = await asyncio.to_thread(service().cursor)
            if current != cursor:
                cursor = current
                yield f"data: {json.dumps({'cursor': cursor})}\n\n"
            elif heartbeat % 10 == 0:
                yield ": heartbeat\n\n"
            heartbeat += 1
            await asyncio.sleep(.5)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
