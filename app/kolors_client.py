"""快手 Kolors 虚拟试衣（Hugging Face Space）调用。

注意：该 Space 官方关闭了 API（tryon 函数 api_name=False, show_api=False）。
这里的调用方式是非官方的：
  1. 直连 *.hf.space 域名，绕过在本网络下无法访问的 huggingface.co；
  2. 手动把被隐藏的端点标记为可用，用 fn_index 强行调用。
仅供本地测试 / 效果对比，不建议用于生产。
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

SPACE_URL = "https://kwai-kolors-kolors-virtual-try-on.hf.space"
TRYON_FN_INDEX = 2

_client = None


class KolorsError(Exception):
    pass


def _get_client(force_new: bool = False):
    global _client
    if _client is not None and not force_new:
        return _client
    try:
        from gradio_client import Client
    except ImportError as e:
        raise KolorsError("未安装 gradio_client，请先 pip install gradio_client") from e
    try:
        client = Client(SPACE_URL)
    except Exception as e:  # noqa: BLE001
        raise KolorsError(f"连接 Kolors Space 失败（可能网络不通或 Space 休眠）：{e}") from e
    # 强制启用被官方隐藏的 tryon 端点
    ep = client.endpoints[TRYON_FN_INDEX]
    ep.is_valid = True
    if not getattr(ep, "api_name", None):
        ep.api_name = "/tryon"
    _client = client
    return client


@dataclass
class KolorsResult:
    image_bytes: bytes
    seed: int
    response: str


def try_on(
    person: bytes,
    garment: bytes,
    seed: int = 0,
    randomize: bool = True,
) -> KolorsResult:
    """给 person 换上 garment，返回结果图字节。Kolors 只支持单件服装、无类型区分。"""
    from gradio_client import handle_file

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "person.jpg"
        p.write_bytes(person)
        g = Path(td) / "garment.jpg"
        g.write_bytes(garment)

        def _call(client):
            return client.predict(
                handle_file(str(p)),
                handle_file(str(g)),
                seed,
                randomize,
                fn_index=TRYON_FN_INDEX,
            )

        client = _get_client()
        try:
            res = _call(client)
        except Exception:  # noqa: BLE001
            # 连接可能已失效，重建 client 重试一次
            try:
                res = _call(_get_client(force_new=True))
            except Exception as e:  # noqa: BLE001
                raise KolorsError(f"Kolors 调用失败：{e}") from e

    result_path, used_seed, response = res[0], res[1], res[2]
    return KolorsResult(
        image_bytes=Path(result_path).read_bytes(),
        seed=int(used_seed),
        response=str(response),
    )
