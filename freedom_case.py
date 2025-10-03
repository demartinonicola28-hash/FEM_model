# freedom_case.py
# Crea/attiva un Freedom Case e vincola Tz, Rx, Ry SOLO ai nodi di base.
# Se base_nodes è None, i nodi alla quota Y minima vengono identificati come "a terra".

import os
import ctypes as ct

os.add_dll_directory(r"C:\Program Files\Straus7 R31\Bin64")
from St7API import *

# --------------------------- utilità -----------------------------------------
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

def c_long_arr(n): return (ct.c_long * n)()
def c_dbl_arr(n):  return (ct.c_double * n)()

def _get_total(uID: int, ent: int) -> int:
    n = ct.c_long(); check(St7GetTotal(uID, ent, ct.byref(n))); return n.value

def _get_node_xyz(uID: int, nid: int):
    a = c_dbl_arr(3); check(St7GetNodeXYZ(uID, nid, a)); return float(a[0]), float(a[1]), float(a[2])

def _try_set_node_restraint(uID: int, case_num: int, nid: int, ucs, dof, vals) -> bool:
    """Prova entrambe le firme note del wrapper: (uID, case, node, ...) e (uID, node, case, ...)."""
    rc = St7SetNodeRestraint6(uID, case_num, nid, ucs, dof, vals)
    if rc == 0: return True
    rc = St7SetNodeRestraint6(uID, nid, case_num, ucs, dof, vals)
    return rc == 0

# --------------------------- API principale ----------------------------------
def apply_freedom_case(model_path: str,
                       case_name: str = "2d plane XY",
                       base_nodes: list[int] | None = None,
                       uID: int = 1) -> dict:
    """
    - Crea il Freedom Case se assente (usa il case #1).
    - Vincola Tz, Rx, Ry solo ai nodi di base.
    - base_nodes: lista opzionale degli ID nodi da bloccare. Se None, li rileva a Y=min.
    """
    p = os.path.abspath(model_path)

    check(St7Init())
    check(St7OpenFile(uID, _b(p), b""))

    # Assicurati che esista almeno un freedom case
    nfc = ct.c_long()
    check(St7GetNumFreedomCase(uID, ct.byref(nfc)))
    if nfc.value == 0:
        check(St7NewFreedomCase(uID, _b(case_name)))
        check(St7GetNumFreedomCase(uID, ct.byref(nfc)))

    case_num = 1  # usa il primo caso
    try: check(St7SetFreedomCaseName(uID, case_num, _b(case_name)))
    except Exception: pass
    try: check(St7SetFreedomCaseType(uID, case_num, fcNormalFreedom))
    except Exception: pass
    try: check(St7SetSolverFreedomCase(uID, case_num))
    except Exception: pass
    try: check(St7SetWindowFreedomCase(uID, case_num))
    except Exception: pass

    # Identifica i nodi di base se non forniti
    if base_nodes is None:
        n_nodes = _get_total(uID, tyNODE)
        ys = []
        for nid in range(1, n_nodes + 1):
            _, y, _ = _get_node_xyz(uID, nid)
            ys.append((y, nid))
        if not ys:
            raise RuntimeError("Nessun nodo nel modello.")
        y_min = min(y for y, _ in ys)
        # tolleranza numerica 1e-9
        base_nodes = [nid for y, nid in ys if abs(y - y_min) < 1e-9]

    # DOF: blocca Tz, Rx, Ry. Tx, Ty, Rz liberi.
    dof  = c_long_arr(6); vals = c_dbl_arr(6)
    dof[0]=1; dof[1]=1; dof[2]=1; dof[3]=1; dof[4]=1; dof[5]=1
    ucs_candidates = (1, ct.c_long(1))  # alcuni wrapper vogliono int puro, altri c_long

    # Applica ai soli nodi di base
    applied = []
    for nid in base_nodes:
        ok = False
        for ucs in ucs_candidates:
            if _try_set_node_restraint(uID, case_num, nid, ucs, dof, vals):
                ok = True
                break
        if not ok:
            raise RuntimeError(f"Set vincoli nodo {nid} fallito: controlla versione wrapper/API.")
        applied.append(nid)

    check(St7SaveFile(uID))
    check(St7CloseFile(uID))

    return {"model_path": p, "freedom_case_num": case_num, "base_nodes": applied}
