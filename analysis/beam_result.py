# beam_result.py
# Requisiti: St7API.dll e St7API.py nel PYTHONPATH.
# Scopo: estrarre, per ogni trave e in N stazioni, gli stress di sezione:
#   - FB = max(|MaxFibreStress|, |MinFibreStress|)      [MPa]
#   - SY = |Mean Shear Stress dovuta a Shear Force 2|   [MPa]  (piano y, nel sist. principale 1-2)
# e calcolare la verifica elastica EC3 (6.1):  η = sqrt( (FB/den)^2 + 3*(SY/den)^2 )  con den in MPa.
#
# NOTE IMPORTANTI:
# - I risultati Straus7 letti qui sono in MPa (non kN/m^2) perché si interroga il "Beam All Stress"
#   che restituisce tensioni coerenti con le unità del modello convertite come stress [MPa].
# - "stations" è un MINIMO richiesto a St7GetBeamResultArray. Il numero effettivo restituito
#   in NumStations può essere >= stations. Mai minore. Qui si usa SEMPRE NumStations.
# - Lungo l’asse della trave si usa la modalità "parametrica" (bpParam): BeamPos va da 0 (inizio)
#   a 1 (fine). Non forniamo le posizioni a priori, le sceglie l’API in modo uniforme.
#
# Output della funzione max_check_value: massimo η su tutte le travi e stazioni.

import os
import ctypes as ct
import St7API as st7

# ----------------------------- Apertura file modello + risultati -----------------------------
def _open(uID: int, model_path: str) -> None:
    """Apre il file .st7 con percorso scratch. Firma: (long uID, char* FileName, char* ScratchPath)."""
    st7.St7OpenFile.argtypes = [ct.c_long, ct.c_char_p, ct.c_char_p]
    st7.St7OpenFile.restype  = ct.c_long

    # Cartella scratch accanto al modello: Straus7 la usa per file temporanei
    scratch = os.path.join(os.path.dirname(os.path.abspath(model_path)), "_scratch")
    os.makedirs(scratch, exist_ok=True)

    fn = os.fspath(model_path).encode("mbcs")
    sp = os.path.abspath(scratch).encode("mbcs")

    # Chiamata API apertura modello
    i = st7.St7OpenFile(ct.c_long(uID), ct.c_char_p(fn), ct.c_char_p(sp))
    if i != 0:
        # In caso di errore, decodifica le cause fornite dall’API per una diagnosi rapida
        code = st7.St7GetLastOpenFileCode()
        flags = {
            "FileNameTooLongOrInvalid": bool(code & (1 << 0)),
            "FileSharingError":         bool(code & (1 << 1)),
            "FileCantRead":             bool(code & (1 << 2)),
            "FileNotFound":             bool(code & (1 << 3)),
            "FileInvalidData":          bool(code & (1 << 4)),
            "FileTruncated":            bool(code & (1 << 5)),
            "FileIsBXS":                bool(code & (1 << 6)),
            "FileIsNotSt7":             bool(code & (1 << 7)),
            "InsufficientFreeSpace":    bool(code & (1 << 8)),
        }
        raise RuntimeError(f"St7OpenFile iErr={i}, flags={flags}")


def _open_results(uID: int, model_path: str) -> None:
    """Apre un file risultati compatibile (.lsa prioritario, altrimenti .sra) nella stessa cartella del .st7."""
    # Firme funzioni risultati (da manuale API)
    st7.St7OpenResultFile.argtypes = [
        ct.c_long, ct.c_char_p, ct.c_char_p, ct.c_long,
        ct.POINTER(ct.c_long), ct.POINTER(ct.c_long)
    ]
    st7.St7OpenResultFile.restype = ct.c_long
    st7.St7ValidateResultFile.argtypes = [ct.c_long, ct.c_char_p, ct.POINTER(ct.c_long), ct.POINTER(ct.c_long)]
    st7.St7ValidateResultFile.restype  = ct.c_long

    base = os.path.dirname(os.path.abspath(model_path))
    stem = os.path.splitext(os.path.basename(model_path))[0]

    # Opzione: usa eventuali combinazioni già presenti nel file risultati
    comb = getattr(st7, "kUseExistingCombinations", 0)  # fallback se costante non presente

    def _try_open(fullpath: str) -> bool:
        """Prova ad aprire 'fullpath' come risultati. Ritorna True se ok."""
        numP, numS = ct.c_long(0), ct.c_long(0)
        i = st7.St7OpenResultFile(
            ct.c_long(uID),
            os.fspath(fullpath).encode("mbcs"),
            ct.c_char_p(b""),              # SpectralName nullo → usa default del file
            ct.c_long(comb),               # combina usando l’eventuale .LSC
            ct.byref(numP), ct.byref(numS)
        )
        return i == 0

    # 1) Prova <modello>.lsa (risultati lineari)
    cand = os.path.join(base, stem + ".lsa")
    if os.path.isfile(cand) and _try_open(cand):
        return

    # 2) In alternativa, qualunque .lsa valido nella cartella
    for fn in sorted(os.listdir(base)):
        if fn.lower().endswith(".lsa"):
            full = os.path.join(base, fn)
            vc, sv = ct.c_long(0), ct.c_long(0)
            st7.St7ValidateResultFile(ct.c_long(uID), os.fspath(full).encode("mbcs"), ct.byref(vc), ct.byref(sv))
            if _try_open(full):
                return

    # 3) Fallback: cerca un .sra (risposta spettrale)
    for fn in sorted(os.listdir(base)):
        if fn.lower().endswith(".sra") and _try_open(os.path.join(base, fn)):
            return

    raise RuntimeError("Nessun file risultati aperto (.lsa/.sra).")


