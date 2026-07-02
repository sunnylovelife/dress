#!/usr/bin/env python3
"""图片换装命令行工具。

示例：
    python cli.py --model data/man1.jpg --garment data/dress1.jpeg --type full --out result.png
    python cli.py --model data/man1.jpg \\
        --garment data/top.jpg:upper --garment data/pants.jpg:bottom --out result.png
"""
import argparse
import base64
import sys
import urllib.request
from pathlib import Path

from app.volc_client import DressError, dress_up


def parse_garment(spec: str) -> tuple[str, str]:
    """解析 '路径' 或 '路径:类型'。"""
    if ":" in spec and not spec[1:3] == ":\\":  # 避免误伤 Windows 盘符
        path, _, gtype = spec.rpartition(":")
        if gtype in ("upper", "bottom", "full"):
            return path, gtype
    return spec, "full"


def main() -> int:
    parser = argparse.ArgumentParser(description="火山引擎图片换装 CLI")
    parser.add_argument("--model", required=True, help="模特图路径")
    parser.add_argument(
        "--garment",
        action="append",
        required=True,
        metavar="PATH[:TYPE]",
        help="服装图路径，可选类型 upper/bottom/full（默认 full）。可重复，最多 2 件",
    )
    parser.add_argument(
        "--type",
        choices=["upper", "bottom", "full"],
        help="统一指定服装类型（当只传一件且未在 --garment 中带类型时使用）",
    )
    parser.add_argument("--out", default="result.png", help="结果图保存路径前缀，默认 result.png")
    parser.add_argument("--timeout", type=float, default=120.0, help="轮询超时秒数")
    parser.add_argument("--do-sr", action="store_true", help="对结果做超分处理")
    args = parser.parse_args()

    garments: list[tuple[str, str]] = []
    for spec in args.garment:
        path, gtype = parse_garment(spec)
        if args.type and ":" not in spec:
            gtype = args.type
        garments.append((path, gtype))

    inference_config = {"do_sr": True} if args.do_sr else None

    print(f"模特图: {args.model}")
    for p, t in garments:
        print(f"服装图: {p}  类型: {t}")
    print("提交任务并等待结果中……")

    try:
        result = dress_up(
            args.model,
            garments,
            return_url=True,
            inference_config=inference_config,
            timeout=args.timeout,
        )
    except (DressError, FileNotFoundError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1

    urls = result.image_urls
    if not urls:
        print("未返回图片链接，改存 base64。")
        for i, b64 in enumerate(result.image_b64):
            out = _numbered(args.out, i, len(result.image_b64))
            Path(out).write_bytes(base64.b64decode(b64))
            print(f"已保存: {out}")
        return 0

    print(f"生成成功，共 {len(urls)} 张候选图，下载中……")
    for i, url in enumerate(urls):
        out = _numbered(args.out, i, len(urls))
        try:
            urllib.request.urlretrieve(url, out)
            print(f"已保存: {out}  <- {url}")
        except Exception as e:
            print(f"下载失败 {url}: {e}", file=sys.stderr)
    return 0


def _numbered(out: str, index: int, total: int) -> str:
    p = Path(out) if total <= 1 else Path(out).with_stem(f"{Path(out).stem}_{index + 1}")
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


if __name__ == "__main__":
    raise SystemExit(main())
