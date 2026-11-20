import os
import sys
from pathlib import Path

import uvicorn

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
sys.path.insert(0, str(BASE))

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, app_dir=str(BASE), reload_dirs=[str(BASE)])