def _close(uID: int) -> None:
    """Chiude il file modello. UnLoad lo fa il chiamante se necessario."""
    try:
        st7.St7CloseFile(uID)
    except Exception:
        pass


# ----------------------------- Utilità per Result Case ---------------------------------------
def _norm(s: str) -> str:
    """Normalizza stringa per confronto robusto: minuscole + rimuove caratteri non alfanumerici."""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _resolve_case_tokens(uID: int, tokens: list[str], limit: int = 2048) -> int:
    """
    Trova un Result Case il cui nome normalizzato contiene TUTTI i token normalizzati.
    Esempi token: ["linear static", "combination", "slu"] oppure solo ["slu"].
    Se non trovato: lancia eccezione con l’elenco dei nomi disponibili utili per il debug.
    """
    buf = ct.create_string_buffer(st7.kMaxStrLen)
    want = [_norm(t) for t in tokens if t]
    candidates = []
    for rc in range(1, limit + 1):
        if st7.St7GetResultCaseName(uID, rc, buf, st7.kMaxStrLen) != 0:
            continue
        name = buf.value.decode("mbcs", errors="ignore")
        if not name:
            continue
        candidates.append((rc, name, _norm(name)))

    # Match: tutti i token devono comparire nella versione normalizzata
    for rc, nm, nnm in candidates:
        if all(t in nnm for t in want):
            return rc

    # Diagnosi se non trovato
    available = [nm for _, nm, _ in candidates]
    raise RuntimeError(f"Result case non trovato per tokens {tokens}. Disponibili: {available}")


# ----------------------------- Conteggio travi ------------------------------------------------
def _n_beams(uID: int) -> int:
    """Ritorna il numero totale di elementi BEAM nel modello aperto."""
    n = ct.c_long()
    if st7.St7GetTotal(uID, st7.tyBEAM, ct.byref(n)) != 0:
        raise RuntimeError("St7GetTotal(tyBEAM) failed")
    return n.value

# ----------------------------- Utility: leggi proprietà beam ---------------------------------
def _beam_prop_name(uID: int, beam_num: int) -> tuple[int, str]:
    """Ritorna (numero_prop, nome_prop) del beam."""
    prop = ct.c_long()
    st7.St7GetElementProperty.argtypes = [ct.c_long, ct.c_long, ct.c_long, ct.POINTER(ct.c_long)]
    st7.St7GetElementProperty.restype  = ct.c_long
    ierr = st7.St7GetElementProperty(uID, st7.ptBEAMPROP, beam_num, ct.byref(prop))
    if ierr != 0:
        return (0, "")
    buf = ct.create_string_buffer(st7.kMaxStrLen)
    st7.St7GetPropertyName.argtypes = [ct.c_long, ct.c_long, ct.c_long, ct.c_char_p, ct.c_long]
    st7.St7GetPropertyName.restype  = ct.c_long
    st7.St7GetPropertyName(uID, st7.ptBEAMPROP, prop.value, buf, st7.kMaxStrLen)
    return (prop.value, buf.value.decode("mbcs", errors="ignore"))

