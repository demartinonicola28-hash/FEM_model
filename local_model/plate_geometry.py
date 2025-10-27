# local_model/plate_geometry.py
# -*- coding: utf-8 -*-

from __future__ import annotations
import ctypes as ct
from typing import Dict, List, Tuple, Sequence, Optional, Any
from collections import defaultdict

import St7API as st7

# ----------------- util API -----------------
# ... (Funzioni _ck, _get_total_nodes, _get_xyz, _new_node, _get_total_elements INVARIATE) ...
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

def _get_total_elements(uID: int) -> int:
    tot = ct.c_long()
    _ck(st7.St7GetTotal(uID, st7.tyPLATE, ct.byref(tot)), "GetTotal tyPLATE")
    return int(tot.value)


# ----------------- API per PLATE (usando SetElementConnection) -----------------
def _new_plate_with_set_connection(uID: int, prop_id: int, n1: int, n2: int, n3: int, n4: int,
                                  next_id: int) -> int:
    """Crea un nuovo elemento Plate Quad4 usando St7SetElementConnection."""
    elem_id = int(next_id)
    conn = (ct.c_long * (1 + 4))()
    conn[0] = 4 # Num nodi
    conn[1] = int(n1); conn[2] = int(n2); conn[3] = int(n3); conn[4] = int(n4) # Nodi CCW
    _ck(st7.St7SetElementConnection(uID, st7.tyPLATE, elem_id, int(prop_id), conn),
        f"SetElementConnection Plate {elem_id}")
    return elem_id + 1

# ----------------- geometria sezioni -----------------
# ... (Funzioni _AXIS_IDX, _calculate_centroid_distances, _six_nodes_from_centroid_axes, _copy_points_set_along_Y, _copy_points_set_along_X INVARIATE) ...
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
    """Calcola le coordinate dei 6 nodi chiave (piano mediano) ai bordi esterni."""
    p = [x0, y0, z0]; d_idx = _AXIS_IDX[depth_axis]; w_idx = _AXIS_IDX[width_axis]
    d_bot = p[d_idx] - (dist_c_to_ext_bot - tf1/2.0)
    d_top = p[d_idx] + (dist_c_to_ext_top - tf2/2.0)
    w_top = B2/2.0; w_bot = B1/2.0
    wb = p.copy(); wb[d_idx] = d_bot; wt = p.copy(); wt[d_idx] = d_top
    tl = wt.copy(); tl[w_idx] -= w_top; tr = wt.copy(); tr[w_idx] += w_top
    bl = wb.copy(); bl[w_idx] -= w_bot; br = wb.copy(); br[w_idx] += w_bot
    return {"web_bot": tuple(wb), "web_top": tuple(wt), "top_left": tuple(tl),
            "top_right": tuple(tr), "bot_left": tuple(bl), "bot_right": tuple(br)}

def _copy_points_set_along_Y(pts: Dict[str, Tuple[float,float,float]], y_target: float
                             ) -> Dict[str, Tuple[float,float,float]]:
    """Crea una copia dei punti con coordinata Y modificata."""
    return {k: (x, float(y_target), z) for k, (x, y, z) in pts.items()}

def _copy_points_set_along_X(pts: Dict[str, Tuple[float,float,float]], x_target: float
                             ) -> Dict[str, Tuple[float,float,float]]:
    """Crea una copia dei punti con coordinata X modificata."""
    return {k: (float(x_target), y, z) for k, (x, y, z) in pts.items()}


