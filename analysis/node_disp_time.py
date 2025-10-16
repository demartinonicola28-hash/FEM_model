# analysis/node_disp.py
# Trova il nodo trave-pilastro destro (X≈span, Y≈h_story) e
# esporta gli spostamenti nel tempo DX/DY/DZ per 3 nodi vicini dalla LTD.

import os                 # gestione percorsi/cartelle
import glob               # ricerca file per pattern (*.lta)
import math               # distanza euclidea
import ctypes as C        # tipi C per le API Straus7
import St7API as st7      # API Straus7 R3, usate sempre con namespace "st7"


# ------------------------- utilità API di base -------------------------

def _ck(err: int, msg: str) -> None:
    """Controllo errori API: solleva con ultimo errore Straus7."""
    if err != 0:
        last = st7.St7GetLastError()                  # ultimo codice errore registrato da Straus7
        raise RuntimeError(f"{msg} (err={err}, last={last})")

def _open(uID: int, path: str) -> None:
    """Apre il modello .st7 con l'unit ID dato."""
    _ck(st7.St7OpenFile(uID, path.encode("utf-8"), b""), "St7OpenFile")

def _close(uID: int) -> None:
    """Chiude il modello associato all'unit ID dato."""
    _ck(st7.St7CloseFile(uID), "St7CloseFile")

def _total_nodes(uID: int) -> int:
    """Ritorna il numero totale di nodi nel modello."""
    tot = C.c_long()                                   # variabile long C per output
    _ck(st7.St7GetTotal(uID, st7.tyNODE, C.byref(tot)), "St7GetTotal tyNODE")
    return tot.value

def _xyz(uID: int, node_num: int) -> tuple[float, float, float]:
    """Ritorna le coordinate (X,Y,Z) di un nodo."""
    arr = (C.c_double * 3)()                           # buffer C double[3]
    _ck(st7.St7GetNodeXYZ(uID, node_num, arr), f"St7GetNodeXYZ {node_num}")
    return arr[0], arr[1], arr[2]

def _dist3(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """Distanza euclidea 3D."""
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)


# ------------------------- ricerca nodi di interesse -------------------------

def find_node(model_path: str, span: float, h_story: float, offset: float, tol: float = 1e-6) -> dict:
    """
    Trova il nodo trave-pilastro destro del primo solaio:
      - condizione: X≈span e Y≈h_story, tie-break su X massimo
    Trova poi i 3 nodi più vicini a distanza≈offset.
    Ritorna: {"ref_node": {"id", "xyz"}, "neighbors": [{"id","dist","xyz"}×3]}.
    """
    _ck(st7.St7Init(), "St7Init")                      # inizializza la sessione API
    try:
        _open(1, model_path)                           # apre il modello sul file unit 1
        try:
            N = _total_nodes(1)                        # numero totale di nodi
            nodes: list[tuple[int, float, float, float]] = []  # (id, x, y, z)
            for n in range(1, N + 1):                  # Straus7 indicizza nodi da 1 a N
                try:
                    x, y, z = _xyz(1, n)               # coord nodo n
                    nodes.append((n, x, y, z))         # accumula
                except RuntimeError:
                    continue                           # salta nodi non risolti

            # filtra nodi alla quota Y≈h_story e X≈span
            cands = [t for t in nodes if abs(t[1] - span) <= tol and abs(t[2] - h_story) <= tol]
            if not cands:
                raise ValueError(f"Nessun nodo con X≈{span} e Y≈{h_story}. Aumenta tol.")

            # nodo di riferimento = con X massima tra i candidati
            ref_id, xr, yr, zr = max(cands, key=lambda t: t[1])

            # ricerca vicini a distanza ≈ offset con finestra relativa 0.1% o tol assoluto
            pr = (xr, yr, zr)                          # punto di riferimento
            win = max(tol, offset * 1e-3)              # tolleranza sulla distanza
            neigh: list[tuple[float, int, tuple[float, float, float]]] = []  # (dist, id, xyz)
            for n, x, y, z in nodes:
                if n == ref_id:
                    continue
                d = _dist3(pr, (x, y, z))
                if abs(d - offset) <= win:
                    neigh.append((d, n, (x, y, z)))

            # se meno di 3 nodi trovati all'offset, completa coi più vicini
            if len(neigh) < 3:
                ordered = sorted(
                    (( _dist3(pr, (x, y, z)), n, (x, y, z)) for n, x, y, z in nodes if n != ref_id),
                    key=lambda t: t[0]
                )
                seen = {n for _, n, _ in neigh}
                for d, n, p in ordered:
                    if n not in seen:
                        neigh.append((d, n, p))
                    if len(neigh) >= 3:
                        break

            neigh.sort(key=lambda t: t[0])             # ordina per distanza crescente
            sel = neigh[:3]                            # prendi i 3 nodi

            # stampa diagnostica essenziale
            print(f"Rif: Node {ref_id}  XYZ=({xr:.6g}, {yr:.6g}, {zr:.6g})")
            for i, (d, n, p) in enumerate(sel, 1):
                print(f"{i}: Node {n}  d={d:.6g}  XYZ=({p[0]:.6g},{p[1]:.6g},{p[2]:.6g})")

            # pacchetto risultati
            return {
                "ref_node": {"id": ref_id, "xyz": (xr, yr, zr)},
                "neighbors": [{"id": n, "dist": d, "xyz": p} for d, n, p in sel],
            }
        finally:
            _close(1)                                   # chiude il modello
    finally:
        _ck(st7.St7Release(), "St7Release")            # rilascia la sessione API


