# notch_offset.py
# Calcola l'offset per le verifiche tensionali (notch)
# ed esegue un clean mesh sul modello con opzioni dettagliate.
# AGGIUNTI MESSAGGI DI DEBUG E CONTROLLO NUMERO NODI
# AGGIUNTE OPZIONI CLEAN MESH DA SCREENSHOT

import os
import ctypes as ct
from typing import Dict, List, Optional, Any

try:
    import St7API as st7
    # Importa la funzione 'ck' per il controllo errori
    try:
        from analysis.ltd_analysis import ck
    except ImportError:
        print("ATTENZIONE: Funzione 'ck' non trovata in analysis.ltd_analysis.")
        # Fallback: crea una funzione 'ck' fittizia che solleva errore
        def ck(result, *args):
            print(f"DEBUG: Chiamata ck con result={result}, args={args}") # DEBUG
            if result != 0:
                try:
                    buf = ct.create_string_buffer(st7.kMaxStrLen)
                    st7.St7GetAPIErrorString(result, buf, st7.kMaxStrLen)
                    api_err_msg = buf.value.decode('utf-8','ignore')
                except:
                    api_err_msg = "Impossibile ottenere messaggio errore API."
                print(f"ERRORE API: {args} (codice={result}, msg='{api_err_msg}')")
                raise RuntimeError(f"Errore API: {args} (codice={result}, msg='{api_err_msg}')")
            # else: # DEBUG - Stampa anche le chiamate OK
            #     print(f"DEBUG: Chiamata API OK: {args}")

except ImportError:
    print("ERRORE CRITICO: Impossibile importare St7API.")
    # Definisci un fallback per 'ck' anche qui
    def ck(result, *args):
        print(f"DEBUG: Chiamata ck (fallback) con result={result}, args={args}") # DEBUG
        if result != 0:
             print(f"ERRORE API (St7API non importato): {args} (codice={result})")
             raise RuntimeError(f"Errore API (St7API non importato): {args} (codice={result})")
    raise # Ferma lo script se St7API non è importabile

# --- Funzioni Helper API (Minime necessarie) ---

def _get_total_entities(uID: int, entity_type: int) -> int:
    """Ritorna il numero totale di un'entità."""
    tot = ct.c_long()
    ck(st7.St7GetTotal(uID, entity_type, ct.byref(tot)), f"GetTotal {entity_type}")
    return int(tot.value)

# --- Funzione Calcolo Offset (Invariata) ---

def calculate_notch_offset(
    beam_thk: Dict[str, float],
    col_thk: Dict[str, float],
    extra_thk: Dict[str, Optional[float]]
) -> float:
    """
    Calcola l'offset dalla saldatura basandosi sulla formula fornita.
    """
    print("  ...Inizio calcolo notch offset...")
    all_thicknesses: List[float] = []
    all_thicknesses.extend(v for v in beam_thk.values() if v is not None and v > 0)
    all_thicknesses.extend(v for v in col_thk.values() if v is not None and v > 0)
    for thk in extra_thk.values():
        if thk is not None and thk > 0:
            all_thicknesses.append(thk)

    valid_thicknesses = sorted(list(set(t for t in all_thicknesses if t > 1e-9)))

    if not valid_thicknesses:
        print("ERRORE: Nessuno spessore valido (maggiore di zero) trovato.")
        return 0.0

    print(f"  Spessori analizzati: {[round(t, 5) for t in valid_thicknesses]} m")

    t = max(valid_thicknesses)
    tmin = min(valid_thicknesses)
    t1 = sum(valid_thicknesses) / len(valid_thicknesses)

    print(f"  t (max)   = {t:.5f} m")
    print(f"  t1 (mean) = {t1:.5f} m")
    print(f"  tmin (min) = {tmin:.5f} m")

    notch_offset_val = (0.5 * t1) + (1.5 * t) + (0.7 * tmin)

    print(f"  Valore notch offset calcolato: {notch_offset_val:.5f} m")
    return notch_offset_val

# --- Funzione Principale (Calcolo Offset + Clean Mesh) ---

