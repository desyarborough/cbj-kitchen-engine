"""CBJ's Kitchen Designer: shared geometry for plans, elevations and renders.
All dimensions in inches. Plan coordinates: x right, y up (math orientation).
Room vertices go counter-clockwise so the room interior is to the LEFT of each wall.
"""
import json, math

BASE_KINDS = {"base", "drawer_base", "sink_base", "wastebasket", "corner_base",
              "range", "dishwasher", "filler", "panel", "fridge", "tall", "base_end"}
WALL_KINDS = {"wall", "wall_filler", "microwave", "hood"}
APPLIANCES = {"range", "dishwasher", "fridge", "microwave", "hood"}

DEFAULTS = {
    "base":        dict(d=24, h=34.5, z=0),
    "drawer_base": dict(d=24, h=34.5, z=0),
    "sink_base":   dict(d=24, h=34.5, z=0),
    "wastebasket": dict(d=24, h=34.5, z=0),
    "corner_base": dict(d=24, h=34.5, z=0),
    "filler":      dict(d=24, h=34.5, z=0),
    "base_end":    dict(d=24, h=34.5, z=0),
    "dishwasher":  dict(d=24, h=34.5, z=0),
    "range":       dict(d=26, h=36, z=0),
    "fridge":      dict(d=30, h=70, z=0),
    "panel":       dict(d=24, h=96, z=0),
    "tall":        dict(d=24, h=84, z=0),
    "wall":        dict(d=12, h=30),
    "wall_filler": dict(d=12, h=30),
    "microwave":   dict(d=15, h=17),
    "hood":        dict(d=20, h=10),
}
TOE = 4.5          # toe kick height
COUNTER_T = 1.5    # countertop thickness
COUNTER_OVER = 1.5 # front overhang


def frac(v):
    """Format inches like 37 1/2" (nearest 1/16)."""
    neg = v < 0
    v = abs(v)
    n = round(v * 16)
    whole, rem = divmod(n, 16)
    s = ""
    if rem:
        g = math.gcd(rem, 16)
        s = f"{rem // g}/{16 // g}"
    out = (f"{whole} {s}" if whole and s else (s if s else f"{whole}")) + '"'
    return ("-" if neg else "") + out


def _sub(a, b): return (a[0] - b[0], a[1] - b[1])
def _add(a, b): return (a[0] + b[0], a[1] + b[1])
def _mul(a, k): return (a[0] * k, a[1] * k)
def _norm(a):
    L = math.hypot(*a)
    return (a[0] / L, a[1] / L)
def _left(u): return (-u[1], u[0])


class Item:
    """A cabinet, filler or appliance placed in plan."""
    def __init__(self, spec, origin, u, n, s, run_id, run_len=None):
        self.spec = spec
        self.code = spec["code"]
        self.kind = spec["kind"]
        dflt = DEFAULTS.get(self.kind, dict(d=24, h=34.5, z=0))
        self.w = float(spec["w"])
        self.d = float(spec.get("d", dflt["d"]))
        self.h = float(spec.get("h", dflt["h"]))
        if "top" in spec:
            self.z = float(spec["top"]) - self.h
        elif "z" in spec:
            self.z = float(spec["z"])
        elif self.kind in WALL_KINDS:
            self.z = 54.0
        else:
            self.z = float(dflt.get("z", 0))
        self.s = s                    # offset along run
        self.origin, self.u, self.n = origin, u, n
        self.run_id = run_id
        self.run_len = run_len
        self.layer = "wall" if self.kind in WALL_KINDS else "base"
        # plan footprint corners: back-left, back-right, front-right, front-left
        p0 = _add(origin, _mul(u, s))
        p1 = _add(origin, _mul(u, s + self.w))
        self.poly = [p0, p1, _add(p1, _mul(n, self.d)), _add(p0, _mul(n, self.d))]

    @property
    def top(self): return self.z + self.h

    def center(self):
        xs = [p[0] for p in self.poly]; ys = [p[1] for p in self.poly]
        return (sum(xs) / 4, sum(ys) / 4)