# ------------------------- utilità risultati LTD -------------------------

def _guess_lta_path(model_path: str) -> str:
    """
    Ricava il percorso del file risultati LTD:
    1) prova <model>.lta
    2) altrimenti il primo *.lta nella stessa cartella.
    """
    base = os.path.splitext(model_path)[0]             # parte senza estensione
    cand = base + ".lta"                               # tentativo stesso nome .lta
    if os.path.isfile(cand):
        return cand
    folder = os.path.dirname(model_path)               # cartella del modello
    lst = sorted(glob.glob(os.path.join(folder, "*.lta")))  # cerca qualsiasi .lta
    if lst:
        return lst[0]
    raise FileNotFoundError("File risultati LTD (.lta) non trovato")


# ------------------------- export spostamenti nel tempo -------------------------

def export_ltd_node_displacements(model_path: str, node_ids: list[int], out_dir: str) -> dict:
    """
    Estrae DX, DY, DZ nel tempo dai risultati LTD e salva 3 file TXT per nodo.
    Parametri:
      - model_path: percorso del .st7
      - node_ids: lista di ID nodi
      - out_dir: cartella di output per i TXT
    Ritorna: {node_id: {"DX": path, "DY": path, "DZ": path}}
    """
    os.makedirs(out_dir, exist_ok=True)                # crea la cartella se non esiste
    resfile = _guess_lta_path(model_path)              # trova il .lta associato

    uID = 1                                           # unit ID file Straus7
    _ck(st7.St7Init(), "Init")                        # inizializza API
    created: dict[int, dict[str, str]] = {}           # mappa output per nodo/direzione
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open .st7")  # apre il modello
        try:
            # apre file risultati LTD senza combinazioni
            numP = C.c_long()                          # numero di "primary cases" (steps temporali)
            numS = C.c_long()                          # non usato qui (secondary)
            _ck(
                st7.St7OpenResultFile(
                    uID,
                    resfile.encode("utf-8"),
                    b"",
                    st7.kNoCombinations,
                    C.byref(numP),
                    C.byref(numS)
                ),
                "Open .lta"
            )
            ncases = int(numP.value)                   # numero di step temporali

            # prepara i file di output per ogni nodo e per DX/DY/DZ
            fhandles: dict[tuple[int, int], any] = {}  # mappa (node_id, comp_idx) -> file
            for nid in node_ids:
                created[nid] = {}
                for comp, label in [(0, "DX"), (1, "DY"), (2, "DZ")]:  # 0..2 = traslazioni globali
                    fp = os.path.join(out_dir, f"node{nid}_{label}.txt")
                    fh = open(fp, "w", encoding="utf-8")
                    fh.write("t\tvalue\n")            # intestazione colonne
                    fhandles[(nid, comp)] = fh
                    created[nid][label] = fp

            # buffer per letture risultato
            vec6 = (C.c_double * 6)()                  # risultato nodale 6 componenti
            tval = C.c_double()                        # tempo del case

            # loop su tutti i cases temporali
            for case in range(1, ncases + 1):          # cases indicizzati da 1
                _ck(st7.St7GetResultCaseTime(uID, case, C.byref(tval)), "Get time")
                t = tval.value                         # tempo corrente [s]
                for nid in node_ids:
                    _ck(st7.St7GetNodeResult(uID, st7.rtNodeDisp, nid, case, vec6), "Get node disp")
                    # scrive DX/DY/DZ
                    for comp in (0, 1, 2):
                        fhandles[(nid, comp)].write(f"{t}\t{vec6[comp]}\n")

            # chiusura file TXT
            for fh in fhandles.values():
                fh.close()

            _ck(st7.St7CloseResultFile(uID), "Close results")  # chiude il .lta
            return created
        finally:
            _ck(st7.St7CloseFile(uID), "Close .st7")           # chiude il .st7
    finally:
        _ck(st7.St7Release(), "Release")                       # rilascia API
