# local_model/plate_geometry.py
# -*- coding: utf-8 -*-

from __future__ import annotations
import ctypes as ct
from typing import Dict, List, Tuple, Sequence, Optional

import St7API as st7

# ----------------- util API -----------------

def _ck(code: int, where: str = "") -> None:
    if code != 0:
        buf = ct.create_string_buffer(st7.kMaxStrLen)
        st7.St7GetAPIErrorString(code, buf, st7.kMaxStrLen)
        raise RuntimeError(f"{where}: {buf.value.decode('utf-8','ignore')}")

def _get_total_nodes(uID: int) -> int:
    tot = ct.c_long()
    _ck(st7.St7GetTotal(uID, st7.tyNODE, ct.byref(tot)), "GetTotal tyNODE")
    return int(tot.value)

def _get_xyz(uID: int, node: int) -> Tuple[float, float, float]:
    arr = (ct.c_double * 3)()
    _ck(st7.St7GetNodeXYZ(uID, int(node), arr), f"GetNodeXYZ {node}")
    return float(arr[0]), float(arr[1]), float(arr[2])

def _new_node(uID: int, xyz: Sequence[float], node_num: int) -> int:
    P = (ct.c_double * 3)(float(xyz[0]), float(xyz[1]), float(xyz[2]))
    _ck(st7.St7SetNodeUCS(uID, int(node_num), 1, P), f"SetNodeUCS n{node_num}")
    return int(node_num)

# ----------------- geometria sezioni -----------------

_AXIS_IDX = {"x": 0, "y": 1, "z": 2}

def _six_nodes_from_centroid_axes(x0: float, y0: float, z0: float,
                                  depth_axis: str, width_axis: str,
                                  D: float, tf1: float, tf2: float,
                                  B1: float, B2: float) -> Dict[str, Tuple[float, float, float]]:
    p = [x0, y0, z0]
    d_idx = _AXIS_IDX[depth_axis]
    w_idx = _AXIS_IDX[width_axis]

    d_bot = p[d_idx] - (float(D)/2.0 - float(tf1))
    d_top = p[d_idx] + (float(D)/2.0 - float(tf2))
    w_top = float(B2)/2.0
    w_bot = float(B1)/2.0

    wb = p.copy(); wb[d_idx] = d_bot
    wt = p.copy(); wt[d_idx] = d_top

    tl = wt.copy(); tl[w_idx] -= w_top
    tr = wt.copy(); tr[w_idx] += w_top
    bl = wb.copy(); bl[w_idx] -= w_bot
    br = wb.copy(); br[w_idx] += w_bot

    return {
        "web_bot":   tuple(wb),
        "web_top":   tuple(wt),
        "top_left":  tuple(tl),
        "top_right": tuple(tr),
        "bot_left":  tuple(bl),
        "bot_right": tuple(br),
    }

def _copy_points_set_along_Y(pts: Dict[str, Tuple[float,float,float]], y_target: float,
                             suffix: str) -> Dict[str, Tuple[float,float,float]]:
    out = {}
    for k, (x,y,z) in pts.items():
        out[f"{k}@{suffix}"] = (x, float(y_target), z)
    return out

# ----------------- API principale -----------------

