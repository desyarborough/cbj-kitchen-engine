"""CBJ's Kitchen Designer: floor plan + elevations (PNG + multi-page PDF).
Usage: python3 drawings.py spec.json outdir
"""
import sys, os, math, datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Circle, FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages
import kitchen_core as kc
from kitchen_core import frac, TOE, COUNTER_T

NAVY = "#1b2a8a"
GRIDC = "#cfe6cf"
WALLC = "#a3a3a3"
CAB_FILL = "#fcf9ee"
UP_EDGE = "#2e7d32"
APP_FILL = "#e4e7fb"
CTR = "#d32f2f"
INK = "#222222"


def _ang(u):
    a = math.degrees(math.atan2(u[1], u[0]))
    if a > 90: a -= 180
    if a <= -90: a += 180
    return a


def _p(o, u, n, s, t):
    return (o[0] + u[0] * s + n[0] * t, o[1] + u[1] * s + n[1] * t)


# ------------------------------------------------------------ dimension chain
def dim_chain(ax, o, u, n, pts, off, fs, color=NAVY, ext_from=0.0):
    """Draw a dimension chain along u at distance `off` along n from origin line."""
    pts = sorted(set(round(p, 4) for p in pts))
    if len(pts) < 2: return
    ang = _ang(u)
    a = _p(o, u, n, pts[0], off); b = _p(o, u, n, pts[-1], off)
    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=0.8, zorder=6)
    tick = 1.6
    for p in pts:
        c = _p(o, u, n, p, off)
        e0 = _p(o, u, n, p, ext_from);
        ax.plot([e0[0], c[0] + n[0] * 1.5 * (1 if off > ext_from else -1)],
                [e0[1], c[1] + n[1] * 1.5 * (1 if off > ext_from else -1)], color=color, lw=0.4, zorder=5)
        d = (u[0] + n[0], u[1] + n[1])
        ax.plot([c[0] - d[0] * tick, c[0] + d[0] * tick], [c[1] - d[1] * tick, c[1] + d[1] * tick],
                color=color, lw=0.9, zorder=6)
    side = 1 if off > ext_from else -1
    for p0, p1 in zip(pts[:-1], pts[1:]):
        L = p1 - p0
        if L < 0.01: continue
        t = off + side * 1.4
        small = L < 7
        if small:
            t = off + side * (4.2)
        c = _p(o, u, n, (p0 + p1) / 2, t)
        ax.text(c[0], c[1], frac(L), rotation=_ang(u), ha="center", va="center", fontsize=fs * (0.8 if small else 1),
                color=color, zorder=7, rotation_mode="anchor",
                bbox=dict(boxstyle="square,pad=0.08", fc="white", ec="none", alpha=0.85))


def ray_hit(p, d, segs):
    best = None
    for a, b in segs:
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-9: continue
        t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den
        s = ((a[0] - p[0]) * d[1] - (a[1] - p[1]) * d[0]) / den
        if t > 0.01 and -1e-6 <= s <= 1 + 1e-6 and (best is None or t < best):
            best = t
    return best


