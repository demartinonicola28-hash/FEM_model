import os, ctypes as ct
import St7API as st7

def ck(code, msg=""):
    if code != 0:
        buf = (ct.c_char * 512)()
        try:
            st7.St7GetAPIErrorString(int(code), buf, 512)
            err = buf.value.decode(errors="ignore")
        except Exception:
            err = "n/a"
        raise RuntimeError(f"{msg} (St7 err={code}: {err})")

def _get_total(uID, etype):
    n = ct.c_long()
    ck(st7.St7GetTotal(uID, etype, ct.byref(n)), "GetTotal")
    return int(n.value)

def _get_node_xyz(uID, nid):
    a = (ct.c_double * 3)()
    ck(st7.St7GetNodeXYZ(uID, int(nid), a), f"GetNodeXYZ {nid}")
    return float(a[0]), float(a[1]), float(a[2])

def _clear_select_nodes(uID):
    ck(st7.St7SetAllEntitySelectState(uID, st7.tyNODE, st7.btFalse), "Clear node selection")

def _select_node(uID, nid, state=True):
    ck(st7.St7SetEntitySelectState(uID, st7.tyNODE, int(nid), 0, st7.btTrue if state else st7.btFalse),
       f"Select node {nid}")

def _masters_same_x(uID, x_ref, exclude_id, tol):
    out, n_tot = [], _get_total(uID, st7.tyNODE)
    for nid in range(1, n_tot + 1):
        if nid == exclude_id: continue
        try:
            xi, _, _ = _get_node_xyz(uID, nid)
        except RuntimeError:
            continue
        if abs(xi - x_ref) <= tol:
            out.append(nid)
    return out

def _masters_same_y(uID, y_ref, exclude_id, tol):
    out, n_tot = [], _get_total(uID, st7.tyNODE)
    for nid in range(1, n_tot + 1):
        if nid == exclude_id: continue
        try:
            _, yi, _ = _get_node_xyz(uID, nid)
        except RuntimeError:
            continue
        if abs(yi - y_ref) <= tol:
            out.append(nid)
    return out

def create_link_clusters_beamYZ_and_colsXZ(model_path: str,
                                           beam_mid_id: int,
                                           col_low_id: int,
                                           col_up_id: int,
                                           tol: float = 1e-6) -> dict:
    uID = 41
    opened = False
    ck(st7.St7Init(), "Init API")
    try:
        ck(st7.St7OpenFile(uID, os.fspath(model_path).encode("utf-8"), b""), f"Open {model_path}")
        opened = True

        # BEAM -> YZ
        x_b, _, _ = _get_node_xyz(uID, beam_mid_id)
        masters_beam = _masters_same_x(uID, x_b, beam_mid_id, tol)
        if not masters_beam:
            print("[WARN] Nessun master per BEAM (YZ)")
        else:
            _clear_select_nodes(uID)
            for n in masters_beam: _select_node(uID, n, True)
            ck(st7.St7CreateRigidLinkCluster(uID, 1, st7.rlPlaneYZ, int(beam_mid_id)),
               "CreateRigidLinkCluster BEAM YZ")

        # COL LOW -> XZ
        _, y_l, _ = _get_node_xyz(uID, col_low_id)
        masters_low = _masters_same_y(uID, y_l, col_low_id, tol)
        if not masters_low:
            print("[WARN] Nessun master per COLONNA INF (XZ)")
        else:
            _clear_select_nodes(uID)
            for n in masters_low: _select_node(uID, n, True)
            ck(st7.St7CreateRigidLinkCluster(uID, 1, st7.rlPlaneZX, int(col_low_id)),
               "CreateRigidLinkCluster COL LOW XZ")

        # COL UP -> XZ
        _, y_u, _ = _get_node_xyz(uID, col_up_id)
        masters_up = _masters_same_y(uID, y_u, col_up_id, tol)
        if not masters_up:
            print("[WARN] Nessun master per COLONNA SUP (XZ)")
        else:
            _clear_select_nodes(uID)
            for n in masters_up: _select_node(uID, n, True)
            ck(st7.St7CreateRigidLinkCluster(uID, 1, st7.rlPlaneZX, int(col_up_id)),
               "CreateRigidLinkCluster COL UP XZ")

        ck(st7.St7SaveFile(uID), "Save")
        return {
            "beamYZ":   {"slave": int(beam_mid_id), "x": x_b, "masters": len(masters_beam)},
            "colLowXZ": {"slave": int(col_low_id),  "y": y_l, "masters": len(masters_low)},
            "colUpXZ":  {"slave": int(col_up_id),   "y": y_u, "masters": len(masters_up)},
        }
    finally:
        if opened:
            try:
                ck(st7.St7CloseFile(uID), "Close")
            finally:
                st7.St7Release()
        else:
            st7.St7Release()
