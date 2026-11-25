"""CBJ's Kitchen Designer: one command for drawings + renders.

  python3 make_kitchen.py spec.json OUTDIR                 # drawings only
  python3 make_kitchen.py spec.json OUTDIR --render quick  # + fast preview render (~1-2 min)
  python3 make_kitchen.py spec.json OUTDIR --render normal # + presentation render (~5 min)
  python3 make_kitchen.py spec.json OUTDIR --render final  # + full HD render (~10+ min)
  add --render-python /path/to/python if setup.sh printed a different RENDER_PY
"""
import sys, os, subprocess, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ap = argparse.ArgumentParser()
ap.add_argument("spec"); ap.add_argument("outdir")
ap.add_argument("--render", choices=["none", "quick", "normal", "final"], default="none")
ap.add_argument("--render-python", default=sys.executable)
ap.add_argument("--name", default="render")
a = ap.parse_args()

import drawings
drawings.main(a.spec, a.outdir)
if a.render != "none":
    out = os.path.join(a.outdir, f"{a.name}.png")
    cmd = [a.render_python, os.path.join(HERE, "render.py"), a.spec, out]
    if a.render == "quick": cmd.append("--quick")
    if a.render == "final": cmd.append("--final")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(out):
        print(out)
    else:
        print("RENDER FAILED:\n" + (r.stderr or r.stdout)[-2000:])