# ----------------- API principale (NODI) -----------------
# ... (Funzione create_midplane_nodes_for_members INVARIATA) ...
def create_midplane_nodes_for_members(
    model_path: str,
    beam_intermediate_ids: List[int],     # Lista ID nodi intermedi travi
    col_intermediate_ids: List[int],      # Lista ID nodi intermedi colonne (inf+sup)
    beam_dims: Dict[str, float],
    col_dims: Dict[str, float],
    col_upper_intermediate_node_id: Optional[int] = None # ID nodo intermedio colonna sup
) -> Dict[str, Any]:
    """
    Crea i nodi del piano mediano per travi e colonne, restituendo
    un dizionario strutturato per funzione e livello.
    Usa la versione di _six_nodes_from_centroid_axes che mette i nodi ai bordi esterni.
    """
    col_lower_intermediate_node_id = None
    if col_upper_intermediate_node_id is not None:
        for cid in col_intermediate_ids:
            if cid != col_upper_intermediate_node_id:
                col_lower_intermediate_node_id = cid; break
    elif len(col_intermediate_ids) == 1: col_lower_intermediate_node_id = col_intermediate_ids[0]
    if not col_lower_intermediate_node_id and len(col_intermediate_ids) > 0:
         print("ATTENZIONE: Impossibile identificare nodo colonna inferiore. Uso il primo.");
         col_lower_intermediate_node_id = col_intermediate_ids[0]

    uID = 1
    _ck(st7.St7Init(), "Init API")
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open model")
        next_id = _get_total_nodes(uID) + 1

        out: Dict[str, Any] = {
            "beam_nodes": defaultdict(list), "col_inf_nodes_base": defaultdict(list),
            "col_inf_nodes_yBeamMin": defaultdict(list), "col_inf_nodes_yBeamMax": defaultdict(list),
            "col_sup_nodes_base": defaultdict(list), "_y_levels": {},
            "_beam_node_coords": {}
        }

        # ---- Travi ----
        beam_y_vals: List[float] = []
        if beam_intermediate_ids:
            D, B1, tf1, B2, tf2, tw = (float(beam_dims.get(k, 0.0)) for k in ["D", "B1", "tf1", "B2", "tf2", "tw"])
            dist_c_top_beam, dist_c_bot_beam = _calculate_centroid_distances(D, B1, tf1, B2, tf2, tw)
            for nid in beam_intermediate_ids:
                x0, y0, z0 = _get_xyz(uID, int(nid))
                pts_coords = _six_nodes_from_centroid_axes(x0, y0, z0, "y", "z", dist_c_top_beam, dist_c_bot_beam, tf1, tf2, B1, B2)
                out["_beam_node_coords"] = pts_coords
                ids_map: Dict[str, int] = {lab: _new_node(uID, P, next_id + i) for i, (lab, P) in enumerate(pts_coords.items())}; next_id += len(ids_map)
                beam_y_vals.extend(P[1] for P in pts_coords.values())
                out["beam_nodes"]["flangia_sup"].extend([ids_map["top_left"], ids_map["top_right"]])
                out["beam_nodes"]["flangia_inf"].extend([ids_map["bot_left"], ids_map["bot_right"]])
                out["beam_nodes"]["anima"].extend([ids_map["web_top"], ids_map["web_bot"]])

        y_min_beam = min(beam_y_vals) if beam_y_vals else None
        y_max_beam = max(beam_y_vals) if beam_y_vals else None
        y_col_upper_mid = None
        if col_upper_intermediate_node_id is not None: _, y_col_upper_mid, _ = _get_xyz(uID, int(col_upper_intermediate_node_id))
        out["_y_levels"] = {"beam_y_min": y_min_beam, "beam_y_max": y_max_beam, "col_upper_mid": y_col_upper_mid}

        # ---- Colonne ----
        if col_intermediate_ids:
            D, B1, tf1, B2, tf2, tw = (float(col_dims.get(k, 0.0)) for k in ["D", "B1", "tf1", "B2", "tf2", "tw"])
            dist_c_top_col, dist_c_bot_col = _calculate_centroid_distances(D, B1, tf1, B2, tf2, tw)
            for nid in col_intermediate_ids:
                x0, y0, z0 = _get_xyz(uID, int(nid))
                base_pts_coords = _six_nodes_from_centroid_axes(x0, y0, z0, "x", "z", dist_c_top_col, dist_c_bot_col, tf1, tf2, B1, B2)
                base_ids_map: Dict[str, int] = {lab: _new_node(uID, P, next_id + i) for i, (lab, P) in enumerate(base_pts_coords.items())}; next_id += len(base_ids_map)
                target_base_dict = out["col_sup_nodes_base"] if nid == col_upper_intermediate_node_id else out["col_inf_nodes_base"]
                target_base_dict["flangia_sx"].extend([base_ids_map["top_left"], base_ids_map["bot_left"]])
                target_base_dict["flangia_dx"].extend([base_ids_map["top_right"], base_ids_map["bot_right"]])
                target_base_dict["anima"].extend([base_ids_map["web_top"], base_ids_map["web_bot"]])

                if nid == col_lower_intermediate_node_id:
                    if y_min_beam is not None:
                        rep_pts_min = _copy_points_set_along_Y(base_pts_coords, y_min_beam)
                        ids_map_min: Dict[str, int] = {lab: _new_node(uID, P, next_id + i) for i, (lab, P) in enumerate(rep_pts_min.items())}; next_id += len(ids_map_min)
                        out["col_inf_nodes_yBeamMin"]["flangia_sx"].extend([ids_map_min["top_left"], ids_map_min["bot_left"]])
                        out["col_inf_nodes_yBeamMin"]["flangia_dx"].extend([ids_map_min["top_right"], ids_map_min["bot_right"]])
                        out["col_inf_nodes_yBeamMin"]["anima"].extend([ids_map_min["web_top"], ids_map_min["web_bot"]])
                    if y_max_beam is not None:
                        rep_pts_max = _copy_points_set_along_Y(base_pts_coords, y_max_beam)
                        ids_map_max: Dict[str, int] = {lab: _new_node(uID, P, next_id + i) for i, (lab, P) in enumerate(rep_pts_max.items())}; next_id += len(ids_map_max)
                        out["col_inf_nodes_yBeamMax"]["flangia_sx"].extend([ids_map_max["top_left"], ids_map_max["bot_left"]])
                        out["col_inf_nodes_yBeamMax"]["flangia_dx"].extend([ids_map_max["top_right"], ids_map_max["bot_right"]])
                        out["col_inf_nodes_yBeamMax"]["anima"].extend([ids_map_max["web_top"], ids_map_max["web_bot"]])

        _ck(st7.St7SaveFile(uID), "Save model")
        for key in list(out.keys()):
             if isinstance(out[key], defaultdict):
                 out[key] = dict(out[key])
                 if not out[key] and key.startswith("col_inf_nodes_y"): del out[key]
        return out

    finally:
        try: _ck(st7.St7CloseFile(uID), "Close")
        finally: st7.St7Release()


