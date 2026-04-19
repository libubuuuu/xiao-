from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from itertools import cycle
from pathlib import Path
from typing import Any, Dict, List, Optional
import textwrap

from .config import get_settings
from .repository import get_repository

SETTINGS = get_settings()
REPOSITORY = get_repository()
OWNER_ACCESS_TOKEN = SETTINGS.owner_access_token
BASE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = BASE_DIR / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
FFMPEG_BIN = shutil.which("ffmpeg") or "ffmpeg"

LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slugify(value: str) -> str:
    value = value.strip().lower()
    chars = []
    for ch in value:
        chars.append(ch if ch.isalnum() else "-")
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "item"


def _stable_score(*parts: str) -> int:
    digest = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _artifact_url(filename: str) -> str:
    return f"/api/artifacts/{filename}"


def _artifact_text_path(filename: str) -> Path:
    return ARTIFACT_DIR / f"{Path(filename).stem}.txt"


def _color_from_score(score: int, palette: List[str]) -> str:
    return palette[score % len(palette)]


def _wrap_line(prefix: str, value: str, width: int = 42) -> List[str]:
    wrapped = textwrap.wrap(value, width=width) or [""]
    return [f"{prefix}{wrapped[0]}"] + [f"  {line}" for line in wrapped[1:]]


