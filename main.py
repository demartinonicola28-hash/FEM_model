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
import St7API as st7

# Ensure the parent directory of 'analysis' is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'model')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'analysis')))

DLL_DIR = r"C:\Program Files\Straus7 R31\Bin64"
if not os.path.isdir(DLL_DIR):
    raise RuntimeError(f"Percorso DLL non trovato: {DLL_DIR}")
os.add_dll_directory(DLL_DIR)

from pathlib import Path

from model.gui import run_gui
from model.create_file import create_file
from model.build_geometry import build_geometry
from model.apply_properties import apply_properties
from model.freedom_case import apply_freedom_case
from model.load_cases import apply_load_cases

from analysis.lsa_combine_and_solve import lsa_combine_and_solve
from analysis.modal_analysis import run_modal_analysis
from spettro_ntc18.spettro_ntc18 import run_spettro_ntc18_gui
from analysis.import_spettro import run as import_spettro_run
from analysis.spectral_analysis import run as spectral_run
from analysis.beam_result import max_check_value, list_result_cases
from analysis.import_accelerogram import run

# Assicura che percorsi relativi (es. spettro_ntc18.txt) puntino alla cartella del progetto
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # === Step 0: input GUI ====================================================
    gui_params = run_gui()  # None se annullata/chiusa
    if gui_params is None:
        print("Analisi annullata dall'utente.")
        sys.exit(0)

    # === Step 1: crea file ====================================================
    # crea un nuovo file .st7 e restituisce il path
    path = create_file("straus7_model/telaio_2D.st7")
    print("File generato:", path)

    # === Step 2: geometria ====================================================
    # costruisce nodi/elementi; ritorna info su path e nodi base
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
    # assegna materiale e sezioni; ritorna riepilogo proprietà
    props = apply_properties(
        model_path=geom["model_path"],
        steel_grade="S 355",
        fy=gui_params["fy"],    # MPa
        fu=gui_params["fu"],    # MPa
        gamma_M0=gui_params["gamma_M0"],
        E=gui_params["E"],      # MPa
        nu=gui_params["nu"],
        rho=gui_params["rho"],
        section_columns=gui_params["section_columns"],
        section_beams=gui_params["section_beams"],
        prop_col=1,
        prop_beam=2,
        library_dir_bsl=r"C:\ProgramData\Straus7 R31\Data"
    )
    print("Proprietà applicate:", props)

    # design yeld stress
    DEN = gui_params["fy"]/gui_params["gamma_M0"]    # MPa

    # === Step 4: freedom case =================================================
    # definisce i gradi di libertà bloccati; ritorna dict con numero caso
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
            "SLV q=4": {1: 1.00, 2: 1.00, 3: 0.30},
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

    # === Step 8: create and import spettro nel Table ====================================

    # 1) Calcolo ed export spettro NTC18 (GUI + salvataggio JPG/TXT)
    try:
        # cartella dove si trova questo script
        path_spettro = os.path.join("spettro_ntc18") # cartella dove salvare lo spettro

        # esegui GUI e salva in questa cartella
        res = run_spettro_ntc18_gui(output_dir=path_spettro, show_plot=True)

        print("Spettro NTC18 generato in:", path_spettro)
    except Exception as e:
        print("Errore generazione spettro NTC18:", e)
        sys.exit(1)


    # 2) Esegue: lettura TXT spettro -> tabella Factor vs Period (asse = Period, unità = acceleration response in g).
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

    #list_result_cases(path)  # stampa tutti i case: copia il nome esatto da qui

    try:
        sr_res = spectral_run(model_path=path)
        print("Analisi spettrale completata:", sr_res)
    except Exception as e:
        print("Analisi spettrale fallita:", e)
        sys.exit(1)

    # === Step 10: Verifica elastica EN 1993-1-1:2005 (6.1) =====================
    mx_slu, b_slu, pnum_slu, pname_slu = max_check_value(path, ["combination", "slu"], stations=100, den=DEN, print_table=True)
    mx_slv, b_slv, pnum_slv, pname_slv = max_check_value(path, ["combination", "slv q=4"], stations=100, den=DEN, print_table=True)

    print(f"\nη max SLU = {mx_slu:.3f}  | beam {b_slu}  | section “{pname_slu}”")
    print("SLU verificato" if mx_slu <= 1.0 else "SLU NON verificato")

    print(f"\nη max SLV = {mx_slv:.3f}  | beam {b_slv}  | section “{pname_slv}”")
    print("SLV verificato" if mx_slv <= 1.0 else "SLV NON verificato")

    # === Step 11: import accelerogramma ===========================================
    base = Path(__file__).parent
    model_dir = base / "straus7_model"
    acc_dir   = base / "accelerogram"

    # se sai il nome del file:
    model = model_dir / "Telaio_2D.st7"  # <-- metti il nome reale
    assert model.is_file(), f"Modello non trovato: {model}"
    ids = run(model_path=str(model), acc_dir=str(acc_dir), names=("acc1","acc2","acc3"), units="g")
    print(ids)

    # in alternativa, prendi il primo .st7 nella cartella:
    # candidates = sorted(model_dir.glob("*.st7"))
    # assert candidates, f"Nessun .st7 in {model_dir}"
    # ids = run(model_path=str(candidates[0]), acc_dir=str(acc_dir))

    # === Step 12: setup e solve ===============================================
    #run_LTD(uid, acc_table_name="acc1")    # SIAMO ARRIVATI QUI

    # === Step 13: apertura automatica del file Straus7 ==========================
    print("\nApertura automatica del file Straus7...")
    os.startfile(model)
