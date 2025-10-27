# local_model/cut_elements.py
# Taglia tutti i plate del modello lungo i piani XZ, YZ e XY
# definiti dalle coordinate di tutti i nodi.
# Questo serve a "cucire" (stitch) le varie parti del giunto.

import os
import ctypes as ct
from typing import Dict

try:
    import St7API as st7
except ImportError:
    print("ERRORE: Impossibile importare St7API.")
    raise

# Importa la funzione 'ck' per il controllo errori
try:
    from analysis.ltd_analysis import ck
except ImportError:
    print("ATTENZIONE: Funzione 'ck' non trovata. Gli errori API non verranno controllati.")
    def ck(result, *args):
        if result != 0:
            buf = ct.create_string_buffer(st7.kMaxStrLen)
            st7.St7GetAPIErrorString(result, buf, st7.kMaxStrLen)
            api_err_msg = buf.value.decode('utf-8','ignore')
            print(f"ERRORE API: {args} (codice={result}, msg='{api_err_msg}')")
            raise RuntimeError(f"Errore API: {args} (codice={result}, msg='{api_err_msg}')")
        pass

# --- Funzioni Helper API ---

def _get_total_entities(uID: int, entity_type: int) -> int:
    """Ritorna il numero totale di un'entità (nodo o plate)."""
    tot = ct.c_long()
    ck(st7.St7GetTotal(uID, entity_type, ct.byref(tot)), f"GetTotal {entity_type}")
    return int(tot.value)

def _get_node_xyz(uID: int, node_id: int) -> tuple[float, float, float]:
    """Ritorna le coordinate (X,Y,Z) di un nodo."""
    arr = (ct.c_double * 3)()
    ck(st7.St7GetNodeXYZ(uID, node_id, arr), f"GetNodeXYZ {node_id}")
    return arr[0], arr[1], arr[2]

def _select_all_plates(uID: int) -> int:
    """Seleziona tutti i plate nel modello e ritorna il loro numero."""
    total_plates = _get_total_entities(uID, st7.tyPLATE)
    print(f"  ...Selezionando {total_plates} plate...")
    for p_id in range(1, total_plates + 1):
        # St7SetEntitySelectState(uID, Entity, EntityNum, EndEdgeFace, Selected)
        # Entity=tyPLATE, EndEdgeFace=0, Selected=1 (True)
        ck(st7.St7SetEntitySelectState(uID, st7.tyPLATE, p_id, 0, 1), f"Select plate {p_id}")
    return total_plates

def _deselect_all_plates(uID: int):
    """Deseleziona tutti i plate nel modello."""
    # Ottieni il *nuovo* totale dopo i tagli
    total_plates = _get_total_entities(uID, st7.tyPLATE)
    print(f"  ...Deselezionando {total_plates} plate...")
    for p_id in range(1, total_plates + 1):
        # Selected = 0 (False)
        ck(st7.St7SetEntitySelectState(uID, st7.tyPLATE, p_id, 0, 0), f"Deselect plate {p_id}")

# --- Funzione Principale ---

