# load_cases.py
# G1 = rinomina il case #1 di default e imposta gravità
# G2 = carico distribuito uniforme su tutte le TRAVI + NS mass
# Q  = carico distribuito su travi di piano e di copertura + NS mass

import os
import ctypes as ct

os.add_dll_directory(r"C:\Program Files\Straus7 R31\Bin64")
from St7API import *

# ------------------------ utilità base ---------------------------------------
def _b(s: str) -> bytes: return s.encode("utf-8")

def check(rc: int):
    if rc != 0:
        buf = (ct.c_char * 256)()
        try:
            St7GetAPIErrorString(rc, buf, 256)
            msg = buf.value.decode("utf-8", errors="ignore")
        except Exception:
            msg = ""
        raise RuntimeError(f"St7 error {rc}: {msg}")

def c_dbl_arr(n):  return (ct.c_double * n)()

def _get_total(uID: int, ent: int) -> int:
    n = ct.c_long(); check(St7GetTotal(uID, ent, ct.byref(n))); return n.value

def _elem_nodes(uID: int, ety: int, eid: int) -> list[int]:
    conn = (ct.c_long * (kMaxElementNode + 1))()
    check(St7GetElementConnection(uID, ety, eid, conn))
    m = conn[0]; return [conn[i] for i in range(1, m+1)]

def _node_y(uID: int, nid: int) -> float:
    a = c_dbl_arr(3); check(St7GetNodeXYZ(uID, nid, a)); return float(a[1])

def _elem_prop(uID: int, ety: int, eid: int) -> int:
    p = ct.c_long(); check(St7GetElementProperty(uID, ety, eid, ct.byref(p))); return p.value

# ---------------- carico distribuito e NS mass su BEAM -----------------------
def _apply_uniform_beam_load(uID: int, lc: int, eid: int, q_kNpm: float):
    # St7SetBeamDistributedForceGlobal6ID(uID, BeamNum, BeamDir, ProjectFlag, CaseNum, DLType, ID, double[6])
    try:   dl_const = dlConstant
    except NameError: dl_const = 0
    try:   proj_none = bpNone
    except NameError: proj_none = 0
    vals = c_dbl_arr(6); vals[0] = q_kNpm; vals[1] = q_kNpm
    check(St7SetBeamDistributedForceGlobal6ID(uID, eid, 2, proj_none, lc, dl_const, 1, vals))

def _apply_uniform_beam_nsm(uID: int, lc: int, eid: int, mass_per_m: float):
    # St7SetBeamNSMass10ID(uID, BeamNum, CaseNum, DLType, ID, double[10])
    try:   dl_const = dlConstant
    except NameError: dl_const = 0
    vals = c_dbl_arr(10)
    vals[0] = mass_per_m; vals[1] = mass_per_m; vals[6] = 1.0
    check(St7SetBeamNSMass10ID(uID, eid, lc, dl_const, 1, vals))

# ---------------------------- API principale ---------------------------------
def apply_load_cases(model_path: str,
                     gravity: float = 9.80665,
                     q_G2: float = -26.25,
                     q_Q: float = -22.50,
                     q_Q_roof: float = -3.00,
                     prop_beam: int = 2,
                     uID: int = 1) -> dict:
    p = os.path.abspath(model_path)
    check(St7Init()); check(St7OpenFile(uID, _b(p), b""))

    # ---- G1: usa il case #1 esistente e rinominalo --------------------------
    num = ct.c_long(); check(St7GetNumLoadCase(uID, ct.byref(num)))
    if num.value == 0:
        # alcuni modelli potrebbero non avere il case di default
        check(St7NewLoadCase(uID, _b("G1"))); check(St7GetNumLoadCase(uID, ct.byref(num)))
    lc_g1 = 1  # usa esplicitamente il case #1
    try: check(St7SetLoadCaseName(uID, lc_g1, _b("G1")))
    except Exception: pass
    try: check(St7SetLoadCaseType(uID, lc_g1, lcGravity))
    except Exception: pass
    try:
        check(St7SetLoadCaseGravityDir(uID, lc_g1, 2))            # Y
        check(St7SetLoadCaseGravity(uID, lc_g1, -abs(gravity)))
    except Exception:
        vec = c_dbl_arr(3); vec[1] = -abs(gravity)
        try: check(St7SetLoadCaseGravityVector(uID, lc_g1, vec))
        except Exception: pass

    # ---- G2 ------------------------------------------------------------------
    check(St7NewLoadCase(uID, _b("G2")))
    check(St7GetNumLoadCase(uID, ct.byref(num))); lc_g2 = num.value
    try: check(St7SetLoadCaseType(uID, lc_g2, lcNonInertia))
    except Exception: pass

    # ---- Q -------------------------------------------------------------------
    check(St7NewLoadCase(uID, _b("Q")))
    check(St7GetNumLoadCase(uID, ct.byref(num))); lc_q = num.value
    try: check(St7SetLoadCaseType(uID, lc_q, lcNonInertia))
    except Exception: pass

    # ---- individua travi e copertura ----------------------------------------
    n_beam = _get_total(uID, tyBEAM)
    beams, roof, ymax, ypair = [], [], None, {}
    for eid in range(1, n_beam + 1):
        if _elem_prop(uID, tyBEAM, eid) != prop_beam:
            continue
        n1, n2 = _elem_nodes(uID, tyBEAM, eid)
        y1, y2 = _node_y(uID, n1), _node_y(uID, n2)
        beams.append(eid); ypair[eid] = (y1, y2)
        ytop = min(y1, y2) if ymax is None else max(ymax, min(y1, y2))
        ymax = ytop if ymax is None else max(ymax, ytop)
    if ymax is not None:
        for eid, (y1, y2) in ypair.items():
            if abs(y1 - ymax) < 1e-8 and abs(y2 - ymax) < 1e-8:
                roof.append(eid)
    floors = [e for e in beams if e not in roof]

    # ---- applica carichi -----------------------------------------------------
    if beams:
        mpm = abs(q_G2) * 1000.0 / float(gravity)
        for e in beams:
            _apply_uniform_beam_load(uID, lc_g2, e, q_G2)
            _apply_uniform_beam_nsm(uID, lc_g2, e, mpm)

    if floors:
        mpm = abs(q_Q) * 1000.0 / float(gravity)
        for e in floors:
            _apply_uniform_beam_load(uID, lc_q, e, q_Q)
            _apply_uniform_beam_nsm(uID, lc_q, e, mpm)

    if roof:
        mpm = abs(q_Q_roof) * 1000.0 / float(gravity)
        for e in roof:
            _apply_uniform_beam_load(uID, lc_q, e, q_Q_roof)
            _apply_uniform_beam_nsm(uID, lc_q, e, mpm)

    check(St7SaveFile(uID)); check(St7CloseFile(uID))
    return {
        "model_path": p,
        "load_cases": {"G1": lc_g1, "G2": lc_g2, "Q": lc_q},
        "n_beams": len(beams),
        "n_roof": len(roof),
    }
