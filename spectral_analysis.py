# spectral_analysis.py
# Configura ed esegue l’analisi Spectral Response (SRA) con metodo CQC.
# 1) Imposta SRA: BaseExcitation ON, LoadExcitation OFF, SpectrumType=stResponse
# 2) Imposta results: CQC=ON, SRSS=OFF
# 3) Crea 3 BaseCases (X,Y,Z), assegna tabella PERIODO→FATTORE (TABLE_ID), vettori e tipo = Acc alla base
# 4) Avvia solver SRA
# 5) Crea combinazione dai risultati .SRA e lancia Linear Static

import os
import ctypes as C
import St7API as st7

# === CONFIG ================================================================
MODEL_UID = 1
TABLE_ID  = 101                  # tabella importata (design_spectre)
COMB_NAME = b"SR_COMB"           # nome combinazione
DAMPING   = 0.05                 # se supportato da St7SetSRADamping
# ==========================================================================

# ---------------------- util ----------------------------------------------
def _err():
    buf = (C.c_char * 256)()
    code = st7.St7GetLastError()
    st7.St7GetAPIErrorString(code, buf, len(buf))
    return f"{code}: {buf.value.decode('ascii','ignore')}"

def _open(uID, path):
    e = st7.St7Init()
    if e: raise RuntimeError(f"St7Init failed: {e}")
    scratch = os.path.dirname(path) or "."
    e = st7.St7OpenFile(uID, path.encode("utf-8"), scratch.encode("utf-8"))
    if e: raise RuntimeError(f"St7OpenFile failed: {e} ({_err()})")

def _close(uID):
    st7.St7SaveFile(uID); st7.St7CloseFile(uID); st7.St7Release()

# ---------------------- SRA: opzioni globali ------------------------------
def _setup_sra_global(uID: int):
    # Abilita solo Base Excitation.
    e = st7.St7SetSRABaseExcitation(uID, True)
    if e: raise RuntimeError(f"St7SetSRABaseExcitation failed: {e} ({_err()})")
    e = st7.St7SetSRALoadExcitation(uID, False)
    if e: raise RuntimeError(f"St7SetSRALoadExcitation failed: {e} ({_err()})")

    # Tipo spettro: response (non PSD).
    # Manuale: St7SetSRAType(uID, stResponse|stPSD)
    if hasattr(st7, "St7SetSRAType"):
        stResponse = getattr(st7, "stResponse", 0)  # default 0 se non esposto
        e = st7.St7SetSRAType(uID, stResponse)
        if e: raise RuntimeError(f"St7SetSRAType failed: {e} ({_err()})")

    # Metodo risultati: CQC ON, SRSS OFF.
    if hasattr(st7, "St7SetSRAResultCQC"):
        e = st7.St7SetSRAResultCQC(uID, True)
        if e: raise RuntimeError(f"St7SetSRAResultCQC failed: {e} ({_err()})")
    if hasattr(st7, "St7SetSRAResultSRSS"):
        e = st7.St7SetSRAResultSRSS(uID, False)
        if e: raise RuntimeError(f"St7SetSRAResultSRSS failed: {e} ({_err()})")

    # Overwrite SRA file ad ogni run (niente append).
    if hasattr(st7, "St7SetAppendSRA"):
        e = st7.St7SetAppendSRA(uID, False)
        if e: raise RuntimeError(f"St7SetAppendSRA failed: {e} ({_err()})")

    # Smorzamento globale, se disponibile.
    if hasattr(st7, "St7SetSRADamping"):
        e = st7.St7SetSRADamping(uID, C.c_double(DAMPING))
        if e: raise RuntimeError(f"St7SetSRADamping failed: {e} ({_err()})")

