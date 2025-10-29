# local_model/rigid_links_columns.py
# Crea due rigid link cluster sulle colonne (piano XZ) e fornisce anche
# la funzione per creare il cluster YZ della trave orizzontale (stessa X del nodo 2).

import os, ctypes as ct                 # importa os e ctypes
import St7API as st7                    # importa le API Straus7

def ck(c, m=""):                        # wrapper per check errori API
    if c != 0:                          # se codice diverso da zero c'è errore
        buf = (ct.c_char * 512)()       # buffer per stringa errore
        try:
            st7.St7GetAPIErrorString(int(c), buf, 512)  # legge messaggio API
            err = buf.value.decode(errors="ignore")     # decodifica messaggio
        except Exception:
            err = "n/a"                 # fallback se fallisce
        raise RuntimeError(f"{m} (St7 err={c}: {err})") # solleva eccezione

def _get_total_nodes(uID) -> int:       # ritorna numero totale di nodi nel modello
    n = ct.c_long()                      # variabile long per output
    ck(st7.St7GetTotal(uID, st7.tyNODE, ct.byref(n)), "GetTotal tyNODE")  # API call
    return int(n.value)                  # cast e ritorno

def _xyz(uID, nid):                      # coord x,y,z di un nodo
    a = (ct.c_double * 3)()              # array 3 double
    ck(st7.St7GetNodeXYZ(uID, int(nid), a), f"GetNodeXYZ {nid}")  # API call
    return float(a[0]), float(a[1]), float(a[2])                   # tuple x,y,z

def _clear_sel(uID):                     # deseleziona tutti i nodi
    ck(st7.St7SetAllEntitySelectState(uID, st7.tyNODE, st7.btFalse), "Clear selection")  # API call

def _select(uID, nid, state=True):       # seleziona/deseleziona un nodo
    ck(st7.St7SetEntitySelectState(
        uID,                             # unit id
        st7.tyNODE,                      # tipo entità: nodo
        int(nid),                        # id nodo
        0,                               # EndEdgeFace = 0 per nodi
        st7.btTrue if state else st7.btFalse  # stato selezione
    ), f"Select node {nid}")             # messaggio errore

def _masters_same_y(uID, y_ref, exclude, tol):  # trova nodi con stessa Y (entro tolleranza)
    res = []                              # lista risultati
    tot = _get_total_nodes(uID)           # numero nodi
    for nid in range(1, tot + 1):         # loop su tutti i nodi
        if nid == exclude:                # salta lo slave
            continue
        try:
            _, yi, _ = _xyz(uID, nid)     # legge Y del nodo
        except Exception:
            continue                      # se nodo invalido, salta
        if abs(yi - y_ref) <= tol:        # confronto con tolleranza
            res.append(nid)               # aggiungi ai master
    return res                             # ritorna lista master

def create_column_clusters_XZ(model_path: str,   # crea due cluster XZ sulle colonne
                              node_ids: list[int],
                              tol: float = 1e-6) -> None:
    """
    node_ids: i tre 'intermediate_ids_by_branch' dello step 16.
    Crea due cluster rigidi nel piano XZ:
      - slave = nodo con Y massima, masters = tutti i nodi con stessa Y
      - slave = nodo con Y minima,  masters = tutti i nodi con stessa Y
    """
    if not node_ids or len(node_ids) < 3:  # controllo input
        raise ValueError("Servono 3 nodi intermedi")  # errore se meno di 3

    uID = 7                                # file unit id dedicato
    opened = False                         # flag apertura
    ck(st7.St7Init(), "Init API")          # inizializza API
    try:
        ck(st7.St7OpenFile(uID, os.fspath(model_path).encode("utf-8"), b""), "Open model")  # apre file
        opened = True                      # segna aperto

        coords = {nid: _xyz(uID, nid) for nid in node_ids}   # mappa id->(x,y,z)
        n_ymax = max(node_ids, key=lambda n: coords[n][1])   # trova nodo con Y max
        n_ymin = min(node_ids, key=lambda n: coords[n][1])   # trova nodo con Y min

        # XZ @ Y max -----------------------------------------------------------
        y_ref = coords[n_ymax][1]                            # Y di riferimento
        masters = _masters_same_y(uID, y_ref, n_ymax, tol)   # nodi con stessa Y
        if not masters:                                      # se vuoto, errore
            raise RuntimeError("Nessun master per cluster XZ (y max)")
        _clear_sel(uID)                                      # pulisci selezione
        for m in masters:
            _select(uID, m, True)                            # seleziona master
        ck(st7.St7CreateRigidLinkCluster(uID, 1, st7.rlPlaneZX, int(n_ymax)),  # crea cluster XZ
           "Create RL XZ y_max")

        # XZ @ Y min -----------------------------------------------------------
        y_ref = coords[n_ymin][1]                            # Y di riferimento
        masters = _masters_same_y(uID, y_ref, n_ymin, tol)   # nodi con stessa Y
        if not masters:                                      # se vuoto, errore
            raise RuntimeError("Nessun master per cluster XZ (y min)")
        _clear_sel(uID)                                      # pulisci selezione
        for m in masters:
            _select(uID, m, True)                            # seleziona master
        ck(st7.St7CreateRigidLinkCluster(uID, 1, st7.rlPlaneZX, int(n_ymin)),  # crea cluster XZ
           "Create RL XZ y_min")

        ck(st7.St7SaveFile(uID), "Save")                     # salva file
    finally:
        try:
            if opened:                                       # chiudi solo se aperto
                ck(st7.St7CloseFile(uID), "Close")           # chiude file
        finally:
            st7.St7Release()                                 # rilascia API