def create_midplane_nodes_for_members(
    model_path: str,
    beam_intermediate_ids: List[int],
    col_intermediate_ids: List[int],
    beam_dims: Dict[str, float],
    col_dims: Dict[str, float],
    col_upper_intermediate_node_id: Optional[int] = None,  # nodo intermedio colonna superiore
) -> Dict[str, Dict[int, Dict[str, int]]]:
    """
    Step 1 + repliche colonne su 3 quote Y:
      Y=min nodi trave, Y=max nodi trave, Y=Y(nodo intermedio colonna superiore).
    Trave: YZ (D→Y, B→Z). Colonna: XZ (D→X, B→Z).
    """
    uID = 1
    _ck(st7.St7Init(), "Init API")
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open model")
        next_id = _get_total_nodes(uID) + 1

        out: Dict[str, Dict[int, Dict[str, int]]] = {"beam": {}, "column": {}}

        # ---- Travi ----
        beam_y_vals: List[float] = []
        if beam_intermediate_ids:
            D  = float(beam_dims.get("D", 0.0))
            B1 = float(beam_dims.get("B1", beam_dims.get("B", 0.0)))
            B2 = float(beam_dims.get("B2", beam_dims.get("B", 0.0)))
            tf1 = float(beam_dims.get("tf1", 0.0))
            tf2 = float(beam_dims.get("tf2", 0.0))

            for nid in beam_intermediate_ids:
                x0, y0, z0 = _get_xyz(uID, int(nid))
                pts = _six_nodes_from_centroid_axes(
                    x0, y0, z0, depth_axis="y", width_axis="z",
                    D=D, tf1=tf1, tf2=tf2, B1=B1, B2=B2,
                )
                ids_map: Dict[str, int] = {}
                for lab, P in pts.items():
                    ids_map[lab] = _new_node(uID, P, next_id); next_id += 1
                    beam_y_vals.append(P[1])
                out["beam"][int(nid)] = ids_map

        y_min_beam = min(beam_y_vals) if beam_y_vals else None
        y_max_beam = max(beam_y_vals) if beam_y_vals else None
        y_col_upper_mid = None
        if col_upper_intermediate_node_id is not None:
            _, y_col_upper_mid, _ = _get_xyz(uID, int(col_upper_intermediate_node_id))

        # ---- Colonne ----
        if col_intermediate_ids:
            D  = float(col_dims.get("D", 0.0))
            B1 = float(col_dims.get("B1", col_dims.get("B", 0.0)))
            B2 = float(col_dims.get("B2", col_dims.get("B", 0.0)))
            tf1 = float(col_dims.get("tf1", 0.0))
            tf2 = float(col_dims.get("tf2", 0.0))

            for nid in col_intermediate_ids:
                x0, y0, z0 = _get_xyz(uID, int(nid))
                base_pts = _six_nodes_from_centroid_axes(
                    x0, y0, z0, depth_axis="x", width_axis="z",
                    D=D, tf1=tf1, tf2=tf2, B1=B1, B2=B2,
                )

                replicas: Dict[str, Tuple[float,float,float]] = {}
                if y_min_beam is not None:
                    replicas.update(_copy_points_set_along_Y(base_pts, y_min_beam, "yBeamMin"))
                if y_max_beam is not None:
                    replicas.update(_copy_points_set_along_Y(base_pts, y_max_beam, "yBeamMax"))
                if y_col_upper_mid is not None:
                    replicas.update(_copy_points_set_along_Y(base_pts, y_col_upper_mid, "yColUpperMid"))

                ids_map: Dict[str, int] = {}
                for lab, P in {**base_pts, **replicas}.items():
                    ids_map[lab] = _new_node(uID, P, next_id); next_id += 1

                out["column"][int(nid)] = ids_map

        _ck(st7.St7SaveFile(uID), "Save model")
        out["_y_levels"] = {  # type: ignore
            "beam_y_min": y_min_beam,
            "beam_y_max": y_max_beam,
            "col_upper_mid": y_col_upper_mid,
        }
        return out

    finally:
        try:
            _ck(st7.St7CloseFile(uID), "Close")
        finally:
            st7.St7Release()

# ----- util plate -----
def _next_plate_id(uID: int) -> int:
    tot = ct.c_long()
    _ck(st7.St7GetTotal(uID, st7.tyPLATE, ct.byref(tot)), "GetTotal tyPLATE")
    return int(tot.value) + 1

def _add_plate4(uID: int, n1: int, n2: int, n3: int, n4: int, prop: int, where=""):
    pid = _next_plate_id(uID)
    Conn = (ct.c_long * 5)()
    Conn[0], Conn[1], Conn[2], Conn[3], Conn[4] = 4, n1, n2, n3, n4
    _ck(st7.St7SetElementConnection(uID, st7.tyPLATE, pid, int(prop), Conn),
        f"SetElementConnection {where}")
    return pid

def _flange_band(col_map: dict, tag: str):
    """Ritorna nodi (L1,R1,R2,L2) alle quote 'tag' usando chiavi top/bot_*@tag."""
    L1 = col_map.get(f"bot_left@{tag}")
    R1 = col_map.get(f"bot_right@{tag}")
    L2 = col_map.get(f"top_left@{tag}")
    R2 = col_map.get(f"top_right@{tag}")
    if None in (L1,R1,L2,R2): return None
    return (int(L1), int(R1), int(R2), int(L2))  # ordine orario
