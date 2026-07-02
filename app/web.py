"""图片换装 Web 服务（FastAPI），支持多引擎（火山 / 快手 Kolors）并发出图。

启动：
    uvicorn app.web:app --reload --port 8077
然后浏览器打开 http://127.0.0.1:8077
"""
import asyncio
import base64
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .kolors_client import try_on as kolors_try_on
from .volc_client import dress_up

BASE_DIR = Path(__file__).resolve().parent
LIST_MD = BASE_DIR.parent / "docs" / "list.md"
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="图片换装后台")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/list", response_class=HTMLResponse)
def project_list(request: Request):
    import markdown as md

    if LIST_MD.exists():
        table_html = md.markdown(
            LIST_MD.read_text(encoding="utf-8"), extensions=["tables"]
        )
    else:
        table_html = "<p>未找到 docs/list.md</p>"
    return templates.TemplateResponse(
        request, "list.html", {"table_html": table_html}
    )


@app.post("/api/dress")
async def api_dress(
    model: UploadFile = File(...),
    garment1: UploadFile = File(...),
    garment1_type: str = Form("full"),
    garment2: UploadFile | None = File(None),
    garment2_type: str = Form("full"),
    # ---- 引擎选择（可多选）----
    use_volcengine: bool = Form(True),
    use_kolors: bool = Form(False),
    # ---- 火山 inference_config 参数 ----
    do_sr: bool = Form(False),
    keep_head: bool = Form(True),
    keep_hand: bool = Form(False),
    keep_foot: bool = Form(False),
    keep_upper: bool = Form(False),
    keep_lower: bool = Form(False),
    seed: int = Form(-1),
    num_steps: int = Form(16),
    tight_mask: str = Form("loose"),
    p_bbox_iou_ratio: float = Form(0.3),
    p_bbox_expand_ratio: float = Form(1.1),
    max_process_side_length: int = Form(1920),
    # ---- Kolors 参数 ----
    kolors_seed: int = Form(0),
    kolors_randomize: bool = Form(True),
):
    if not (use_volcengine or use_kolors):
        return JSONResponse(status_code=400, content={"error": "请至少选择一个引擎"})

    model_bytes = await model.read()
    g1_bytes = await garment1.read()
    garments: list[tuple[bytes, str]] = [(g1_bytes, garment1_type)]
    if garment2 is not None and garment2.filename:
        garments.append((await garment2.read(), garment2_type))

    inference_config = {
        "do_sr": do_sr,
        "keep_head": keep_head,
        "keep_hand": keep_hand,
        "keep_foot": keep_foot,
        "keep_upper": keep_upper,
        "keep_lower": keep_lower,
        "seed": seed,
        "num_steps": num_steps,
        "tight_mask": tight_mask,
        "p_bbox_iou_ratio": p_bbox_iou_ratio,
        "p_bbox_expand_ratio": p_bbox_expand_ratio,
        "max_process_side_length": max_process_side_length,
    }

    results: list[dict] = []
    errors: list[dict] = []

    async def run_volcengine():
        try:
            r = await asyncio.to_thread(
                dress_up, model_bytes, garments, True, inference_config
            )
            results.append(
                {"engine": "火山引擎", "images": r.image_urls, "meta": f"task_id={r.task_id}"}
            )
        except Exception as e:  # noqa: BLE001
            errors.append({"engine": "火山引擎", "error": str(e)})

    async def run_kolors():
        try:
            r = await asyncio.to_thread(
                kolors_try_on, model_bytes, g1_bytes, kolors_seed, kolors_randomize
            )
            b64 = base64.b64encode(r.image_bytes).decode()
            results.append(
                {
                    "engine": "快手 Kolors",
                    "images": [f"data:image/webp;base64,{b64}"],
                    "meta": f"seed={r.seed}（仅用服装图1）",
                }
            )
        except Exception as e:  # noqa: BLE001
            errors.append({"engine": "快手 Kolors", "error": str(e)})

    tasks = []
    if use_volcengine:
        tasks.append(run_volcengine())
    if use_kolors:
        tasks.append(run_kolors())
    await asyncio.gather(*tasks)

    return {"results": results, "errors": errors}
