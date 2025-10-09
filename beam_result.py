# beam_result.py
# Requisiti: St7API.dll e St7API.py nel PYTHONPATH.
# Scopo: estrarre, per ogni trave e in N stazioni, gli stress di sezione:
#   - FB = max(|MaxFibreStress|, |MinFibreStress|)      [kN/m^2]
#   - SY = |Mean Shear Stress dovuta a Shear Force 2|   [kN/m^2]  (piano y)
# e calcolare il valore:  (FB/den)^2 + 3*(SY/den)^2  con den in MPa.
# NB: i risultati Straus7 per le travi sono in unità del modello. Se lavori in kN–m,
#     le tensioni sono in kN/m^2. Per confrontarle con den [MPa = N/mm^2], serve 1.0e-3.
#
# Output della funzione max_check_value: massimo di quella espressione su tutte le travi e stazioni.

import os
import ctypes as ct
import St7API as st7

# Default del denominatore (se non lo passi): fy/gamma_M0 = 355/1.05 [MPa]
_DEFAULT_DEN = 355.0 / 1.05


# ----------------------------- Apertura file modello + risultati -----------------------------
def _open(uID: int, model_path: str) -> None:
    """Apre il file .st7 con percorso scratch. Firma: (long uID, char* FileName, char* ScratchPath)."""
    st7.St7OpenFile.argtypes = [ct.c_long, ct.c_char_p, ct.c_char_p]
    st7.St7OpenFile.restype  = ct.c_long

    scratch = os.path.join(os.path.dirname(os.path.abspath(model_path)), "_scratch")
    os.makedirs(scratch, exist_ok=True)

    fn = os.fspath(model_path).encode("mbcs")
    sp = os.path.abspath(scratch).encode("mbcs")

    i = st7.St7OpenFile(ct.c_long(uID), ct.c_char_p(fn), ct.c_char_p(sp))
    if i != 0:
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
    st7.St7OpenResultFile.argtypes = [
        ct.c_long, ct.c_char_p, ct.c_char_p, ct.c_long,
        ct.POINTER(ct.c_long), ct.POINTER(ct.c_long)
    ]
    st7.St7OpenResultFile.restype = ct.c_long
    st7.St7ValidateResultFile.argtypes = [ct.c_long, ct.c_char_p, ct.POINTER(ct.c_long), ct.POINTER(ct.c_long)]
    st7.St7ValidateResultFile.restype  = ct.c_long

    base = os.path.dirname(os.path.abspath(model_path))
    stem = os.path.splitext(os.path.basename(model_path))[0]

    comb = getattr(st7, "kUseExistingCombinations", 0)  # fallback se costante non presente
    def _try_open(fullpath: str) -> bool:
        numP, numS = ct.c_long(0), ct.c_long(0)
        i = st7.St7OpenResultFile(
            ct.c_long(uID),
            os.fspath(fullpath).encode("mbcs"),
            ct.c_char_p(b""),              # SpectralName nullo → usa default
            ct.c_long(comb),               # combina usando l’eventuale .LSC
            ct.byref(numP), ct.byref(numS)
        )
        return i == 0

    # 1) <modello>.lsa
    cand = os.path.join(base, stem + ".lsa")
    if os.path.isfile(cand) and _try_open(cand):
        return

    # 2) qualsiasi .lsa valido
    for fn in sorted(os.listdir(base)):
        if fn.lower().endswith(".lsa"):
            full = os.path.join(base, fn)
            vc, sv = ct.c_long(0), ct.c_long(0)
            st7.St7ValidateResultFile(ct.c_long(uID), os.fspath(full).encode("mbcs"), ct.byref(vc), ct.byref(sv))
            if _try_open(full):
                return

    # 3) fallback .sra (spettrale)
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
    """Normalizza per confronto: minuscole + soli alfanumerici."""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _resolve_case_tokens(uID: int, tokens: list[str], limit: int = 2048) -> int:
    """
    Trova un Result Case il cui nome normalizzato contiene TUTTI i token normalizzati.
    Esempi token: ["linear static", "combination", "slu"] oppure solo ["slu"].
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

    # match: tutti i token devono comparire
    for rc, nm, nnm in candidates:
        if all(t in nnm for t in want):
            return rc

    # diagnosi se non trovato
    available = [nm for _, nm, _ in candidates]
    raise RuntimeError(f"Result case non trovato per tokens {tokens}. Disponibili: {available}")


# ----------------------------- Conteggio travi ------------------------------------------------
def _n_beams(uID: int) -> int:
    n = ct.c_long()
    if st7.St7GetTotal(uID, st7.tyBEAM, ct.byref(n)) != 0:
        raise RuntimeError("St7GetTotal(tyBEAM) failed")
    return n.value


# ----------------------------- Core: calcolo massimo valore ----------------------------------
def max_check_value(model_path: str,
                    case_name: str | list[str],
                    stations: int = 10,
                    den: float = _DEFAULT_DEN,
                    print_table: bool = True) -> float:
    """
    Calcola e stampa, per ogni trave e stazione, le tensioni da verifica EC3:

        η² = (FB/den)² + 3*(SY/den)²

    dove:
      FB = max(|MaxFibreStress|, |MinFibreStress|)            [kN/m²]
      SY = |Mean Shear Stress da Shear Force 2 (piano y)|     [kN/m²]
      den = fy / γM0                                           [MPa]

    Tutti i risultati di Straus7 sono in kN/m² (per modelli kN–m),
    per cui si convertono in MPa moltiplicando per 1.0e-3.

    Parametri:
      model_path : percorso completo del file .st7 del modello
      case_name  : nome o lista di token per cercare il result case (es. "SLU" o ["combination","slu"])
      stations   : numero minimo di stazioni da campionare lungo ciascun elemento beam
      den        : denominatore di verifica (MPa)
      print_table: se True, stampa tabella con le tensioni per ogni stazione
    Ritorna:
      vmax : valore massimo di η² trovato sull’intero modello
    """

    uID = 1
    st7.St7Init()
    try:
        # 1) Apre il modello e il file risultati (.lsa o .sra)
        _open(uID, model_path)
        _open_results(uID, model_path)

        # 2) Risolve il Result Case cercando i token nel nome (es. "SLU", "Combination", ...)
        tokens = case_name if isinstance(case_name, list) else [case_name]
        rc = _resolve_case_tokens(uID, tokens)

        # 3) Imposta la firma della funzione St7GetBeamResultArray come da manuale
        st7.St7GetBeamResultArray.argtypes = [
            ct.c_long, ct.c_long, ct.c_long, ct.c_long, ct.c_long, ct.c_long,
            ct.POINTER(ct.c_long), ct.POINTER(ct.c_long),
            ct.POINTER(ct.c_double), ct.POINTER(ct.c_double),
        ]
        st7.St7GetBeamResultArray.restype = ct.c_long

        # 4) Imposta le posizioni stazionali lungo la trave come parametro (0→inizio, 1→fine)
        st7.St7SetBeamResultPosMode(uID, st7.bpParam)

        # 5) Prepara buffer per i risultati
        BeamPos     = (ct.c_double * st7.kMaxBeamResult)()   # posizione 0..1
        BeamResult  = (ct.c_double * st7.kMaxBeamResult)()   # array risultati
        NumStations = ct.c_long()
        NumColumns  = ct.c_long()

        # Variabile per massimo globale
        vmax = 0.0
        nbeams = _n_beams(uID)

        # Stampa intestazione tabella, se richiesto
        if print_table:
            header = f"{'Beam':>5} {'s':>6} {'FBmax[kN/m²]':>15} {'FBmin[kN/m²]':>15} {'SY[kN/m²]':>12} {'FBabs[kN/m²]':>15} {'η²':>10}"
            print("\n" + header)
            print("-" * len(header))

        # 6) Loop su tutte le travi del modello
        for b in range(1, nbeams + 1):
            # Richiama l’API per ottenere l’array dei risultati di stress
            ierr = st7.St7GetBeamResultArray(
                uID,
                st7.rtBeamAllStress,     # Tipo risultati: tutti gli stress di sezione
                st7.stBeamPrincipal,     # Sistema assi principali 1-2
                b,                       # Numero elemento beam
                int(stations),           # N° minimo di stazioni lungo la trave
                int(rc),                 # Result case identificato
                ct.byref(NumStations),
                ct.byref(NumColumns),
                BeamPos,
                BeamResult
            )
            if ierr != 0:
                raise RuntimeError(f"GetBeamResultArray iErr={ierr} (beam {b})")

            ns, nc = NumStations.value, NumColumns.value

            # Indici per accedere alle colonne dei risultati nel pacchetto All Stress
            i_max_fibre = st7.ipMaxFibreStress          # max fibre stress (kN/m²)
            i_min_fibre = st7.ipMinFibreStress          # min fibre stress (kN/m²)
            i_shear_y   = st7.ipShearF2MeanShearStress  # mean shear stress (plane 2 → y)

            # 7) Loop sulle stazioni lungo la trave
            for k in range(ns):
                s_par = BeamPos[k]                      # posizione normalizzata 0..1
                s_max = BeamResult[k*nc + i_max_fibre]  # kN/m²
                s_min = BeamResult[k*nc + i_min_fibre]  # kN/m²
                s_y   = BeamResult[k*nc + i_shear_y]    # kN/m²

                # Tensioni in kN/m² → MPa per il confronto con den
                FBmax = abs(s_max) * 1.0e-3
                FBmin = abs(s_min) * 1.0e-3
                FBabs = max(FBmax, FBmin)
                SY    = abs(s_y) * 1.0e-3

                # Calcolo dell’espressione EC3 (η²)
                val = (FBabs/den)**2 + 3.0*(SY/den)**2
                if val > vmax:
                    vmax = val

                # Stampa tabella per ogni stazione
                if print_table:
                    print(f"{b:5d} {s_par:6.3f} {FBmax/_KNSQM_TO_MPA:15.2f} {FBmin/_KNSQM_TO_MPA:15.2f} {SY/_KNSQM_TO_MPA:12.2f} {FBabs/_KNSQM_TO_MPA:15.2f} {val:10.3f}")

        # Ritorna il massimo valore trovato
        return vmax

    finally:
        # Chiusura file e scaricamento API
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
