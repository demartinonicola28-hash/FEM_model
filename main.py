# main.py
# Richiama la funzione create_file dal modulo create_file.py
# e la funzione build_geometry dal modulo build_geometry.py

from create_file import create_file
from build_geometry import build_geometry
from apply_properties import apply_properties
from freedom_case import apply_freedom_case
from load_cases import apply_load_cases
from lsa_combine_and_solve import lsa_combine_and_solve


if __name__ == "__main__":

    # Step 1: crea il file .st7 vuoto con le unità
    path = create_file("telaio_2D.st7")
    print("File generato:", path)

    # Step 2: aggiungi la geometria parametrica al file
    geom = build_geometry(path,
                          h_story=3.50,
                          span=5.00,
                          n_floors=2,
                          offset=1.50,
                          prop_col=1,    # proprietà colonne
                          prop_beam=2)   # proprietà travi
    print("Geometria scritta su:", geom["model_path"])
    print("Nodi di base:", geom["base_nodes"])

    # Step 3: proprietà con E, ν, ρ dal main e sezioni da .BSL
    from apply_properties import apply_properties

    props = apply_properties(model_path=geom["model_path"],
                             E=200000.0,          # MPa
                             nu=0.30,             # -
                             rho=7850.0,          # kg/m^3
                             section_columns="BS EN - HE 160 A - BS EN 10365-2017 BSL",
                             section_beams="BS EN - IPE 270 - BS EN 10365-2017 BSL",
                             prop_col=1,
                             prop_beam=2,
                             library_dir_bsl = r"C:\ProgramData\Straus7 R31\Data")
    print("Proprietà applicate:", props)

    # Step 4: crea freedom cases
    fc = apply_freedom_case(path, case_name="2d plane XY", base_nodes=geom["base_nodes"])
    print("Freedom case:", fc)

    # Step 5: crea load cases
    lc = apply_load_cases(path,
                      gravity=9.80665,
                      q_G2=-26.25,
                      q_Q=-22.5,
                      q_Q_roof=-3.0,
                      prop_beam=2)
    print("Load cases:", lc)

    # Step 6: crea combination e solver Linear Static Analysis (LSA)
    res = lsa_combine_and_solve(
    model_path=path,
    freedom_case=1,                    # FC 1 “2D plane XY”
    lc_G1=1, lc_G2=2, lc_Q=3,          # come creati prima
    combos={
        "SLU":       {1: 1.35, 2: 1.35, 3: 1.50},
        "SISMA q=4": {1: 1.00, 2: 1.00, 3: 0.30},
    })
    print("Combinazioni LSA create e solver avviato:", res)