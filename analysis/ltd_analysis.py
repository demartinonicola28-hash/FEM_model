# ltd_analysis.py

# Import standard library
import ctypes as ct  # Tipi C (long, double, array)
import sys           # Per argv se lanciato diretto

# Import API Straus7
import St7API as st7  # Wrapper ufficiale

# ---- Utility ---------------------------------------------------------------

def ck(err, msg):                                   # Check errori API
    if err != 0:                                    # 0 = OK
        raise RuntimeError(f"{msg} (St7 err={err})")# Eccezione con codice

def _resolve_acc_table_id(uID, acc_table):          # Accetta ID int o nome str
    if isinstance(acc_table, int):                  # Se è già un ID
        return int(acc_table)                       # Ritorna l’ID
    TableID = ct.c_long(0)                          # Alloca out param
    name_b = str(acc_table).encode("utf-8")         # Nome in bytes
    # Nota: il wrapper vuole un int puro per TableType
    ck(st7.St7GetTableID(uID, int(st7.ttAccVsTime), name_b, ct.byref(TableID)),
       f"St7GetTableID('{acc_table}')")             # Lookup per nome
    return TableID.value                            # ID tabella

# ---- Configurazione e run LTD ---------------------------------------------

def run_LTD(uID, acc_table_name="acc1"):            # Funzione principale LTD
    # 0) Solver DLL (integrazione in-process)
    try:                                            # Alcuni wrapper non la espongono
        ck(st7.St7SetUseSolverDLL(st7.btTrue), "Use solver DLL")  # Preferisci DLL
    except Exception:                                # Se non disponibile
        pass                                         # Continua

    # 1) Metodo tempo: Newmark
    try:                                            # API dedicata
        ck(st7.St7SetLTAMethod(uID, st7.ltNewmark), "Set Newmark")  # Newmark
    except Exception:                                # Se assente
        pass                                         # Usa default

    # 2) Solution type: Full System
    set_full_ok = False                              # Flag locale
    try:                                            # API specifica
        ck(st7.St7SetLTASolutionType(uID, st7.stFullSystem), "Set FullSystem")  # FullSystem
        set_full_ok = True                           # Impostato
    except Exception:                                # Fallback
        try:
            ck(st7.St7SetSolverDefaultsLogical(uID, st7.spFullSystemTransient, st7.btTrue),
               "Force FullSystem via defaults")      # Forza FullSystem
            set_full_ok = True                       # Impostato
        except Exception:
            pass                                     # Continua
    if not set_full_ok:                              # Se non impostato
        print("ATTENZIONE: Full System non impostato esplicitamente.")  # Avviso

    # 3) Condizioni iniziali: none
    try:                                            # Opzionale
        ck(st7.St7SetTransientInitialConditionsType(uID, st7.icNone), "Set IC none")  # icNone
    except Exception:
        pass

    # 4) Base excitation = Acceleration
    ck(st7.St7SetTransientBaseExcitation(uID, st7.beAcceleration), "Base = acceleration")  # beAcceleration

    # 5) Base vector (1,0,0)
    base_vec = (ct.c_double * 3)(1.0, 0.0, 0.0)     # Array double[3]
    ck(st7.St7SetTransientBaseVector(uID, base_vec), "Base vector (1,0,0)")  # Direzione X

    # 6) Tabella Acceleration vs Time su X (ID o nome)
    acc_id = _resolve_acc_table_id(uID, acc_table_name)               # Risolvi ID
    tabs = (ct.c_long * 3)(acc_id, 0, 0)                              # X=tabella, Y/Z=none
    ck(st7.St7SetTransientBaseTables(uID, st7.beAcceleration, tabs),  # Associa tabelle
       "Bind base tables")

    # 7) Time stepping: uID, Row, NumSteps, SaveEvery, TimeStep
    ck(st7.St7SetTimeStepUnit(uID, st7.tuSec), "Time unit = sec")     # tuSec
    ck(st7.St7SetTimeStepData(uID, 1, 250, 1, ct.c_double(0.1)),
       "Time step data")

    # 8) Massa beam consistente
    try:                                                               # Opzione solver
        ck(st7.St7SetSolverDefaultsLogical(uID, st7.spLumpedMassBeam, st7.btFalse),
           "Beam mass consistent")                                     # No lumped
    except Exception:
        pass

    # 9) Avvio solver LTD (firma a 4 argomenti)
    ck(st7.St7RunSolver(uID, st7.stLinearTransientDynamic, st7.smBackgroundRun, st7.btTrue),
       "Run LTD")                                                      # Esegui e attendi

# ---- Esecuzione diretta opzionale -----------------------------------------

if __name__ == "__main__":                          # Se lanci questo file
    uid = int(sys.argv[1]) if len(sys.argv) > 1 else 1  # uID da argv o 1
    run_LTD(uid, acc_table_name="acc1")             # Esegui LTD
    print("LTD completata")                         # Log
