# -*- coding: utf-8 -*-
# pytest 全局配置：将项目根目录加入 sys.path，保证 `import src.xxx` 可用
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
