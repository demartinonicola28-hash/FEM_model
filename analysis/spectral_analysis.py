# spectral_analysis.py
# ============================================================
# SRA (CQC) in direzione X -> registra file .SRA -> Linear Static
# - Non ricalcola la modale
# - Non crea combinazioni
# - Usa la tabella spettro con ID = TABLE_ID
# - Impone run "silenzioso": preferisce background; chiude la GUI
# - Opzionale: imposta fattore 1.0 alla riga SR_X nelle Combined LSA
# ============================================================

import os
import ctypes as C
import St7API as st7

# ------------------------- CONFIG ----------------------------
MODEL_UID = 1         # ID modello Straus7 aperto via API
TABLE_ID  = 1         # ID tabella spettro già importata
BASE_NAME = b"SR_X"   # nome caso spettrale in X

# Imposta a un intero (es. 4) se vuoi forzare fattore 1.0
# sulla riga SR_X nelle Combined LSA (vedi tabella in GUI).
# Lascialo None se non vuoi toccare i fattori.
SR_PRIMARY_ROW = None  # es.: 4

# Alternativa: individua la riga per NOME, utile quando in GUI non vedi l'indice.
# Se SR_PRIMARY_ROW è None o <=0, lo script cercherà questa riga per nome.
SR_PRIMARY_ROW_NAME = b"SR_X"  # lascia b"SR_X" se la riga si chiama così

# Target fattori per combinazioni: chiave = substring nome combinazione (case-insensitive)
# Esempio richiesto: 1 sotto "SLV q=4" e 0 sotto "SLU".
TARGET_COMBO_MATCHES = {
    "SLV q=4": 1.0,
    "SLU": 0.0,
}

# In alternativa ai nomi, usa gli INDICI colonna delle combinazioni (1-based)
# Esempio coerente con lo screenshot: {1: 0.0, 2: 1.0}
COMBO_FACTORS_BY_INDEX = {
    1: 0.0,  # SLU
    2: 1.0,  # SLV q=4
}
# ------------------------------------------------------------


# --------------------- ERRORI / I/O -------------------------
def _err():
    """Testo ultimo errore Straus7."""
    buf = (C.c_char * 256)()
    code = st7.St7GetLastError()
    st7.St7GetAPIErrorString(code, buf, len(buf))
    return f"{code}: {buf.value.decode('ascii','ignore')}"


def _open(uID, path):
    """Init API e apertura file .st7."""
    e = st7.St7Init()
    if e:
        raise RuntimeError(f"St7Init failed: {e}")
    scratch = os.path.dirname(path) or "."
    # assicurati che la cartella scratch esista
    os.makedirs(scratch, exist_ok=True)
    e = st7.St7OpenFile(uID, path.encode("utf-8"), scratch.encode("utf-8"))
    if e:
        raise RuntimeError(f"St7OpenFile failed: {e} ({_err()})")


def _close(uID):
    """Salvataggio, chiusura e release API."""
    # ignora gli errori di salvataggio/chiusura per garantire release
    try:
        st7.St7SaveFile(uID)
    finally:
        try:
            st7.St7CloseFile(uID)
        finally:
            st7.St7Release()


# -------------------- ESECUZIONE SOLVER ---------------------
def _run(uID, solver_enum):
    """
    Esegue un solver evitando la finestra:
    - preferisce background (se disponibile)
    - impone chiusura automatica
    - tenta eventuali API di chiusura/occultamento
    """
    # run mode: background > normal
    run_mode = getattr(st7, "smBackgroundRun", None) or getattr(st7, "smNormalRun", None)
    if run_mode is None:
        raise RuntimeError("Run mode solver non disponibile nel wrapper.")

    # close mode: preferisci chiusura automatica esplicita
    close_mode = (
        getattr(st7, "smCloseRun", None)
        or getattr(st7, "smNormalCloseRun", None)
        or getattr(st7, "smClose", None)
        or 0
    )

    e = st7.St7RunSolver(uID, solver_enum, run_mode, close_mode)
    if e:
        raise RuntimeError(f"St7RunSolver({solver_enum}) failed: {e} ({_err()})")

    # nuove build: prova a chiudere/occultare eventuali GUI residue
    for fn_name in ("St7CloseSolverWindow", "St7HideSolverWindow", "St7CloseResultsWindow"):
        fn = getattr(st7, fn_name, None)
        if fn:
            try:
                fn(uID)
            except Exception:
                pass


