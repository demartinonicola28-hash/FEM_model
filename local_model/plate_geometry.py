# local_model/plate_geometry.py
# -*- coding: utf-8 -*-

from __future__ import annotations
import ctypes as ct
from typing import Dict, List, Tuple, Sequence, Optional, Any
from collections import defaultdict

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

# --- Funzioni relative a Plate/Beam rimosse ---

# ----------------- geometria sezioni -----------------

_AXIS_IDX = {"x": 0, "y": 1, "z": 2}

def _calculate_centroid_distances(
    D: float, B1: float, tf1: float, B2: float, tf2: float, tw: float
) -> Tuple[float, float]:
    """Calcola le distanze dal baricentro teorico ai LEMBI ESTERNI."""
    try:
        A1 = B1 * tf1; y1 = tf1 / 2.0
        hw = D - tf1 - tf2; Aw = hw * tw; yw = tf1 + hw / 2.0
        A2 = B2 * tf2; y2 = D - tf2 / 2.0
        Atot = A1 + Aw + A2
        if Atot == 0: return (D / 2.0, D / 2.0)
        yc = (A1 * y1 + Aw * yw + A2 * y2) / Atot
        dist_c_to_ext_bot = yc; dist_c_to_ext_top = D - yc
        return (dist_c_to_ext_top, dist_c_to_ext_bot)
    except Exception: return (D / 2.0, D / 2.0)


def _six_nodes_from_centroid_axes(x0: float, y0: float, z0: float,
                                 depth_axis: str, width_axis: str,
                                 dist_c_to_ext_top: float, dist_c_to_ext_bot: float,
                                 tf1: float, tf2: float, B1: float, B2: float
                                 ) -> Dict[str, Tuple[float, float, float]]:
    """Calcola le coordinate dei 6 nodi chiave."""
    p = [x0, y0, z0]
    d_idx = _AXIS_IDX[depth_axis]; w_idx = _AXIS_IDX[width_axis]

    d_bot = p[d_idx] - (dist_c_to_ext_bot - tf1/2.0)
    d_top = p[d_idx] + (dist_c_to_ext_top - tf2/2.0)
    w_top = B2/2.0; w_bot = B1/2.0

    wb = p.copy(); wb[d_idx] = d_bot
    wt = p.copy(); wt[d_idx] = d_top
    tl = wt.copy(); tl[w_idx] -= w_top
    tr = wt.copy(); tr[w_idx] += w_top
    bl = wb.copy(); bl[w_idx] -= w_bot
    br = wb.copy(); br[w_idx] += w_bot

    return {"web_bot": tuple(wb), "web_top": tuple(wt),
            "top_left": tuple(tl), "top_right": tuple(tr),
            "bot_left": tuple(bl), "bot_right": tuple(br)}


def _copy_points_set_along_Y(pts: Dict[str, Tuple[float,float,float]], y_target: float
                             ) -> Dict[str, Tuple[float,float,float]]:
    """Crea una copia dei punti con coordinata Y modificata."""
    return {k: (x, float(y_target), z) for k, (x, y, z) in pts.items()}

# ----------------- API principale (SOLO NODI) -----------------
# <--- MODIFICA: Struttura del dizionario restituito ---