# ---------------------- SRA: base cases X/Y/Z -----------------------------
def _add_base_case(uID: int, name_b: bytes, vec_xyz: tuple[float, float, float], table_id: int):
    # Crea caso base.
    e = st7.St7AddSRABaseCase(uID, name_b)
    if e: raise RuntimeError(f"St7AddSRABaseCase({name_b}) failed: {e} ({_err()})")

    # L’indice del caso base è l’ultimo (conta totale).
    num = C.c_long(0)
    e = st7.St7GetNumSRABaseCases(uID, C.byref(num))
    if e or num.value <= 0:
        raise RuntimeError(f"St7GetNumSRABaseCases failed: {e} ({_err()})")
    idx = num.value

    # Tabella spettro.
    e = st7.St7SetSRABaseCaseTable(uID, idx, table_id)
    if e: raise RuntimeError(f"St7SetSRABaseCaseTable failed: {e} ({_err()})")

    # Tipo di carico modale: accelerazione alla base.
    # Manuale: St7SetSRABaseCaseType(uID, idx, VectType) con VectType ∈ {slBaseAcc, slBaseVel, slBaseDisp}
    vect_type = getattr(st7, "slBaseAcc", getattr(st7, "sBaseAcc", 0))
    e = st7.St7SetSRABaseCaseType(uID, idx, vect_type)
    if e: raise RuntimeError(f"St7SetSRABaseCaseType failed: {e} ({_err()})")

    # Direzione globale.
    vec = (C.c_double * 3)(*vec_xyz)
    e = st7.St7SetSRABaseCaseFactors(uID, idx, vec)
    if e: raise RuntimeError(f"St7SetSRABaseCaseFactors failed: {e} ({_err()})")

    # Abilita caso.
    if hasattr(st7, "St7EnableSRABaseCase"):
        e = st7.St7EnableSRABaseCase(uID, idx)
        if e: raise RuntimeError(f"St7EnableSRABaseCase failed: {e} ({_err()})")

    return idx

# ---------------------- run solver SRA ------------------------------------
def _run_sr(uID: int):
    e = st7.St7RunSolver(uID, st7.stSpectralResponse, st7.smNone, st7.smNormalCloseRun)
    if e: raise RuntimeError(f"St7RunSolver(SR) failed: {e} ({_err()})")

# ---------------------- combinazione + LS ---------------------------------
def _combine_and_solve_ls(uID: int, comb_name: bytes):
    # Crea combinazione (ignora "già esiste").
    if hasattr(st7, "St7CreateCombinationCase"):
        e = st7.St7CreateCombinationCase(uID, comb_name)
        if e not in (0, 71):
            raise RuntimeError(f"St7CreateCombinationCase failed: {e} ({_err()})")
    else:
        raise AttributeError("St7CreateCombinationCase non presente nel wrapper.")

    # Aggiungi ogni BaseCase SRA alla combinazione con coefficiente 1.0.
    num = C.c_long(0)
    e = st7.St7GetNumSRABaseCases(uID, C.byref(num))
    if e: raise RuntimeError(f"St7GetNumSRABaseCases failed: {e} ({_err()})")

    add_fn = getattr(st7, "St7AddCaseToCombinationSRA",
                     getattr(st7, "St7AddSRACaseToCombination", None))
    if not add_fn:
        raise AttributeError("Funzione per aggiungere casi SRA alla combinazione non trovata.")

    for i in range(1, num.value + 1):
        e = add_fn(uID, comb_name, i, 1.0)
        if e: raise RuntimeError(f"Add SRA case {i} failed: {e} ({_err()})")

    # Risolve Linear Static sulla combinazione.
    e = st7.St7RunSolver(uID, st7.stLinearStatic, st7.smNone, st7.smNormalCloseRun)
    if e: raise RuntimeError(f"St7RunSolver(LS) failed: {e} ({_err()})")

# ------------------------------- ENTRYPOINT --------------------------------
def run(model_path: str):
    """
    Esegue tutta la pipeline SRA con CQC.
    Ritorna un riepilogo con #casi base e combinazione.
    """
    _open(MODEL_UID, model_path)
    try:
        _setup_sra_global(MODEL_UID)
        idxX = _add_base_case(MODEL_UID, b"SR_X", (1.0, 0.0, 0.0), TABLE_ID)
        idxY = _add_base_case(MODEL_UID, b"SR_Y", (0.0, 1.0, 0.0), TABLE_ID)
        idxZ = _add_base_case(MODEL_UID, b"SR_Z", (0.0, 0.0, 1.0), TABLE_ID)
        _run_sr(MODEL_UID)
        _combine_and_solve_ls(MODEL_UID, COMB_NAME)
        return {"base_cases": [idxX, idxY, idxZ],
                "combination": COMB_NAME.decode("ascii", "ignore"),
                "table_id": TABLE_ID,
                "method": "CQC"}
    finally:
        _close(MODEL_UID)