# --------------------- SETUP SRA GLOBALE --------------------
def _setup_sra_global(uID):
    """BaseExcitation=ON, LoadExcitation=OFF, Tipo=Response, CQC ON, SRSS OFF, overwrite .SRA."""
    if st7.St7SetSRABaseExcitation(uID, True):
        raise RuntimeError(_err())
    if st7.St7SetSRALoadExcitation(uID, False):
        raise RuntimeError(_err())

    if hasattr(st7, "St7SetSRAType"):
        stResponse = getattr(st7, "stResponse", 0)
        if st7.St7SetSRAType(uID, stResponse):
            raise RuntimeError(_err())

    if hasattr(st7, "St7SetSRAResultCQC") and st7.St7SetSRAResultCQC(uID, True):
        raise RuntimeError(_err())
    if hasattr(st7, "St7SetSRAResultSRSS") and st7.St7SetSRAResultSRSS(uID, False):
        raise RuntimeError(_err())

    # assicurati di NON fare append: forza overwrite .SRA
    if hasattr(st7, "St7GetAppendSRA"):
        # se supportato, leggi stato corrente e cambia solo se necessario
        b = C.c_bool()
        if st7.St7GetAppendSRA(uID, C.byref(b)) == 0 and b.value:
            if st7.St7SetAppendSRA(uID, False):
                raise RuntimeError(_err())
    elif hasattr(st7, "St7SetAppendSRA"):
        if st7.St7SetAppendSRA(uID, False):
            raise RuntimeError(_err())


# ----------------- BASE CASE: "BASE ACCEL" -------------------
def _set_base_type_acc(uID, idx):
    """Imposta il tipo 'Base Acceleration' con fallback su alias interi."""
    for name in ("slBaseAcc", "slBaseAccel", "slBaseAcceleration", "sBaseAcc"):
        val = getattr(st7, name, None)
        if val is not None:
            if st7.St7SetSRABaseCaseType(uID, idx, val):
                raise RuntimeError(_err())
            return
    for guess in (2, 1, 0, 3):  # fallback enum numerico
        if st7.St7SetSRABaseCaseType(uID, idx, guess) == 0:
            return
    raise RuntimeError("Impossibile impostare 'Base Acceleration'.")


def _find_base_case_index_by_name(uID, name_bytes: bytes):
    """
    Cerca un caso base SRA per nome.
    Se l'API per leggere il nome non è disponibile, restituisce None.
    """
    get_num = getattr(st7, "St7GetNumSRABaseCases", None)
    get_name = getattr(st7, "St7GetSRABaseCaseName", None)
    if not get_num or not get_name:
        return None

    n = C.c_long(0)
    if get_num(uID, C.byref(n)):
        raise RuntimeError(_err())

    buf = (C.c_char * 256)()
    for i in range(1, n.value + 1):
        if get_name(uID, i, buf, len(buf)):
            raise RuntimeError(_err())
        if buf.value == name_bytes:
            return i
    return None


def _ensure_base_x(uID, table_id):
    """
    Garantisce esistenza del caso SR_X:
    - crea se assente, altrimenti riusa quello chiamato SR_X
    - assegna tabella spettro
    - imposta tipo Base Acceleration
    - direzione X = (1,0,0)
    """
    num = C.c_long(0)
    st7.St7GetNumSRABaseCases(uID, C.byref(num))

    # prova a trovare per nome se esiste
    idx = _find_base_case_index_by_name(uID, BASE_NAME)

    if idx is None:
        if num.value == 0:
            if st7.St7AddSRABaseCase(uID, BASE_NAME):
                raise RuntimeError(_err())
            st7.St7GetNumSRABaseCases(uID, C.byref(num))
            idx = num.value
        else:
            # se non trovato per nome, usa la prima riga disponibile
            idx = 1

    if st7.St7SetSRABaseCaseTable(uID, idx, table_id):
        raise RuntimeError(_err())

    _set_base_type_acc(uID, idx)

    vec = (C.c_double * 3)(1.0, 0.0, 0.0)  # X
    if st7.St7SetSRABaseCaseFactors(uID, idx, vec):
        raise RuntimeError(_err())

    # abilita il caso se l'API esiste
    if hasattr(st7, "St7EnableSRABaseCase") and st7.St7EnableSRABaseCase(uID, idx):
        raise RuntimeError(_err())

    return idx