def _run_ffmpeg(command: List[str], cwd: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to generate image and video artifacts.")

    result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(stderr or "ffmpeg failed to generate an artifact.")


def _render_image(filename: str, lines: List[str], seed: str) -> str:
    output_path = ARTIFACT_DIR / filename
    text_path = _artifact_text_path(filename)
    palette = [
        "0x102A43",
        "0x1F2933",
        "0x0F172A",
        "0x1E3A5F",
        "0x274060",
        "0x2D1B4E",
    ]
    accents = [
        "0x38BDF8",
        "0x22C55E",
        "0xF97316",
        "0xA855F7",
        "0xFB7185",
        "0xFACC15",
    ]
    background = _color_from_score(_stable_score(seed, "background"), palette)
    accent = _color_from_score(_stable_score(seed, "accent"), accents)

    text_path.write_text("\n".join(lines), encoding="utf-8")
    try:
        vf = (
            f"drawbox=x=0:y=0:w=iw:h=18:color={accent}:t=fill,"
            "drawbox=x=0:y=ih-28:w=iw:h=28:color=black@0.32:t=fill,"
            "drawtext="
            f"fontsize=34:fontcolor=white:line_spacing=14:box=1:boxcolor=black@0.45:"
            f"boxborderw=26:x=60:y=72:textfile={text_path.name}"
        )
        _run_ffmpeg(
            [
                FFMPEG_BIN,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={background}:s=1280x720",
                "-frames:v",
                "1",
                "-update",
                "1",
                "-vf",
                vf,
                output_path.name,
            ],
            cwd=ARTIFACT_DIR,
        )
    finally:
        text_path.unlink(missing_ok=True)

    return _artifact_url(output_path.name)


def _render_video(filename: str, storyboard_filename: str) -> str:
    output_path = ARTIFACT_DIR / filename
    _run_ffmpeg(
        [
            FFMPEG_BIN,
            "-y",
            "-loop",
            "1",
            "-i",
            storyboard_filename,
            "-t",
            "5",
            "-vf",
            "scale=1280:720,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-movflags",
            "+faststart",
            output_path.name,
        ],
        cwd=ARTIFACT_DIR,
    )
    return _artifact_url(output_path.name)


PLATFORMS: List[Dict[str, Any]] = [
    {"id": "xiaohongshu", "name": "Xiaohongshu", "region": "domestic", "supports": ["text", "image", "video", "mixed"], "audience": "Lifestyle, product discovery, consumer decisions", "note": "Strong for image-led and short-form content.", "source_hint": "Public discovery feed and saved-note trends"},
    {"id": "douyin", "name": "Douyin", "region": "domestic", "supports": ["video", "mixed", "text", "image"], "audience": "Short video traffic, live commerce, fast trend spread", "note": "Best for punchy hooks and quick cuts.", "source_hint": "Trending list, recommendation feed, creator clips"},
    {"id": "weixin-official", "name": "WeChat Official Account", "region": "domestic", "supports": ["text", "image", "mixed"], "audience": "Deep content, brand retention, conversion support", "note": "Good for long-form and article-style content.", "source_hint": "Article pages, repost chains, historical viral posts"},
    {"id": "wechat-channel", "name": "WeChat Channels", "region": "domestic", "supports": ["video", "mixed", "text"], "audience": "WeChat ecosystem short video and private traffic", "note": "Good for social and community-linked content.", "source_hint": "Recommendation feed, topic pages, live replays"},
    {"id": "kuaishou", "name": "Kuaishou", "region": "domestic", "supports": ["video", "mixed", "text"], "audience": "Community content, live streaming, strong interaction", "note": "Well suited for continuous updates and live content.", "source_hint": "Hot recommendations, creator pages, topic challenges"},
    {"id": "zhihu", "name": "Zhihu", "region": "domestic", "supports": ["text", "image", "video", "mixed"], "audience": "Knowledge, opinions, search traffic", "note": "Good for structured answers and expert content.", "source_hint": "Hot list, question pages, columns and articles"},
    {"id": "tieba", "name": "Tieba", "region": "domestic", "supports": ["text", "image", "video", "mixed"], "audience": "Interest communities and discussion-led content", "note": "Good for topic discussion and community activation.", "source_hint": "Hot posts, pinned threads, reply chains"},
    {"id": "bilibili", "name": "Bilibili", "region": "domestic", "supports": ["video", "mixed", "image", "text"], "audience": "Young users, long/short video, knowledge and entertainment", "note": "Great for scripted video with a clear structure.", "source_hint": "Trending charts, creator pages, comments"},
    {"id": "x", "name": "X", "region": "overseas", "supports": ["text", "image", "video", "mixed"], "audience": "Real-time trends, topic spread, opinion content", "note": "Good for short posts and chained amplification.", "source_hint": "Trending topics, hashtags, repost chains"},
    {"id": "youtube", "name": "YouTube", "region": "overseas", "supports": ["video", "mixed", "text", "image"], "audience": "Long and short video, search traffic, education", "note": "Best as a primary video surface with strong thumbnails.", "source_hint": "Trending, channel pages, recommended videos"},
    {"id": "tiktok", "name": "TikTok", "region": "overseas", "supports": ["video", "mixed", "text", "image"], "audience": "Short video, challenges, viral distribution", "note": "Good for fast, visual, highly engaging content.", "source_hint": "For You, tags, challenge charts"},
]


ACCOUNTS: List[Dict[str, Any]] = [
    {"id": "acc-xhs-brand", "platform_id": "xiaohongshu", "display_name": "Brand Content", "handle": "@brand_lab", "status": "connected", "draft_count": 3, "last_sync": _now(), "owner_only": True},
    {"id": "acc-douyin-main", "platform_id": "douyin", "display_name": "Douyin Main", "handle": "@main_show", "status": "connected", "draft_count": 5, "last_sync": _now(), "owner_only": True},
    {"id": "acc-youtube-studio", "platform_id": "youtube", "display_name": "YouTube Studio", "handle": "@studio_channel", "status": "connected", "draft_count": 2, "last_sync": _now(), "owner_only": True},
]

REPOSITORY.seed_accounts(ACCOUNTS, _now())


STATE: Dict[str, Any] = {
    "cart": [],
    "remix_jobs": {},
    "canvas_jobs": {},
    "drafts": [],
    "comment_jobs": {},
    "activity_log": [],
}


def log_activity(action: str, payload: Dict[str, Any]) -> None:
    with LOCK:
        timestamp = _now()
        record = {"action": action, "payload": payload, "timestamp": timestamp}
        STATE["activity_log"].append(record)
    REPOSITORY.log_activity(action, payload, timestamp)


def get_cart_items() -> List[Dict[str, Any]]:
    items = REPOSITORY.list_cart_items()
    with LOCK:
        STATE["cart"] = items
    return items


def add_cart_item(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    timestamp = _now()
    REPOSITORY.add_cart_item(item, timestamp)
    with LOCK:
        if not any(entry["id"] == item["id"] for entry in STATE["cart"]):
            STATE["cart"].append(item)
        items = list(STATE["cart"])
    log_activity("add_to_cart", {"item_id": item["id"]})
    return items


def remove_cart_item(item_id: str) -> List[Dict[str, Any]]:
    REPOSITORY.remove_cart_item(item_id)
    with LOCK:
        STATE["cart"] = [item for item in STATE["cart"] if item["id"] != item_id]
        items = list(STATE["cart"])
    log_activity("remove_cart_item", {"item_id": item_id})
    return items


def get_remix_job(job_id: str) -> Optional[Dict[str, Any]]:
    job = STATE["remix_jobs"].get(job_id) or REPOSITORY.get_remix_job(job_id)
    if job and job_id not in STATE["remix_jobs"]:
        with LOCK:
            STATE["remix_jobs"][job_id] = job
    return job


def get_canvas_job(job_id: str) -> Optional[Dict[str, Any]]:
    job = STATE["canvas_jobs"].get(job_id) or REPOSITORY.get_canvas_job(job_id)
    if job and job_id not in STATE["canvas_jobs"]:
        with LOCK:
            STATE["canvas_jobs"][job_id] = job
    return job


def get_drafts() -> List[Dict[str, Any]]:
    drafts = REPOSITORY.list_drafts()
    with LOCK:
        STATE["drafts"] = drafts
    return drafts


def get_activity_log(limit: int = 25) -> List[Dict[str, Any]]:
    activity = REPOSITORY.list_activity(limit)
    with LOCK:
        STATE["activity_log"] = activity
    return activity


def get_platforms(region: Optional[str] = None) -> List[Dict[str, Any]]:
    if region:
        return [item for item in PLATFORMS if item["region"] == region]
    return PLATFORMS


def get_platform(platform_id: str) -> Optional[Dict[str, Any]]:
    return next((item for item in PLATFORMS if item["id"] == platform_id), None)


def get_accounts(platform_id: Optional[str] = None) -> List[Dict[str, Any]]:
    accounts = REPOSITORY.list_accounts(platform_id)
    if platform_id is None:
        with LOCK:
            ACCOUNTS[:] = accounts
    return accounts


def connect_account(platform_id: str, display_name: str, handle: str) -> Dict[str, Any]:
    platform = get_platform(platform_id)
    if not platform:
        raise ValueError("Unknown platform")

    with LOCK:
        account_id = f"acc-{uuid.uuid4().hex[:10]}"
    account = REPOSITORY.create_account(account_id, platform_id, display_name, handle, _now())
    with LOCK:
        ACCOUNTS.insert(0, account)
    log_activity("connect_account", {"account_id": account["id"], "platform_id": platform_id})
    return account


def _choose_content_type(platform: Dict[str, Any], index: int) -> str:
    supported = platform["supports"]
    return supported[index % len(supported)]


def _build_media(content_type: str, keyword: str, platform: Dict[str, Any], index: int) -> List[str]:
    slug = _slugify(keyword)
    base = f"https://assets.example.com/{platform['id']}/{slug}/{index + 1}"
    if content_type == "text":
        return []
    if content_type == "image":
        return [f"{base}.jpg"]
    if content_type == "video":
        return [f"{base}.mp4"]
    return [f"{base}.jpg", f"{base}.mp4"]


def build_radar_items(region: str, platform_id: Optional[str], keyword: str, limit: int) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    keyword = keyword.strip() or "trend"
    platforms = get_platforms(region)
    if platform_id:
        filtered = [item for item in platforms if item["id"] == platform_id]
        if filtered:
            platforms = filtered
    if not platforms:
        platforms = get_platforms(region)

    items: List[Dict[str, Any]] = []
    type_counts = {"text": 0, "image": 0, "video": 0, "mixed": 0}
    spread_template = ["source post", "creator follow-up", "comment expansion", "cross-community remix"]

    platform_cycle = cycle(platforms)
    for index in range(limit):
        platform = next(platform_cycle)
        content_type = _choose_content_type(platform, index)
        type_counts[content_type] += 1
        score_seed = _stable_score(region, platform["id"], keyword, str(index))
        potential = 74 + (score_seed % 23)
        freshness_labels = ["live", "24h", "7d"]
        freshness = freshness_labels[index % len(freshness_labels)]
        title = f"{keyword} - {platform['name']} sample {index + 1}"
        summary = (
            f"Content on {platform['name']} around '{keyword}' is likely to be saved and shared, "
            f"and can be repackaged as {content_type}."
        )
        why_hot = (
            "The trend is usually driven by a strong hook, follow-up comments, "
            f"and remix-friendly formats. The main source surface is {platform['source_hint']}."
        )
        items.append(
            {
                "id": f"radar-{platform['id']}-{_slugify(keyword)}-{index + 1}",
                "platform_id": platform["id"],
                "platform_name": platform["name"],
                "region": region,
                "title": title,
                "summary": summary,
                "source_name": platform["source_hint"],
                "source_url": f"https://example.com/{platform['id']}/{_slugify(keyword)}/{index + 1}",
                "content_type": content_type,
                "why_hot": why_hot,
                "spread_path": spread_template,
                "potential_score": potential,
                "freshness": freshness,
                "prompt_seed": f"{keyword} / {platform['name']} / {content_type} / {freshness}",
                "media": _build_media(content_type, keyword, platform, index),
                "created_at": _now(),
            }
        )

    insights = {
        "analysis": (
            f"Primary source surface: {platforms[0]['source_hint']}. "
            "Typical spread goes from the source post to creator amplification, then comments and remixes."
        ),
        "trend_reason": f"Keyword '{keyword}' maps to multiple platform scenarios and can power a content matrix.",
        "content_mix": type_counts,
        "source_hint": platforms[0]["source_hint"],
    }
    log_activity("build_radar_items", {"region": region, "platform_id": platform_id, "keyword": keyword, "limit": limit})
    return items, insights


def _rewrite_from_sources(sources: List[Dict[str, Any]], tone: str, preserve_media: bool, mode: str) -> Dict[str, Any]:
    if not sources:
        raise ValueError("At least one source item is required")

    source_titles = [item["title"] for item in sources]
    source_labels = [f"{item['platform_name']} / {item['content_type']}" for item in sources]
    keyword = sources[0]["title"].split(" - ")[0]

    if mode == "one_by_one":
        drafts = []
        for index, item in enumerate(sources, start=1):
            drafts.append(
                {
                    "draft_id": f"draft-{uuid.uuid4().hex[:10]}",
                    "title": f"{item['title']} - rewrite",
                    "text": (
                        f"Reframe {item['title']} in a {tone} tone, keep the core idea, "
                        "and restructure it for a single-post release."
                    ),
                    "source_id": item["id"],
                    "source_title": item["title"],
                    "media_plan": item["media"] if preserve_media else [],
                    "position": index,
                }
            )
        return {"drafts": drafts, "summary": f"Generated {len(drafts)} separate rewrite drafts."}

    merged_text = (
        f"Built a {tone} composite draft around '{keyword}' using {len(sources)} sources. "
        f"It combines {', '.join(source_labels)} into one structure with shared hooks, examples, and actions."
    )
    if mode == "rewrite":
        merged_text += " The structure is tighter and better suited for a single post."
    else:
        merged_text += " The result is suitable for series distribution and a content matrix."

    media_plan = []
    if preserve_media:
        for item in sources:
            media_plan.extend(item["media"])

    return {
        "drafts": [
            {
                "draft_id": f"draft-{uuid.uuid4().hex[:10]}",
                "title": f"{sources[0]['title']} - composite version",
                "text": merged_text,
                "source_ids": [item["id"] for item in sources],
                "source_titles": source_titles,
                "media_plan": media_plan,
            }
        ],
        "summary": f"Generated 1 {mode} draft.",
    }


def _build_canvas_preview_lines(image_name: str, prompt_hint: str, style: str, variants: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "Canvas Preview",
        "",
        *_wrap_line("Image: ", image_name),
        *_wrap_line("Prompt hint: ", prompt_hint),
        *_wrap_line("Style: ", style),
        f"Variant count: {len(variants)}",
        "",
        "Rendered variants:",
    ]
    for variant in variants[:4]:
        lines.append(f"  {variant['id']} | score {variant['score']}")
    if len(variants) > 4:
        lines.append(f"  + {len(variants) - 4} more")
    return lines


def _build_canvas_variant_lines(index: int, variant: Dict[str, Any]) -> List[str]:
    return [
        f"Canvas Variant {index + 1}",
        "",
        *_wrap_line("Prompt: ", variant["prompt"]),
        *_wrap_line("Style: ", variant["style"]),
        f"Score: {variant['score']}",
        variant["note"],
    ]


def _build_remix_storyboard_lines(job_id: str, request: Dict[str, Any], sources: List[Dict[str, Any]], summary: str) -> List[str]:
    lines = [
        "Remix Storyboard",
        "",
        *_wrap_line("Job: ", job_id),
        *_wrap_line("Mode: ", request["mode"]),
        *_wrap_line("Tone: ", request["tone"]),
        f"Preserve media: {'yes' if request['preserve_media'] else 'no'}",
        "",
        "Sources:",
    ]
    for source in sources:
        lines.extend(_wrap_line(f"- {source['platform_name']}: ", source["title"]))
    lines.extend(["", *_wrap_line("Summary: ", summary)])
    return lines


def create_remix_job(request: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    job_id = f"remix-{uuid.uuid4().hex[:10]}"
    result = _rewrite_from_sources(
        sources=sources,
        tone=request["tone"],
        preserve_media=request["preserve_media"],
        mode=request["mode"],
    )
    storyboard_filename = f"{job_id}-storyboard.png"
    storyboard_url = _render_image(
        storyboard_filename,
        _build_remix_storyboard_lines(job_id, request, sources, result["summary"]),
        f"{job_id}-storyboard",
    )
    preview_video_filename = f"{job_id}-preview.mp4"
    preview_video_url = _render_video(preview_video_filename, storyboard_filename)
    job = {
        "job_id": job_id,
        "status": "completed",
        "mode": request["mode"],
        "tone": request["tone"],
        "preserve_media": request["preserve_media"],
        "sources": [
            {
                "id": item["id"],
                "title": item["title"],
                "platform_name": item["platform_name"],
                "content_type": item["content_type"],
                "source_url": item["source_url"],
            }
            for item in sources
        ],
        "drafts": result["drafts"],
        "summary": result["summary"],
        "storyboard_url": storyboard_url,
        "preview_video_url": preview_video_url,
        "created_at": _now(),
    }
    with LOCK:
        STATE["remix_jobs"][job_id] = job
    REPOSITORY.save_remix_job(job)
    log_activity("create_remix_job", {"job_id": job_id, "source_count": len(sources)})
    return job


def create_canvas_job(request: Dict[str, Any]) -> Dict[str, Any]:
    job_id = f"canvas-{uuid.uuid4().hex[:10]}"
    base_prompt = f"{request['prompt_hint']} | {request['style']} | {request['image_name']}"
    count = max(1, min(int(request.get("count", 6) or 6), 12))
    variants = []
    for index in range(count):
        variant = {
            "id": f"{job_id}-{index + 1}",
            "prompt": f"{base_prompt} | similarity {90 - index * 5}%",
            "style": f"{request['style']} variant {index + 1}",
            "note": "You can extract this prompt again and feed it into the next pass.",
            "score": 91 - index * 4,
        }
        variant_filename = f"{job_id}-variant-{index + 1:02d}.png"
        variant["image_url"] = _render_image(
            variant_filename,
            _build_canvas_variant_lines(index, variant),
            f"{job_id}-variant-{index + 1}",
        )
        variants.append(variant)

    preview_filename = f"{job_id}-preview.png"
    preview_image_url = _render_image(
        preview_filename,
        _build_canvas_preview_lines(request["image_name"], request["prompt_hint"], request["style"], variants),
        f"{job_id}-preview",
    )

    job = {
        "job_id": job_id,
        "status": "completed",
        "image_name": request["image_name"],
        "prompt_hint": request["prompt_hint"],
        "style": request["style"],
        "preview_image_url": preview_image_url,
        "variants": variants,
        "created_at": _now(),
    }
    with LOCK:
        STATE["canvas_jobs"][job_id] = job
    REPOSITORY.save_canvas_job(job)
    log_activity("create_canvas_job", {"job_id": job_id, "count": count})
    return job


def create_draft(request: Dict[str, Any], account: Dict[str, Any], platform: Dict[str, Any]) -> Dict[str, Any]:
    draft = {
        "id": f"publish-{uuid.uuid4().hex[:10]}",
        "platform_id": request["platform_id"],
        "platform_name": platform["name"],
        "account_id": request["account_id"],
        "account_name": account["display_name"],
        "handle": account["handle"],
        "title": request["title"],
        "body": request["body"],
        "source_ids": request.get("source_ids", []),
        "media": request.get("media", []),
        "target": request.get("target", "draft"),
        "notes": request.get("notes", ""),
        "status": "saved",
        "created_at": _now(),
    }
    with LOCK:
        STATE["drafts"].insert(0, draft)
    REPOSITORY.save_draft(draft)
    REPOSITORY.bump_account_draft_count(account["id"], draft["created_at"])
    log_activity("create_draft", {"draft_id": draft["id"], "account_id": account["id"]})
    return draft


def create_comment_suggestions(request: Dict[str, Any]) -> Dict[str, Any]:
    targets = request["targets"] or ["Target A", "Target B"]
    shared_points = [
        "Shared point 1: the opening line emphasizes a clear benefit.",
        "Shared point 2: each post invites follow-up in the comment section.",
        "Shared point 3: the titles use a strong verb and a specific scene.",
    ]
    suggestions = []
    for target in targets[:5]:
        suggestions.append(
            {
                "target": target,
                "comment": (
                    f"Strong point on {target}. You can extend this with one more actionable step "
                    f"to keep the {request['tone']} tone."
                ),
                "angle": f"follow-up suggestion for {target}",
            }
        )

    job = {
        "job_id": f"comment-{uuid.uuid4().hex[:10]}",
        "targets": targets,
        "context": request["context"],
        "tone": request["tone"],
        "status": "completed",
        "shared_points": shared_points,
        "suggestions": suggestions,
        "safety_note": "Only comment suggestions are produced. Human review is required before posting.",
        "created_at": _now(),
    }
    with LOCK:
        STATE["comment_jobs"][job["job_id"]] = job
    REPOSITORY.save_comment_job(job)
    log_activity("create_comment_suggestions", {"target_count": len(targets)})
    return job


def validate_owner_token(token: str) -> bool:
    return token == OWNER_ACCESS_TOKEN


def get_overview() -> Dict[str, Any]:
    dynamic = REPOSITORY.overview_counts()
    return {
        "platform_count": len(PLATFORMS),
        "domestic_count": len([item for item in PLATFORMS if item["region"] == "domestic"]),
        "overseas_count": len([item for item in PLATFORMS if item["region"] == "overseas"]),
        "connected_accounts": dynamic["connected_accounts"],
        "draft_count": dynamic["draft_count"],
        "remix_jobs": dynamic["remix_jobs"],
        "canvas_jobs": dynamic["canvas_jobs"],
        "cart_count": dynamic["cart_count"],
        "comment_jobs": dynamic["comment_jobs"],
        "activity_count": dynamic["activity_count"],
        "database_path": str(SETTINGS.database_path),
        "service_version": SETTINGS.service_version,
    }


def get_health_status() -> Dict[str, Any]:
    health = REPOSITORY.health()
    health.update(
        {
            "service_version": SETTINGS.service_version,
            "environment": SETTINGS.environment,
            "owner_console_enabled": bool(SETTINGS.owner_access_token),
        }
    )
    return health
