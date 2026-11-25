#!/usr/bin/env bash
# One-time setup per session. Installs drawing + render dependencies.
# Prints the python to use for rendering on the last line: RENDER_PY=<path>
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
pip install -q --break-system-packages matplotlib >/dev/null 2>&1 || pip install -q matplotlib >/dev/null 2>&1
if python3 -c "import bpy" >/dev/null 2>&1; then echo "RENDER_PY=$(command -v python3)"; exit 0; fi
if pip install -q --break-system-packages bpy >/dev/null 2>&1 && python3 -c "import bpy" >/dev/null 2>&1; then
  echo "RENDER_PY=$(command -v python3)"; exit 0
fi
# Fallback: this Python has no Blender wheel, so build a Python 3.13 venv with uv.
pip install -q --break-system-packages uv >/dev/null 2>&1 || pip install -q uv >/dev/null 2>&1
VENV="$HERE/.venv313"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m uv venv --python 3.13 "$VENV" >/dev/null 2>&1 || uv venv --python 3.13 "$VENV" >/dev/null 2>&1
fi
python3 -m uv pip install -q --python "$VENV/bin/python" bpy matplotlib >/dev/null 2>&1 || uv pip install -q --python "$VENV/bin/python" bpy matplotlib >/dev/null 2>&1
if "$VENV/bin/python" -c "import bpy" >/dev/null 2>&1; then echo "RENDER_PY=$VENV/bin/python"; exit 0; fi
echo "RENDER_PY=NONE  (Blender could not be installed here; drawings still work)"
