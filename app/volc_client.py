"""火山引擎「图片换装 V2」核心调用逻辑（Web 与 CLI 共用）。

流程：base64 直传模特图+服装图 -> CVSubmitTask 拿 task_id -> 轮询 CVGetResult 直到完成。
接口文档：docs/图片换装V2接口文档.md
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from volcengine.visual.VisualService import VisualService

from .config import get_credentials

REQ_KEY = "dressing_diffusionV2"
VALID_TYPES = {"upper", "bottom", "full"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 文档限制：单图 < 5MB


class DressError(Exception):
    """换装调用失败（含火山业务错误码）。"""


@dataclass
class Garment:
    """一件服装：图片 + 类型（upper/bottom/full）。"""

    image: bytes
    type: str = "full"

    def __post_init__(self) -> None:
        if self.type not in VALID_TYPES:
            raise DressError(f"服装类型非法：{self.type!r}，应为 {sorted(VALID_TYPES)}")
        if len(self.image) > MAX_IMAGE_BYTES:
            raise DressError("服装图超过 5MB 限制")


@dataclass
class DressResult:
    image_urls: list[str] = field(default_factory=list)
    image_b64: list[str] = field(default_factory=list)
    task_id: str = ""
    raw: dict = field(default_factory=dict)


def _read_image(src: str | Path | bytes) -> bytes:
    if isinstance(src, bytes):
        data = src
    else:
        data = Path(src).read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        raise DressError(f"图片超过 5MB 限制：{src if not isinstance(src, bytes) else '<bytes>'}")
    return data


def _build_service() -> VisualService:
    ak, sk = get_credentials()
    service = VisualService()
    service.set_ak(ak)
    service.set_sk(sk)
    return service


def _check_code(resp: dict, stage: str) -> dict:
    """校验 code==10000，否则抛出带错误信息的异常。"""
    if not isinstance(resp, dict):
        raise DressError(f"{stage}：返回格式异常：{resp!r}")
    code = resp.get("code")
    if code != 10000:
        msg = resp.get("message", "未知错误")
        req_id = resp.get("request_id", "")
        raise DressError(f"{stage}失败 code={code} message={msg} request_id={req_id}")
    return resp


def submit_task(
    service: VisualService,
    model_image: bytes,
    garments: list[Garment],
    inference_config: dict | None = None,
) -> str:
    if not 1 <= len(garments) <= 2:
        raise DressError("服装图数量应为 1~2 件")

    # binary_data_base64 顺序：[模特图, 服装图1, 服装图2...]，与 garment.data 顺序一致
    binary = [base64.b64encode(model_image).decode()]
    binary += [base64.b64encode(g.image).decode() for g in garments]

    body: dict = {
        "req_key": REQ_KEY,
        "req_image_store_type": 0,
        "binary_data_base64": binary,
        "garment": {"data": [{"type": g.type} for g in garments]},
    }
    if inference_config:
        body["inference_config"] = inference_config

    resp = _check_code(service.cv_submit_task(body), "提交任务")
    task_id = resp.get("data", {}).get("task_id")
    if not task_id:
        raise DressError(f"提交任务未返回 task_id：{resp}")
    return task_id


def get_result(service: VisualService, task_id: str, return_url: bool = True) -> dict:
    body = {
        "req_key": REQ_KEY,
        "task_id": task_id,
        "req_json": json.dumps({"return_url": return_url}),
    }
    return _check_code(service.cv_get_result(body), "查询任务")


def poll_result(
    service: VisualService,
    task_id: str,
    return_url: bool = True,
    interval: float = 3.0,
    timeout: float = 120.0,
) -> DressResult:
    deadline = time.time() + timeout
    while True:
        resp = get_result(service, task_id, return_url=return_url)
        data = resp.get("data") or {}
        status = data.get("status")
        if status == "done":
            return DressResult(
                image_urls=data.get("image_urls") or [],
                image_b64=data.get("binary_data_base64") or [],
                task_id=task_id,
                raw=resp,
            )
        if status in ("not_found", "expired"):
            raise DressError(f"任务状态 {status}，无法获取结果（task_id={task_id}）")
        if time.time() > deadline:
            raise DressError(f"轮询超时（{timeout}s），任务仍为 {status}（task_id={task_id}）")
        time.sleep(interval)


def dress_up(
    model_image: str | Path | bytes,
    garments: list[tuple[str | Path | bytes, str]],
    return_url: bool = True,
    inference_config: dict | None = None,
    interval: float = 3.0,
    timeout: float = 120.0,
) -> DressResult:
    """给模特图换上指定服装。

    model_image: 模特图路径或字节
    garments: [(服装图路径或字节, 类型), ...]，类型为 upper/bottom/full，1~2 件
    return_url: True 返回图片链接（24h 有效），False 返回 base64
    """
    model_bytes = _read_image(model_image)
    garment_objs = [Garment(image=_read_image(src), type=t) for src, t in garments]

    service = _build_service()
    task_id = submit_task(service, model_bytes, garment_objs, inference_config)
    return poll_result(
        service, task_id, return_url=return_url, interval=interval, timeout=timeout
    )