def run_cut_elements_at_nodes(model_path: str, edge_tol: int = 10):
    """
    Taglia tutti i plate del modello lungo i piani XZ, YZ e XY
    definiti da tutte le coordinate uniche dei nodi.
    
    Args:
        model_path (str): Percorso a local_model.st7
        edge_tol (int): Tolleranza per il taglio (0-40).
    """
    print(f"\nInizio taglio (stitching) dei plate in: {os.path.basename(model_path)}")

    uID = 1
    ck(st7.St7Init(), "Init API per Cut Elements")
    try:
        ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), f"Open local model {model_path}")
        
        # 1. Colleziona UN NODO per ogni coordinata X, Y e Z unica
        total_nodes = _get_total_entities(uID, st7.tyNODE)
        # Mappa [coordinata] -> node_id
        nodes_for_x: Dict[float, int] = {}
        nodes_for_y: Dict[float, int] = {}
        nodes_for_z: Dict[float, int] = {} # <-- AGGIUNTO
        
        print(f"  ...Lettura delle coordinate di {total_nodes} nodi...")
        for n_id in range(1, total_nodes + 1):
            try:
                x, y, z = _get_node_xyz(uID, n_id)
                # Salva un nodo di riferimento per ogni coordinata
                if x not in nodes_for_x:
                    nodes_for_x[x] = n_id
                if y not in nodes_for_y:
                    nodes_for_y[y] = n_id
                if z not in nodes_for_z: # <-- AGGIUNTO
                    nodes_for_z[z] = n_id
            except Exception:
                continue
        
        print(f"  ...Trovati {len(nodes_for_x)} piani YZ (costante X).")
        print(f"  ...Trovati {len(nodes_for_y)} piani XZ (costante Y).")
        print(f"  ...Trovati {len(nodes_for_z)} piani XY (costante Z).") # <-- AGGIUNTO

        # 2. Seleziona tutti i plate
        _select_all_plates(uID)

        # 3. Imposta "Keep Selected"
        ck(st7.St7SetKeepSelect(uID, 1), "Set KeepSelect = ON")
        
        # Variabile C per ricevere l'ID del piano creato
        plane_id_output = ct.c_long()
        
        # 4. Taglia lungo i piani YZ (costante X)
        #    Plane=2 per YZ
        print(f"  ...Inizio taglio lungo {len(nodes_for_x)} piani YZ...")
        for node_id_on_plane in nodes_for_x.values():
            ck(st7.St7DefinePlaneGlobalN(uID, node_id_on_plane, 2, ct.byref(plane_id_output)), 
               f"Define YZ plane at node {node_id_on_plane}")
            
            new_plane_id = plane_id_output.value
            ck(st7.St7CutElementsByPlane(uID, new_plane_id, edge_tol, -1, -1), 
               f"Cut at plane {new_plane_id} (Node {node_id_on_plane})")

        # 5. Taglia lungo i piani XZ (costante Y)
        #    Plane=3 per ZX (XZ)
        print(f"  ...Inizio taglio lungo {len(nodes_for_y)} piani XZ...")
        for node_id_on_plane in nodes_for_y.values():
            ck(st7.St7DefinePlaneGlobalN(uID, node_id_on_plane, 3, ct.byref(plane_id_output)), 
               f"Define XZ plane at node {node_id_on_plane}")

            new_plane_id = plane_id_output.value
            ck(st7.St7CutElementsByPlane(uID, new_plane_id, edge_tol, -1, -1), 
               f"Cut at plane {new_plane_id} (Node {node_id_on_plane})")
        
        # 6. Taglia lungo i piani XY (costante Z) <-- BLOCCO AGGIUNTO
        #    Plane=1 per XY
        print(f"  ...Inizio taglio lungo {len(nodes_for_z)} piani XY...")
        for node_id_on_plane in nodes_for_z.values():
            ck(st7.St7DefinePlaneGlobalN(uID, node_id_on_plane, 1, ct.byref(plane_id_output)), 
               f"Define XY plane at node {node_id_on_plane}")

            new_plane_id = plane_id_output.value
            ck(st7.St7CutElementsByPlane(uID, new_plane_id, edge_tol, -1, -1), 
               f"Cut at plane {new_plane_id} (Node {node_id_on_plane})")

        print("  ...Taglio completato.")

        # 7. Cleanup (Rinumerato)
        ck(st7.St7SetKeepSelect(uID, 0), "Set KeepSelect = OFF")
        _deselect_all_plates(uID) # Deseleziona tutto

        # --- Salva ---
        ck(st7.St7SaveFile(uID), "Salvataggio modello locale dopo il taglio")
        
    finally:
        try:
            ck(st7.St7CloseFile(uID), "Close local model")
        finally:
            st7.St7Release()
            
    print("Taglio (stitching) dei plate completato.")