# ------------- REGISTRAZIONE FILE .SRA -----------------------
def _set_lsa_sra_filename(uID, model_path: str):
    """
    Comunica alla Linear Static quale file .SRA usare.
    API: St7SetLSACombinationSRAName(uID, FileName)
    - qui si usa <basename del modello>.SRA nella stessa cartella
    """
    fn = getattr(st7, "St7SetLSACombinationSRAName", None)
    if fn is None:
        raise AttributeError("St7SetLSACombinationSRAName non disponibile nel wrapper.")

    base, _ = os.path.splitext(model_path)
    sra_path = base + ".SRA"

    e = fn(uID, sra_path.encode("utf-8"))
    if e:
        raise RuntimeError(f"SetLSACombinationSRAName failed: {e} ({_err()})")
    return sra_path


# ------ OPZIONALE: FISSARE FATTORE 1.0 SU SR_X NELLE LSA -----
def _set_factor_on_sr_primary_row(uID, sr_primary_row: int, factor: float = 1.0):
    """
    Imposta 'factor' sulla riga primaria 'sr_primary_row'
    per TUTTE le Combined LSA esistenti.
    Richiede API Combined LSA:
        - St7GetNumCombinedLSACombinations
        - St7SetCombinedLSACombinationFactor
    Nota: 'sr_primary_row' è l'indice di riga che vedi in GUI (es. 4).
    """
    get_num = getattr(st7, "St7GetNumCombinedLSACombinations", None)
    set_fac = getattr(st7, "St7SetCombinedLSACombinationFactor", None)
    if not get_num or not set_fac:
        # Wrapper senza API Combined LSA: esci silenziosamente
        return

    n = C.c_long(0)
    e = get_num(uID, C.byref(n))
    if e:
        raise RuntimeError(f"GetNumCombinedLSACombinations failed: {e} ({_err()})")

    for pos in range(1, n.value + 1):
        # Pos = indice combinazione (1=SLU, 2=SLV q=4, ...)
        e = set_fac(uID, pos, sr_primary_row, C.c_double(factor))
        if e:
            raise RuntimeError(
                f"SetCombinedLSACombinationFactor pos={pos} row={sr_primary_row} failed: {e} ({_err()})"
            )


def _find_lsa_row_index_by_name(uID, row_name_bytes: bytes):
    """
    Restituisce l'indice 1-based della riga Combined LSA col nome dato.
    Se l'API non è disponibile o non trova, restituisce None.
    """
    get_num_rows = getattr(st7, "St7GetNumCombinedLSARows", None)
    get_row_name = getattr(st7, "St7GetCombinedLSARowName", None)
    if not get_num_rows or not get_row_name:
        return None

    n = C.c_long(0)
    if get_num_rows(uID, C.byref(n)):
        raise RuntimeError(_err())

    buf = (C.c_char * 256)()
    for i in range(1, n.value + 1):
        if get_row_name(uID, i, buf, len(buf)):
            raise RuntimeError(_err())
        if buf.value == row_name_bytes:
            return i
    return None


def _set_factor_on_sr_row_by_combo_names(uID, sr_primary_row: int, targets: dict[str, float]):
    """
    Imposta il fattore in SR_PRIMARY_ROW solo per specifiche combinazioni
    identificate per *substring* nel nome combinazione.
    Esempio: {"SLV q=4": 1.0, "SLU": 0.0}
    Se non è possibile leggere i nomi, non fa nulla.
    """
    get_num = getattr(st7, "St7GetNumCombinedLSACombinations", None)
    get_name = (
        getattr(st7, "St7GetCombinedLSACombinationName", None)
        or getattr(st7, "St7GetCombinedLSACombinationTitle", None)
        or getattr(st7, "St7GetCombinedLSACombinationLabel", None)
    )
    set_fac = getattr(st7, "St7SetCombinedLSACombinationFactor", None)

    if not get_num or not get_name or not set_fac:
        return  # API non disponibile nel wrapper

    n = C.c_long(0)
    if get_num(uID, C.byref(n)):
        raise RuntimeError(_err())

    buf = (C.c_char * 256)()
    for pos in range(1, n.value + 1):
        if get_name(uID, pos, buf, len(buf)):
            raise RuntimeError(_err())
        name = buf.value.decode("utf-8", "ignore")
        # match case-insensitive per ciascun target
        for key, val in targets.items():
            if key.lower() in name.lower():
                if set_fac(uID, pos, sr_primary_row, C.c_double(val)):
                    raise RuntimeError(
                        f"SetCombinedLSACombinationFactor pos={pos} name='{name}' failed: {_err()}"
                    )
                break


