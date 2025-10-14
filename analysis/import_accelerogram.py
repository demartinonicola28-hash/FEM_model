"""Importa 3 accelerogrammi in Straus7 (LAYOUTS → Tables → Acceleration vs Time)."""  # doc del modulo
# Funzioni principali:
# - import_accelerograms(uID, files, names=None, units="g") → List[int]                # API con modello già aperto
# - run(model_path, acc_dir="accelerogram", names=("X","Y","Z"), units="g", uID=1)    # wrapper che apre/salva/chiude
# Requisiti:
# - St7API.py nel PYTHONPATH; per Python ≥3.8 indicare STRAUS7_DLL_DIR se serve        # caricamento DLL

from __future__ import annotations  # future typing per annotazioni più forti

import os                           # percorsi e filesystem
import ctypes                       # buffer C e chiamate API
from typing import Sequence, Tuple, List, Optional  # tipi utili

# --- caricamento St7API.dll per Python ≥3.8 se serve ---
_DLL_DIR = os.environ.get("STRAUS7_DLL_DIR")        # path opzionale alla DLL
if _DLL_DIR:                                        # se definita
    try:
        os.add_dll_directory(_DLL_DIR)  # type: ignore[attr-defined]  # aggiunge dir a PATH di caricamento DLL
    except Exception:
        pass                                          # ignora se non supportato (es. Python <3.8)

import St7API  # noqa: E402                           # import del wrapper ufficiale Straus7

# ================= Utilità errori =================
_DEF_STRLEN = getattr(St7API, "kMaxStrLen", 255)      # lunghezza buffer errori API (fallback 255)

def _raise_if_err(ierr: int, ctx: str = "") -> None:  # helper: solleva eccezione se codice errore ≠ 0
    if ierr:                                          # se c'è errore API
        buf = ctypes.create_string_buffer(_DEF_STRLEN)  # buffer per testo errore
        try:
            St7API.St7GetAPIErrorString(ierr, buf, len(buf))  # traduce codice in stringa
            msg = buf.value.decode("utf-8", "ignore")         # decodifica a str
        except Exception:
            msg = ""                                           # fallback vuoto
        raise RuntimeError(f"{ctx} St7API error {ierr}: {msg}")  # eccezione con contesto

# ================= Lettura file XY =================
def _read_xy(path: str) -> List[Tuple[float, float]]:  # legge due colonne t, a da TXT/CSV
    data: List[Tuple[float, float]] = []               # accumulatore righe valide
    with open(path, "r", encoding="utf-8", errors="ignore") as f:  # apertura tollerante
        for raw in f:                                  # scorre righe
            line = raw.strip()                         # trim spazi
            if not line or line.startswith("#") or line.startswith("%"):  # salta vuote/commenti
                continue
            line = line.replace(";", " ").replace(",", ".")  # normalizza separatori ; e decimali ,
            parts = [p for p in line.split() if p]           # split su spazi multipli
            if len(parts) < 2:                               # richiede almeno 2 colonne
                continue
            try:
                t = float(parts[0])                          # tempo
                a = float(parts[1])                          # accelerazione
            except ValueError:
                continue                                     # salta header non numerici
            data.append((t, a))                              # aggiunge coppia valida
    if not data:                                            # controllo dati
        raise ValueError(f"Nessun dato valido in: {path}")   # errore se vuoto
    data.sort(key=lambda x: x[0])                            # ordina per tempo
    cleaned: List[Tuple[float, float]] = []                  # lista senza duplicati su t
    last_t: Optional[float] = None                           # ultimo tempo visto
    for t, a in data:                                        # dedup su t identico
        if last_t is None or t != last_t:
            cleaned.append((t, a))
            last_t = t
    return cleaned                                           # ritorna lista ordinata e pulita

def _xy_to_ctypes(data: Sequence[Tuple[float, float]]):      # converte in buffer C interlacciato
    n = len(data)                                            # numero coppie XY
    arr = (ctypes.c_double * (2 * n))()                      # array C double[2*n]
    for i, (x, y) in enumerate(data):                        # riempie [x1,y1,x2,y2,...]
        arr[2 * i] = float(x)
        arr[2 * i + 1] = float(y)
    return arr, n                                            # ritorna buffer e numero righe

# ================= Gestione Tabelle =================
def _next_table_id(uID: int, table_type: int) -> int:        # calcola prossimo TableID libero
    num = ctypes.c_long()                                     # numero tabelle
    last = ctypes.c_long()                                    # ultimo ID
    _raise_if_err(                                            # chiama API conteggio
        St7API.St7GetNumTables(uID, table_type, ctypes.byref(num), ctypes.byref(last)),
        "St7GetNumTables",
    )
    return (last.value + 1) if last.value >= 1 else 1         # propone ID successivo o 1