class Run:
    def __init__(self, rid, origin, u, n, length, items_spec, is_island=False, extra=None):
        self.id, self.origin, self.u, self.n = rid, origin, u, n
        self.length = length
        self.is_island = is_island
        self.extra = extra or {}
        self.items = []
        cur = {"base": 0.0, "wall": 0.0}
        for it in items_spec:
            kind = it["kind"]
            layer = "wall" if kind in WALL_KINDS else "base"
            s = float(it["offset"]) if "offset" in it else cur[layer]
            item = Item(it, origin, u, n, s, rid, length)
            self.items.append(item)
            cur[layer] = s + item.w
            # tall things block the wall layer too
            if kind in ("fridge", "panel", "tall") or (kind == "filler" and item.h > 60):
                cur["wall"] = max(cur["wall"], s + item.w)
        if is_island and self.length is None:
            self.length = max((i.s + i.w for i in self.items), default=0)

    def layer_items(self, layer):
        return sorted([i for i in self.items if i.layer == layer], key=lambda i: i.s)


class Kitchen:
    def __init__(self, spec):
        self.spec = spec
        room = spec["room"]
        self.ceiling = float(room.get("ceiling", 96))
        self.wall_t = float(room.get("wall_thickness", 4.5))
        self.verts = [tuple(map(float, v)) for v in room["vertices"]]
        self.open_edges = set(room.get("open_edges", []))
        self.openings = room.get("openings", [])
        self.edges = []
        nv = len(self.verts)
        for i in range(nv):
            a, b = self.verts[i], self.verts[(i + 1) % nv]
            u = _norm(_sub(b, a))
            self.edges.append(dict(i=i, a=a, b=b, u=u, n=_left(u), L=math.dist(a, b),
                                   open=i in self.open_edges,
                                   openings=[o for o in self.openings if o["edge"] == i]))
        self.runs = []
        for r in spec.get("runs", []):
            e = self.edges[r["edge"]]
            self.runs.append(Run(f"wall{r['edge']}", e["a"], e["u"], e["n"], e["L"], r["items"]))
            self.runs[-1].edge = e
        for k, isl in enumerate(spec.get("islands", [])):
            u = _norm(tuple(isl["direction"]))
            n = _norm(tuple(isl["front"]))
            run = Run(f"island{k}", tuple(isl["origin"]), u, n, None, isl["items"],
                      is_island=True, extra=isl)
            run.edge = None
            self.runs.append(run)

    def all_items(self):
        for r in self.runs:
            for i in r.items:
                yield i

    def bounds(self):
        xs = [v[0] for v in self.verts]; ys = [v[1] for v in self.verts]
        for i in self.all_items():
            xs += [p[0] for p in i.poly]; ys += [p[1] for p in i.poly]
        return min(xs), min(ys), max(xs), max(ys)


def load(path):
    with open(path) as f:
        return Kitchen(json.load(f))


# ---------- door / drawer layout shared by elevations and renders ----------
def fronts(item):
    """Return list of fronts in cabinet-local coords as seen from the front:
    (x0, z0, x1, z1, type, hinge) with x from the viewer's left edge, z from the cabinet's bottom.
    type: 'door' | 'drawer' | 'false' | 'panel'. hinge: 'L','R' or None.
    """
    k, w, h = item.kind, item.w, item.h
    code = item.code.upper()
    r = 0.125  # reveal
    out = []
    def doors(z0, z1, count=None):
        c = count or (1 if w < 24 else 2)
        if c == 1:
            hinge = item.spec.get("hinge", "L" if code.endswith("L") else "R")
            out.append((r, z0, w - r, z1, "door", hinge))
        else:
            m = w / 2
            out.append((r, z0, m - r / 2, z1, "door", "L"))
            out.append((m + r / 2, z0, w - r, z1, "door", "R"))
    if k in ("filler", "wall_filler", "panel", "base_end"):
        return [(0, (TOE if k == "filler" and item.h < 60 else 0), w, h, "panel", None)]
    if k in ("base", "corner_base"):
        z0, top = TOE, h
        if w >= 12 and k == "base":
            out.append((r, top - 6, w - r, top - r, "drawer", None))
            doors(z0 + r, top - 6 - r)
        else:
            doors(z0 + r, top - r)
        return out
    if k == "sink_base":
        out.append((r, h - 6, w - r, h - r, "false", None))
        doors(TOE + r, h - 6 - r)
        return out
    if k == "wastebasket":
        out.append((r, h - 6, w - r, h - r, "drawer", None))
        out.append((r, TOE + r, w - r, h - 6 - r, "drawer", None))
        return out
    if k == "drawer_base":
        nd = int(item.spec.get("drawers", 3))
        avail = h - TOE
        if nd == 2:
            hs = [avail / 2, avail / 2]
        elif nd == 4:
            hs = [5.5, 7, 8, avail - 20.5]
        else:
            hs = [6, (avail - 6) / 2, (avail - 6) / 2]
        z = h
        for hh in hs:
            out.append((r, z - hh + r, w - r, z - r, "drawer", None))
            z -= hh
        return out
    if k == "wall":
        doors(r, h - r)
        return out
    if k == "tall":
        doors(r + TOE, 50, None)
        doors(50 + r, h - r, None)
        return out
    return out