def _set_factor_on_sr_row_by_combo_index(uID, sr_primary_row: int, targets: dict[int, float]):
    """
    Imposta il fattore sulla riga SR per INDICE combinazione 1-based.
    Usa quando i nomi non sono leggibili o non matchano.
    """
    get_num = getattr(st7, "St7GetNumCombinedLSACombinations", None)
    set_fac = getattr(st7, "St7SetCombinedLSACombinationFactor", None)
    if not get_num or not set_fac:
        return

    n = C.c_long(0)
    if get_num(uID, C.byref(n)):
        raise RuntimeError(_err())

    for pos, val in targets.items():
        if 1 <= int(pos) <= n.value:
            if set_fac(uID, int(pos), sr_primary_row, C.c_double(float(val))):
                raise RuntimeError(
                    f"SetCombinedLSACombinationFactor pos={pos} row={sr_primary_row} failed: {_err()}"
                )
# helper: mappa nomi combinazioni -> posizione (colonna)
def _get_combined_combo_names(uID):
    get_num = getattr(st7, "St7GetNumCombinedLSACombinations", None)
    get_name = (
        getattr(st7, "St7GetCombinedLSACombinationName", None)
        or getattr(st7, "St7GetCombinedLSACombinationTitle", None)
        or getattr(st7, "St7GetCombinedLSACombinationLabel", None)
    )
    if not get_num or not get_name:
        return {}
    n = C.c_long(0)
    if get_num(uID, C.byref(n)):
        raise RuntimeError(_err())
    out = {}
    buf = (C.c_char * 256)()
    for pos in range(1, n.value + 1):
        if get_name(uID, pos, buf, len(buf)):
            raise RuntimeError(_err())
        out[pos] = buf.value.decode("utf-8", "ignore")
    return out


# helper: setta fattori sulla riga del CASO SPETTRALE tramite CaseNum
# API manuale: St7SetCombinedLSACombinationFactor(uID, Pos, CaseNum, Factor)
#              St7GetCombinedLSACombinationFactor(uID, Pos, CaseNum, *Factor)

def _set_spectral_factor_by_pos(uID, spectral_case_num: int, pos_to_factor: dict[int, float]):
    """
    USER-GENERATED Combined LSA path.
    Usa St7SetCombinedLSACombinationFactor(Pos, CaseNum, Factor).
    """
    set_fac = getattr(st7, "St7SetCombinedLSACombinationFactor", None)
    get_fac = getattr(st7, "St7GetCombinedLSACombinationFactor", None)
    if not set_fac:
        return
    for pos, val in pos_to_factor.items():
        err = set_fac(uID, int(pos), int(spectral_case_num), C.c_double(float(val)))
        if err:
            raise RuntimeError(
                f"SetCombinedLSACombinationFactor pos={pos} case={spectral_case_num} failed: {err} ({_err()})"
            )
        if get_fac:
            chk = C.c_double(0.0)
            if get_fac(uID, int(pos), int(spectral_case_num), C.byref(chk)) == 0:
                if abs(chk.value - float(val)) > 1e-9:
                    raise RuntimeError(
                        f"Verify factor mismatch pos={pos} case={spectral_case_num}: {chk.value} != {val}"
                    )

# SOLVER-GENERATED LSA path.
# Usa St7SetLSACombinationFactor(LType=ltSpectralCase, Pos, LoadCaseNum=spectral_case_num,
# FreedomCaseNum=0, Factor)

