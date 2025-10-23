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
import os, glob
import ctypes as ct

# Ensure the parent directory of 'analysis' is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'model')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'analysis')))

DLL_DIR = r"C:\Program Files\Straus7 R31\Bin64"
if not os.path.isdir(DLL_DIR):
    raise RuntimeError(f"Percorso DLL non trovato: {DLL_DIR}")
os.add_dll_directory(DLL_DIR)
import St7API as st7


from pathlib import Path

from global_model.gui import run_gui
from global_model.create_file import create_file
from global_model.build_geometry import build_geometry
from global_model.apply_properties import apply_properties
from global_model.freedom_case import apply_freedom_case
from global_model.load_cases import apply_load_cases

from analysis.lsa_combine_and_solve import lsa_combine_and_solve
from analysis.modal_analysis import run_modal_analysis, get_modal_freqs_periods
from spettro_ntc18.spettro_ntc18 import run_spettro_ntc18_gui
from analysis.import_spettro import run as import_spettro_run
from analysis.spectral_analysis import run as spectral_run
from analysis.beam_result import max_check_value, list_result_cases
from analysis.import_accelerogram import run
from analysis.ltd_analysis import run_LTD, ck
from analysis.node_disp_time import find_node, export_ltd_node_displacements

from local_model.create_file import create_st7_with_nodes
from local_model.freedom_cases import create_unit_disp_freedom_cases
from local_model.section_data import export_section_data
from local_model.plate_properties import create_plate_properties, ask_panel_gusset_thicknesses
from local_model.plate_geometry import create_midplane_nodes_for_members, create_plates_for_joint


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
    path = create_file("straus7_model/global/telaio_2D.st7")
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

    print("Analisi modale completata")

    # Frequenze modali + Rayleigh (unica sessione API)
    ck(st7.St7Init(), "Init API")
    try:
        ck(st7.St7OpenFile(1, model.encode("utf-8"), b""), "Open model")
        try:
            # leggi e stampa modi
            modes = get_modal_freqs_periods(1, res)
            for k, f, T in modes:
                print(f"Mode {k:>2}   freq {f:.6g} Hz   period {k:>2} {T:.6g} s")

            # Rayleigh F1=min, F2=max, display idem, R1=R2=5%
            freqs = [f for _, f, _ in modes]
            fmin, fmax = min(freqs), max(freqs)

            arr = (ct.c_double * 6)()
            arr[st7.ipRayleighF1]        = fmin
            arr[st7.ipRayleighF2]        = fmax
            arr[st7.ipRayleighR1]        = 0.05
            arr[st7.ipRayleighR2]        = 0.05
            arr[st7.ipRayleighDisplayF1] = fmin
            arr[st7.ipRayleighDisplayF2] = fmax

            ck(st7.St7SetDampingType(1, st7.dtRayleighDamping), "Set damping type")
            ck(st7.St7SetRayleighFactors(1, st7.rmSetFrequencies, arr), "Set Rayleigh factors")
            ck(st7.St7SaveFile(1), "Save model with Rayleigh")
        finally:
            ck(st7.St7CloseFile(1), "Close model")
    finally:
        st7.St7Release()

    # === Step 8: create and import spettro nel Table ====================================

    # 1) Calcolo ed export spettro NTC18 (GUI + salvataggio JPG/TXT)
    try:
        # cartella dove si trova questo script
        path_spettro = os.path.join("spettro_ntc18") # cartella dove salvare lo spettro

        # esegui GUI e salva in questa cartella
        res = run_spettro_ntc18_gui(output_dir=path_spettro, show_plot=True)

        print("\nSpettro NTC18 generato in:", path_spettro)
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
    model = model_dir / "global/Telaio_2D.st7"  # <-- metti il nome reale
    assert model.is_file(), f"Modello non trovato: {model}"
    ids = run(model_path=str(model), acc_dir=str(acc_dir), names=("acc1","acc2","acc3"), units="g")
    print("Accelerogrammi importati, Table IDs:", ids, "\n") 

    # === Step 12: Linear Transient Dynamic (Full System) =======================
    print("Avvio Linear Transient Dynamic...")                                   # Log
    uID = 1                                                               # ID modello

    ck(st7.St7Init(), "Init API")                                         # Inizializza API
    try:
        ck(st7.St7OpenFile(uID, str(model).encode("utf-8"), b""), "Open") # Apre il .st7 creato
        # Usa l’ID tabella importato allo Step 11 se disponibile
        acc_arg = int(ids[0]) if ('ids' in globals() and ids) else "acc1" # ID oppure nome
        run_LTD(uID, acc_table_name=acc_arg)                               # Lancia LTD
        print("LTD completata.")                                          # Log
    finally:
        try:
            ck(st7.St7CloseFile(uID), "Close")                            # Chiudi
        finally:
            st7.St7Release()                                              # Rilascia

    # === Step 13: trova nodo trave-pilastro destro e 3 nodi offset ============
    print("\nRicerca nodi trave-pilastro destro...")
    try:
        # individua il nodo con X≈span e Y≈h_story e i tre nodi offset vicini
        nodes_info = find_node(
            model_path=str(model),
            span=gui_params["span"],
            h_story=gui_params["h_story"],
            offset=gui_params["offset"],
        )
        ref_id = nodes_info["ref_node"]["id"]
        neigh_ids = [n["id"] for n in nodes_info["neighbors"]]
        print(f"Nodo trave-pilastro destro: {ref_id}")
        print("Nodi offset vicini:", neigh_ids, "\n")
    except Exception as e:
        print("Errore ricerca nodi:", e)
        nodes_info = None

    # === Step 14: esporta spostamenti nel tempo (solo nodi offset) ===========
    try:
        if not nodes_info:
            raise RuntimeError("Nodi non trovati, impossibile esportare spostamenti.")

        # usa solo i nodi offset, escludendo il nodo trave-pilastro
        node_ids = [n["id"] for n in nodes_info["neighbors"]]

        # cartella di output: disp_time
        out_dir = os.path.join(os.path.dirname(str(model)), "..", "disp_time")

        # elimina eventuali file .txt già presenti nella cartella
        old_txt = glob.glob(os.path.join(out_dir, "*.txt"))
        if old_txt:
            print(f"\nPulizia cartella: {out_dir}")
            for f in old_txt:
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"  Errore eliminazione {f}: {e}")

        # esporta DX/DY/DZ nel tempo per i nodi offset dai risultati LTD (.LTA)
        paths_by_node = export_ltd_node_displacements(
            model_path=str(model),
            node_ids=node_ids,
            out_dir=out_dir
        )

        print("\nSpostamenti nel tempo esportati (solo nodi offset):")
        for nid, dirs in paths_by_node.items():
            print(f" Nodo {nid}:")
            for comp, fp in dirs.items():
                print(f"   {comp}: {fp}")
    except Exception as e:
        print("Errore esportazione spostamenti:", e)

    # === Step 15: apertura automatica del file Straus7 global model ==========================
    print("\nApertura automatica del file Straus7...")
    os.startfile(model)

    # === Step 16: crea modello locale con nodi e beam =====================
    try:
        # 4 nodi: centro + 3 offset
        node_list = [nodes_info["ref_node"]] + nodes_info["neighbors"]

        new_nodes = [{"id": n.get("id"), "xyz": n["xyz"]} for n in node_list]

        new_model_path = os.path.join(
            os.path.dirname(os.path.dirname(str(model))), "local","local_model.st7")    # risale da "global" a "straus7_model"

        # n_intermediate = quanti nodi fra centro e ciascun periferico
        out = create_st7_with_nodes(
            model_path=new_model_path,
            nodes=new_nodes,
            keep_ids=False,       # numerazione 1..N
            center_index=0,       # il primo è il nodo centrale
            n_intermediate=1      # esempio: 3 nodi intermedi per raggio
        )

        print("Creati nodi base:", out["base_node_ids"])
        print("Intermedi per branch:")
        for i, lst in enumerate(out["intermediate_ids_by_branch"], 1):
            print(f"  Branch {i}: {lst}")
        print(f"Nuovo modello: {new_model_path}")
    except Exception as e:
        print("Errore creazione modello locale:", e)

    # === Step 17: freedom cases =====================
    # ids dei 3 nodi esterni dal risultato di create_st7_with_nodes (step 16)
    
    outer_nodes = [int(n) for n in out["base_node_ids"][1:]]  # tutti tranne il primo
    fc_map = create_unit_disp_freedom_cases(
        model_path=new_model_path,
        outer_node_ids=outer_nodes,
        delete_default=True
    )
    print("Freedom cases creati:", fc_map)
    
    # === Step 18: proprietà BEAM nel modello locale (uguali al global) =====================
    # riuso della funzione già importata: from global_model.apply_properties import apply_properties
    props_local = apply_properties(
        model_path=new_model_path,                      # .st7 locale appena creato
        steel_grade="S 355",
        fy=gui_params["fy"],
        fu=gui_params["fu"],
        gamma_M0=gui_params["gamma_M0"],
        E=gui_params["E"],
        nu=gui_params["nu"],
        rho=gui_params["rho"],
        section_columns=gui_params["section_columns"],  # stessa sezione colonne
        section_beams=gui_params["section_beams"],      # stessa sezione travi
        prop_col=1,                                     # ID proprietà colonne nel locale
        prop_beam=2,                                    # ID proprietà travi nel locale
        library_dir_bsl=r"C:\ProgramData\Straus7 R31\Data"
    )
    print("Proprietà BEAM create nel modello locale:", props_local)

    # === Step 18: export section data ==========================
    sec_out = export_section_data(model_path=path, only_props=[1,2])  # colonne e travi
    sec = sec_out["data"]                                             # <-- riuso sotto
    print("Section data:", sec_out["csv"], "|", sec_out["json"])

    # === Step 19: plate_properties + GUI ========================================
    # quote sezioni dal global (1=colonna, 2=trave)
    sec = export_section_data(model_path=path, only_props=[1,2])["data"]

    # Dati Sezione Trave (Prop 2)
    s_beam = sec[2] 
    beam_dims = {
        # Fallback: nome generico -> nome BSL I-Section (es. D3)
        "D":   s_beam.get("D",   s_beam.get("D3")),
        "B1":  s_beam.get("B1",  s_beam.get("D1", s_beam.get("B"))),
        "B2":  s_beam.get("B2",  s_beam.get("D2", s_beam.get("B"))),
        "tw":  s_beam.get("tw",  s_beam.get("T3")),                        # T3 = spessore anima
        "tf2": s_beam.get("tf2", s_beam.get("T1", s_beam.get("tf"))), # T1 = flangia sup
        "tf1": s_beam.get("tf1", s_beam.get("T2", s_beam.get("tf"))), # T2 = flangia inf
    }
    
    # Dati Sezione Colonna (Prop 1)
    s_col = sec[1]
    col_dims = {
        "D":   s_col.get("D",   s_col.get("D3")),
        "B1":  s_col.get("B1",  s_col.get("D1", s_col.get("B"))),
        "B2":  s_col.get("B2",  s_col.get("D2", s_col.get("B"))),
        "tw":  s_col.get("tw",  s_col.get("T3")),
        "tf2": s_col.get("tf2", s_col.get("T1", s_col.get("tf"))),
        "tf1": s_col.get("tf1", s_col.get("T2", s_col.get("tf"))),
    }
    # GUI: mostra quote e chiede spessori extra (pannello modale, fazzoletti)
    extra = ask_panel_gusset_thicknesses(beam_dims, col_dims)

    # spessori base per creare le plate properties
    # (Questa logica ora è corretta perché beam_dims/col_dims sono corretti)
    beam_thk = {"tw": beam_dims["tw"], "tf1": beam_dims["tf1"], "tf2": beam_dims["tf2"]}
    col_thk  = {"tw": col_dims["tw"],  "tf1": col_dims["tf1"],  "tf2": col_dims["tf2"]}

    # crea/aggiorna proprietà plate (inclusi eventuali extra)
    props_map = create_plate_properties(
        model_path=new_model_path,
        beam_thk=beam_thk,
        col_thk=col_thk,
        E=gui_params["E"], nu=gui_params["nu"], rho=gui_params["rho"],
        extra=extra
    )
    print("Plate properties:", props_map)


    # === Step 20: plate geometry (midplane nodes) ====================
    
    # === Nodi piani medi + plate centrali flange colonna =========================

    # ID intermedi dallo step 16
    beam_mid_id = out["intermediate_ids_by_branch"][0][0] # Trave (Branch 0)
    col_low_id  = out["intermediate_ids_by_branch"][1][0] # Colonna Inf (Branch 1)
    col_up_id   = out["intermediate_ids_by_branch"][2][0] # Colonna Sup (Branch 2)

    # Genera/aggiorna i nodi piani medi per trave e per entrambe le colonne
    # La nuova 'create_midplane_nodes_for_members' calcola i centroidi internamente.
    res_nodes = create_midplane_nodes_for_members(
        model_path=new_model_path,
        beam_intermediate_ids=[beam_mid_id],
        col_intermediate_ids=[col_low_id, col_up_id], # Passa entrambe le colonne
        beam_dims=beam_dims, # Dims corretti da Step 19
        col_dims=col_dims,   # Dims corretti da Step 19
        col_upper_intermediate_node_id=col_up_id, # Terza quota = intermedio colonna superiore
    )
    
    print("Nodi piani medi creati.")
    print("Quote Y usate:", res_nodes["_y_levels"]) # Stampa per debug

    # Mappe nodi per le due colonne (per usi futuri, se servono)
    col_lower_nodes = res_nodes["column"][col_low_id]
    col_upper_nodes = res_nodes["column"][col_up_id]

    # === Step 21: create plates for joint (Beam Polygon Conversion) ========================
    try:
        print("\nCreazione plate per il nodo...")
        create_plates_for_joint(
            model_path=new_model_path,
            res_nodes=res_nodes,       # Nodi creati allo Step 20
            props_map=props_map,       # Proprietà create allo Step 19
            beam_mid_id=beam_mid_id,
            col_low_id=col_low_id,   
            col_up_id=col_up_id      
        )
    except Exception as e:
        print(f"Errore creazione plate: {e}")


    # === Step 22: apertura automatica del file Straus7 local model ==========================
    # (Questo era il vecchio Step 21)
    print("\nApertura automatica del file Straus7...")
    os.startfile(new_model_path)