# ----------------- API principale (PLATE) -----------------
# <--- MODIFICA: Corretto target X copia trave (usa flangia colonna); Condizionale creazione fazzoletti ---

def create_plates_for_joint(
    model_path: str,
    res_nodes: Dict[str, Any], # La struttura restituita da create_midplane_nodes...
    props_map: Dict[str, int], # La mappa nome->ID da plate_properties.py
) -> None:
    """
    Crea i plate (Quad4).
    Copia i nodi trave lungo X fino alla FLANGIA VICINA della colonna.
    Crea i fazzoletti (irrigidimenti) solo se la proprietà 't_fazzoletti' esiste.
    Utilizza St7SetElementConnection per la creazione.
    """

    uID = 1
    _ck(st7.St7Init(), "Init API")
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open model")

        elements_before = _get_total_elements(uID)
        next_plate_id = elements_before + 1
        next_node_id = _get_total_nodes(uID) + 1
        print(f"Inizio creazione plate. Elementi attuali: {elements_before}. ID plate iniziale: {next_plate_id}. ID nodo iniziale: {next_node_id}")

        # --- Estrai ID proprietà PLATE ---
        try:
            p_beam_w  = props_map["tw_sez.trave"]
            p_beam_f1 = props_map["tf1_sez.trave"]; p_beam_f2 = props_map["tf2_sez.trave"]
            p_col_w   = props_map["tw_sez.colonna"]
            p_col_f1  = props_map["tf1_sez.colonna"]; p_col_f2  = props_map["tf2_sez.colonna"]
            p_panel   = props_map["t_panel.modale"]
            p_gusset  = props_map.get("t_fazzoletti")
        except KeyError as e: raise KeyError(f"Chiave proprietà mancante: {e}") from e

        # --- Estrai gruppi di nodi ---
        beam_nodes_orig_ids = res_nodes.get("beam_nodes", {})
        beam_nodes_orig_coords = res_nodes.get("_beam_node_coords", {})
        col_inf_base = res_nodes.get("col_inf_nodes_base", {})
        col_inf_min = res_nodes.get("col_inf_nodes_yBeamMin", {})
        col_inf_max = res_nodes.get("col_inf_nodes_yBeamMax", {})
        col_sup_base = res_nodes.get("col_sup_nodes_base", {})

        if not beam_nodes_orig_ids or not beam_nodes_orig_coords or not col_inf_base or not col_inf_min or not col_inf_max or not col_sup_base:
             missing = [k for k, v in [("beam", beam_nodes_orig_ids), ("_beam_coords", beam_nodes_orig_coords),
                                      ("col_inf_base", col_inf_base), ("col_inf_min", col_inf_min),
                                      ("col_inf_max", col_inf_max), ("col_sup_base", col_sup_base)] if not v]
             raise ValueError(f"Dati nodi mancanti: {missing}")

        # --- Copia nodi trave lungo X (fino alla FLANGIA VICINA colonna) ---
        print("Copia dei nodi della trave lungo X...")
        target_x_coord = None
        # <--- MODIFICA: Usa il nodo della FLANGIA SX (top_left) come riferimento per X ---
        if col_inf_max.get("flangia_sx"):
            sx_node_id = col_inf_max["flangia_sx"][1] # ID del nodo top_left @ yBeamMin
            target_x_coord, _, _ = _get_xyz(uID, sx_node_id)
            print(f"  Coordinata X target (da nodo flangia sx {sx_node_id}): {target_x_coord}")
        # ---> FINE MODIFICA
        else:
            raise ValueError("Nodi flangia sx colonna inferiore @ yBeamMin non trovati.")

        copied_beam_coords = _copy_points_set_along_X(beam_nodes_orig_coords, target_x_coord)
        copied_beam_node_ids: Dict[str, int] = {}
        for label, coords in copied_beam_coords.items():
            copied_beam_node_ids[label] = _new_node(uID, coords, next_node_id); next_node_id += 1
        print(f"  Creati {len(copied_beam_node_ids)} nuovi nodi per la trave (ID: {list(copied_beam_node_ids.values())})")

        # Lista di plate da creare: (PropID, [Nodi CCW])
        plates_to_create: List[Tuple[int, List[int]]] = []

        # --- NODI ESTRATTI (per leggibilità) ---
        cib_wb=col_inf_base["anima"][1]; cib_wt=col_inf_base["anima"][0]; cib_tl=col_inf_base["flangia_sx"][0]; cib_bl=col_inf_base["flangia_sx"][1]; cib_tr=col_inf_base["flangia_dx"][0]; cib_br=col_inf_base["flangia_dx"][1]
        cim_wb=col_inf_min["anima"][1]; cim_wt=col_inf_min["anima"][0]; cim_tl=col_inf_min["flangia_sx"][0]; cim_bl=col_inf_min["flangia_sx"][1]; cim_tr=col_inf_min["flangia_dx"][0]; cim_br=col_inf_min["flangia_dx"][1]
        cia_wb=col_inf_max["anima"][1]; cia_wt=col_inf_max["anima"][0]; cia_tl=col_inf_max["flangia_sx"][0]; cia_bl=col_inf_max["flangia_sx"][1]; cia_tr=col_inf_max["flangia_dx"][0]; cia_br=col_inf_max["flangia_dx"][1]
        csb_wb=col_sup_base["anima"][1]; csb_wt=col_sup_base["anima"][0]; csb_tl=col_sup_base["flangia_sx"][0]; csb_bl=col_sup_base["flangia_sx"][1]; csb_tr=col_sup_base["flangia_dx"][0]; csb_br=col_sup_base["flangia_dx"][1]
        bn_wb=beam_nodes_orig_ids["anima"][1]; bn_wt=beam_nodes_orig_ids["anima"][0]; bn_tl=beam_nodes_orig_ids["flangia_sup"][0]; bn_tr=beam_nodes_orig_ids["flangia_sup"][1]; bn_bl=beam_nodes_orig_ids["flangia_inf"][0]; bn_br=beam_nodes_orig_ids["flangia_inf"][1]
        bnc_wb=copied_beam_node_ids["web_bot"]; bnc_wt=copied_beam_node_ids["web_top"]; bnc_tl=copied_beam_node_ids["top_left"]; bnc_tr=copied_beam_node_ids["top_right"]; bnc_bl=copied_beam_node_ids["bot_left"]; bnc_br=copied_beam_node_ids["bot_right"]

        # --- 1. Segmento Colonna Inferiore ---
        plates_to_create.extend([
            (p_col_w, [cib_wb, cib_wt, cim_wt, cim_wb]),
            (p_col_f1, [cib_wb, cib_bl, cim_bl, cim_wb]), (p_col_f2, [cib_wt, cib_tl, cim_tl, cim_wt]),
            (p_col_f1, [cib_wb, cib_br, cim_br, cim_wb]), (p_col_f2, [cib_wt, cib_tr, cim_tr, cim_wt]),
        ])
        # --- 2. Segmento Colonna Pannello ---
        plates_to_create.extend([
            (p_panel, [cim_wb, cim_wt, cia_wt, cia_wb]),
            (p_col_f1, [cim_wb, cim_bl, cia_bl, cia_wb]), (p_col_f2, [cim_wt, cim_tl, cia_tl, cia_wt]),
            (p_col_f1, [cim_wb, cim_br, cia_br, cia_wb]), (p_col_f2, [cim_wt, cim_tr, cia_tr, cia_wt]),
        ])
        # --- 3. Segmento Colonna Superiore ---
        plates_to_create.extend([
            (p_col_w, [cia_wb, cia_wt, csb_wt, csb_wb]),
            (p_col_f1, [cia_wb, cia_bl, csb_bl, csb_wb]), (p_col_f2, [cia_wt, cia_tl, csb_tl, csb_wt]),
            (p_col_f1, [cia_wb, cia_br, csb_br, csb_wb]), (p_col_f2, [cia_wt, cia_tr, csb_tr, csb_wt]),
        ])
        # --- 4. Trave (Originale -> Copiata @ X flangia colonna) ---
        plates_to_create.extend([
            (p_beam_w, [bn_wb, bn_wt, bnc_wt, bnc_wb]),
            (p_beam_f1, [bn_bl, bn_br, bnc_br, bnc_bl]),
            (p_beam_f2, [bn_tl, bn_tr, bnc_tr, bnc_tl]),
        ])
        # --- 5. Irrigidimenti / Diaframmi (CONDIZIONALE) ---
        if p_gusset is not None:
            print("Creazione plate irrigidimenti (fazzoletti)...")
            plates_to_create.extend([
                (p_gusset, [cim_bl, cim_wb, cim_wt, cim_tl]), (p_gusset, [cim_wb, cim_br, cim_tr, cim_wt]),
                (p_gusset, [cia_bl, cia_wb, cia_wt, cia_tl]), (p_gusset, [cia_wb, cia_br, cia_tr, cia_wt]),
            ])
        else: print("Proprietà 't_fazzoletti' non trovata, irrigidimenti non creati.")

        # --- Creazione effettiva elementi ---
        print(f"Tentativo di creazione di {len(plates_to_create)} plate usando St7SetElementConnection...")
        created_count = 0
        for plate_prop, node_ids_ccw in plates_to_create:
            if len(node_ids_ccw) != 4: continue
            try:
                next_plate_id = _new_plate_with_set_connection(uID, plate_prop,
                                                               node_ids_ccw[0], node_ids_ccw[1],
                                                               node_ids_ccw[2], node_ids_ccw[3],
                                                               next_plate_id)
                created_count += 1
            except Exception as e: print(f"  ERRORE plate {next_plate_id-1} nodi {node_ids_ccw}: {e}")

        print(f"Loop API eseguito {created_count} volte.")
        _ck(st7.St7SaveFile(uID), "Save model")
        elements_after = _get_total_elements(uID)
        print(f"Elementi plate dopo salvataggio: {elements_after}")
        final_created = elements_after - elements_before
        if final_created == 0: print("ATTENZIONE: 0 plate sono stati creati.")
        elif final_created < created_count: print(f"ATTENZIONE: Creati solo {final_created} / {created_count} plate richiesti.")
        else: print(f"Successo: {final_created} plate creati.")

    finally:
        try: _ck(st7.St7CloseFile(uID), "Close")
        finally: st7.St7Release()