# ----------------------------- Core: calcolo massimo valore ----------------------------------
def max_check_value(model_path: str,
                    case_name: str | list[str],
                    stations: int = 100,
                    den: float = 1,
                    print_table: bool = True) -> float:
    """
    Calcola η e stampa la tabella. In più:
    - stampa una riga 'Combination SLU' o 'Combination SLV' (o il nome case reale)
    - stampa ηmax per prop1 e prop2 a fine tabella
    """

    uID = 1
    st7.St7Init()
    try:
        _open(uID, model_path)
        _open_results(uID, model_path)

        # --- risolvi result case dai token ---
        tokens = case_name if isinstance(case_name, list) else [case_name]
        rc = _resolve_case_tokens(uID, tokens)

        # --- ricava nome reale del case per stampa header "Combination ..." ---
        buf = ct.create_string_buffer(st7.kMaxStrLen)
        st7.St7GetResultCaseName(uID, rc, buf, st7.kMaxStrLen)
        rc_real_name = buf.value.decode("mbcs", errors="ignore").strip()

        # prova a sintetizzare SLU/SLV se i token o il nome lo contengono
        wanted_label = None
        norm_tokens = [_norm(t) for t in tokens if t]
        norm_rcname = _norm(rc_real_name)
        for key in ("slu", "slv"):
            if any(key in t for t in norm_tokens) or key in norm_rcname:
                wanted_label = key.upper()
                break
        comb_label = wanted_label if wanted_label else rc_real_name or "Unknown"

        # --- set API per beam results ---
        st7.St7GetBeamResultArray.argtypes = [
            ct.c_long, ct.c_long, ct.c_long, ct.c_long, ct.c_long, ct.c_long,
            ct.POINTER(ct.c_long), ct.POINTER(ct.c_long),
            ct.POINTER(ct.c_double), ct.POINTER(ct.c_double),
        ]
        st7.St7GetBeamResultArray.restype = ct.c_long
        st7.St7SetBeamResultPosMode(uID, st7.bpParam)

        BeamPos     = (ct.c_double * st7.kMaxBeamResult)()
        BeamResult  = (ct.c_double * st7.kMaxBeamResult)()
        NumStations = ct.c_long()
        NumColumns  = ct.c_long()

        min_st = int(stations)
        if min_st < 1:
            min_st = 1
        if min_st > st7.kMaxBeamResult:
            min_st = st7.kMaxBeamResult

        vmax = 0.0
        vmax_beam = 0
        vmax_propnum = 0
        vmax_propname = ""

        # ηmax per proprietà 1 e 2: {propnum: (ηmax, nome_prop)}
        eta_max_by_prop = {1: (0.0, ""), 2: (0.0, "")}

        nbeams = _n_beams(uID)

        # --- stampa intestazioni ---
        if print_table:
            # riga richiesta per distinguere la combinazione
            print(f"\nCombination {comb_label}")
            #header = f"{'Beam':>5} {'s':>6} {'FBmax[MPa]':>15} {'FBmin[MPa]':>15} {'SY[MPa]':>12} {'FBabs[MPa]':>15} {'η':>10}"
            #print(header)
            #print("-" * len(header))

        # --- loop travi ---
        for b in range(1, nbeams + 1):
            propnum, propname = _beam_prop_name(uID, b)

            ierr = st7.St7GetBeamResultArray(
                uID, st7.rtBeamAllStress, st7.stBeamPrincipal, b, min_st, int(rc),
                ct.byref(NumStations), ct.byref(NumColumns), BeamPos, BeamResult
            )
            if ierr != 0:
                raise RuntimeError(f"GetBeamResultArray iErr={ierr} (beam {b})")

            ns, nc = NumStations.value, NumColumns.value
            i_max_fibre = st7.ipMaxFibreStress
            i_min_fibre = st7.ipMinFibreStress
            i_shear_y   = st7.ipShearF2MeanShearStress

            for k in range(ns):
                s_par = BeamPos[k]
                base  = k * nc

                s_max = BeamResult[base + i_max_fibre]
                s_min = BeamResult[base + i_min_fibre]
                s_y   = BeamResult[base + i_shear_y]

                FBmax = abs(s_max)
                FBmin = abs(s_min)
                FBabs = max(FBmax, FBmin)
                SY    = abs(s_y)

                val = ((FBabs/den)**2 + 3.0*(SY/den)**2)**0.5

                if val > vmax:
                    vmax = val
                    vmax_beam = b
                    vmax_propnum, vmax_propname = propnum, propname

                if propnum in eta_max_by_prop and val > eta_max_by_prop[propnum][0]:
                    eta_max_by_prop[propnum] = (val, propname)

                #if print_table:
                    #print(f"{b:5d} {s_par:6.3f} {s_max:15.2f} {s_min:15.2f} {s_y:12.2f} {FBabs:15.2f} {val:10.3f}")

        # --- riepilogo richiesto: ηmax per prop1 e prop2 ---
        if print_table:
            v1, n1 = eta_max_by_prop.get(1, (0.0, ""))
            v2, n2 = eta_max_by_prop.get(2, (0.0, ""))
            print(f"η max column [{n1}] = {v1:.3f}")
            print(f"η max beam [{n2}] = {v2:.3f}")

        return vmax, vmax_beam, vmax_propnum, vmax_propname

    finally:
        _close(uID)



# ----------------------------- Utility: elenca i Result Case ---------------------------------
def list_result_cases(model_path: str) -> None:
    """Stampa tutti i Result Case disponibili dopo aver aperto il .st7 e il file risultati."""
    uID = 1
    st7.St7Init()
    try:
        _open(uID, model_path)
        _open_results(uID, model_path)

        buf = ct.create_string_buffer(st7.kMaxStrLen)
        print("=== Result Cases disponibili ===")
        for rc in range(1, 2048):
            if st7.St7GetResultCaseName(uID, rc, buf, st7.kMaxStrLen) == 0:
                name = buf.value.decode("mbcs", errors="ignore")
                if name:
                    print(f"{rc:4d}: {name}")
    finally:
        _close(uID)