# ------------------------------------------------------------ floor plan
def draw_plan(K, path_png, pdf=None):
    spec = K.spec
    x0, y0, x1, y1 = K.bounds()
    pad = 46
    W, H = (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad
    scale = 11.0 / max(W, H * 0.85)
    fig = plt.figure(figsize=(11, 8.5))
    ax = fig.add_axes([0.03, 0.12, 0.94, 0.85])
    ax.set_aspect("equal"); ax.axis("off")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = max(W / 2, H / 2 * (11 / 8.5) * (0.94 / 0.85) ** -1 * 1.0)
    ax.set_xlim(cx - W / 2 - 10, cx + W / 2 + 10)
    ax.set_ylim(cy - H / 2 - 4, cy + H / 2 + 4)
    fs = 6.5
    # grid
    gx0, gx1 = ax.get_xlim(); gy0, gy1 = ax.get_ylim()
    g = 12
    for gx in range(int(gx0 // g) * g, int(gx1) + g, g):
        ax.axvline(gx, color=GRIDC, lw=0.6, zorder=0)
    for gy in range(int(gy0 // g) * g, int(gy1) + g, g):
        ax.axhline(gy, color=GRIDC, lw=0.6, zorder=0)

    t = K.wall_t
    wall_segs = []
    # walls with openings
    for e in K.edges:
        if e["open"]:
            a, b = e["a"], e["b"]
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#999", lw=0.6, ls=(0, (4, 3)), zorder=2)
            continue
        wall_segs.append((e["a"], e["b"]))
        o, u, n, L = e["a"], e["u"], e["n"], e["L"]
        cuts = sorted([(op["offset"], op["offset"] + op["width"], op) for op in e["openings"]])
        pos = 0.0
        pieces = []
        for c0, c1, op in cuts:
            pieces.append((pos, c0)); pos = c1
        pieces.append((pos, L))
        for s0, s1 in pieces:
            # extend into corners so walls join
            e0 = -t if s0 == 0 else 0; e1 = t if abs(s1 - L) < 1e-6 else 0
            poly = [_p(o, u, n, s0 + e0, 0), _p(o, u, n, s1 + e1, 0), _p(o, u, n, s1 + e1, -t), _p(o, u, n, s0 + e0, -t)]
            ax.add_patch(Polygon(poly, closed=True, fc=WALLC, ec="#6d6d6d", lw=0.8, zorder=3))
        for c0, c1, op in cuts:
            if op["type"] == "window":
                for tt in (-t * 0.35, -t * 0.65):
                    a, b = _p(o, u, n, c0, tt), _p(o, u, n, c1, tt)
                    ax.plot([a[0], b[0]], [a[1], b[1]], color="#555", lw=0.7, zorder=3)
                poly = [_p(o, u, n, c0, 0), _p(o, u, n, c1, 0), _p(o, u, n, c1, -t), _p(o, u, n, c0, -t)]
                ax.add_patch(Polygon(poly, closed=True, fc="none", ec="#555", lw=0.7, zorder=3))
            else:
                poly = [_p(o, u, n, c0, 0), _p(o, u, n, c1, 0), _p(o, u, n, c1, -t), _p(o, u, n, c0, -t)]
                ax.add_patch(Polygon(poly, closed=True, fc="#f2f2f2", ec="#777", lw=0.6, zorder=3))
                if op.get("swing"):
                    hinge = _p(o, u, n, c0, 0)
                    r = c1 - c0
                    from matplotlib.patches import Arc
                    ang0 = math.degrees(math.atan2(u[1], u[0]))
                    ax.add_patch(Arc(hinge, 2 * r, 2 * r, theta1=ang0, theta2=ang0 + 90, color="#777", lw=0.6, zorder=3))

    # countertops (red outline like the sample)
    for run in K.runs:
        for s0, s1, b, f in kc.counters(run):
            poly = [_p(run.origin, run.u, run.n, s0, b), _p(run.origin, run.u, run.n, s1, b),
                    _p(run.origin, run.u, run.n, s1, f), _p(run.origin, run.u, run.n, s0, f)]
            ax.add_patch(Polygon(poly, closed=True, fc="none", ec=CTR, lw=0.9, zorder=8))

    # base layer
    for run in K.runs:
        for it in run.layer_items("base"):
            fc = APP_FILL if kc.is_appliance(it) else ("#ece9dc" if it.kind in ("filler", "panel") else CAB_FILL)
            ec = NAVY if kc.is_appliance(it) else INK
            ax.add_patch(Polygon(it.poly, closed=True, fc=fc, ec=ec, lw=0.9, zorder=4))
            if it.kind == "sink_base":
                sk = it.spec.get("sink", "single")
                inset = 3
                bowls = [(inset, it.w - inset)] if sk == "single" else [(inset, it.w / 2 - 0.75), (it.w / 2 + 0.75, it.w - inset)]
                for b0, b1 in bowls:
                    poly = [_p(run.origin, run.u, run.n, it.s + b0, 4), _p(run.origin, run.u, run.n, it.s + b1, 4),
                            _p(run.origin, run.u, run.n, it.s + b1, 21), _p(run.origin, run.u, run.n, it.s + b0, 21)]
                    ax.add_patch(Polygon(poly, closed=True, fc="#eef1ff", ec=NAVY, lw=0.7, zorder=9))
                c = _p(run.origin, run.u, run.n, it.s + it.w / 2, 2.5)
                ax.add_patch(Circle(c, 1.0, fc="none", ec=NAVY, lw=0.7, zorder=9))
            if it.kind == "range":
                for bx in (0.27, 0.73):
                    for by in (0.3, 0.7):
                        c = _p(run.origin, run.u, run.n, it.s + it.w * bx, it.d * by)
                        ax.add_patch(Circle(c, 4.2, fc="none", ec=NAVY, lw=0.6, zorder=9))
            if it.kind == "dishwasher":
                a = _p(run.origin, run.u, run.n, it.s, it.d); b = _p(run.origin, run.u, run.n, it.s + it.w, 0)
                ax.plot([a[0], b[0]], [a[1], b[1]], color=NAVY, lw=0.5, zorder=9)
            if it.kind == "fridge":
                for tt in (0.5,):
                    a = _p(run.origin, run.u, run.n, it.s + it.w * tt, 2); b = _p(run.origin, run.u, run.n, it.s + it.w * tt, it.d)
                    ax.plot([a[0], b[0]], [a[1], b[1]], color=NAVY, lw=0.5, zorder=9)
            if it.w >= 8:
                c = _p(run.origin, run.u, run.n, it.s + it.w / 2, (it.d * 0.62 if (not kc.is_appliance(it) or not run.is_island) else it.d * 0.5))
                ax.text(c[0], c[1], it.code, rotation=_ang(run.u) + (90 if it.w < 20 else 0) if False else (_ang((run.n[0], run.n[1])) if it.w < 20 else _ang(run.u)),
                        ha="center", va="center", fontsize=fs, color=NAVY, zorder=12,
                        bbox=dict(boxstyle="square,pad=0.1", fc=(1, 1, 1, 0.75), ec="none"))
    # wall layer
    for run in K.runs:
        for it in run.layer_items("wall"):
            ec = NAVY if kc.is_appliance(it) else UP_EDGE
            ax.add_patch(Polygon(it.poly, closed=True, fc=(1, 1, 1, 0.0), ec=ec, lw=0.9, ls=(0, (3, 1.5)) if it.kind == "microwave" else "-", zorder=10))
            if it.w >= 8 and it.kind != "microwave":
                c = _p(run.origin, run.u, run.n, it.s + it.w / 2, min(it.d, 12) * 0.45)
                ax.text(c[0], c[1], it.code, rotation=_ang(run.u), ha="center", va="center", fontsize=fs * 0.92,
                        color=UP_EDGE, zorder=12, bbox=dict(boxstyle="square,pad=0.1", fc=(1, 1, 1, 0.75), ec="none"))

    # dimensions for wall runs
    for run in K.runs:
        if run.is_island:
            continue
        e = run.edge
        o, u, n, L = e["a"], e["u"], e["n"], e["L"]
        base_pts = [0, L] + [p for it in run.layer_items("base") for p in (it.s, it.s + it.w)]
        wall_pts = [0, L] + [p for it in run.items if (it.layer == "wall" and it.kind != "microwave") or it.h > 60 for p in (it.s, it.s + it.w)]
        op_pts = [0, L] + [p for op in e["openings"] for p in (op["offset"], op["offset"] + op["width"])]
        chains, seen = [], set()
        for pts in (base_pts, wall_pts, op_pts, [0, L]):
            key = tuple(sorted(set(round(p, 3) for p in pts)))
            if key in seen or len(key) < 2: continue
            seen.add(key); chains.append(pts)
        for k, pts in enumerate(chains):
            dim_chain(ax, o, u, n, pts, -(t + 9 + k * 9), fs, ext_from=-t)

    # islands
    closed = list(wall_segs)
    for run in K.runs:
        for it in run.layer_items("base"):
            p = it.poly
            closed.append((p[2], p[3]))  # front edge
    for run in K.runs:
        if not run.is_island: continue
        o, u, n, L = run.origin, run.u, run.n, run.length
        back = -float(run.extra.get("overhang_back", 0))
        pts = [0, L] + [p for it in run.items for p in (it.s, it.s + it.w)]
        dim_chain(ax, o, u, n, pts, back - 9, fs, ext_from=back)
        dim_chain(ax, o, u, n, [0, L], back - 18, fs, ext_from=back)
        # locate island: from its back-start corner to walls, and aisle in front
        own = set((tuple(i.poly[2]), tuple(i.poly[3])) for i in run.items)
        others = [s for s in closed if (tuple(s[0]), tuple(s[1])) not in own]
        probes = [
            (_p(o, u, n, 0, back), (-n[0], -n[1])),
            (_p(o, u, n, 0, back), (-u[0], -u[1])),
            (_p(o, u, n, L / 2, max(i.d for i in run.items) + kc.COUNTER_OVER), n),
        ]
        for p, d in probes:
            hit = ray_hit(p, d, others)
            if hit is None or hit > 400: continue
            q = (p[0] + d[0] * hit, p[1] + d[1] * hit)
            ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="<->", color="#c25e00", lw=0.8), zorder=11)
            m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            ax.text(m[0], m[1], frac(hit), rotation=_ang(d), ha="center", va="center", fontsize=fs, color="#c25e00",
                    zorder=12, bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"))

    _title_block(fig, K, "FLOOR PLAN", "Not to scale on screen. All dimensions in inches.")
    fig.savefig(path_png, dpi=220)
    if pdf: pdf.savefig(fig)
    plt.close(fig)


def _title_block(fig, K, sheet, note):
    p = K.spec.get("project", {}); f = K.spec.get("finish", {})
    ax = fig.add_axes([0.03, 0.015, 0.94, 0.085]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(Rectangle((0, 0), 1, 1, fc="white", ec=INK, lw=1.0))
    for x in (0.27, 0.62, 0.84):
        ax.plot([x, x], [0, 1], color=INK, lw=0.6)
    ax.text(0.012, 0.66, "CABINETS BY JOHNNY", fontsize=12, weight="bold", color=INK, va="center")
    ax.text(0.012, 0.25, p.get("designer_line", "Design  |  Supply  |  Install"), fontsize=7.5, color="#555", va="center")
    ax.text(0.28, 0.72, f"Client: {p.get('client', '')}", fontsize=8, va="center")
    ax.text(0.28, 0.42, f"Cabinets: {f.get('line', '')}  /  {f.get('color', '')}" +
            (f"   Island: {f['island_color']}" if f.get("island_color") else ""), fontsize=8, va="center")
    ax.text(0.28, 0.14, f"Ceiling: {frac(K.ceiling)}   Concept: {p.get('concept', '')}", fontsize=8, va="center")
    ax.text(0.63, 0.66, sheet, fontsize=11, weight="bold", va="center")
    ax.text(0.63, 0.25, note, fontsize=6.5, color="#555", va="center")
    ax.text(0.85, 0.66, datetime.date.today().strftime("%b %d, %Y"), fontsize=8, va="center")
    ax.text(0.85, 0.25, "Verify all sizes in spec book", fontsize=6.5, color="#555", va="center")


# ------------------------------------------------------------ elevations
def _shaker(ax, x0, z0, x1, z1, style, fc, ec, lw=0.7):
    ax.add_patch(Rectangle((x0, z0), x1 - x0, z1 - z0, fc=fc, ec=ec, lw=lw, zorder=4))
    rail = {"shaker": 2.5, "slim_shaker": 1.25, "raised": 2.5}.get(style)
    if rail and (x1 - x0) > 2 * rail + 1 and (z1 - z0) > 2 * rail + 1:
        ax.add_patch(Rectangle((x0 + rail, z0 + rail), x1 - x0 - 2 * rail, z1 - z0 - 2 * rail, fc="none", ec=ec, lw=lw * 0.7, zorder=5))
        if style == "raised":
            ax.add_patch(Rectangle((x0 + rail + 1.2, z0 + rail + 1.2), x1 - x0 - 2 * rail - 2.4, z1 - z0 - 2 * rail - 2.4, fc="none", ec=ec, lw=lw * 0.5, zorder=5))


def _handle(ax, x0, z0, x1, z1, typ, hinge, upper, hw):
    if typ in ("panel", "false"):
        if typ == "false" and hw == "pulls":
            pass
        else:
            return
    if typ in ("drawer", "false"):
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2 if (z1 - z0) < 12 else z1 - 3
        L = 4 if (x1 - x0) < 20 else 6
        ax.plot([cx - L / 2, cx + L / 2], [cz, cz], color="#222", lw=1.6, solid_capstyle="round", zorder=6)
        return
    m = 2.2
    hx = x1 - m if hinge == "L" else x0 + m
    hz = z0 + m + 1 if upper else z1 - m - 1
    if hw == "pulls":
        ax.plot([hx, hx], [hz - 2 if not upper else hz, hz + (2 if upper else 0) + (0 if upper else 2)], color="#222", lw=1.6, zorder=6)
    else:
        ax.add_patch(Circle((hx, hz), 0.6, fc="#222", ec="none", zorder=6))


def _x_of(run, it):
    """Left edge of item in the elevation (viewer looks at run from its front)."""
    n = run.n
    right = (-n[1], n[0])
    sgn = 1 if (run.u[0] * right[0] + run.u[1] * right[1]) > 0 else -1
    L = run.length
    return (it.s if sgn > 0 else L - it.s - it.w), sgn


def draw_elevation(K, run, title, path_png, pdf=None):
    f = K.spec.get("finish", {})
    style = f.get("door_style", "shaker")
    hw = "pulls" if "pull" in f.get("hardware", "").lower() and "knob" not in f.get("hardware", "").lower() else "knobs"
    L = run.length
    C = K.ceiling if not run.is_island else 36
    fig = plt.figure(figsize=(11, 8.5))
    ax = fig.add_axes([0.05, 0.13, 0.9, 0.84]); ax.set_aspect("equal"); ax.axis("off")
    ax.set_xlim(-30, L + 30); ax.set_ylim(-34, C + 18)
    fs = 6.5
    if not run.is_island:
        ax.add_patch(Rectangle((0, 0), L, C, fc="#fafafa", ec="#888", lw=0.8, zorder=1))
    ax.plot([-8, L + 8], [0, 0], color=INK, lw=1.4, zorder=2)
    # openings
    if run.edge:
        for op in run.edge["openings"]:
            sgn = _x_of(run, kc.Item({"code": "x", "kind": "base", "w": op["width"]}, run.origin, run.u, run.n, op["offset"], run.id, L))
            x = sgn[0]
            z0 = float(op.get("sill", 0)) if op["type"] == "window" else 0
            hh = float(op.get("height", 80 if op["type"] == "door" else 36))
            ax.add_patch(Rectangle((x, z0), op["width"], hh, fc="#e8f1fb" if op["type"] == "window" else "white", ec="#666", lw=0.9, zorder=2))
            ax.text(x + op["width"] / 2, z0 + hh / 2, op["type"].upper(), ha="center", va="center", fontsize=fs, color="#666", zorder=3)
    # counters
    for s0, s1, b, fr in kc.counters(run):
        fake = kc.Item({"code": "c", "kind": "base", "w": s1 - s0}, run.origin, run.u, run.n, s0, run.id, L)
        x, _ = _x_of(run, fake)
        ax.add_patch(Rectangle((x, 34.5), s1 - s0, COUNTER_T, fc="#cfc6b8", ec=INK, lw=0.8, zorder=7))
    cab_fc = "#fcf9ee"
    for it in sorted(run.items, key=lambda i: i.layer):
        x, _ = _x_of(run, it)
        z = it.z
        if it.kind == "range":
            ax.add_patch(Rectangle((x, 0), it.w, 36, fc="#dcdfe6", ec=NAVY, lw=0.9, zorder=4))
            ax.add_patch(Rectangle((x + 2.5, 6), it.w - 5, 18, fc="#3a3f4a", ec=NAVY, lw=0.6, zorder=5))
            ax.plot([x + 3, x + it.w - 3], [27.5, 27.5], color="#444", lw=1.6, zorder=6)
            for k in range(5):
                ax.add_patch(Circle((x + 4 + k * (it.w - 8) / 4, 32.5), 0.8, fc="#333", zorder=6))
        elif it.kind == "fridge":
            ax.add_patch(Rectangle((x + 0.5, 0), it.w - 1, it.h, fc="#dcdfe6", ec=NAVY, lw=0.9, zorder=4))
            ax.plot([x + it.w / 2, x + it.w / 2], [28, it.h], color=NAVY, lw=0.7, zorder=5)
            ax.plot([x + 0.5, x + it.w - 0.5], [28, 28], color=NAVY, lw=0.7, zorder=5)
            for hx in (x + it.w / 2 - 2, x + it.w / 2 + 2):
                ax.plot([hx, hx], [38, 62], color="#555", lw=1.8, zorder=6)
            ax.plot([x + 8, x + it.w - 8], [25, 25], color="#555", lw=1.8, zorder=6)
        elif it.kind == "dishwasher":
            ax.add_patch(Rectangle((x, TOE), it.w, it.h - TOE, fc="#dcdfe6", ec=NAVY, lw=0.9, zorder=4))
            ax.plot([x + 3, x + it.w - 3], [it.h - 3, it.h - 3], color="#444", lw=1.6, zorder=6)
        elif it.kind == "microwave":
            ax.add_patch(Rectangle((x + 0.25, z), it.w - 0.5, it.h, fc="#dcdfe6", ec=NAVY, lw=0.9, zorder=4))
            ax.add_patch(Rectangle((x + 2, z + 2), it.w * 0.62, it.h - 4, fc="#3a3f4a", ec=NAVY, lw=0.5, zorder=5))
        elif it.kind == "hood":
            ax.add_patch(Polygon([(x + 2, z), (x + it.w - 2, z), (x + it.w * 0.62, z + it.h), (x + it.w * 0.38, z + it.h)], fc="#dcdfe6", ec=NAVY, lw=0.9, zorder=4))
        else:
            fcol = cab_fc
            if it.kind in ("filler", "wall_filler", "panel", "base_end"):
                z0 = TOE if (it.kind == "filler" and it.h < 60) else it.z
                ax.add_patch(Rectangle((x, z0), it.w, it.top - z0, fc=fcol, ec=INK, lw=0.6, zorder=4))
            else:
                if it.layer == "base":
                    ax.add_patch(Rectangle((x + 0.5, 0), it.w - 1, TOE, fc="#555", ec="none", zorder=3))
                for fx0, fz0, fx1, fz1, typ, hinge in kc.fronts(it):
                    # mirror local x when the run reads right-to-left is unnecessary (fronts are viewer-relative)
                    _shaker(ax, x + fx0, z + fz0, x + fx1, z + fz1, style if typ != "panel" else None, fcol, INK)
                    _handle(ax, x + fx0, z + fz0, x + fx1, z + fz1, typ, hinge, it.layer == "wall", hw)
                if it.kind == "sink_base":
                    ax.plot([x + it.w / 2, x + it.w / 2, x + it.w / 2 + 5], [36, 46, 46], color="#666", lw=1.4, zorder=8)
        # crown on wall cabinets
        if it.layer == "wall" and it.kind not in ("microwave", "hood") and f.get("crown", True) and it.top + 3 <= C:
            ax.add_patch(Rectangle((x - 0.75, it.top), it.w + 1.5, 3, fc="#f3efe2", ec=INK, lw=0.6, zorder=6))
        if it.kind == "fridge" and f.get("crown", True):
            pass
        # code label
        if it.w >= 9:
            lz = (it.z + it.h / 2) if it.layer == "wall" else (it.z + it.h * 0.5)
            if it.kind == "fridge": lz = 50
            ax.text(x + it.w / 2, lz, it.code, ha="center", va="center", fontsize=fs * 0.95, color=NAVY, zorder=9,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    # width chains
    def chain_h(xs, zline, above):
        xs = sorted(set(round(v, 3) for v in xs))
        ax.plot([xs[0], xs[-1]], [zline, zline], color=NAVY, lw=0.8, zorder=8)
        for v in xs:
            ax.plot([v - 1.2, v + 1.2], [zline - 1.2, zline + 1.2], color=NAVY, lw=0.9, zorder=8)
        for a, b in zip(xs[:-1], xs[1:]):
            if b - a < 0.01: continue
            small = b - a < 7
            ax.text((a + b) / 2, zline + (2.2 if above else -2.2) * (1.9 if small else 1), frac(b - a), ha="center",
                    va="center", fontsize=fs * (0.8 if small else 1), color=NAVY, zorder=9)
    bx = [0, L]; wx = [0, L]
    for it in run.items:
        x, _ = _x_of(run, it)
        if it.layer == "base": bx += [x, x + it.w]
        if (it.layer == "wall" and it.kind != "microwave") or it.h > 60: wx += [x, x + it.w]
    chain_h(bx, -9, False); chain_h([0, L], -19, False)
    if not run.is_island: chain_h(wx, C + 7, True)
    # heights on the right
    zs = sorted(set([0, TOE, 34.5, 36, C] + [it.z for it in run.items if it.layer == "wall"] + [it.top for it in run.items if it.layer == "wall"]))
    xv = L + 12
    ax.plot([xv, xv], [0, C], color=NAVY, lw=0.8)
    for zz in zs:
        ax.plot([xv - 1.2, xv + 1.2], [zz - 1.2, zz + 1.2], color=NAVY, lw=0.9)
    for a, b in zip(zs[:-1], zs[1:]):
        if b - a < 0.6: continue
        ax.text(xv + 2.5 + (3 if b - a < 5 else 0), (a + b) / 2, frac(b - a), rotation=90, ha="center", va="center", fontsize=fs * (0.8 if b - a < 5 else 1), color=NAVY)
    _title_block(fig, K, title, "Elevation viewed from inside the kitchen.")
    fig.savefig(path_png, dpi=220)
    if pdf: pdf.savefig(fig)
    plt.close(fig)


def main(spec_path, outdir):
    os.makedirs(outdir, exist_ok=True)
    K = kc.load(spec_path)
    outs = []
    with PdfPages(os.path.join(outdir, "drawings.pdf")) as pdf:
        p = os.path.join(outdir, "01_floor_plan.png"); draw_plan(K, p, pdf); outs.append(p)
        letters = "ABCDEFGH"
        k = 0
        for run in K.runs:
            if not run.items: continue
            name = f"ISLAND ELEVATION" if run.is_island else f"WALL {letters[k]} ELEVATION"
            if not run.is_island: k += 1
            p = os.path.join(outdir, f"0{len(outs)+1}_{name.lower().replace(' ', '_')}.png")
            draw_elevation(K, run, name, p, pdf); outs.append(p)
        # cabinet / appliance list page + csv
        rows = kc.cabinet_list(K)
        import csv
        with open(os.path.join(outdir, "cabinet_list.csv"), "w", newline="") as fcsv:
            wr = csv.writer(fcsv); wr.writerow(["Location", "Code", "Type", "Width", "Height", "Depth", "Qty"])
            for r in rows: wr.writerow([r[0], r[1], r[2].replace("_", " "), frac(r[3]), frac(r[4]), frac(r[5]), r[6]])
        per = 34
        for pg in range(0, len(rows), per):
            fig = plt.figure(figsize=(11, 8.5)); ax = fig.add_axes([0.05, 0.13, 0.9, 0.82]); ax.axis("off")
            data = [[r[0], r[1], r[2].replace("_", " "), frac(r[3]), frac(r[4]), frac(r[5]), str(r[6])] for r in rows[pg:pg + per]]
            tb = ax.table(cellText=data, colLabels=["Location", "Code", "Type", "W", "H", "D", "Qty"], loc="upper center",
                          colWidths=[0.12, 0.24, 0.18, 0.1, 0.1, 0.1, 0.07], cellLoc="left")
            tb.auto_set_font_size(False); tb.set_fontsize(8.5); tb.scale(1, 1.35)
            for (rr, cc), cell in tb.get_celld().items():
                cell.set_edgecolor("#bbb")
                if rr == 0: cell.set_facecolor("#e9ecf8"); cell.set_text_props(weight="bold")
            warns = kc.check(K)
            if warns and pg == 0:
                ax.text(0, -0.02, "CHECK BEFORE ORDERING:  " + "   |   ".join(warns[:6]), fontsize=7.5, color="#b00020", transform=ax.transAxes, wrap=True)
            _title_block(fig, K, "CABINET & APPLIANCE LIST", "Confirm every code in the line's spec book.")
            pdf.savefig(fig); plt.close(fig)
        for w_ in kc.check(K): print("WARNING:", w_)
    outs.append(os.path.join(outdir, "cabinet_list.csv"))
    outs.append(os.path.join(outdir, "drawings.pdf"))
    print("\n".join(outs))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
