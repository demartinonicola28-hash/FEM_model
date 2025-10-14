# lsa_combine_and_solve.py
# Crea combinazioni LSA (lineari) con i tre load case primari G1, G2, Q
# e lancia il solver di Analisi Statica Lineare.
#
# API usate (manuale Straus7):
#   St7EnableLSALoadCase(long uID, long LoadCaseNum, long FreedomCaseNum)
#   St7GetNumLSACombinations(long uID, long* NumCases)
#   St7AddLSACombination(long uID, char* CaseName)
#   St7SetLSACombinationName(long uID, long CaseNum, char* CaseName)
#   St7SetLSACombinationFactor(long uID, long LType, long Pos, long LoadCaseNum,
#                              long FreedomCaseNum, double Factor)
#   St7RunSolver(long uID, long Solver, long Mode, long Wait)
#       -> Solver = solver_lin_static (dal tuo St7API.py)
#       -> Mode   = smBackgroundRun
#       -> Wait   = 1 (blocca finché termina)

import os
import ctypes as ct

os.add_dll_directory(r"C:\Program Files\Straus7 R31\Bin64")
from St7API import *  # Import all from St7API
try:
    from St7API import solver_lin_static  # Ensure solver_lin_static is imported
except ImportError:
    solver_lin_static = 1  # Fallback value if not defined in St7API

# ---------- utilità minime ----------
def _b(s: str) -> bytes:
    return s.encode("utf-8")

def check(rc: int):
    if rc != 0:
        buf = (ct.c_char * 256)()
        try:
            St7GetAPIErrorString(rc, buf, 256)
            msg = buf.value.decode("utf-8", errors="ignore")
        except Exception:
            msg = ""
        raise RuntimeError(f"St7 error {rc}: {msg}")

# ---------- core ----------
def lsa_combine_and_solve(model_path: str,
                          freedom_case: int = 1,
                          # numeri dei tre load case primari creati prima
                          lc_G1: int = 1,
                          lc_G2: int = 2,
                          lc_Q:  int = 3,
                          # definizione combinazioni: nome -> fattori {loadcase: coeff}
                          # esempio default sotto
                          combos: dict[str, dict[int, float]] | None = None,
                          uID: int = 1) -> dict:
    """
    model_path    : percorso file .st7
    freedom_case  : numero freedom case (da associare ai LC per l'LSA)
    lc_G1, lc_G2, lc_Q : ID dei load case primari G1, G2, Q
    combos        : mappa: NomeCombinazione -> {LoadCaseNum: coefficiente}
    """
    p = os.path.abspath(model_path)

    # default combinazioni se non passate
    if combos is None:
        combos = {
            "SLU":       {lc_G1: 1.35, lc_G2: 1.35, lc_Q: 1.50},
            "SLV q=4": {lc_G1: 1.00, lc_G2: 1.00, lc_Q: 0.30},
        }

    # NEW: azzera qualsiasi dialog di licenza PRIMA di St7Init (silenzioso)
    try:
        from St7API import lmWaitRetry
        check(St7SetLicenceOptions(lmWaitRetry, 1, 1))
    except Exception:
        pass

    # 1) apri modello
    check(St7Init())
    check(St7OpenFile(uID, _b(p), b""))

    # 2) abilita le coppie (LoadCase, FreedomCase) per la Linear Static Analysis
    #    (questo dice al solver quali LC/FC sono “attivabili”)
    for lc in (lc_G1, lc_G2, lc_Q):
        check(St7EnableLSALoadCase(uID, lc, freedom_case))

    # 3) crea combinazioni LSA utente e imposta i fattori
    #    LType: ltLoadCase = fattori riferiti a load case primari
    try:
        ltype_lc = ltLoadCase
    except NameError:
        ltype_lc = 0  # fallback comune nei wrapper

    # quante combinazioni esistono già
    ncomb = ct.c_long()
    check(St7GetNumLSACombinations(uID, ct.byref(ncomb)))
    start_count = ncomb.value

    created = {}
    # aggiungiamo in coda: la prima nuova avrà indice start_count+1
    for i, (name, factors) in enumerate(combos.items(), start=1):
        new_idx = start_count + i
        # crea combinazione
        check(St7AddLSACombination(uID, _b(name)))
        # (opzionale ma sicuro) rinomina esplicitamente
        check(St7SetLSACombinationName(uID, new_idx, _b(name)))
        # imposta i fattori per ogni LC coinvolto nella combo
        for lc, coeff in factors.items():
            check(St7SetLSACombinationFactor(uID, ltype_lc, new_idx, lc, freedom_case, float(coeff)))
        # (opzionale) assicura che la combinazione sia “enabled”
        try:
            check(St7SetLSACombinationState(uID, new_idx, True))
        except Exception:
            pass
        created[name] = new_idx

    # 4) lancia solver Linear Static
    #    Firma corretta: St7RunSolver(uID, Solver, Mode, Wait) -> TUTTI long
    #    - Solver: costante 'solver_lin_static' (dal tuo St7API.py)
    #    - Mode:   smBackgroundRun senza dialog
    #    - Wait:   1 (attendi termine), 0 (ritorna subito)
    try:
        solver_id = solver_lin_static   # definita nel wrapper
    except NameError:
        solver_id = 1                   # fallback ragionevole
    try:
        run_mode = smBackgroundRun      # niente dialog/progress
    except NameError:
        run_mode = 0

    # NEW: forza l'uso del solver in DLL per evitare l'eseguibile esterno con finestra
    try:
        check(St7SetUseSolverDLL(True))
    except Exception:
        pass

    # NEW: rete di sicurezza anti-GUI: sposta eventuale finestra solver fuori schermo
    try:
        check(St7SetSolverWindowPos(-32000, -32000, 1, 1))
    except Exception:
        pass

    check(St7RunSolver(uID, solver_id, run_mode, 1))

    # 5) salva e chiudi
    check(St7SaveFile(uID))
    check(St7CloseFile(uID))

    # NEW: ripristina posizione finestra solver per run futuri
    try:
        check(St7ClearSolverWindowPos())
    except Exception:
        pass

    return {
        "model_path": p,
        "freedom_case": freedom_case,
        "load_cases": {"G1": lc_G1, "G2": lc_G2, "Q": lc_Q},
        "combinations": created,  # nome -> indice combo
    }
