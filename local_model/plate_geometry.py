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

def _get_total_elements(uID: int) -> int:
    tot = ct.c_long()
    _ck(st7.St7GetTotal(uID, st7.tyPLATE, ct.byref(tot)), "GetTotal tyPLATE")
    return int(tot.value)

def _get_total_beams(uID: int) -> int:
    tot = ct.c_long()
    _ck(st7.St7GetTotal(uID, st7.tyBEAM, ct.byref(tot)), "GetTotal tyBEAM")
    return int(tot.value)

# <--- MODIFICA CRITICA: Funzione _new_beam CORRETTA ---
def _new_beam(uID: int, prop_id: int, n1: int, n2: int, next_id: int) -> int:
    """Crea un nuovo elemento Beam2."""
    elem_id = int(next_id)
    
    # 1. Imposta la proprietà
    _ck(st7.St7SetBeamProperty(uID, elem_id, int(prop_id)), f"SetBeamProp {elem_id}")
    
    # 2. Imposta connessione e tipo
    conn = (ct.c_long * 2)(int(n1), int(n2))
    
    # ERRORE PRECEDENTE: passavo st7.bpEnd invece di st7.btBeam2
    # La chiamata corretta per un beam a 2 nodi usa st7.btBeam2
    _ck(st7.St7SetBeamConnection(uID, elem_id, st7.btBeam2, conn), f"SetBeamConn {elem_id} type=Beam2")
    
    return elem_id + 1
# <--- FINE MODIFICA ---

def _create_dummy_beam_prop(uID: int, prop_id: int):
    """
    Crea una proprietà BEAM fittizia (Null Section) da usare 
    per i beam di contorno temporanei.
    """
    try:
        _ck(st7.St7SetPropertyType(uID, prop_id, st7.ptBeam), f"SetPropType {prop_id}")
        _ck(st7.St7SetMaterial(uID, prop_id, 1), f"SetMaterial {prop_id}")
        _ck(st7.St7SetBeamSectionType(uID, prop_id, st7.btNullSection), f"SetBeamSect {prop_id}")
        _ck(st7.St7SetSectionName(uID, prop_id, b"Temp_Outline"), "SetSectionName Temp")
    except Exception as e:
        # Ignora l'errore se la proprietà 99 esiste già
        print(f"Nota: Impossibile creare prop beam fittizia {prop_id} (potrebbe esistere già).")

# ----------------- geometria sezioni -----------------

_AXIS_IDX = {"x": 0, "y": 1, "z": 2}

def _calculate_centroid_distances(
    D: float, B1: float, tf1: float, B2: float, tf2: float, tw: float
) -> Tuple[float, float]:
    """Calcola le distanze dal baricentro teorico ai LEMBI ESTERNI."""
    try:
        A1 = B1 * tf1
        y1 = tf1 / 2.0
        hw = D - tf1 - tf2
        Aw = hw * tw
        yw = tf1 + hw / 2.0
        A2 = B2 * tf2
        y2 = D - tf2 / 2.0
        Atot = A1 + Aw + A2
        if Atot == 0:
            return (D / 2.0, D / 2.0) 
        yc = (A1 * y1 + Aw * yw + A2 * y2) / Atot
        dist_c_to_ext_bot = yc
        dist_c_to_ext_top = D - yc 
        return (dist_c_to_ext_top, dist_c_to_ext_bot)
    except Exception:
        return (D / 2.0, D / 2.0)


def _six_nodes_from_centroid_axes(x0: float, y0: float, z0: float,
                                 depth_axis: str, width_axis: str,
                                 dist_c_to_ext_top: float, 
                                 dist_c_to_ext_bot: float, 
                                 tf1: float, tf2: float,
                                 B1: float, B2: float
                                 ) -> Dict[str, Tuple[float, float, float]]:
    p = [x0, y0, z0]
    d_idx = _AXIS_IDX[depth_axis]
    w_idx = _AXIS_IDX[width_axis]

    d_bot = p[d_idx] - (float(dist_c_to_ext_bot) - float(tf1)/2.0)
    d_top = p[d_idx] + (float(dist_c_to_ext_top) - float(tf2)/2.0)
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

# ----------------- API principale (NODI) -----------------

