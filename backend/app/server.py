from __future__ import annotations

from typing import Any, Dict, Optional

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import store
from .frontend import resolve_frontend_asset


def json(data: Dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def _root_payload() -> Dict[str, Any]:
    return {
        "name": "Social Content Platform API",
        "version": "0.1.0",
        "policy": "official APIs and authorized integrations only",
        "docs": "/docs",
    }


async def read_json(request: Request) -> Dict[str, Any]:
    try:
        payload = await request.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def owner_ok(request: Request) -> bool:
    return store.validate_owner_token(request.headers.get("x-owner-token") or "")


async def root(request: Request):
    asset = resolve_frontend_asset("/")
    if asset is not None:
        return FileResponse(asset)
    return json(_root_payload())


async def api_root(request: Request) -> JSONResponse:
    return json(_root_payload())


async def frontend_fallback(request: Request):
    path = request.url.path
    if path.startswith("/api/"):
        return json({"detail": "Not found"}, status=404)

    asset = resolve_frontend_asset(path)
    if asset is not None:
        return FileResponse(asset)

    return json({"detail": "Not found"}, status=404)


async def meta(request: Request) -> JSONResponse:
    return json(
        {
            "name": "Social Content Platform",
            "version": "0.1.0",
            "modules": [
                "platform_radar",
                "cart_workspace",
                "remix_studio",
                "image_canvas",
                "publishing_center",
                "comment_assistant",
            ],
            "policy": "compliant workflow only",
        }
    )


async def overview(request: Request) -> JSONResponse:
    return json(store.get_overview())


async def list_platforms(request: Request) -> JSONResponse:
    region = request.query_params.get("region")
    if region is not None and region not in {"domestic", "overseas"}:
        return json({"detail": "region must be domestic or overseas"}, status=400)
    return json({"items": store.get_platforms(region)})


async def list_accounts(request: Request) -> JSONResponse:
    if not owner_ok(request):
        return json({"detail": "Owner access required"}, status=403)
    platform_id = request.query_params.get("platform_id")
    return json({"items": store.get_accounts(platform_id)})


async def connect_account(request: Request) -> JSONResponse:
    if not owner_ok(request):
        return json({"detail": "Owner access required"}, status=403)
    payload = await read_json(request)
    try:
        account = store.connect_account(
            payload.get("platform_id", ""),
            payload.get("display_name", ""),
            payload.get("handle", ""),
        )
    except ValueError as exc:
        return json({"detail": str(exc)}, status=400)
    return json({"account": account})


async def radar(request: Request) -> JSONResponse:
    region = request.query_params.get("region", "domestic")
    if region not in {"domestic", "overseas"}:
        return json({"detail": "region must be domestic or overseas"}, status=400)
    platform_id = request.query_params.get("platform_id")
    keyword = request.query_params.get("keyword", "trend")
    try:
        limit = int(request.query_params.get("limit", "6"))
    except ValueError:
        limit = 6
    limit = max(1, min(limit, 20))
    items, insights = store.build_radar_items(region, platform_id, keyword, limit)
    return json(
        {
            "query": {
                "region": region,
                "platform_id": platform_id,
                "keyword": keyword,
                "limit": limit,
            },
            "items": items,
            "insights": insights,
        }
    )


async def cart_items(request: Request) -> JSONResponse:
    payload = await read_json(request)
    item = payload.get("item")
    if not item:
        return json({"detail": "item is required"}, status=400)
    with store.LOCK:
        if not any(entry["id"] == item["id"] for entry in store.STATE["cart"]):
            store.STATE["cart"].append(item)
    store.log_activity("add_to_cart", {"item_id": item["id"]})
    return json({"items": store.STATE["cart"], "count": len(store.STATE["cart"])})


async def cart_list(request: Request) -> JSONResponse:
    return json({"items": store.STATE["cart"], "count": len(store.STATE["cart"])})


async def cart_delete(request: Request) -> JSONResponse:
    item_id = request.path_params["item_id"]
    with store.LOCK:
        store.STATE["cart"] = [item for item in store.STATE["cart"] if item["id"] != item_id]
    store.log_activity("remove_cart_item", {"item_id": item_id})
    return json({"items": store.STATE["cart"], "count": len(store.STATE["cart"])})


async def create_remix(request: Request) -> JSONResponse:
    payload = await read_json(request)
    item_ids = payload.get("item_ids") or []
    mode = payload.get("mode", "merge")
    preserve_media = bool(payload.get("preserve_media", True))
    tone = payload.get("tone", "professional")
    sources = [item for item in store.STATE["cart"] if item["id"] in item_ids]
    if not sources:
        return json({"detail": "At least one cart item is required"}, status=400)
    try:
        job = store.create_remix_job({"mode": mode, "preserve_media": preserve_media, "tone": tone}, sources)
    except RuntimeError as exc:
        return json({"detail": str(exc)}, status=500)
    return json(job)


async def get_remix(request: Request) -> JSONResponse:
    job_id = request.path_params["job_id"]
    job = store.STATE["remix_jobs"].get(job_id)
    if not job:
        return json({"detail": "Remix job not found"}, status=404)
    return json(job)


async def create_canvas(request: Request) -> JSONResponse:
    payload = await read_json(request)
    try:
        count = int(payload.get("count", 6) or 6)
    except (TypeError, ValueError):
        count = 6
    try:
        job = store.create_canvas_job(
            {
                "image_name": payload.get("image_name", "uploaded-image.png"),
                "prompt_hint": payload.get("prompt_hint", "clean, commercial, future"),
                "count": count,
                "style": payload.get("style", "editorial"),
            }
        )
    except RuntimeError as exc:
        return json({"detail": str(exc)}, status=500)
    return json(job)


async def get_canvas(request: Request) -> JSONResponse:
    job_id = request.path_params["job_id"]
    job = store.STATE["canvas_jobs"].get(job_id)
    if not job:
        return json({"detail": "Canvas job not found"}, status=404)
    return json(job)


async def validate_owner(request: Request) -> JSONResponse:
    payload = await read_json(request)
    return json({"valid": store.validate_owner_token(payload.get("token", ""))})


async def create_draft(request: Request) -> JSONResponse:
    if not owner_ok(request):
        return json({"detail": "Owner access required"}, status=403)
    payload = await read_json(request)
    account = next((item for item in store.get_accounts() if item["id"] == payload.get("account_id")), None)
    if not account:
        return json({"detail": "Account not found"}, status=404)
    platform = store.get_platform(payload.get("platform_id", ""))
    if not platform:
        return json({"detail": "Platform not found"}, status=404)
    return json({"draft": store.create_draft(payload, account, platform)})


async def list_drafts(request: Request) -> JSONResponse:
    if not owner_ok(request):
        return json({"detail": "Owner access required"}, status=403)
    return json({"items": store.STATE["drafts"]})


async def comment_suggestions(request: Request) -> JSONResponse:
    payload = await read_json(request)
    return json(
        store.create_comment_suggestions(
            {
                "targets": payload.get("targets") or [],
                "context": payload.get("context", ""),
                "tone": payload.get("tone", "professional"),
            }
        )
    )


async def activity(request: Request) -> JSONResponse:
    return json({"items": store.STATE["activity_log"][-25:]})


routes = [
    Route("/api", api_root, methods=["GET"]),
    Route("/api/meta", meta, methods=["GET"]),
    Route("/api/overview", overview, methods=["GET"]),
    Route("/api/platforms", list_platforms, methods=["GET"]),
    Route("/api/accounts", list_accounts, methods=["GET"]),
    Route("/api/accounts/connect", connect_account, methods=["POST"]),
    Route("/api/radar", radar, methods=["GET"]),
    Route("/api/cart/items", cart_items, methods=["POST"]),
    Route("/api/cart", cart_list, methods=["GET"]),
    Route("/api/cart/{item_id:str}", cart_delete, methods=["DELETE"]),
    Route("/api/remix/jobs", create_remix, methods=["POST"]),
    Route("/api/remix/jobs/{job_id:str}", get_remix, methods=["GET"]),
    Route("/api/canvas/similar", create_canvas, methods=["POST"]),
    Route("/api/canvas/jobs/{job_id:str}", get_canvas, methods=["GET"]),
    Route("/api/owner/validate", validate_owner, methods=["POST"]),
    Route("/api/publishing/drafts", create_draft, methods=["POST"]),
    Route("/api/publishing/drafts", list_drafts, methods=["GET"]),
    Route("/api/comments/suggestions", comment_suggestions, methods=["POST"]),
    Route("/api/activity", activity, methods=["GET"]),
    Mount("/api/artifacts", StaticFiles(directory=str(store.ARTIFACT_DIR)), name="artifacts"),
    Route("/", root, methods=["GET"]),
    Route("/{path:path}", frontend_fallback, methods=["GET"]),
]

app = Starlette(debug=False, routes=routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
