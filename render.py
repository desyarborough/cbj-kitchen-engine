"""CBJ's Kitchen Designer: realistic 3D render with Blender (Cycles).
Usage: python3 render.py spec.json out.png [--quick]
Needs: pip install bpy (Python 3.13 wheel). Uses kitchen_core.py and finishes.json beside this file.
"""
import sys, os, json, math
import bpy, bmesh
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitchen_core as kc
from kitchen_core import TOE

I = 0.0254  # inches -> meters
HERE = os.path.dirname(os.path.abspath(__file__))


def hex_rgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c) + (1,)


# ------------------------------------------------------------------ materials
MATS = {}

def principled(name, color, rough=0.5, metal=0.0, coat=0.0, emit=None, emit_str=0.0, aniso=0.0, spec=0.5):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Specular IOR Level"].default_value = spec
    if aniso: b.inputs["Anisotropic"].default_value = aniso
    if emit:
        b.inputs["Emission Color"].default_value = emit
        b.inputs["Emission Strength"].default_value = emit_str
    MATS[name] = m
    return m


def _nodes(m):
    nt = m.node_tree
    return nt, nt.nodes, nt.links, nt.nodes["Principled BSDF"]


def wood_mat(name, hexc, rough=0.45, scale=1.0, planks=False):
    if name in MATS: return MATS[name]
    m = principled(name, hex_rgb(hexc), rough)
    nt, N, Lk, b = _nodes(m)
    tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 * scale, 14 * scale, 1 * scale)
    Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
    noise = N.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 6; noise.inputs["Detail"].default_value = 8
    noise.inputs["Distortion"].default_value = 2.5
    Lk.new(mp.outputs["Vector"], noise.inputs["Vector"])
    wave = N.new("ShaderNodeTexWave"); wave.inputs["Scale"].default_value = 3; wave.inputs["Distortion"].default_value = 9
    wave.inputs["Detail"].default_value = 4
    Lk.new(mp.outputs["Vector"], wave.inputs["Vector"])
    mix = N.new("ShaderNodeMix"); mix.data_type = "FLOAT"; mix.inputs["Factor"].default_value = 0.5
    Lk.new(noise.outputs["Fac"], mix.inputs["A"]); Lk.new(wave.outputs["Fac"], mix.inputs["B"])
    ramp = N.new("ShaderNodeValToRGB")
    c = hex_rgb(hexc)
    ramp.color_ramp.elements[0].color = tuple(v * 0.62 for v in c[:3]) + (1,)
    ramp.color_ramp.elements[1].color = tuple(min(1, v * 1.25) for v in c[:3]) + (1,)
    Lk.new(mix.outputs["Result"], ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    if planks:
        brick = N.new("ShaderNodeTexBrick")
        brick.inputs["Scale"].default_value = 1.0
        brick.inputs["Mortar Size"].default_value = 0.0035
        brick.inputs["Brick Width"].default_value = 1.2 / 0.0254 * I * 1.0
        brick.inputs["Row Height"].default_value = 0.127
        brick.offset = 0.37; brick.squash = 1.0
        brick.inputs["Color1"].default_value = (1, 1, 1, 1); brick.inputs["Color2"].default_value = (0.82, 0.82, 0.82, 1)
        brick.inputs["Mortar"].default_value = (0.25, 0.25, 0.25, 1)
        tc2 = N.new("ShaderNodeTexCoord")
        Lk.new(tc2.outputs["Object"], brick.inputs["Vector"])
        mul = N.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 1
        Lk.new(col, mul.inputs["A"]); Lk.new(brick.outputs["Color"], mul.inputs["B"])
        col = mul.outputs["Result"]
        bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.3
        Lk.new(brick.outputs["Fac"], bump.inputs["Height"]); Lk.new(bump.outputs["Normal"], b.inputs["Normal"])
    Lk.new(col, b.inputs["Base Color"])
    return m


def stone_mat(name, kind):
    if name in MATS: return MATS[name]
    k = (kind or "white quartz").lower()
    if "butcher" in k or "wood" in k:
        return wood_mat(name, "#a8743f", 0.4)
    m = principled(name, (1, 1, 1, 1), 0.18, coat=0.4)
    nt, N, Lk, b = _nodes(m)
    tc = N.new("ShaderNodeTexCoord")
    if any(w in k for w in ("quartz", "marble", "white")) and "granite" not in k:
        base = hex_rgb("#efede9")
        noise = N.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 3; noise.inputs["Detail"].default_value = 10
        noise.inputs["Distortion"].default_value = 4
        wave = N.new("ShaderNodeTexWave"); wave.inputs["Scale"].default_value = 1.6; wave.inputs["Distortion"].default_value = 14
        wave.inputs["Detail"].default_value = 6; wave.wave_profile = "SIN"
        Lk.new(tc.outputs["Object"], noise.inputs["Vector"]); Lk.new(noise.outputs["Color"], wave.inputs["Vector"])
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = hex_rgb("#a9a6a2")
        ramp.color_ramp.elements[1].position = 0.07; ramp.color_ramp.elements[1].color = base
        Lk.new(wave.outputs["Fac"], ramp.inputs["Fac"]); Lk.new(ramp.outputs["Color"], b.inputs["Base Color"])
    else:
        dark = "dark" in k or "black" in k
        v = N.new("ShaderNodeTexVoronoi"); v.inputs["Scale"].default_value = 260
        n2 = N.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 40; n2.inputs["Detail"].default_value = 12
        Lk.new(tc.outputs["Object"], v.inputs["Vector"]); Lk.new(tc.outputs["Object"], n2.inputs["Vector"])
        mix = N.new("ShaderNodeMix"); mix.data_type = "FLOAT"; mix.inputs["Factor"].default_value = 0.55
        Lk.new(v.outputs["Distance"], mix.inputs["A"]); Lk.new(n2.outputs["Fac"], mix.inputs["B"])
        ramp = N.new("ShaderNodeValToRGB")
        cols = (["#151311", "#3b2c22", "#7a5a3a", "#d9c8b0"] if dark else ["#4a4440", "#8d8279", "#c9bfb2", "#efe9e0"])
        ramp.color_ramp.elements[0].color = hex_rgb(cols[0]); ramp.color_ramp.elements[1].color = hex_rgb(cols[3])
        e = ramp.color_ramp.elements.new(0.45); e.color = hex_rgb(cols[1])
        e = ramp.color_ramp.elements.new(0.62); e.color = hex_rgb(cols[2])
        Lk.new(mix.outputs["Result"], ramp.inputs["Fac"]); Lk.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def tile_mat(name, kind, along="x"):
    name = f"{name}_{along}"
    if name in MATS: return MATS[name]
    k = kind.lower()
    color = "#f4f2ee"
    for word, hx in (("gray", "#b9bbbd"), ("grey", "#b9bbbd"), ("green", "#8ea08a"), ("blue", "#6f8aa3"), ("black", "#2a2a2a"), ("cream", "#ece3cf")):
        if word in k: color = hx
    m = principled(name, hex_rgb(color), 0.12, coat=0.6)
    nt, N, Lk, b = _nodes(m)
    tc = N.new("ShaderNodeTexCoord")
    br = N.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1
    br.inputs["Brick Width"].default_value = 6 * I; br.inputs["Row Height"].default_value = 3 * I
    br.inputs["Mortar Size"].default_value = 0.11 * I
    br.inputs["Color1"].default_value = hex_rgb(color); br.inputs["Color2"].default_value = tuple(v * 0.94 for v in hex_rgb(color)[:3]) + (1,)
    br.inputs["Mortar"].default_value = hex_rgb("#bdbab3")
    sep = N.new("ShaderNodeSeparateXYZ"); com = N.new("ShaderNodeCombineXYZ")
    Lk.new(tc.outputs["Object"], sep.inputs["Vector"])
    Lk.new(sep.outputs["X" if along == "x" else "Y"], com.inputs["X"]); Lk.new(sep.outputs["Z"], com.inputs["Y"])
    Lk.new(com.outputs["Vector"], br.inputs["Vector"])
    Lk.new(br.outputs["Color"], b.inputs["Base Color"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.4; bump.invert = True
    Lk.new(br.outputs["Fac"], bump.inputs["Height"]); Lk.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def cabinet_mat(name, fin):
    if fin["mat"] == "wood":
        return wood_mat(name, fin["hex"], 0.42)
    rough = {"gloss": 0.08, "glazed": 0.35}.get(fin["mat"], 0.38)
    return principled(name, hex_rgb(fin["hex"]), rough, coat=(0.5 if fin["mat"] == "gloss" else 0.15))


# ------------------------------------------------------------------ geometry helpers
COLL = None

def _link(obj):
    COLL.objects.link(obj)
    return obj


def mesh_box(name, corners8, mat, bevel=0.0):
    me = bpy.data.meshes.new(name)
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me.from_pydata([tuple(v) for v in corners8], [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    _link(ob)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    if bevel > 0:
        md = ob.modifiers.new("bev", "BEVEL"); md.width = bevel * I; md.segments = 2; md.limit_method = "ANGLE"
    return ob


def obox(o, u, n, s0, s1, t0, t1, z0, z1, mat, bevel=0.0, name="box"):
    def P(s, t, z):
        return Vector(((o[0] + u[0] * s + n[0] * t) * I, (o[1] + u[1] * s + n[1] * t) * I, z * I))
    c = [P(s0, t0, z0), P(s1, t0, z0), P(s1, t1, z0), P(s0, t1, z0),
         P(s0, t0, z1), P(s1, t0, z1), P(s1, t1, z1), P(s0, t1, z1)]
    return mesh_box(name, c, mat, bevel)


def cyl(p0, p1, r, mat, verts=20, name="cyl"):
    p0 = Vector(p0) * I; p1 = Vector(p1) * I
    d = p1 - p0
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r * I, depth=d.length, location=(p0 + p1) / 2)
    ob = bpy.context.active_object
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    ob.data.materials.append(mat)
    for c in ob.users_collection: c.objects.unlink(ob)
    _link(ob)
    bpy.ops.object.shade_smooth() if False else None
    for f in ob.data.polygons: f.use_smooth = True
    return ob


def sphere(p, r, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=r * I, location=Vector(p) * I)
    ob = bpy.context.active_object; ob.data.materials.append(mat)
    for c in ob.users_collection: c.objects.unlink(ob)
    _link(ob)
    for f in ob.data.polygons: f.use_smooth = True
    return ob


def rp(run, s, t, z):
    o, u, n = run.origin, run.u, run.n
    return (o[0] + u[0] * s + n[0] * t, o[1] + u[1] * s + n[1] * t, z)


# ------------------------------------------------------------------ builders
def viewer_s(run, it, x):
    """Convert a front's viewer-relative x (from the left) to run coordinate s."""
    n = run.n; right = (-n[1], n[0])
    sgn = 1 if (run.u[0] * right[0] + run.u[1] * right[1]) > 0 else -1
    return it.s + x if sgn > 0 else it.s + it.w - x


def build_front(run, it, f, style, mat, hw_mat, hw, upper):
    x0, z0, x1, z1, typ, hinge = f
    sa, sb = sorted((viewer_s(run, it, x0), viewer_s(run, it, x1)))
    Z0, Z1 = it.z + z0, it.z + z1
    d = it.d
    if typ == "panel" or style == "slab" or typ == "false" and style == "slab":
        obox(run.origin, run.u, run.n, sa, sb, d - 0.75, d, Z0, Z1, mat, 0.06, "front")
    else:
        rail = 1.25 if style == "slim_shaker" else 2.4
        if (sb - sa) < 2 * rail + 2 or (Z1 - Z0) < 2 * rail + 2:
            rail = min((sb - sa), (Z1 - Z0)) / 4.0
        obox(run.origin, run.u, run.n, sa, sb, d - 0.75, d - 0.3, Z0, Z1, mat, 0.04, "panel")
        for (a, b, c, e) in ((sa, sa + rail, Z0, Z1), (sb - rail, sb, Z0, Z1), (sa + rail, sb - rail, Z1 - rail, Z1), (sa + rail, sb - rail, Z0, Z0 + rail)):
            obox(run.origin, run.u, run.n, a, b, d - 0.3, d, c, e, mat, 0.08, "rail")
        if style == "raised":
            obox(run.origin, run.u, run.n, sa + rail + 1.4, sb - rail - 1.4, d - 0.3, d - 0.05, Z0 + rail + 1.4, Z1 - rail - 1.4, mat, 0.6, "raise")
    # hardware
    if typ in ("panel",) or (typ == "false" and hw != "pulls"):
        return
    t = d + 0.1
    if typ in ("drawer", "false"):
        cz = (Z0 + Z1) / 2 if (Z1 - Z0) < 12 else Z1 - 3
        L = 4 if (sb - sa) < 20 else 6
        cs = (sa + sb) / 2
        a = rp(run, cs - L / 2, t + 1.1, cz); b = rp(run, cs + L / 2, t + 1.1, cz)
        cyl(a, b, 0.2, hw_mat, 12, "pull")
        for s in (cs - L / 2 + 0.3, cs + L / 2 - 0.3):
            cyl(rp(run, s, d, cz), rp(run, s, t + 1.1, cz), 0.16, hw_mat, 10, "post")
        return
    vx = (x1 - 2.2) if hinge == "L" else (x0 + 2.2)
    s = viewer_s(run, it, vx)
    hz = Z0 + 3.2 if upper else Z1 - 3.2
    if hw == "pulls":
        a = rp(run, s, t + 1.1, hz - (0 if upper else 4)); b = rp(run, s, t + 1.1, hz + (4 if upper else 0))
        cyl(a, b, 0.2, hw_mat, 12, "pull")
    else:
        cyl(rp(run, s, d, hz), rp(run, s, t + 0.7, hz), 0.18, hw_mat, 10, "stem")
        sphere(rp(run, s, t + 0.95, hz), 0.6, hw_mat)


def build_cabinet(run, it, style, mat, hw_mat, hw, dark):
    d = it.d
    if it.kind in ("filler", "wall_filler", "panel", "base_end"):
        z0 = TOE if (it.kind == "filler" and it.h < 60) else it.z
        obox(run.origin, run.u, run.n, it.s, it.s + it.w, 0, d, z0, it.top, mat, 0.05, "filler")
        if it.kind == "filler" and it.h < 60:
            obox(run.origin, run.u, run.n, it.s, it.s + it.w, 0, d - 3, 0, TOE, dark, 0, "toe")
        return
    if it.layer == "base":
        obox(run.origin, run.u, run.n, it.s, it.s + it.w, 0, d - 3, 0, TOE, dark, 0, "toe")
        obox(run.origin, run.u, run.n, it.s + 0.02, it.s + it.w - 0.02, 0, d - 0.76, TOE, it.top, mat, 0.03, "box")
    else:
        obox(run.origin, run.u, run.n, it.s + 0.02, it.s + it.w - 0.02, 0, d - 0.76, it.z, it.top, mat, 0.03, "box")
    for f in kc.fronts(it):
        build_front(run, it, f, style, mat, hw_mat, hw, it.layer == "wall")


def build_appliance(run, it, M):
    ss, glass, black = M["ss"], M["glass"], M["black"]
    o, u, n = run.origin, run.u, run.n
    s0, s1, d = it.s, it.s + it.w, it.d
    if it.kind == "range":
        obox(o, u, n, s0 + 0.1, s1 - 0.1, 0, d - 1, 0.5, 35.6, ss, 0.1, "range")
        obox(o, u, n, s0 + 0.1, s1 - 0.1, 0, d, 35.6, 36, glass, 0.05, "cooktop")
        obox(o, u, n, s0 + 0.5, s1 - 0.5, d - 1, d - 0.3, 6, 30, ss, 0.2, "ovendoor")
        obox(o, u, n, s0 + 4, s1 - 4, d - 0.3, d - 0.1, 10, 24, glass, 0.1, "ovenwin")
        obox(o, u, n, s0 + 0.5, s1 - 0.5, d - 1, d - 0.3, 0.6, 5.6, ss, 0.15, "drawer")
        cyl(rp(run, s0 + 3, d + 1.3, 28), rp(run, s1 - 3, d + 1.3, 28), 0.45, ss, 16, "handle")
        for s in (s0 + 3.5, s1 - 3.5):
            cyl(rp(run, s, d - 0.3, 28), rp(run, s, d + 1.3, 28), 0.25, ss)
        for k in range(5):
            s = s0 + 5 + k * (it.w - 10) / 4
            cyl(rp(run, s, d - 0.5, 32.6), rp(run, s, d + 0.9, 32.6), 0.75, black, 20, "knob")
        for k in range(4):  # grates
            ss_ = s0 + 2 + k * (it.w - 4) / 3
            obox(o, u, n, ss_ - 0.25, ss_ + 0.25, 2, d - 2, 36, 36.6, black, 0, "grate")
        for t in (3, d / 2, d - 3):
            obox(o, u, n, s0 + 2, s1 - 2, t - 0.25, t + 0.25, 36, 36.6, black, 0, "grate")
    elif it.kind == "fridge":
        h = it.h
        obox(o, u, n, s0 + 0.2, s1 - 0.2, 0, d - 2, 0.5, h, ss, 0.3, "fridgebody")
        mid = (s0 + s1) / 2
        for a, b in ((s0 + 0.2, mid - 0.1), (mid + 0.1, s1 - 0.2)):
            obox(o, u, n, a, b, d - 2, d, 30.2, h - 0.2, ss, 0.25, "fdoor")
        obox(o, u, n, s0 + 0.2, s1 - 0.2, d - 2, d, 1.0, 29.8, ss, 0.25, "freezer")
        for s in (mid - 2.2, mid + 2.2):
            cyl(rp(run, s, d + 2, 36), rp(run, s, d + 2, h - 8), 0.45, ss, 16)
            for z in (37, h - 9):
                cyl(rp(run, s, d, z), rp(run, s, d + 2, z), 0.3, ss)
        cyl(rp(run, s0 + 7, d + 2, 26), rp(run, s1 - 7, d + 2, 26), 0.45, ss, 16)
        obox(o, u, n, s0 + 1, s1 - 1, d - 2.5, d - 0.5, 0, 1.0, black, 0, "grille")
    elif it.kind == "dishwasher":
        obox(o, u, n, s0 + 0.1, s1 - 0.1, 0, d - 3, 0, TOE, M["dark"], 0, "toe")
        obox(o, u, n, s0 + 0.15, s1 - 0.15, d - 1, d, TOE, it.h - 0.2, ss, 0.2, "dw")
        cyl(rp(run, s0 + 3, d + 1.2, it.h - 3.5), rp(run, s1 - 3, d + 1.2, it.h - 3.5), 0.4, ss, 16)
        for s in (s0 + 3.5, s1 - 3.5):
            cyl(rp(run, s, d, it.h - 3.5), rp(run, s, d + 1.2, it.h - 3.5), 0.25, ss)
    elif it.kind == "microwave":
        z0, z1 = it.z, it.top
        obox(o, u, n, s0 + 0.2, s1 - 0.2, 0, d - 0.5, z0, z1, ss, 0.15, "mw")
        obox(o, u, n, s0 + 0.4, s0 + it.w * 0.72, d - 0.5, d, z0 + 0.4, z1 - 0.4, glass, 0.1, "mwdoor")
        obox(o, u, n, s0 + it.w * 0.72 + 0.3, s1 - 0.4, d - 0.5, d, z0 + 0.4, z1 - 0.4, glass, 0.05, "keypad")
        cyl(rp(run, s0 + it.w * 0.69, d + 1, z0 + 3), rp(run, s0 + it.w * 0.69, d + 1, z1 - 3), 0.35, ss, 12)
    elif it.kind == "hood":
        obox(o, u, n, s0, s1, 0, d, it.z, it.z + 4, ss, 0.2, "hood")
        obox(o, u, n, s0 + it.w * 0.3, s1 - it.w * 0.3, 0, d * 0.5, it.z + 4, kc_ceiling, ss, 0.2, "chimney")


def build_sink(run, it, cmat, M):
    """Undermount stainless sink + faucet. Cuts the counter with a boolean."""
    kind = it.spec.get("sink", "single")
    inset = 3.0
    if kind == "double":
        bowls = [(inset, it.w / 2 - 0.75), (it.w / 2 + 0.75, it.w - inset)]
    else:
        bowls = [(inset, it.w - inset)]
    cutters = []
    for a, b in bowls:
        sa, sb = sorted((it.s + a, it.s + b))
        c = obox(run.origin, run.u, run.n, sa, sb, 4, 21, 27, 37, M["ss"], 0, "cut")
        cutters.append(c)
        # basin walls
        for (p, q, t0, t1) in ((sa, sb, 4, 4.15), (sa, sb, 20.85, 21), (sa, sa + 0.15, 4, 21), (sb - 0.15, sb, 4, 21)):
            obox(run.origin, run.u, run.n, p, q, t0, t1, 27, 34.5, M["sink"], 0, "basin")
        obox(run.origin, run.u, run.n, sa, sb, 4, 21, 26.85, 27, M["sink"], 0, "basinbot")
        cyl(rp(run, (sa + sb) / 2, 12.5, 26.9), rp(run, (sa + sb) / 2, 12.5, 27.05), 1.6, M["black"])
    for c in cutters:
        md = cmat.modifiers.new("cut", "BOOLEAN"); md.object = c; md.operation = "DIFFERENCE"
        c.hide_render = True; c.hide_viewport = True
    # faucet (gooseneck)
    cs = it.s + it.w / 2
    base = rp(run, cs, 2.3, 36)
    cyl(base, rp(run, cs, 2.3, 37.2), 1.2, M["chrome"], 24)
    cu = bpy.data.curves.new("faucet", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.55 * I; cu.bevel_resolution = 4
    sp = cu.splines.new("BEZIER")
    pts = [(cs, 2.3, 37), (cs, 2.3, 49), (cs, 6.5, 53.5), (cs, 11, 49), (cs, 11, 45)]
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = Vector(rp(run, *p)) * I
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new("faucet", cu); ob.data.materials.append(M["chrome"]); _link(ob)
    cyl(rp(run, cs, 11, 45.5), rp(run, cs, 11, 43.2), 0.8, M["chrome"], 20)


# ------------------------------------------------------------------ scene
def build_scene(K, quick=False):
    global COLL, kc_ceiling
    kc_ceiling = K.ceiling
    spec = K.spec
    fin_spec = spec.get("finish", {})
    bpy.ops.wm.read_factory_settings(use_empty=True)
    COLL = bpy.context.scene.collection
    sc = bpy.context.scene
    finishes = json.load(open(os.path.join(HERE, "finishes.json")))

    def finish(line, color):
        key = f"{line} | {color}"
        if key in finishes: return finishes[key]
        for k, v in finishes.items():
            if color and color.lower() in k.lower(): return v
        return {"hex": "#f2f0ea", "mat": "paint", "door": "shaker"}

    main = finish(fin_spec.get("line", ""), fin_spec.get("color", ""))
    if fin_spec.get("hex"): main = dict(main, hex=fin_spec["hex"])
    style = fin_spec.get("door_style") or main["door"]
    isl = None
    if fin_spec.get("island_color"):
        isl = finish(fin_spec.get("island_line", fin_spec.get("line", "")), fin_spec["island_color"])
    hwtxt = fin_spec.get("hardware", "matte black knobs").lower()
    hw = "pulls" if ("pull" in hwtxt and "knob" not in hwtxt) else "knobs"
    if "knobs and pulls" in hwtxt or "knob" in hwtxt and "pull" in hwtxt: hw = "mixed"
    hwcol = {"brass": ("#b08d57", 1, 0.3), "gold": ("#b08d57", 1, 0.3), "nickel": ("#b9b9b6", 1, 0.25),
             "chrome": ("#d8d8d8", 1, 0.08), "bronze": ("#4a3527", 1, 0.4)}
    hc = ("#151515", 0.3, 0.45)
    for k, v in hwcol.items():
        if k in hwtxt: hc = v
    M = {
        "cab": cabinet_mat("cab", main),
        "isl": cabinet_mat("isl", isl) if isl else None,
        "hw": principled("hw", hex_rgb(hc[0]), hc[2], metal=hc[1]),
        "ss": principled("ss", hex_rgb("#c9cbcd"), 0.28, metal=1.0, aniso=0.6),
        "sink": principled("sink", hex_rgb("#6f7275"), 0.5, metal=1.0),
        "chrome": principled("chrome", hex_rgb("#e0e0e0"), 0.06, metal=1.0),
        "glass": principled("glass", hex_rgb("#070708"), 0.04, coat=1.0),
        "black": principled("blk", hex_rgb("#1a1a1a"), 0.4),
        "dark": principled("toe", hex_rgb("#3a3836"), 0.8),
        "wall": principled("wall", hex_rgb(spec.get("room", {}).get("wall_color", "#e7e4de")), 0.85),
        "trim": principled("trim", hex_rgb("#f6f5f2"), 0.4),
        "ceil": principled("ceil", hex_rgb("#f7f7f5"), 0.9),
        "floor": wood_mat("floor", {"light oak": "#c4a07a", "medium oak": "#9a6b42", "dark": "#4e3626", "walnut": "#5e4030",
                                     "gray": "#8d8780", "grey": "#8d8780"}.get(fin_spec.get("floor", "medium oak").lower(), "#9a6b42"), 0.35, 1.0, planks=True),
        "counter": stone_mat("counter", fin_spec.get("countertop", "white quartz")),
        "glow": principled("glow", (1, 1, 1, 1), 1, emit=(1, 0.96, 0.9, 1), emit_str=1.6),
        "sky": principled("skyglow", (1, 1, 1, 1), 1, emit=(0.85, 0.92, 1.0, 1), emit_str=4.0),
        "led": principled("led", (1, 1, 1, 1), 1, emit=(1, 0.88, 0.7, 1), emit_str=12),
    }
    hw_mode = hw
    # room
    x0, y0, x1, y1 = K.bounds()
    C = K.ceiling
    t = K.wall_t
    obox((0, 0), (1, 0), (0, 1), x0 - 150, x1 + 150, y0 - 150, y1 + 150, -1, 0, M["floor"], 0, "floor")
    obox((0, 0), (1, 0), (0, 1), x0 - 150, x1 + 150, y0 - 150, y1 + 150, C, C + 1, M["ceil"], 0, "ceiling")
    for e in K.edges:
        o, u, n, L = e["a"], e["u"], e["n"], e["L"]
        if e["open"]:
            # far wall beyond the open side so light bounces naturally
            obox(o, u, n, -150, L + 150, -110, -110 - t, 0, C, M["wall"], 0, "farwall")
            continue
        cuts = sorted([(op["offset"], op["offset"] + op["width"], op) for op in e["openings"]])
        nE = len(K.edges)
        ext0 = 110 if K.edges[(e["i"] - 1) % nE]["open"] else t
        ext1 = 110 if K.edges[(e["i"] + 1) % nE]["open"] else t
        pos = 0.0
        for c0, c1, op in cuts:
            obox(o, u, n, pos - (ext0 if pos == 0 else 0), c0, -t, 0, 0, C, M["wall"], 0, "wall")
            top = float(op.get("height", 80)) + (float(op.get("sill", 0)) if op["type"] == "window" else 0)
            obox(o, u, n, c0, c1, -t, 0, top, C, M["wall"], 0, "header")
            if op["type"] == "window":
                sill = float(op.get("sill", 42))
                obox(o, u, n, c0, c1, -t, 0, 0, sill, M["wall"], 0, "under")
                obox(o, u, n, c0 - 2, c1 + 2, -0.5, 1.5, sill - 0.75, sill, M["trim"], 0.1, "stool")
                obox(o, u, n, c0 - 60, c1 + 60, -t - 60, -t - 61, -20, C + 40, M["sky"], 0, "outside")
                sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 3.5; sun.angle = 0.08
                so = bpy.data.objects.new("sun", sun); _link(so)
                so.rotation_euler = Vector((-n[0], -n[1], -0.9)).to_track_quat("-Z", "Y").to_euler()
            else:
                obox(o, u, n, c0 - 40, c1 + 40, -t - 40, -t - 41, 0, C, M["glow"], 0, "beyond")
                obox(o, u, n, c0 - 40, c0, -t - 40, -t, 0, C, M["wall"], 0, "hall")
                obox(o, u, n, c1, c1 + 40, -t - 40, -t, 0, C, M["wall"], 0, "hall")
            # casing
            for a, b in ((c0 - 3.5, c0), (c1, c1 + 3.5)):
                z0c = float(op.get("sill", 0)) if op["type"] == "window" else 0
                obox(o, u, n, a, b, 0, 0.75, z0c, top + 3.5, M["trim"], 0.1, "casing")
            obox(o, u, n, c0 - 3.5, c1 + 3.5, 0, 0.75, top, top + 3.5, M["trim"], 0.1, "casing")
            pos = c1
        obox(o, u, n, pos - (ext0 if pos == 0 else 0), L + ext1, -t, 0, 0, C, M["wall"], 0, "wall")
        obox(o, u, n, -(ext0 - t), L + ext1 - t, 0, 0.6, 0, 4, M["trim"], 0.05, "baseboard")

    # cabinets / appliances / counters
    back_runs = []
    for run in K.runs:
        cm = M["isl"] if (run.is_island and M["isl"]) else M["cab"]
        for it in run.items:
            if kc.is_appliance(it):
                build_appliance(run, it, M)
            else:
                hwm = "pulls" if hw_mode == "pulls" else "knobs"
                if hw_mode == "mixed":
                    hwm = "knobs"
                build_cabinet(run, it, style, cm, M["hw"], hwm, M["dark"])
        for s0, s1, b, f in kc.counters(run):
            ctr = obox(run.origin, run.u, run.n, s0, s1, b, f, 34.5, 36, M["counter"], 0.12, "counter")
            for it in run.items:
                if it.kind == "sink_base" and s0 <= it.s < s1:
                    build_sink(run, it, ctr, M)
        if run.is_island:
            # finished back and end panels
            L = run.length; bk = -float(run.extra.get("overhang_back", 0))
            obox(run.origin, run.u, run.n, -0.75, L + 0.75, -0.75, 0, 0, 34.5, cm, 0.05, "islandback")
            obox(run.origin, run.u, run.n, -0.75, 0, 0, max(i.d for i in run.items), 0, 34.5, cm, 0.05, "islandend")
            obox(run.origin, run.u, run.n, L, L + 0.75, 0, max(i.d for i in run.items), 0, 34.5, cm, 0.05, "islandend")
        else:
            back_runs.append(run)
    # backsplash, crown, under-cabinet lights
    bs = fin_spec.get("backsplash", "white subway tile")
    for run in back_runs:
        if bs and bs.lower() != "none":
            tm = tile_mat("tile", bs, "x" if abs(run.u[0]) >= abs(run.u[1]) else "y")
            for s0, s1, b, f in kc.counters(run):
                obox(run.origin, run.u, run.n, s0, s1, -0.01, 0.35, 36, 54, tm, 0, "splash")
            for it in run.items:
                if it.kind == "range":
                    top = min([w.z for w in run.items if w.layer == "wall" and w.s < it.s + it.w and w.s + w.w > it.s] + [54])
                    obox(run.origin, run.u, run.n, it.s, it.s + it.w, -0.01, 0.35, 36, top, tm, 0, "splash")
        if fin_spec.get("crown", True):
            for it in run.items:
                if (it.layer == "wall" and it.kind not in ("microwave", "hood")) or (it.kind in ("panel",) and it.top < C):
                    if it.top + 3 > C: continue
                    obox(run.origin, run.u, run.n, it.s - 0.4, it.s + it.w + 0.4, 0, it.d + 1.0, it.top, it.top + 1.5, M["cab"], 0.15, "crown")
                    obox(run.origin, run.u, run.n, it.s - 0.8, it.s + it.w + 0.8, 0, it.d + 2.0, it.top + 1.5, it.top + 3.0, M["cab"], 0.3, "crown")
        for it in run.items:
            if it.kind == "wall" and it.z < 60:
                obox(run.origin, run.u, run.n, it.s + 1.5, it.s + it.w - 1.5, it.d - 3, it.d - 2.2, it.z - 0.25, it.z - 0.05, M["led"], 0, "led")
                L = bpy.data.lights.new("uc", "AREA"); L.shape = "RECTANGLE"; L.size = (it.w - 3) * I; L.size_y = 0.8 * I
                L.energy = 6 * it.w / 30; L.color = (1, 0.86, 0.68)
                lo = bpy.data.objects.new("uc", L); _link(lo)
                lo.location = Vector(rp(run, it.s + it.w / 2, it.d - 2.6, it.z - 0.3)) * I
                ang = math.atan2(run.u[1], run.u[0])
                lo.rotation_euler = (0, 0, ang)
    # ceiling lights (recessed cans)
    gx = max(2, round((x1 - x0) / 48)); gy = max(2, round((y1 - y0) / 48))
    for i in range(gx):
        for j in range(gy):
            px = x0 + (i + 0.5) * (x1 - x0) / gx; py = y0 + (j + 0.5) * (y1 - y0) / gy
            L = bpy.data.lights.new("can", "AREA"); L.shape = "DISK"; L.size = 5 * I; L.energy = 45; L.color = (1, 0.95, 0.89)
            L.spread = math.radians(110)
            lo = bpy.data.objects.new("can", L); _link(lo); lo.location = (px * I, py * I, (C - 0.2) * I)
            cyl((px, py, C - 0.05), (px, py, C), 3.0, M["glow"], 24, "trimring")
    # soft fill from the camera side
    rnd = spec.get("render", {})
    # pendants over islands
    if rnd.get("pendants", False):
        for run in K.runs:
            if not run.is_island: continue
            L_ = run.length; dmid = max(i.d for i in run.items) / 2
            np_ = 3 if L_ > 72 else 2
            for k in range(np_):
                s = L_ * (k + 1) / (np_ + 1)
                p = rp(run, s, dmid, 0)
                z = 34.5 + 32
                cyl((p[0], p[1], z + 6), (p[0], p[1], C), 0.15, M["black"], 8)
                shade = cyl((p[0], p[1], z), (p[0], p[1], z + 6.5), 4.5, M["black"], 32, "shade")
                cyl((p[0], p[1], z - 0.1), (p[0], p[1], z + 0.2), 4.2, M["glow"], 32)
                Lp = bpy.data.lights.new("pend", "POINT"); Lp.energy = 25; Lp.shadow_soft_size = 1.5 * I; Lp.color = (1, 0.85, 0.65)
                lo = bpy.data.objects.new("pend", Lp); _link(lo); lo.location = Vector((p[0], p[1], z + 1)) * I
    # world
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.9, 0.93, 1, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
    # camera
    cam = rnd.get("camera") or auto_camera(K)
    cd = bpy.data.cameras.new("cam"); cd.lens = cam.get("lens", 20); cd.sensor_width = 36
    co = bpy.data.objects.new("cam", cd); _link(co); sc.camera = co
    co.location = Vector(cam["pos"]) * I
    direction = (Vector(cam["target"]) - Vector(cam["pos"]))
    co.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    fill = bpy.data.lights.new("fill", "AREA"); fill.size = 40 * I; fill.energy = 25; fill.color = (1, 0.96, 0.9)
    fo = bpy.data.objects.new("fill", fill); _link(fo)
    fo.location = Vector(cam["pos"]) * I + Vector((0, 0, 20 * I)); fo.rotation_euler = co.rotation_euler
    # render settings
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24 if quick else int(rnd.get("samples", 48 if "--final" not in sys.argv else 96))
    sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8; sc.cycles.diffuse_bounces = 4; sc.cycles.glossy_bounces = 4
    sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
    sc.render.resolution_x = 960 if quick else int(rnd.get("width", 1440 if "--final" not in sys.argv else 1920))
    sc.render.resolution_y = 540 if quick else int(rnd.get("height", 810 if "--final" not in sys.argv else 1080))
    sc.view_settings.view_transform = "AgX"
    try: sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception: pass
    sc.view_settings.exposure = float(rnd.get("exposure", -0.6))
    return sc


def auto_camera(K):
    items = list(K.all_items())
    cx = sum(i.center()[0] for i in items) / len(items); cy = sum(i.center()[1] for i in items) / len(items)
    x0, y0, x1, y1 = K.bounds()
    corners = [(x0 + 14, y0 + 14), (x1 - 14, y0 + 14), (x1 - 14, y1 - 14), (x0 + 14, y1 - 14)]
    # pick the room corner with the fewest cabinets nearby (open side), facing the cabinets
    def crowd(p): return sum(1 for i in items if math.dist(i.center(), p) < 48)
    p = min(corners, key=lambda c: (crowd(c), -math.dist(c, (cx, cy))))
    return {"pos": [p[0], p[1], 62], "target": [cx, cy, 42], "lens": 18}


def main():
    spec_path, out = sys.argv[1], sys.argv[2]
    quick = "--quick" in sys.argv
    K = kc.load(spec_path)
    sc = build_scene(K, quick)
    sc.render.filepath = os.path.abspath(out)
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