def create_midplane_nodes_for_members(
    model_path: str,
    beam_intermediate_ids: List[int],     # Lista ID nodi intermedi travi
    col_intermediate_ids: List[int],      # Lista ID nodi intermedi colonne (inf+sup)
    beam_dims: Dict[str, float],
    col_dims: Dict[str, float],
    col_upper_intermediate_node_id: Optional[int] = None # ID nodo intermedio colonna sup
) -> Dict[str, Any]:
    """
    Crea i nodi del piano mediano per travi e colonne.
    Le colonne vengono replicate ai livelli Ymin/Ymax della trave e
    al livello Y del nodo intermedio della colonna superiore.

    Restituisce un dizionario con i nodi raggruppati per funzione:
    - beam_nodes: {'flangia_sup': [id1, id2], 'flangia_inf': [...], 'anima': [...]}
    - col_inf_nodes_base: {'flangia_sx': [id1, id2], 'flangia_dx': [...], 'anima': [...]}
    - col_inf_nodes_yBeamMin: Come sopra, ma per i nodi replicati a yBeamMin
    - col_inf_nodes_yBeamMax: Come sopra, ma per i nodi replicati a yBeamMax
    - col_sup_nodes_base: Come col_inf_nodes_base, per la colonna superiore
    - _y_levels: {'beam_y_min': float|None, 'beam_y_max': ..., 'col_upper_mid': ...}
    """

    # Identifica ID colonna inferiore (assumendo sia il primo non superiore)
    col_lower_intermediate_node_id = None
    if col_upper_intermediate_node_id is not None:
        for cid in col_intermediate_ids:
            if cid != col_upper_intermediate_node_id:
                col_lower_intermediate_node_id = cid
                break
    elif len(col_intermediate_ids) == 1: # Se c'è solo una colonna, è quella inferiore
         col_lower_intermediate_node_id = col_intermediate_ids[0]

    if not col_lower_intermediate_node_id and len(col_intermediate_ids) > 0:
         print("ATTENZIONE: Impossibile identificare nodo colonna inferiore.")
         # Prova a usare il primo della lista come fallback
         col_lower_intermediate_node_id = col_intermediate_ids[0]


    uID = 1
    _ck(st7.St7Init(), "Init API")
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open model")
        next_id = _get_total_nodes(uID) + 1

        # Dizionario di output con la nuova struttura
        out: Dict[str, Any] = {
            "beam_nodes": defaultdict(list),
            "col_inf_nodes_base": defaultdict(list),
            "col_inf_nodes_yBeamMin": defaultdict(list),
            "col_inf_nodes_yBeamMax": defaultdict(list),
            "col_sup_nodes_base": defaultdict(list),
            "_y_levels": {}
        }

        # ---- Travi ----
        beam_y_vals: List[float] = []
        if beam_intermediate_ids:
            # Estrai dimensioni
            D, B1, tf1, B2, tf2, tw = (
                float(beam_dims.get(k, 0.0)) for k in ["D", "B1", "tf1", "B2", "tf2", "tw"]
            )
            dist_c_top_beam, dist_c_bot_beam = _calculate_centroid_distances(D, B1, tf1, B2, tf2, tw)

            for nid in beam_intermediate_ids:
                x0, y0, z0 = _get_xyz(uID, int(nid))
                # Calcola coordinate 6 nodi
                pts_coords = _six_nodes_from_centroid_axes(
                    x0, y0, z0, "y", "z", dist_c_top_beam, dist_c_bot_beam, tf1, tf2, B1, B2
                )
                # Crea i nodi e memorizza gli ID
                ids_map: Dict[str, int] = {}
                for lab, P in pts_coords.items():
                    ids_map[lab] = _new_node(uID, P, next_id); next_id += 1
                    beam_y_vals.append(P[1]) # Raccogli coordinate Y

                # Aggiungi ID al dizionario di output
                out["beam_nodes"]["flangia_sup"].extend([ids_map["top_left"], ids_map["top_right"]])
                out["beam_nodes"]["flangia_inf"].extend([ids_map["bot_left"], ids_map["bot_right"]])
                out["beam_nodes"]["anima"].extend([ids_map["web_top"], ids_map["web_bot"]])

        # Calcola livelli Y per le repliche
        y_min_beam = min(beam_y_vals) if beam_y_vals else None
        y_max_beam = max(beam_y_vals) if beam_y_vals else None
        y_col_upper_mid = None
        if col_upper_intermediate_node_id is not None:
            _, y_col_upper_mid, _ = _get_xyz(uID, int(col_upper_intermediate_node_id))

        out["_y_levels"] = {
            "beam_y_min": y_min_beam,
            "beam_y_max": y_max_beam,
            "col_upper_mid": y_col_upper_mid,
        }

        # ---- Colonne ----
        if col_intermediate_ids:
            # Estrai dimensioni
            D, B1, tf1, B2, tf2, tw = (
                float(col_dims.get(k, 0.0)) for k in ["D", "B1", "tf1", "B2", "tf2", "tw"]
            )
            dist_c_top_col, dist_c_bot_col = _calculate_centroid_distances(D, B1, tf1, B2, tf2, tw)

            for nid in col_intermediate_ids:
                x0, y0, z0 = _get_xyz(uID, int(nid))
                # Calcola coordinate 6 nodi base
                base_pts_coords = _six_nodes_from_centroid_axes(
                    x0, y0, z0, "x", "z", dist_c_top_col, dist_c_bot_col, tf1, tf2, B1, B2
                )

                # Crea i nodi base e memorizza gli ID
                base_ids_map: Dict[str, int] = {}
                for lab, P in base_pts_coords.items():
                    base_ids_map[lab] = _new_node(uID, P, next_id); next_id += 1

                # Aggiungi ID base al dizionario corretto (inf o sup)
                target_base_dict = (out["col_sup_nodes_base"]
                                    if nid == col_upper_intermediate_node_id
                                    else out["col_inf_nodes_base"])

                target_base_dict["flangia_sx"].extend([base_ids_map["top_left"], base_ids_map["bot_left"]])
                target_base_dict["flangia_dx"].extend([base_ids_map["top_right"], base_ids_map["bot_right"]])
                target_base_dict["anima"].extend([base_ids_map["web_top"], base_ids_map["web_bot"]])

                # Crea repliche SOLO se è la colonna inferiore
                if nid == col_lower_intermediate_node_id:
                    # Replica a yBeamMin
                    if y_min_beam is not None:
                        rep_pts_min = _copy_points_set_along_Y(base_pts_coords, y_min_beam)
                        ids_map_min: Dict[str, int] = {}
                        for lab, P in rep_pts_min.items():
                            ids_map_min[lab] = _new_node(uID, P, next_id); next_id += 1
                        # Aggiungi ID replica a yBeamMin
                        out["col_inf_nodes_yBeamMin"]["flangia_sx"].extend([ids_map_min["top_left"], ids_map_min["bot_left"]])
                        out["col_inf_nodes_yBeamMin"]["flangia_dx"].extend([ids_map_min["top_right"], ids_map_min["bot_right"]])
                        out["col_inf_nodes_yBeamMin"]["anima"].extend([ids_map_min["web_top"], ids_map_min["web_bot"]])

                    # Replica a yBeamMax
                    if y_max_beam is not None:
                        rep_pts_max = _copy_points_set_along_Y(base_pts_coords, y_max_beam)
                        ids_map_max: Dict[str, int] = {}
                        for lab, P in rep_pts_max.items():
                            ids_map_max[lab] = _new_node(uID, P, next_id); next_id += 1
                        # Aggiungi ID replica a yBeamMax
                        out["col_inf_nodes_yBeamMax"]["flangia_sx"].extend([ids_map_max["top_left"], ids_map_max["bot_left"]])
                        out["col_inf_nodes_yBeamMax"]["flangia_dx"].extend([ids_map_max["top_right"], ids_map_max["bot_right"]])
                        out["col_inf_nodes_yBeamMax"]["anima"].extend([ids_map_max["web_top"], ids_map_max["web_bot"]])

        _ck(st7.St7SaveFile(uID), "Save model")
        # Converti defaultdict in dict normali per l'output
        out["beam_nodes"] = dict(out["beam_nodes"])
        out["col_inf_nodes_base"] = dict(out["col_inf_nodes_base"])
        out["col_inf_nodes_yBeamMin"] = dict(out["col_inf_nodes_yBeamMin"])
        out["col_inf_nodes_yBeamMax"] = dict(out["col_inf_nodes_yBeamMax"])
        out["col_sup_nodes_base"] = dict(out["col_sup_nodes_base"])
        
        # Rimuovi chiavi vuote se non sono state popolate (es. se non c'erano travi)
        if not out["col_inf_nodes_yBeamMin"]: del out["col_inf_nodes_yBeamMin"]
        if not out["col_inf_nodes_yBeamMax"]: del out["col_inf_nodes_yBeamMax"]

        return out

    finally:
        try:
            _ck(st7.St7CloseFile(uID), "Close")
        finally:
            st7.St7Release()

