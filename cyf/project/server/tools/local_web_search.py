#!/usr/bin/env python3
"""本地网络搜索命令行入口。"""

import sys
from pathlib import Path


# 允许从任意工作目录直接执行 ``python tools/local_web_search.py``。
_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from service.tools.local_web_search import main


if __name__ == "__main__":
    raise SystemExit(main())