# --- Beam YZ cluster from "neighbors" ----------------------------------------

def _get_total_nodes(uID) -> int:
    n = ct.c_long()
    ck(st7.St7GetTotal(uID, st7.tyNODE, ct.byref(n)), "GetTotal tyNODE")
    return int(n.value)

def _xyz(uID, nid):
    a = (ct.c_double * 3)()
    ck(st7.St7GetNodeXYZ(uID, int(nid), a), f"GetNodeXYZ {nid}")
    return float(a[0]), float(a[1]), float(a[2])

def _clear_sel(uID):
    ck(st7.St7SetAllEntitySelectState(uID, st7.tyNODE, st7.btFalse), "Clear node selection")

def _select(uID, nid, state=True):
    ck(st7.St7SetEntitySelectState(uID, st7.tyNODE, int(nid), 0, st7.btTrue if state else st7.btFalse),
       f"Select node {nid}")

def get_beam_end_local_id_from_neighbors(out: dict, nodes_info: dict) -> int:
    """
    Restituisce l'ID locale del neighbor con X minima.
    Mapping coerente con create_st7_with_nodes: [ref] + neighbors.
    """
    nb = nodes_info["neighbors"]
    min_x_neighbor = min(nb, key=lambda n: float(n["xyz"][0]))
    idx_in_neighbors = nb.index(min_x_neighbor)  # 0..2
    return int(out["base_node_ids"][1 + idx_in_neighbors])

def create_beam_link_cluster_YZ(model_path: str, slave_node_id: int, tol: float = 1e-3) -> dict:
    """
    Crea un rigid link cluster nel piano YZ:
      - slave = slave_node_id (end trave locale)
      - masters = tutti i nodi con stessa X dello slave entro tol
    Ritorna {'slave': id, 'x_ref': x, 'masters': N}.
    """
    uID = 51
    opened = False
    ck(st7.St7Init(), "Init API")
    try:
        ck(st7.St7OpenFile(uID, os.fspath(model_path).encode("utf-8"), b""), f"Open {model_path}")
        opened = True

        x_ref, _, _ = _xyz(uID, slave_node_id)

        # trova masters con stessa X
        masters = []
        tot = _get_total_nodes(uID)
        for nid in range(1, tot + 1):
            if nid == slave_node_id:
                continue
            try:
                xi, _, _ = _xyz(uID, nid)
            except RuntimeError:
                continue
            if abs(xi - x_ref) <= tol:
                masters.append(nid)

        if not masters:
            raise RuntimeError("Nessun nodo con stessa X dello slave nel tol.")

        # selezione e creazione cluster
        _clear_sel(uID)
        for n in masters:
            _select(uID, n, True)

        ck(st7.St7CreateRigidLinkCluster(uID, 1, st7.rlPlaneYZ, int(slave_node_id)),
           "CreateRigidLinkCluster YZ (beam)")

        ck(st7.St7SaveFile(uID), "Save")
        return {"slave": int(slave_node_id), "x_ref": x_ref, "masters": len(masters)}
    finally:
        try:
            if opened:
                ck(st7.St7CloseFile(uID), "Close")
        finally:
            st7.St7Release()