def build_column_central_flange_plates(
    model_path: str,
    *,
    col_lower_nodes: dict,     # mappa etichette->ID per quota yBeamMin
    col_upper_nodes: dict,     # mappa etichette->ID per quota yBeamMax
    y_beam_min_tag: str = "yBeamMin",
    y_beam_max_tag: str = "yBeamMax",
    prop_tf1: int = 0,         # property plate per tf1 (flangia inferiore)
    prop_tf2: int = 0,         # property plate per tf2 (flangia superiore)
) -> dict:
    """
    Crea i plate blu centrali della colonna:
      - sinistra e destra da yBeamMin -> yMid con prop_tf1
      - sinistra e destra da yMid    -> yBeamMax con prop_tf2
    Usa SOLO nodi esistenti in 'col_lower_nodes' e 'col_upper_nodes'.
    """
    uID = 1
    _ck(st7.St7Init(), "Init")
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open")

        # bande alle due quote di riferimento
        band_min = _flange_band(col_lower_nodes, y_beam_min_tag)
        band_max = _flange_band(col_upper_nodes, y_beam_max_tag)
        if not (band_min and band_max):
            raise RuntimeError("Nodi flange mancanti alle quote yBeamMin/yBeamMax")

        # ricava Y delle due quote per calcolare yMid
        u = 1
        arr = (ct.c_double * 3)()
        _ck(st7.St7GetNodeXYZ(uID, band_min[0], arr), "Get Y min"); y_min = float(arr[1])
        _ck(st7.St7GetNodeXYZ(uID, band_max[0], arr), "Get Y max"); y_max = float(arr[1])
        y_mid = 0.5*(y_min + y_max)

        # crea 2 nodi ausiliari alle mezze quote usando i nodi esistenti come base per X,Z
        def mid_nodes(nL1, nR1, nL2, nR2):
            _ck(st7.St7GetNodeXYZ(uID, nL1, arr), "Get L1"); xL,_,zL = float(arr[0]), float(arr[1]), float(arr[2])
            _ck(st7.St7GetNodeXYZ(uID, nR1, arr), "Get R1"); xR,_,zR = float(arr[0]), float(arr[1]), float(arr[2])
            # crea due nodi temporanei a y_mid e stesse X,Z
            # usa ID nuovi fuori conflitto
            tot_nodes = ct.c_long(); _ck(st7.St7GetTotal(uID, st7.tyNODE, ct.byref(tot_nodes)), "Get nodes")
            nLmid = int(tot_nodes.value)+1; nRmid = nLmid+1
            P = (ct.c_double*3)(xL, y_mid, zL); _ck(st7.St7SetNodeUCS(uID, nLmid, 1, P), "Set Lmid")
            P = (ct.c_double*3)(xR, y_mid, zR); _ck(st7.St7SetNodeUCS(uID, nRmid, 1, P), "Set Rmid")
            return nLmid, nRmid

        # mid nodes tra le due quote
        nLmid, nRmid = mid_nodes(band_min[0], band_min[1], band_max[3], band_max[2])

        created = {}

        # metà inferiore: tf1
        if prop_tf1:
            created["mid_lower_flange_L"] = _add_plate4(uID, band_min[0], band_min[1], nRmid, nLmid, prop_tf1, "mid L tf1")
            created["mid_lower_flange_R"] = _add_plate4(uID, band_min[3], band_min[2], nRmid, nLmid, prop_tf1, "mid R tf1")

        # metà superiore: tf2
        if prop_tf2:
            created["mid_upper_flange_L"] = _add_plate4(uID, nLmid, nRmid, band_max[2], band_max[3], prop_tf2, "mid L tf2")
            created["mid_upper_flange_R"] = _add_plate4(uID, nLmid, nRmid, band_max[1], band_max[0], prop_tf2, "mid R tf2")

        _ck(st7.St7SaveFile(uID), "Save")
        return created

    finally:
        try:
            _ck(st7.St7CloseFile(uID), "Close")
        finally:
            st7.St7Release()