def _set_spectral_factor_by_pos_SOLVER(uID, spectral_case_num: int, pos_to_factor: dict[int, float]):
    set_fac = getattr(st7, "St7SetLSACombinationFactor", None)
    get_fac = getattr(st7, "St7GetLSACombinationFactor", None)
    ltSpectralCase = getattr(st7, "ltSpectralCase", None)
    if ltSpectralCase is None:
        ltSpectralCase = 1  # fallback
    if not set_fac:
        return
    for pos, val in pos_to_factor.items():
        err = set_fac(uID, ltSpectralCase, int(pos), int(spectral_case_num), 0, C.c_double(float(val)))
        if err:
            raise RuntimeError(
                f"SetLSACombinationFactor pos={pos} case={spectral_case_num} failed: {err} ({_err()})"
            )
        if get_fac:
            chk = C.c_double(0.0)
            if get_fac(uID, ltSpectralCase, int(pos), int(spectral_case_num), 0, C.byref(chk)) == 0:
                if abs(chk.value - float(val)) > 1e-9:
                    raise RuntimeError(
                        f"Verify factor mismatch pos={pos} case={spectral_case_num}: {chk.value} != {val}"
                    )
# NOTA: la vecchia chiamata Combined diretta qui sotto è stata rimossa perché eseguita a import-time.
# Manteniamo solo la versione dentro le funzioni per evitare side effects.

def _apply_spectral_factors(uID, spectral_case_num: int):
    """
    Applica i fattori alla riga del caso spettrale SR_X usando CaseNum
    invece che l'indice riga. Prova Combined LSA, poi fallback Solver.
    """
    if not isinstance(spectral_case_num, int) or spectral_case_num <= 0:
        return

    pos_to_factor: dict[int, float] = {}

    # per nome combinazione
    if TARGET_COMBO_MATCHES:
        names = _get_combined_combo_names(uID)
        for pos, nm in names.items():
            for key, val in TARGET_COMBO_MATCHES.items():
                if key.lower() in nm.lower():
                    pos_to_factor[pos] = float(val)

    # per indice combinazione
    if 'COMBO_FACTORS_BY_INDEX' in globals() and COMBO_FACTORS_BY_INDEX:
        for pos, val in COMBO_FACTORS_BY_INDEX.items():
            pos_to_factor[int(pos)] = float(val)

    if not pos_to_factor:
        return

    # tenta Combined; se 120, usa Solver
    try:
        _set_spectral_factor_by_pos(uID, spectral_case_num, pos_to_factor)
    except RuntimeError as ex:
        msg = str(ex)
        if "120" in msg or "combination does not exist" in msg.lower():
            _set_spectral_factor_by_pos_SOLVER(uID, spectral_case_num, pos_to_factor)
        else:
            raise

# -------------------------- ENTRYPOINT -----------------------
def run(model_path: str):
    """
    Pipeline:
      1) Open
      2) Setup SRA globale
      3) Assicura SR_X (X, Base Acceleration, TABLE_ID)
      4) Solver: Spectral Response -> genera <model>.SRA
      5) Registra .SRA per LSA
      6) [Opz] imposta fattore 1.0 su riga primaria SR_X
      7) Solver: Linear Static (usa combinazioni già definite)
    """
    _open(MODEL_UID, model_path)
    try:
        _setup_sra_global(MODEL_UID)
        idx = _ensure_base_x(MODEL_UID, TABLE_ID)

        sr_enum = getattr(st7, "stSpectralResponse", None)
        if sr_enum is None:
            raise RuntimeError("Enum stSpectralResponse non trovato.")
        _run(MODEL_UID, sr_enum)

        sra_file = _set_lsa_sra_filename(MODEL_UID, model_path)

        # opzionale: imposta fattore 1.0 alla riga SR_X nelle Combined LSA
        # USA l'API corretta per Combined LSA: CaseNum = numero del caso PRIMARIO
        # qui è il numero del caso spettrale creato (idx)
        _apply_spectral_factors(MODEL_UID, idx)

        ls_enum = getattr(st7, "stLinearStatic", None)
        if ls_enum is None:
            raise RuntimeError("Enum stLinearStatic non trovato.")
        _run(MODEL_UID, ls_enum)

        return {
            "spectral_case": idx,
            "spectral_name": BASE_NAME.decode(),
            "table_id": TABLE_ID,
            "sra_file": sra_file,
            "method": "CQC",
            "factor_row": SR_PRIMARY_ROW if SR_PRIMARY_ROW else "unchanged",
            "note": "Linear Static su combinazioni già presenti."
        }
    finally:
        _close(MODEL_UID)