def create_acc_vs_time_table(                                 # crea tabella Acc vs Time e restituisce ID
    uID: int,                                                 # uID del modello aperto
    name: str,                                                # nome tabella
    data: Sequence[Tuple[float, float]],                      # sequenza XY
    units: str = "g",                                         # "g" o "model"
) -> int:
    doubles, n = _xy_to_ctypes(data)                          # prepara buffer interlacciato
    table_type = St7API.ttAccVsTime                           # tipo tabella: Acceleration vs Time
    table_id = _next_table_id(uID, table_type)                # calcola nuovo ID

    _raise_if_err(                                            # crea tabella già popolata
        St7API.St7NewTableType(
            uID,                                              # modello
            table_type,                                       # tipo
            table_id,                                         # ID
            n,                                                # numero righe
            name.encode("mbcs", errors="replace"),            # nome in ANSI Windows (MBCS)
            doubles,                                          # buffer XY
        ),
        "St7NewTableType",
    )

    unit_type = (St7API.atModelUnits                        # seleziona unità accelerazione
                 if units.lower() in {"m/s/s", "model"} else St7API.atModelUnits)
    _raise_if_err(                                            # imposta unità per Acc vs Time
        St7API.St7SetAccVsTimeTableUnits(uID, table_id, unit_type),
        "St7SetAccVsTimeTableUnits",
    )

    return table_id                                           # ritorna ID creato

def import_accelerograms(                                     # crea 1 tabella per ciascun file
    uID: int,                                                 # uID del modello aperto
    files: Sequence[str],                                     # tre percorsi file
    names: Optional[Sequence[str]] = None,                    # nomi tabella opzionali
    units: str = "g",                                         # unità accelerazione
) -> List[int]:
    if len(files) != 3:                                       # richiede 3 file
        raise ValueError("Servono esattamente 3 file accelerogramma")
    if names is not None and len(names) != len(files):        # validazione nomi
        raise ValueError("`names` deve avere la stessa lunghezza di `files`")

    table_ids: List[int] = []                                 # risultati
    for i, fp in enumerate(files):                            # ciclo sui 3 file
        if not os.path.isfile(fp):                            # verifica esistenza file
            raise FileNotFoundError(f"File non trovato: {fp}")
        nm = names[i] if names else os.path.splitext(os.path.basename(fp))[0]  # nome tabella
        xy = _read_xy(fp)                                     # leggi dati XY
        tid = create_acc_vs_time_table(uID, nm, xy, units=units)  # crea tabella
        table_ids.append(tid)                                 # accoda ID
    return table_ids                                          # ritorna lista di ID

# ================= Wrapper: modello chiuso =================
def run(                                                      # apre modello, importa, salva, chiude
    model_path: str,                                          # percorso al .st7
    acc_dir: str = "accelerogram",                            # cartella dei TXT
    names: Optional[Sequence[str]] = ("X", "Y", "Z"),         # nomi tabelle
    units: str = "g",                                         # "g" o "model"
    uID: int = 1,                                             # ID modello da usare
) -> List[int]:
    model_path = os.path.abspath(model_path)                  # normalizza percorso modello
    if not os.path.isfile(model_path):                        # verifica esistenza modello
        raise FileNotFoundError(f"Modello non trovato: {model_path}")
    acc_dir = os.path.abspath(acc_dir)                        # normalizza cartella accelerogrammi

    files = [                                                 # costruisce 3 percorsi file
        os.path.join(acc_dir, "acc1.txt"),
        os.path.join(acc_dir, "acc2.txt"),
        os.path.join(acc_dir, "acc3.txt"),
    ]

    _raise_if_err(St7API.St7Init(), "St7Init")                # inizializza API
    try:
        scratch = os.path.dirname(model_path) or os.getcwd()  # cartella scratch
        _raise_if_err(                                        # apre il modello (codifica MBCS per Windows)
            St7API.St7OpenFile(
                uID,
                model_path.encode("mbcs", errors="replace"),
                scratch.encode("mbcs", errors="replace"),
            ),
            "St7OpenFile",
        )
        try:
            ids = import_accelerograms(uID, files, names=names, units=units)  # importa tabelle
            _raise_if_err(St7API.St7SaveFile(uID), "St7SaveFile")             # salva
            return ids                                                        # ritorna ID creati
        finally:
            St7API.St7CloseFile(uID)                         # chiude sempre il file
    finally:
        St7API.St7Release()                                  # rilascia sempre l’API

# ================= CLI opzionale =================
if __name__ == "__main__":                                    # esecuzione diretta da terminale
    import argparse                                           # parser argomenti

    p = argparse.ArgumentParser(description="Importa 3 accelerogrammi in Straus7")  # descrizione
    p.add_argument("files", nargs=3, help="file1 file2 file3")                      # 3 file opzionali per bypass
    p.add_argument("--model", required=True, help="Percorso al file .st7 da aprire")# modello obbligatorio
    p.add_argument("--scratch", default=os.getcwd(), help="Cartella scratch")       # cartella scratch
    p.add_argument("--units", choices=["g", "model"], default="g")                  # scelta unità
    args = p.parse_args()                                                           # parsing

    _raise_if_err(St7API.St7Init(), "St7Init")               # init API
    try:
        uID = 1                                              # usa uID=1
        # usa codifica MBCS per compatibilità percorsi Windows
        _raise_if_err(
            St7API.St7OpenFile(
                uID,
                os.path.abspath(args.model).encode("mbcs", errors="replace"),
                os.path.abspath(args.scratch).encode("mbcs", errors="replace"),
            ),
            "St7OpenFile",
        )
        try:
            files = [os.path.abspath(f) for f in args.files] # normalizza file passati a CLI
            ids = import_accelerograms(uID, files, units=args.units)  # importa
            print("Creati TableID:", ids)                    # output IDs su stdout
            _raise_if_err(St7API.St7SaveFile(uID), "St7SaveFile")     # salva
        finally:
            St7API.St7CloseFile(uID)                         # chiude
    finally:
        St7API.St7Release()                                  # release finale
