# local_model/link_cluster.py
# Crea Rigid Link Clusters per collegare i nodi "slave" (estremità beam)
# ai nodi "master" (la sezione trasversale di piastre).

import os
import ctypes as ct

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
            # --- MODIFICA: Stampa l'errore API effettivo ---
            buf = ct.create_string_buffer(st7.kMaxStrLen)
            st7.St7GetAPIErrorString(result, buf, st7.kMaxStrLen)
            api_err_msg = buf.value.decode('utf-8','ignore')
            print(f"ERRORE API: {args} (codice={result}, msg='{api_err_msg}')")
            raise RuntimeError(f"Errore API: {args} (codice={result}, msg='{api_err_msg}')")
        pass

# --- Funzione Helper Aggiunta ---
def _get_total_nodes(uID: int) -> int:
    """Ritorna il numero totale di nodi nel modello."""
    tot = ct.c_long()
    ck(st7.St7GetTotal(uID, st7.tyNODE, ct.byref(tot)), "GetTotal tyNODE")
    return int(tot.value)
# ---------------------------------

def _get_master_nodes(node_data: dict) -> list[int]:
    """Estrae tutti gli ID dei nodi (flange + web) da un dizionario di sezione."""
    nodes = []
    # Nomi comuni per flange (trave o colonna)
    nodes.extend(node_data.get('flangia_sup', []))   # Trave flangia sup
    nodes.extend(node_data.get('flangia_inf', []))   # Trave flangia inf
    nodes.extend(node_data.get('flange_L', []))      # Colonna flangia L (generico)
    nodes.extend(node_data.get('flange_R', []))      # Colonna flangia R (generico)
    nodes.extend(node_data.get('flangia_sx', []))   # Colonna flangia Sinistra (dall'errore)
    nodes.extend(node_data.get('flangia_dx', []))   # Colonna flangia Destra (dall'errore)
    
    # Nome comune per anima
    nodes.extend(node_data.get('web', []))          # Anima (generico)
    nodes.extend(node_data.get('anima', []))        # Anima (dall'errore)
    
    if not nodes or len(nodes) < 6:
        print(f"ATTENZIONE: Trovati solo {len(nodes)} nodi master (attesi 6). Nodi: {nodes}")
        
    return list(set(nodes)) # Rimuovi duplicati se presenti

def _create_cluster(uID: int, slave_node: int, master_nodes: list[int], axis: int, link_type_name: str, total_nodes: int):
    """
    Funzione helper per creare un singolo cluster.
    Deseleziona tutti i nodi, poi seleziona SOLO i master e imposta lo slave.
    """
    print(f"  - Creazione cluster per {link_type_name} (Slave: {slave_node})...")
    
    # 1. Pulisci la selezione precedente
    print(f"    ...Deselezione di {total_nodes} nodi...")
    for n_id in range(1, total_nodes + 1):
        # St7SetEntitySelectState(uID, Entity, EntityNum, EndEdgeFace, Selected)
        # Entity = st7.tyNODE, EndEdgeFace = 0, Selected = 0 (False)
        ck(st7.St7SetEntitySelectState(uID, st7.tyNODE, n_id, 0, 0), f"Deselezione nodo {n_id}")
    

    # 2. Seleziona SOLO i nodi MASTER
    num_selected = 0
    for node in master_nodes:
        if node == slave_node: # Lo slave NON può essere uno dei master
            print(f"    ATTENZIONE: Il nodo slave {slave_node} è anche nella lista master. Saltato.")
            continue
            
        # Selected = 1 (True)
        ck(st7.St7SetEntitySelectState(uID, st7.tyNODE, node, 0, 1), f"Select master node {node}")
        num_selected += 1
            
    if num_selected != len(master_nodes):
         print(f"    ATTENZIONE: Selezionati {num_selected} nodi master per lo slave {slave_node} (attesi {len(master_nodes)}).")

    # 4. Crea il cluster
    # St7CreateRigidLinkCluster(uID, UCSId, Axis, NodeNum)
    # NodeNum è lo slave, la selezione contiene solo i master.
    
    # --- MODIFICA ERRORE 33 (InvalidUCSId) ---
    # L'ID '0' non è valido. Usiamo '1' per il sistema Globale.
    ck(st7.St7CreateRigidLinkCluster(
        uID,
        1, # UCSId (1 = Globale, 0 era l'errore)
        axis,
        slave_node
    ), f"Create cluster for {link_type_name}")
    # --- FINE MODIFICA ---
    
    print(f"    ...Cluster {link_type_name} creato.")


