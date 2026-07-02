"""读取火山引擎 AK/SK。

优先级：环境变量 > .env 文件 > bin/AccessKey.txt
"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def _parse_access_key_file(path: Path) -> tuple[str | None, str | None]:
    if not path.exists():
        return None, None
    text = path.read_text(encoding="utf-8")
    ak = re.search(r"AccessKeyId:\s*(\S+)", text)
    sk = re.search(r"SecretAccessKey:\s*(\S+)", text)
    return (ak.group(1) if ak else None, sk.group(1) if sk else None)


def get_credentials() -> tuple[str, str]:
    _load_env_file(ROOT / ".env")
    ak = os.environ.get("VOLC_ACCESS_KEY")
    sk = os.environ.get("VOLC_SECRET_KEY")
    if not (ak and sk):
        file_ak, file_sk = _parse_access_key_file(ROOT / "bin" / "AccessKey.txt")
        ak = ak or file_ak
        sk = sk or file_sk
    if not (ak and sk):
        raise RuntimeError(
            "未找到火山引擎密钥。请设置环境变量 VOLC_ACCESS_KEY / VOLC_SECRET_KEY，"
            "或在 bin/AccessKey.txt 中提供 AccessKeyId / SecretAccessKey。"
        )
    return ak, sk
