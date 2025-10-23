# plate_sections.py
# Costruisce una sezione I con plate tra due nodi esistenti (linea verde).
# Crea 3 proprietà plate (web, flange sup, flange inf) con spessori reali.
# Mesh sulle superfici di mezzeria: flange in piani z=±(D/2 - tf/2), anima in piano y=0.

import ctypes as ct
import math
import os
import St7API as st7

# --- utilità ---------------------------------------------------------------

def _ck(code, where=""):
    if code != 0:
        sb = ct.create_string_buffer(st7.kMaxStrLen)
        st7.St7GetAPIErrorString(code, sb, st7.kMaxStrLen)
        raise RuntimeError(f"{where}: {sb.value.decode('utf-8','ignore')}")

def _unit(v):
    n = math.sqrt(sum(c*c for c in v))
    if n == 0:
        raise ValueError("vettore nullo")
    return (v[0]/n, v[1]/n, v[2]/n)

def _dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def _cross(a,b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _add(a,b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def _scal(k,a): return (k*a[0], k*a[1], k*a[2])

def _get_totals(uID):
    def _tot(kind):
        i = ct.c_long()
        l = ct.c_long()
        try:
            _ck(st7.St7GetTotal(uID, kind, ct.byref(i), ct.byref(l)), f"GetTotal kind={kind}")
            return int(l.value)
        except Exception:
            _ck(st7.St7GetTotal(uID, kind, ct.byref(i)), f"GetTotal(3) kind={kind}")
            return int(i.value)
    return {"node_last": _tot(st7.tyNODE), "plate_last": _tot(st7.tyPLATE)}

def _new_node(uID, nid, xyz):
    arr = (ct.c_double * 3)(*xyz)
    _ck(st7.St7SetNodeXYZ(uID, int(nid), arr), f"SetNode {nid}")

def _new_quad4(uID, eid, prop, n1,n2,n3,n4):
    conn = (ct.c_long * 5)()
    conn[0] = 4
    conn[1],conn[2],conn[3],conn[4] = int(n1),int(n2),int(n3),int(n4)
    _ck(st7.St7SetElementConnection(uID, st7.tyPLATE, int(eid), int(prop), conn), f"SetPlate {eid}")

def _make_plate_prop_iso(uID, prop_num, name, t, E, nu, rho):
    name_b = name if isinstance(name, (bytes, bytearray)) else str(name).encode("utf-8")
    _ck(st7.St7NewPlateProperty(uID, int(prop_num), st7.ptPlateShell, st7.mtIsotropic, name_b), "NewPlateProperty")
    th = (ct.c_double * 2)(float(t), float(t))
    _ck(st7.St7SetPlateThickness(uID, int(prop_num), th), "SetPlateThickness")
    mat = (ct.c_double * 8)()
    mat[st7.ipPlateIsoModulus]      = float(E)
    mat[st7.ipPlateIsoPoisson]      = float(nu)
    mat[st7.ipPlateIsoDensity]      = float(rho)
    mat[st7.ipPlateIsoAlpha]        = 0.0
    mat[st7.ipPlateIsoViscosity]    = 0.0
    mat[st7.ipPlateIsoDampingRatio] = 0.0
    mat[st7.ipPlateIsoConductivity] = 0.0
    mat[st7.ipPlateIsoSpecificHeat] = 0.0
    _ck(st7.St7SetPlateIsotropicMaterial(uID, int(prop_num), mat), "SetPlateIsotropicMaterial")

def _next_free_plate_prop(uID):
    nums = (ct.c_long * st7.kMaxEntityTotals)()
    last = (ct.c_long * st7.kMaxEntityTotals)()
    try:
        _ck(st7.St7GetTotalProperties(uID, nums, last), "GetTotalProperties")
        base = int(last[st7.ipPlatePropLast]) + 1
        if base < 1:
            base = 1
        return base
    except Exception:
        return 1000

# --- costruzione sezione I su una linea ------------------------------------

def build_I_section_between(
    model_path,
    n1, n2,
    D, B1, B2, tw, tf1, tf2,    # spessori tf2 e tw scambiati rispetto alla versione precedente
    E, nu, rho,
    nx=8, ny=4, nz=6,
    prop_start=1000,
    save=True
):
    uID = 1
    _ck(st7.St7Init(), "Init")
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open")
        try:
            X = (ct.c_double * 3)()
            _ck(st7.St7GetNodeXYZ(uID, int(n1), X), "GetNodeXYZ n1")
            p1 = (X[0], X[1], X[2])
            _ck(st7.St7GetNodeXYZ(uID, int(n2), X), "GetNodeXYZ n2")
            p2 = (X[0], X[1], X[2])

            ex = _unit((p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2]))
            zref = (0.0,0.0,1.0)
            if abs(_dot(ex, zref)) > 0.95:
                zref = (1.0,0.0,0.0)
            ey = _unit(_cross(zref, ex))
            ez = _unit(_cross(ex, ey))

            # quote piani già corrette:
            z_top = +(D/2.0 - tf2/2.0)
            z_bot = -(D/2.0 - tf1/2.0)

            try:
                base_prop = _next_free_plate_prop(uID)
            except Exception:
                base_prop = int(prop_start)
            props = {"web":base_prop, "top":base_prop+1, "bot":base_prop+2}

            # PROPRIETÀ PLATE — mapping corretto
            _make_plate_prop_iso(uID, props["web"], "WEB",        tw,  E,nu,rho)   # anima
            _make_plate_prop_iso(uID, props["top"], "FLANGE_TOP", tf2, E,nu,rho)   # flangia sup
            _make_plate_prop_iso(uID, props["bot"], "FLANGE_BOT", tf1, E,nu,rho)   # flangia inf

            totals = _get_totals(uID)
            next_node  = totals["node_last"]  + 1
            next_plate = totals["plate_last"] + 1

            def L2G(s, y, z):
                return _add(p1, _add(_scal(s, ex), _add(_scal(y, ey), _scal(z, ez))))

            L = math.sqrt(sum((p2[i]-p1[i])**2 for i in range(3)))
            sx = [L*i/nx for i in range(nx+1)]

            ys_top = [-B2/2.0 + B2*j/ny for j in range(ny+1)]
            grid_top = [[None]*(ny+1) for _ in range(nx+1)]
            for i, s in enumerate(sx):
                for j, y in enumerate(ys_top):
                    xyz = L2G(s, y, z_top)
                    nid = next_node
                    _new_node(uID, nid, xyz)
                    grid_top[i][j] = nid
                    next_node += 1
            for i in range(nx):
                for j in range(ny):
                    n11 = grid_top[i][j]
                    n12 = grid_top[i+1][j]
                    n22 = grid_top[i+1][j+1]
                    n21 = grid_top[i][j+1]
                    _new_quad4(uID, next_plate, props["top"], n11,n12,n22,n21)
                    next_plate += 1

            ys_bot = [-B1/2.0 + B1*j/ny for j in range(ny+1)]
            grid_bot = [[None]*(ny+1) for _ in range(nx+1)]
            for i, s in enumerate(sx):
                for j, y in enumerate(ys_bot):
                    xyz = L2G(s, y, z_bot)
                    nid = next_node
                    _new_node(uID, nid, xyz)
                    grid_bot[i][j] = nid
                    next_node += 1
            for i in range(nx):
                for j in range(ny):
                    n11 = grid_bot[i][j]
                    n12 = grid_bot[i+1][j]
                    n22 = grid_bot[i+1][j+1]
                    n21 = grid_bot[i][j+1]
                    _new_quad4(uID, next_plate, props["bot"], n11,n12,n22,n21)
                    next_plate += 1

            zz = [z_bot + (z_top - z_bot)*k/nz for k in range(nz+1)]
            grid_web = [[None]*(nz+1) for _ in range(nx+1)]
            for i, s in enumerate(sx):
                for k, z in enumerate(zz):
                    xyz = L2G(s, 0.0, z)
                    nid = next_node
                    _new_node(uID, nid, xyz)
                    grid_web[i][k] = nid
                    next_node += 1
            for i in range(nx):
                for k in range(nz):
                    n11 = grid_web[i][k]
                    n12 = grid_web[i+1][k]
                    n22 = grid_web[i+1][k+1]
                    n21 = grid_web[i][k+1]
                    _new_quad4(uID, next_plate, props["web"], n11,n12,n22,n21)
                    next_plate += 1

            if save:
                _ck(st7.St7SaveFile(uID), "Save")

            return {
                "props": props,
                "last_node": next_node-1,
                "last_plate": next_plate-1,
                "z_top": z_top, "z_bot": z_bot,
                "L": L
            }

        finally:
            _ck(st7.St7CloseFile(uID), "Close")
    finally:
        st7.St7Release()