def create_rigid_link_clusters(model_path: str, intermediate_nodes: dict, plate_nodes_info: dict):
    """
    Funzione principale per creare i 3 link cluster (Trave, Colonna Inf, Colonna Sup).
    
    Args:
        model_path (str): Percorso a local_model.st7
        intermediate_nodes (dict): L'output 'out' di create_st7_with_nodes (Step 16)
                                   Contiene gli ID dei nodi intermedi.
        plate_nodes_info (dict): L'output 'res_nodes' di create_midplane_nodes (Step 20)
                                 Contiene gli ID dei 6 nodi plate per ogni sezione.
    """
    
    print(f"\nInizio creazione Link Clusters in: {os.path.basename(model_path)}")
    
    if not os.path.exists(model_path):
        print(f"ERRORE: File modello non trovato: {model_path}")
        return

    # 1. Estrai gli ID dei nodi SLAVE (i nodi intermedi)
    try:
        slave_beam = intermediate_nodes["intermediate_ids_by_branch"][0][0]
        slave_col_low = intermediate_nodes["intermediate_ids_by_branch"][1][0]
        slave_col_up = intermediate_nodes["intermediate_ids_by_branch"][2][0]
        
        print(f"Nodi Slave identificati: Trave={slave_beam}, ColInf={slave_col_low}, ColSup={slave_col_up}")
    except (KeyError, IndexError) as e:
        print(f"ERRORE: Impossibile trovare gli ID dei nodi intermedi (slave). Dati: {intermediate_nodes}")
        raise e

    # 2. Estrai gli ID dei nodi MASTER (i 6 nodi plate per ogni sezione)
    try:
        masters_beam = _get_master_nodes(plate_nodes_info['beam_nodes'])
        masters_col_low = _get_master_nodes(plate_nodes_info['col_inf_nodes_base'])
        masters_col_up = _get_master_nodes(plate_nodes_info['col_sup_nodes_base'])
        
        print(f"Nodi Master (Trave): {masters_beam}")
        print(f"Nodi Master (Col Inf): {masters_col_low}")
        print(f"Nodi Master (Col Sup): {masters_col_up}")
        
    except (KeyError, IndexError) as e:
        print(f"ERRORE: Impossibile trovare i nodi master (plate) usando gli ID slave. Dati: {plate_nodes_info}")
        raise e
        
    # 3. Ottieni le costanti API per i piani
    try:
        AXIS_BEAM = st7.rlPlaneYZ # Piano YZ per la trave
        AXIS_COL = st7.rlPlaneZX  # Piano XZ per le colonne
    except AttributeError:
        print("="*50)
        print("ERRORE CRITICO: Impossibile trovare le costanti 'st7.rlPlaneYZ' o 'st7.rlPlaneZX'.")
        print("                Assicurati che 'St7API as st7' sia importato correttamente.")
        print("="*50)
        raise
        
    # 4. Connetti e crea i clusters
    uID = 1
    ck(st7.St7Init(), "Init API per Link Clusters")
    try:
        ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), f"Open local model {model_path}")
        
        # Ottieni il numero totale di nodi UNA VOLTA
        total_nodes_in_model = _get_total_nodes(uID)
        
        # --- Crea Cluster Trave ---
        _create_cluster(uID, slave_beam, masters_beam, AXIS_BEAM, "Trave", total_nodes_in_model)
        
        # --- Crea Cluster Colonna Inferiore ---
        _create_cluster(uID, slave_col_low, masters_col_low, AXIS_COL, "Colonna Inf", total_nodes_in_model)

        # --- Crea Cluster Colonna Superiore ---
        _create_cluster(uID, slave_col_up, masters_col_up, AXIS_COL, "Colonna Sup", total_nodes_in_model)

        # --- Salva ---
        ck(st7.St7SaveFile(uID), "Salvataggio modello locale con Link Clusters")
        
    finally:
        try:
            ck(st7.St7CloseFile(uID), "Close local model")
        finally:
            st7.St7Release()
            
    print("Creazione Link Clusters completata.")

