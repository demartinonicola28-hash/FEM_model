# freedom_case_xy_full_fixed.py
import os
import ctypes as ct

os.add_dll_directory(r"C:\Program Files\Straus7 R31\Bin64")
from St7API import *

# ------------- util -------------
def _b(s): return s.encode("utf-8")
def c_long_arr(n): return (ct.c_long * n)()
def c_dbl_arr(n):  return (ct.c_double * n)()

def check(rc):
    if rc != 0:
        buf = (ct.c_char * 256)()
        try:
            St7GetAPIErrorString(rc, buf, 256)
            msg = buf.value.decode("utf-8","ignore")
        except Exception:
            msg = f"code {rc}"
        raise RuntimeError(f"St7 error: {msg}")

def _set_node_restraint(uID, case_num, nid, flags6):
    dof = c_long_arr(6); vals = c_dbl_arr(6)
    for i, v in enumerate(flags6): dof[i] = int(v); vals[i] = 0.0
    # Prova (uID, case, node, ...) e poi (uID, node, case, ...)
    rc = St7SetNodeRestraint6(uID, case_num, nid, 1, dof, vals)
    if rc == 0:
        return
    rc = St7SetNodeRestraint6(uID, nid, case_num, 1, dof, vals)
    check(rc)

# ------------- core -------------
def apply_freedom_case(model_path: str,
                       base_nodes: list[int],
                       case_num: int = 1,
                       case_name: str = "2D Beam XY",
                       uID: int = 1) -> dict:
    if not base_nodes:
        raise ValueError("Fornire base_nodes non vuoto.")

    p = os.path.abspath(model_path)
    check(St7Init())
    check(St7OpenFile(uID, _b(p), b""))

    # Assicura l'esistenza del freedom case richiesto
    nfc = ct.c_long(); check(St7GetNumFreedomCase(uID, ct.byref(nfc)))
    while nfc.value < case_num:
        check(St7NewFreedomCase(uID, _b(case_name)))
        check(St7GetNumFreedomCase(uID, ct.byref(nfc)))

    try: check(St7SetFreedomCaseName(uID, case_num, _b(case_name)))
    except Exception: pass
    try: check(St7SetSolverFreedomCase(uID, case_num))
    except Exception: pass
    try: check(St7SetWindowFreedomCase(uID, case_num))
    except Exception: pass

    # Defaults del case = 2D Beam XY: [0,0,1,1,1,0]
    defaults = c_long_arr(6)
    for i, v in enumerate((0, 0, 1, 1, 1, 0)): defaults[i] = v
    check(St7SetFreedomCaseDefaults(uID, case_num, defaults))

    # Verifica
    chk = c_long_arr(6); check(St7GetFreedomCaseDefaults(uID, case_num, chk))
    if tuple(int(chk[i]) for i in range(6)) != (0, 0, 1, 1, 1, 0):
        raise RuntimeError("Defaults non impostati correttamente.")

    # Solo nodi di base: union(default, extra[Tx,Ty,Rz]) = incastro completo
    full_fix = (1, 1, 1, 1, 1, 1)
    for nid in base_nodes:
        _set_node_restraint(uID, case_num, nid, full_fix)

    check(St7SaveFile(uID)); check(St7CloseFile(uID))
    return {
        "model_path": p,
        "freedom_case_num": case_num,
        "defaults": (0, 0, 1, 1, 1, 0),
        "base_nodes": list(base_nodes),
    }
