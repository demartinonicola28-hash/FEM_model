# ltd_analysis.py
# Setup: base acceleration con fattore (1,0,0), tabella Acceleration vs Time "acc1"
# Time stepping: 250 passi, dt=0.1, salva ogni 50
# Mass Matrix: Beam -> consistent (no lumped)
# Avvio solver: Linear Transient Dynamic

import ctypes as ct
import os
import sys

# Usa il wrapper ufficiale: contiene funzioni e costanti (beAcceleration, ttAccVsTime, tuSec, spLumpedMassBeam, stLinearTransientDynamic, ecc.)
# Vedi manuale "Using the Straus7 API with Python".
import St7API as st7  # assicurati che St7API.py sia nel PYTHONPATH

def ck(err, msg):
    if err != 0:
        raise RuntimeError(f"{msg} (St7 err={err})")

def get_table_id_by_name(uID, table_type, name: str) -> int:
    """Ritorna l'ID della tabella con nome 'name' del tipo 'table_type'.
       Se non esiste, solleva errore."""
    # API: St7GetTableID(uID, TableType, Name, TableID)
    TableID = ct.c_long(0)
    ck(st7.St7GetTableID(uID, table_type, name.encode("utf-8"), ct.byref(TableID)),
       f"St7GetTableID({name})")
    return TableID.value

def run_LTD(uID: int, acc_table_name: str = "acc1"):
    # 1) Base excitation = Acceleration
    ck(st7.St7SetTransientBaseExcitation(uID, st7.beAcceleration), "Set base excitation")

    # 2) Base vector factor (X,Y,Z) = (1,0,0)
    vec3 = (ct.c_double * 3)(1.0, 0.0, 0.0)
    ck(st7.St7SetTransientBaseVector(uID, vec3), "Set base vector")

    # 3) Associa tabella Acceleration vs Time = acc1
    acc_table_id = get_table_id_by_name(uID, st7.ttAccVsTime, acc_table_name)
    tab_ids = (ct.c_long * 3)(acc_table_id, 0, 0)  # X usa acc1, Y/Z none
    ck(st7.St7SetTransientBaseTables(uID, st7.beAcceleration, tab_ids), "Set base tables")

    # 4) Time stepping: unità, passi, dt, save every
    ck(st7.St7SetTimeStepUnit(uID, st7.tuSec), "Set time unit to seconds")
    ck(st7.St7SetTimeStepData(uID, 1, 250, 50, ct.c_double(0.1)), "Set time step data")

    # 5) Parameters → Elements → Mass Matrix → Beam mass → consistent
    # Imposta opzione solver: disattiva massa "lumped" per i beam
    ck(st7.St7SetSolverDefaultsLogical(uID, st7.spLumpedMassBeam, st7.btFalse), "Set consistent beam mass")

    # 6) Avvio solver: Linear Transient Dynamic
    ck(st7.St7RunSolver(uID, st7.stLinearTransientDynamic), "Run Linear Transient Dynamic")

if __name__ == "__main__":
    # uID del modello già aperto oppure apri un file e ottieni uID.
    # Qui assumiamo che il modello sia già aperto e che uID=1 sia valido nel tuo processo.
    uid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_LTD(uid, acc_table_name="acc1")
    print("LTD completata")