def is_appliance(item):
    return item.kind in APPLIANCES


COUNTER_KINDS = {"base", "drawer_base", "sink_base", "wastebasket", "corner_base",
                 "dishwasher", "filler", "base_end"}


def counters(run):
    """Countertop segments for a run: list of (s0, s1, back, front) in run coords.
    back/front are distances along n from the run line."""
    segs = []
    items = [i for i in run.layer_items("base")]
    cur = None
    for it in items:
        ok = it.kind in COUNTER_KINDS and not (it.kind == "filler" and it.h > 60)
        if ok:
            if cur and abs(cur[1] - it.s) < 0.01:
                cur[1] = it.s + it.w
            else:
                if cur: segs.append(cur)
                cur = [it.s, it.s + it.w]
        else:
            if cur: segs.append(cur); cur = None
    if cur: segs.append(cur)
    back = -float(run.extra.get("overhang_back", 0)) if run.is_island else 0.0
    depth = max([i.d for i in items if i.kind in COUNTER_KINDS] + [24])
    out = []
    for s0, s1 in segs:
        if run.is_island:
            s0 -= float(run.extra.get("overhang_ends", 0)); s1 += float(run.extra.get("overhang_ends", 0))
        out.append((s0, s1, back, depth + COUNTER_OVER))
    return out


def check(K):
    """Return a list of plain-English warnings (gaps, overlaps, tight aisles)."""
    warn = []
    for run in K.runs:
        name = "Island" if run.is_island else f"Wall {chr(65 + [r for r in K.runs if not r.is_island].index(run))}"
        for layer in ("base", "wall"):
            its = run.layer_items(layer)
            if layer == "wall":
                its = sorted(its + [i for i in run.items if i.layer == "base" and i.h > 60], key=lambda i: i.s)
            for a, b in zip(its, its[1:]):
                if b.s < a.s + a.w - 0.01 and a.z < b.top - 0.01 and b.z < a.top - 0.01:
                    warn.append(f"{name}: {a.code} and {b.code} overlap by {frac(a.s + a.w - b.s)}")
        if not run.is_island:
            base = run.layer_items("base")
            if base:
                end = max(i.s + i.w for i in base)
                if base[0].s > 0.01 and base[0].s < 6:
                    warn.append(f"{name}: {frac(base[0].s)} gap at the start of the base run")
                gap = run.length - end
                if 0.01 < gap < 6:
                    warn.append(f"{name}: base run ends {frac(gap)} short of the wall (add a filler?)")
            for op in run.edge["openings"]:
                for it in run.items:
                    o0, o1 = op["offset"], op["offset"] + op["width"]
                    if it.s < o1 and it.s + it.w > o0:
                        if op["type"] == "door" or (it.layer == "wall") or it.top > float(op.get("sill", 0)):
                            warn.append(f"{name}: {it.code} runs into the {op['type']} opening")
        for it in run.items:
            if it.top > K.ceiling:
                warn.append(f"{it.code} is taller than the ceiling")
            if it.layer == "wall" and it.top + 3 > K.ceiling:
                warn.append(f"{it.code}: less than 3\" above it for crown molding")
    return warn


def cabinet_list(K):
    """Rows for the order list: (location, code, kind, w, h, d, qty)."""
    rows = {}
    letters = iter("ABCDEFGH")
    for run in K.runs:
        loc = "Island" if run.is_island else f"Wall {next(letters)}"
        for it in sorted(run.items, key=lambda i: (i.layer, i.s)):
            key = (loc, it.code, it.kind, it.w, it.h, it.d)
            rows[key] = rows.get(key, 0) + 1
    return [k + (q,) for k, q in rows.items()]
