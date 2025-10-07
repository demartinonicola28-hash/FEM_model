# main.py
# Flusso: GUI -> crea file -> geometria -> proprietà -> freedom case -> load cases -> combinazioni+solver
#        -> import spettro -> spectral analysis
# Questo file orchestra l’intero workflow:
# - raccoglie input dall’utente
# - crea il modello Straus7 (.st7)
# - genera geometria e applica proprietà
# - definisce i vincoli (freedom case)
# - definisce e applica i carichi
# - crea combinazioni e lancia il solver per l’analisi lineare (LSA)
# - importa lo spettro nel Table Factor vs Frequency/Period
# - esegue l’analisi spettrale (solver SR, combinazione .SRA, solver statico)

import sys
import os
from pathlib import Path

# --- crea modello FEM ---
from create_file import create_file                 # crea un nuovo file .st7 e restituisce il path
from gui import run_gui                             # apre la GUI; ritorna dict parametri o None se annullata
from build_geometry import build_geometry           # costruisce nodi/elementi; ritorna info su path e nodi base
from apply_properties import apply_properties       # assegna materiale e sezioni; ritorna riepilogo proprietà
from freedom_case import apply_freedom_case         # definisce i gradi di libertà bloccati; ritorna dict con numero caso
from load_cases import apply_load_cases

# --- analisi statica SLU ---
from lsa_combine_and_solve import lsa_combine_and_solve  # crea combinazioni e lancia solver LSA

# --- analisi modale ---
import St7API as st7
from modal_analysis import run_modal_analysis, default_model_path

# --- analisi spettrale ---
from import_spettro import run as import_spettro_run        # importa TXT -> Table ttVsFrequency (asse Period, unità g)
from spectral_analysis import run as spectral_run           # solver SR -> combina .SRA -> solver Linear Static


# Assicura che percorsi relativi (es. spettro_ntc18.txt) puntino alla cartella del progetto
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # === Step 0: input GUI ====================================================
    gui_params = run_gui()  # None se annullata/chiusa
    if gui_params is None:
        print("Analisi annullata dall'utente.")
        sys.exit(0)

    # === Step 1: crea file ====================================================
    path = create_file("telaio_2D.st7")
    print("File generato:", path)

    # === Step 2: geometria ====================================================
    geom = build_geometry(
        path,
        h_story=gui_params["h_story"],
        span=gui_params["span"],
        n_floors=gui_params["n_floors"],
        offset=gui_params["offset"],
        prop_col=1,
        prop_beam=2
    )
    print("Geometria scritta su:", geom["model_path"])
    print("Nodi di base:", geom["base_nodes"])

    # === Step 3: proprietà ====================================================
    props = apply_properties(
        model_path=geom["model_path"],
        E=gui_params["E"],
        nu=gui_params["nu"],
        rho=gui_params["rho"],
        section_columns=gui_params["section_columns"],
        section_beams=gui_params["section_beams"],
        prop_col=1,
        prop_beam=2,
        library_dir_bsl=r"C:\ProgramData\Straus7 R31\Data"
    )
    print("Proprietà applicate:", props)

    # === Step 4: freedom case =================================================
    base_ids = [int(i) for i in geom["base_nodes"]]  # niente numpy.int32
    if not base_ids:
        raise ValueError("base_nodes è vuoto")

    fc = apply_freedom_case(
        path,
        base_nodes=base_ids,
        case_num=1,
        case_name="2D Beam XY"
    )
    print("Freedom case:", fc)

    # === Step 5: load cases ===================================================
    # Converti carichi superficiali [kN/m²] in carichi lineari [kN/m]
    span = gui_params["span"]
    q_G2     = gui_params["G2_int_kNm2"]  * span
    q_Q      = gui_params["Q_int_kNm2"]   * span
    q_Q_roof = gui_params["Q_roof_kNm2"]  * span

    lc = apply_load_cases(
        path,
        gravity=9.80665,
        q_G2=q_G2,            # kN/m
        q_Q=q_Q,              # kN/m
        q_Q_roof=q_Q_roof,    # kN/m
        prop_beam=2
    )
    print("Load cases:", lc)

    # === Step 6: combinazioni LSA e solver ====================================
    res = lsa_combine_and_solve(
        model_path=path,
        freedom_case=fc["freedom_case_num"],
        lc_G1=lc["load_cases"]["G1"],
        lc_G2=lc["load_cases"]["G2"],
        lc_Q=lc["load_cases"]["Q"],
        combos={
            "SLU":       {1: 1.35, 2: 1.35, 3: 1.50},
            "SISMA q=4": {1: 1.00, 2: 1.00, 3: 0.30},
        }
    )
    print("Combinazioni LSA create e solver avviato:", res)
    # chiude la finestra al termine:

    # === Step 7: Analisi Modale (Natural Frequency) ==========================

        # >>> uso il file appena creato invece di cercarne un altro in una cartella diversa
    base = os.path.dirname(os.path.abspath(path))                 # >>> cartella del modello corrente
    model = os.path.abspath(path)                                 # >>> uso il .st7 creato allo Step 1

    # individua automaticamente il .st7 presente nella cartella
    # model = find_model_in(base)                                 # (lasciato come riferimento, NON usato)  # >>>

    scratch = os.path.join(base, "_scratch")                      # cartella temporanea
    res = os.path.join(base, os.path.splitext(os.path.basename(model))[0] + ".nfa")
    log = os.path.join(base, os.path.splitext(os.path.basename(model))[0] + ".log")

    # esecuzione: modi = numero di piani utente (non altezza interpiano)
    n_modes = int(gui_params["n_floors"])                         # >>> allineo ai piani; prima era fisso = 2
    
    run_modal_analysis(
        model_path=model,
        scratch_path=scratch,
        n_modes=n_modes,                                          # >>> passo il numero di modi corretto
        res_path=res,
        log_path=log
    )

    print("Analisi modale completata e risultati salvati in:", res)

    # === Step 8: import spettro nel Table ====================================
    # Esegue: lettura TXT spettro -> tabella Factor vs Period (asse = Period, unità = acceleration response in g).
    print("Import spettro nel Table...")
    try:
        imp_res = import_spettro_run(model_path=path)
        print("Spettro importato:", imp_res)
    except Exception as e:
        print("Import spettro fallito:", e)
        sys.exit(1)

    # === Step 9: analisi spettrale ===========================================
    # Esegue: solver Spectral Response -> import .SRA in combinazione -> solver Linear Static finale.
    print("Avvio analisi spettrale...")
    try:
        sr_res = spectral_run(model_path=path)
        print("Analisi spettrale completata:", sr_res)
    except Exception as e:
        print("Analisi spettrale fallita:", e)
        sys.exit(1)

    # === Step 10: apertura automatica del file Straus7 ==========================
    print("Apertura automatica del file Straus7...")
    os.startfile(model)
