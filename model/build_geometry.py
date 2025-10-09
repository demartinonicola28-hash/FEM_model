# build_geometry.py
# Genera nodi ed elementi beam per un telaio 2D parametrico.
# Parametri:
#   - h_story  : altezza interpiano [m]
#   - span     : luce trave [m]
#   - n_floors : numero piani
#   - offset   : offset nodi da ogni giunto trave-colonna [m] su trave e su colonna
# Assegnazione proprietà:
#   - colonne -> property 1
#   - travi   -> property 2
#
# Requisiti:
#   - Il file .st7 esiste (creato prima con create_file.py) e le proprietà 1 e 2 sono definite altrove.

import os
import ctypes as ct

# Rende visibile la DLL Straus7 (Python 3.8+)
os.add_dll_directory(r"C:\Program Files\Straus7 R31\Bin64")
from St7API import *

# --- utility error handling ---
def api_err_str(code: int) -> str:
    buf = (ct.c_char * 256)()
    St7GetAPIErrorString(code, buf, 256)
    return buf.value.decode("utf-8", errors="ignore")

def check(rc: int):
    if rc != 0:
        raise RuntimeError(f"St7 error {rc}: {api_err_str(rc)}")

def c_dbl_array(n): return (ct.c_double * n)()

def build_geometry(filename: str,
                   h_story: float = 3.50,
                   span: float = 5.00,
                   n_floors: int = 2,
                   offset: float = 1.50,
                   prop_col: int = 1,
                   prop_beam: int = 2,
                   uID: int = 1):
    """
    Apre filename (.st7) già creato e imposta la geometria del telaio:
      - 2 colonne a x=0 e x=span, continue 0→H
      - travi a y = k*h_story per k=0..n_floors
      - nodi interni sulle travi: x = offset e x = span-offset
      - nodi sulle colonne: y = k*h_story ± offset per i piani interni
    Assegna proprietà:
      - colonne -> prop_col
      - travi   -> prop_beam
    """
    model_path = os.path.abspath(filename)

    # ---- apertura file Straus7 ----
    check(St7Init())
    scratch = b""  # oppure un path valido, es. os.path.dirname(model_path).encode("utf-8")
    check(St7OpenFile(uID, model_path.encode("utf-8"), scratch))

    # ---------- costruzione lista nodi ----------
    H = n_floors * h_story
    levels = [k*h_story for k in range(n_floors+1)]    # quote 0..H
    beam_levels = [k*h_story for k in range(1, n_floors+1)]  # SOLO piani: esclude 0

    # nodi su travi: giunti colonna + nodi offset su ogni piano
    beam_nodes = []
    for y in beam_levels:  # <-- non includere y=0
        xs = [0.0, span]
        if 0.0 < offset < span:
            xs += [offset, span - offset]
        xs = sorted(set(xs))
        for x in xs:
            beam_nodes.append((x, y, 0.0))

    # nodi su colonne: per ciascuna colonna inserisci livello, livelli ± offset e estremi
    col_nodes = []
    for x in (0.0, span):
        ys = [0.0, H]
        for k in range(1, n_floors):  # solo livelli interni
            yk = k*h_story
            ys.append(yk)  # nodo livello
            if yk - offset > 0.0:
                ys.append(yk - offset)
            if yk + offset < H:
                ys.append(yk + offset)
        ys = sorted(set(ys))
        for y in ys:
            col_nodes.append((x, y, 0.0))

    # unisci e rimuovi duplicati (arrotondamento per stabilità)
    all_nodes = []
    seen = set()
    for p in beam_nodes + col_nodes:
        key = (round(p[0], 9), round(p[1], 9), 0.0)
        if key not in seen:
            seen.add(key)
            all_nodes.append((key[0], key[1], 0.0))

    # --- scrittura nodi su modello ---
    def set_node(nid: int, xyz):
        arr = c_dbl_array(3); arr[0], arr[1], arr[2] = xyz
        check(St7SetNodeXYZ(uID, nid, arr))

    id_from_xy = {}
    next_id = 1
    for xyz in all_nodes:
        set_node(next_id, xyz)
        id_from_xy[(xyz[0], xyz[1])] = next_id
        next_id += 1

    # ---------- helper per elementi ----------
    def add_beam(eid: int, n1: int, n2: int, prop: int):
        # In Straus7 St7SetElementConnection richiede:
        # (uID, Entity, EntityNum, PropNum, Connection)
        # - PropNum è il numero di proprietà da assegnare all’elemento
        # - Connection è un array di long:
        #   [0] = numero di nodi
        #   [1..NumNodes] = ID nodi
        #
        # Quindi per un BEAM 2-nodi: conn[0]=2, conn[1]=n1, conn[2]=n2
        from St7API import kMaxElementNode  # costante dal wrapper
        conn = (ct.c_long * (kMaxElementNode + 1))()
        conn[0] = 2      # numero di nodi
        conn[1] = n1     # primo nodo
        conn[2] = n2     # secondo nodo
        check(St7SetElementConnection(uID, tyBEAM, eid, prop, conn))

    beams = []

    # --- travi per ogni livello: segmenti consecutivi lungo x ---
    for y in beam_levels:
        xs = [0.0, span]
        if 0.0 < offset < span:
            xs += [offset, span - offset]
        xs = sorted(set(xs))
        for a, b in zip(xs[:-1], xs[1:]):
            n1 = id_from_xy[(a, y)]
            n2 = id_from_xy[(b, y)]
            beams.append((n1, n2, prop_beam))  # proprietà 2 per travi

    # --- colonne: per x=0 e x=span, collega nodi adiacenti lungo y ---
    for x in (0.0, span):
        ys = [0.0, H]
        for k in range(1, n_floors):
            yk = k*h_story
            ys += [yk]
            if yk - offset > 0.0:
                ys += [yk - offset]
            if yk + offset < H:
                ys += [yk + offset]
        ys = sorted(set(ys))
        for a, b in zip(ys[:-1], ys[1:]):
            n1 = id_from_xy[(x, a)]
            n2 = id_from_xy[(x, b)]
            beams.append((n1, n2, prop_col))  # proprietà 1 per colonne

    # --- scrittura elementi sul modello ---
    eid = 1
    for n1, n2, prop in beams:
        add_beam(eid, n1, n2, prop)
        eid += 1

    # ---- nodi di base, salva e chiudi ----
    base_left  = id_from_xy[(0.0, 0.0)]
    base_right = id_from_xy[(span, 0.0)]

    check(St7SaveFile(uID))
    check(St7CloseFile(uID))

    return {"model_path": model_path, "base_nodes": [base_left, base_right]}

# esecuzione diretta per test rapido
if __name__ == "__main__":
    info = build_geometry("frame_parametrico.st7",
                          h_story=3.50, span=5.00,
                          n_floors=2, offset=1.50,
                          prop_col=1, prop_beam=2)
    print("Geometria scritta su:", info["model_path"], "base_nodes:", info["base_nodes"])