def create_midplane_nodes_for_members(
    model_path: str,
    beam_intermediate_ids: List[int],
    col_intermediate_ids: List[int],
    beam_dims: Dict[str, float],
    col_dims: Dict[str, float],
    col_upper_intermediate_node_id: Optional[int] = None, 
) -> Dict[str, Dict[int, Dict[str, int]]]:
    
    # ... (Codice per la creazione dei nodi - INVARIATO) ...
    
    uID = 1
    _ck(st7.St7Init(), "Init API")
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open model")
        next_id = _get_total_nodes(uID) + 1

        out: Dict[str, Dict[int, Dict[str, int]]] = {"beam": {}, "column": {}}

        # ---- Travi ----
        beam_y_vals: List[float] = []
        if beam_intermediate_ids:
            D   = float(beam_dims.get("D", 0.0)) 
            B1  = float(beam_dims.get("B1", beam_dims.get("B", 0.0)))
            B2  = float(beam_dims.get("B2", beam_dims.get("B", 0.0)))
            tf1 = float(beam_dims.get("tf1", 0.0))
            tf2 = float(beam_dims.get("tf2", 0.0))
            tw  = float(beam_dims.get("tw", 0.0)) 
            
            dist_c_top_beam, dist_c_bot_beam = _calculate_centroid_distances(
                D, B1, tf1, B2, tf2, tw
            )

            for nid in beam_intermediate_ids:
                x0, y0, z0 = _get_xyz(uID, int(nid))
                pts = _six_nodes_from_centroid_axes(
                    x0, y0, z0, depth_axis="y", width_axis="z",
                    dist_c_to_ext_top=dist_c_top_beam, 
                    dist_c_to_ext_bot=dist_c_bot_beam, 
                    tf1=tf1, tf2=tf2, B1=B1, B2=B2
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
            D   = float(col_dims.get("D", 0.0))
            B1  = float(col_dims.get("B1", col_dims.get("B", 0.0)))
            B2  = float(col_dims.get("B2", col_dims.get("B", 0.0)))
            tf1 = float(col_dims.get("tf1", 0.0))
            tf2 = float(col_dims.get("tf2", 0.0))
            tw  = float(col_dims.get("tw", 0.0)) 

            dist_c_top_col, dist_c_bot_col = _calculate_centroid_distances(
                D, B1, tf1, B2, tf2, tw
            )

            for nid in col_intermediate_ids:
                x0, y0, z0 = _get_xyz(uID, int(nid))
                base_pts = _six_nodes_from_centroid_axes(
                    x0, y0, z0, depth_axis="x", width_axis="z",
                    dist_c_to_ext_top=dist_c_top_col, 
                    dist_c_to_ext_bot=dist_c_bot_col, 
                    tf1=tf1, tf2=tf2, B1=B1, B2=B2
                )

                replicas: Dict[str, Tuple[float,float,float]] = {}
                if y_min_beam is not None:
                    replicas.update(_copy_points_set_along_Y(base_pts, y_min_beam, "yBeamMin"))
                if y_max_beam is not None:
                    replicas.update(_copy_points_set_along_Y(base_pts, y_max_beam, "yBeamMax"))
                if y_col_upper_mid is not None:
                    if nid == col_upper_intermediate_node_id:
                         pass
                    else:
                        replicas.update(_copy_points_set_along_Y(base_pts, y_col_upper_mid, "yColUpperMid"))

                ids_map: Dict[str, int] = {}
                for lab, P in {**base_pts, **replicas}.items():
                    ids_map[lab] = _new_node(uID, P, next_id); next_id += 1

                out["column"][int(nid)] = ids_map

        _ck(st7.St7SaveFile(uID), "Save model")
        out["_y_levels"] = { 
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


# ----------------- API principale (PLATE) -----------------
# <--- Logica "Beam Polygon Conversion" CON funzione _new_beam CORRETTA ---

def create_plates_for_joint(
    model_path: str,
    res_nodes: Dict,
    props_map: Dict,
    beam_mid_id: int,
    col_low_id: int, 
    col_up_id: int   
) -> None:
    """
    Crea i plate usando l'approccio "Beam Polygon Conversion".
    """
    
    uID = 1
    _ck(st7.St7Init(), "Init API")
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open model")
        
        elements_before = _get_total_elements(uID)
        next_beam_id = _get_total_beams(uID) + 1
        
        # 1. Creare una proprietà beam temporanea (usa un ID alto)
        TEMP_BEAM_PROP = 99
        _create_dummy_beam_prop(uID, TEMP_BEAM_PROP)
        print(f"Creata/verificata proprietà beam temporanea {TEMP_BEAM_PROP}")

        # --- Estrai mappe nodi ---
        beam_nodes = res_nodes["beam"][beam_mid_id]
        col_nodes_low = res_nodes["column"][col_low_id]
        col_nodes_up = res_nodes["column"][col_up_id]

        # --- Estrai ID proprietà PLATE ---
        p_beam_w  = props_map["beam_web"]
        p_beam_f1 = props_map["beam_flange_bot"]
        p_beam_f2 = props_map["beam_flange_top"]
        
        p_col_w  = props_map["col_web"]
        p_col_f1 = props_map["col_flange_bot"] 
        p_col_f2 = props_map["col_flange_top"] 

        p_panel = props_map.get("panel_zone", p_col_w)
        p_gusset = props_map.get("gusset", p_beam_w) 

        # --- Definizione dei poligoni ---
        polygons_to_create: List[Tuple[int, List[int]]] = []

        # --- 1. Segmento Colonna Inferiore ---
        polygons_to_create.extend([
            (p_col_w, [col_nodes_low["web_bot"], col_nodes_low["web_top"], col_nodes_low["web_top@yBeamMin"], col_nodes_low["web_bot@yBeamMin"]]),
            (p_col_f1, [col_nodes_low["bot_left"], col_nodes_low["web_bot"], col_nodes_low["web_bot@yBeamMin"], col_nodes_low["bot_left@yBeamMin"]]),
            (p_col_f1, [col_nodes_low["web_bot"], col_nodes_low["bot_right"], col_nodes_low["bot_right@yBeamMin"], col_nodes_low["web_bot@yBeamMin"]]),
            (p_col_f2, [col_nodes_low["top_left"], col_nodes_low["web_top"], col_nodes_low["web_top@yBeamMin"], col_nodes_low["top_left@yBeamMin"]]),
            (p_col_f2, [col_nodes_low["web_top"], col_nodes_low["top_right"], col_nodes_low["top_right@yBeamMin"], col_nodes_low["web_top@yBeamMin"]]),
        ])

        # --- 2. Segmento Colonna Pannello ---
        polygons_to_create.extend([
            (p_panel, [col_nodes_low["web_bot@yBeamMin"], col_nodes_low["web_top@yBeamMin"], col_nodes_low["web_top@yBeamMax"], col_nodes_low["web_bot@yBeamMax"]]),
            (p_col_f1, [col_nodes_low["bot_left@yBeamMin"], col_nodes_low["web_bot@yBeamMin"], col_nodes_low["web_bot@yBeamMax"], col_nodes_low["bot_left@yBeamMax"]]),
            (p_col_f1, [col_nodes_low["web_bot@yBeamMin"], col_nodes_low["bot_right@yBeamMin"], col_nodes_low["bot_right@yBeamMax"], col_nodes_low["web_bot@yBeamMax"]]),
            (p_col_f2, [col_nodes_low["top_left@yBeamMin"], col_nodes_low["web_top@yBeamMin"], col_nodes_low["web_top@yBeamMax"], col_nodes_low["top_left@yBeamMax"]]),
            (p_col_f2, [col_nodes_low["web_top@yBeamMin"], col_nodes_low["top_right@yBeamMin"], col_nodes_low["top_right@yBeamMax"], col_nodes_low["web_top@yBeamMax"]]),
        ])

        # --- 3. Segmento Colonna Superiore ---
        polygons_to_create.extend([
            (p_col_w, [col_nodes_low["web_bot@yBeamMax"], col_nodes_low["web_top@yBeamMax"], col_nodes_up["web_top"], col_nodes_up["web_bot"]]),
            (p_col_f1, [col_nodes_low["bot_left@yBeamMax"], col_nodes_low["web_bot@yBeamMax"], col_nodes_up["web_bot"], col_nodes_up["bot_left"]]),
            (p_col_f1, [col_nodes_low["web_bot@yBeamMax"], col_nodes_low["bot_right@yBeamMax"], col_nodes_up["bot_right"], col_nodes_up["web_bot"]]),
            (p_col_f2, [col_nodes_low["top_left@yBeamMax"], col_nodes_low["web_top@yBeamMax"], col_nodes_up["web_top"], col_nodes_up["top_left"]]),
            (p_col_f2, [col_nodes_low["web_top@yBeamMax"], col_nodes_low["top_right@yBeamMax"], col_nodes_up["top_right"], col_nodes_up["web_top"]]),
        ])

        # --- 4. Trave ---
        polygons_to_create.extend([
            (p_beam_w, [beam_nodes["web_bot"], beam_nodes["web_top"], col_nodes_low["web_top@yBeamMax"], col_nodes_low["web_bot@yBeamMin"]]),
            (p_beam_f1, [beam_nodes["bot_left"], beam_nodes["bot_right"], col_nodes_low["bot_right@yBeamMin"], col_nodes_low["bot_left@yBeamMin"]]),
            (p_beam_f2, [beam_nodes["top_left"], beam_nodes["top_right"], col_nodes_low["top_right@yBeamMax"], col_nodes_low["top_left@yBeamMax"]]),
        ])

        # --- 5. Irrigidimenti / Diaframmi ---
        polygons_to_create.extend([
            (p_gusset, [col_nodes_low["bot_left@yBeamMin"], col_nodes_low["web_bot@yBeamMin"], col_nodes_low["web_top@yBeamMin"], col_nodes_low["top_left@yBeamMin"]]),
            (p_gusset, [col_nodes_low["web_bot@yBeamMin"], col_nodes_low["bot_right@yBeamMin"], col_nodes_low["top_right@yBeamMin"], col_nodes_low["web_top@yBeamMin"]]),
            (p_gusset, [col_nodes_low["bot_left@yBeamMax"], col_nodes_low["web_bot@yBeamMax"], col_nodes_low["web_top@yBeamMax"], col_nodes_low["top_left@yBeamMax"]]),
            (p_gusset, [col_nodes_low["web_bot@yBeamMax"], col_nodes_low["bot_right@yBeamMax"], col_nodes_low["top_right@yBeamMax"], col_nodes_low["web_top@yBeamMax"]]),
        ])
        
        # --- Creazione effettiva elementi ---
        print(f"Tentativo di creazione di {len(polygons_to_create)} plate da poligoni di beam...")
        
        created_count_loop = 0
        
        for plate_prop, node_list in polygons_to_create:
            if len(node_list) != 4:
                print(f"  ATTENZIONE: Saltato poligono non-Quad4 per prop {plate_prop}")
                continue
            
            try:
                # Crea i 4 beam temporanei
                n1, n2, n3, n4 = node_list
                b1_id = _new_beam(uID, TEMP_BEAM_PROP, n1, n2, next_beam_id); next_beam_id += 1
                b2_id = _new_beam(uID, TEMP_BEAM_PROP, n2, n3, next_beam_id); next_beam_id += 1
                b3_id = _new_beam(uID, TEMP_BEAM_PROP, n3, n4, next_beam_id); next_beam_id += 1
                b4_id = _new_beam(uID, TEMP_BEAM_PROP, n4, n1, next_beam_id); next_beam_id += 1
                
                beam_ids = [b1_id, b2_id, b3_id, b4_id]
                beam_array = (ct.c_long * 4)(*beam_ids)
                
                # Converti e cancella i beam
                _ck(st7.St7ConvertBeamPolygonToPlate(
                    uID,
                    4,            # NumBeams
                    beam_array,   # BeamList
                    plate_prop,   # PropID (per il plate)
                    0,            # Group (0=nessuno)
                    True          # DeleteBeams = True
                ), f"ConvertBeamPolygonToPlate prop {plate_prop}")
                
                created_count_loop += 1
            except Exception as e:
                print(f"  ERRORE durante la conversione del poligono per prop {plate_prop}: {e}")

        
        print(f"Loop di conversione API eseguito {created_count_loop} volte.")
        _ck(st7.St7SaveFile(uID), "Save model")
        
        elements_after = _get_total_elements(uID)
        print(f"Elementi plate dopo salvataggio: {elements_after}")
        final_created = elements_after - elements_before
        
        if final_created == 0:
            print("ATTENZIONE: 0 plate sono stati creati.")
        elif final_created != len(polygons_to_create):
             print(f"ATTENZIONE: Creati solo {final_created} / {len(polygons_to_create)} plate.")
        else:
            print(f"Successo: {final_created} plate creati.")

    finally:
        try:
            _ck(st7.St7CloseFile(uID), "Close")
        finally:
            st7.St7Release()