def run_notch_offset_calculation_and_clean_mesh(
    model_path: str,
    beam_thk: Dict[str, float],
    col_thk: Dict[str, float],
    extra_thk: Dict[str, Optional[float]],
):
    """
    Calcola l'offset e esegue Clean Mesh per unire i nodi vicini
    con opzioni dettagliate basate sugli screenshot.
    """
    print(f"\nAvvio Calcolo Offset e Clean Mesh in: {os.path.basename(model_path)}")

    notch_offset = calculate_notch_offset(beam_thk, col_thk, extra_thk)

    if notch_offset <= 1e-9:
        print("Calcolo offset nullo o fallito. Clean Mesh non eseguito.")
        return None

    uID = 1
    nodes_before = -1
    nodes_after = -1

    print(f"Inizializzazione API per Clean Mesh...") # DEBUG
    ck(st7.St7Init(), "Init API per Clean Mesh")
    try:
        print(f"Apertura modello {model_path}...") # DEBUG
        ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), f"Open local model {model_path}")

        # --- CONTROLLO NODI PRIMA ---
        nodes_before = _get_total_entities(uID, st7.tyNODE)
        print(f"  --- NODI PRIMA DI CLEAN MESH: {nodes_before} ---")

        # --- Clean Mesh ---
        print("  ...Configurazione Clean Mesh con opzioni dettagliate...")
        clean_ints = (ct.c_long * 20)()
        clean_doubles = (ct.c_double * 1)()

        # -- Impostazioni dalla Tab "Settings" --
        clean_ints[st7.ipMeshToleranceType] = st7.ztAbsolute # Tolleranza Assoluta (basato sul valore)
        clean_ints[st7.ipActOnWholeModel] = st7.btTrue       # Agisci su tutto il modello
        clean_ints[st7.ipZipNodes] = st7.btTrue             # UNISCI NODI (Zip nodes)
        clean_ints[st7.ipRemoveDuplicateElements] = st7.btTrue # CANCELLA DUPLICATI
        clean_ints[st7.ipFixElementConnectivity] = st7.btTrue # CORREGGI CONNETTIVITA'
        clean_ints[st7.ipDeleteFreeNodes] = st7.btTrue         # CANCELLA NODI LIBERI
        clean_ints[st7.ipDeleteInvalidElements] = st7.btTrue   # CANCELLA ELEMENTI INVALIDI
        clean_ints[st7.ipPackStringGroupIDs] = st7.btTrue     # Pack string group IDs (CHECKED)
        # Selezione Entità
        clean_ints[st7.ipDoBeams] = st7.btTrue              # Agisci su Beams (CHECKED)
        clean_ints[st7.ipDoPlates] = st7.btTrue             # Agisci su Plates (CHECKED)
        clean_ints[st7.ipDoBricks] = st7.btFalse            # NON agire su Bricks (UNCHECKED)
        clean_ints[st7.ipDoLinks] = st7.btTrue              # Agisci su Links (CHECKED)

        # -- Impostazioni dalla Tab "Options" --
        try:
            # Assicurati che le costanti esistano nella tua API
            clean_ints[st7.ipNodeAttributeKeep] = st7.naAccumulate # Node Attribute: Accumulate
            clean_ints[st7.ipNodeCoordinates] = st7.ncAverage      # Node coordinates: Average
        except AttributeError as e:
            print(f"ATTENZIONE: Costante API non trovata ({e}). Uso default per Node Attribute/Coordinates.")
            # Lascia i valori a 0 (default) se le costanti non esistono

        clean_ints[st7.ipZeroLengthBeams] = st7.btFalse # Allow zero length beams (UNCHECKED)
        clean_ints[st7.ipZeroLengthLinks] = st7.btTrue  # Allow zero length links (CHECKED)
        clean_ints[st7.ipAllowDifferentProps] = st7.btTrue # Allow duplicates of different property (CHECKED)
        clean_ints[st7.ipAllowDifferentGroups] = st7.btTrue# Allow duplicates of different group (CHECKED)
        clean_ints[st7.ipAllowDifferentBeamOffset] = st7.btTrue # Allow duplicate beams... (CHECKED)
        clean_ints[st7.ipAllowDifferentPlateOffset] = st7.btTrue# Allow duplicate plates... (CHECKED)

        # Tolleranza
        tolerance = 1.0e-5
        clean_doubles[st7.ipMeshTolerance] = tolerance

        ck(st7.St7SetCleanMeshOptions(uID, clean_ints, clean_doubles), "Set Clean Mesh Options")

        print(f"  ...Esecuzione Clean Mesh (Tolleranza={tolerance:.1E})...")
        ck(st7.St7CleanMesh(uID), "Esecuzione Clean Mesh")
        print("  ...Clean Mesh (presumibilmente) completato.")

        # --- CONTROLLO NODI DOPO ---
        nodes_after = _get_total_entities(uID, st7.tyNODE)
        print(f"  --- NODI DOPO CLEAN MESH: {nodes_after} ---")
        if nodes_after < nodes_before:
            print(f"  --- SUCCESSO: {nodes_before - nodes_after} nodi sono stati uniti/eliminati. ---")
        elif nodes_after == nodes_before:
             print(f"  --- ATTENZIONE: Il numero di nodi non è cambiato. Controlla la tolleranza ({tolerance:.1E}) o se non c'era nulla da pulire/unire. ---")
        else:
             print(f"  --- ERRORE INASPETTATO: Il numero di nodi è aumentato? ({nodes_after} > {nodes_before}) ---")


        # --- Salva Modello ---
        print("  ...Salvataggio modello...")
        ck(st7.St7SaveFile(uID), "Salvataggio modello locale dopo Clean Mesh")

    finally:
        try:
            ck(st7.St7CloseFile(uID), "Close local model")
        finally:
            # Rilascia sempre l'API
            st7.St7Release()

    print("Processo Calcolo Offset e Clean Mesh completato.")
    # Ritorna l'offset calcolato
    return notch_offset

