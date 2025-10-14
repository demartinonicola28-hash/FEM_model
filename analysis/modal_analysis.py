# modal_analysis
import os, ctypes
import St7API as st
import glob


KMAX = st.kMaxStrLen

def _api_err(ierr):
    if ierr == st.ERR7_NoError:
        return
    buf = (ctypes.c_char * KMAX)()
    st.St7GetAPIErrorString(ierr, buf, KMAX)
    raise RuntimeError(buf.value.decode("utf-8", errors="ignore"))

def run_modal_analysis(model_path, scratch_path, n_modes=10, res_path=None, log_path=None):
    # risolvi percorsi e precondizioni
    model_path = os.path.abspath(model_path)
    scratch_path = os.path.abspath(scratch_path)
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"ST7 non trovato: {model_path}")
    os.makedirs(scratch_path, exist_ok=True)

    _api_err(st.St7Init())
    uID = 1
    try:
        _api_err(st.St7OpenFile(uID, model_path.encode(), scratch_path.encode()))  # :contentReference[oaicite:0]{index=0}

        if res_path:
            _api_err(st.St7SetResultFileName(uID, os.path.abspath(res_path).encode()))       # :contentReference[oaicite:1]{index=1}
        if log_path:
            _api_err(st.St7SetResultLogFileName(uID, os.path.abspath(log_path).encode()))    # :contentReference[oaicite:2]{index=2}

        # >>> configurazione solver robusta per analisi modale
        # azzera eventuale shift di frequenza
        _api_err(st.St7SetNFAShift(uID, 0.0))
        _api_err(st.St7SetSolverDefaultsDouble(uID, st.spFrequencyShift, 0.0))

        # forza espansione del working set per ottenere tutti i modi richiesti
        _api_err(st.St7SetSolverDefaultsLogical(uID, st.spAutoWorkingSet, True))
        _api_err(st.St7SetSolverDefaultsInteger(uID, st.spExpandWorkingSet, max(10, 2 * int(n_modes))))
        _api_err(st.St7SetSolverDefaultsInteger(uID, st.spMaxIterationEig, 500))
        _api_err(st.St7SetSolverDefaultsLogical(uID, st.spCheckEigenvector, True))
        _api_err(st.St7SetSturmCheck(uID, True))

        # Natural Frequency settings
        _api_err(st.St7SetSolverDefaultsInteger(uID, st.spNumFrequency, int(n_modes)))  # forza il numero di modi
        _api_err(st.St7SetNFANumModes(uID, int(n_modes)))                               # ridondante ma sicuro
        _api_err(st.St7SetSturmCheck(uID, True))                                        # opzionale

        # >>> diagnostica: stampa verifica del parametro interno del solver
        tmp = ctypes.c_long()
        _api_err(st.St7GetSolverDefaultsInteger(uID, st.spNumFrequency, ctypes.byref(tmp)))
        # stampa numero modi impostato ridonadante perchè viene stampato dopo il solver ma può tornare utile se ci sono errori
        #print(f"Numero modi impostato (spNumFrequency) = {tmp.value}")

        # Partecipazioni di massa
        _api_err(st.St7SetNFAModeParticipationCalculate(uID, True))
        doubles = (ctypes.c_double * 9)(0.0,0.0,0.0, 0.0,0.0,0.0, 0.0,0.0,0.0)
        _api_err(st.St7SetNFAModeParticipationVectors(uID, doubles))

        # Lancia solver Natural Frequency e attendi fine
        ierr = st.St7RunSolver(uID, st.stNaturalFrequency, st.smBackgroundRun, True)         # :contentReference[oaicite:7]{index=7}
        if ierr != st.ERR7_NoError:
            buf = (ctypes.c_char * KMAX)()
            st.St7GetSolverErrorString(ierr, buf, KMAX)                                       # :contentReference[oaicite:8]{index=8}
            raise RuntimeError(buf.value.decode("utf-8", errors="ignore"))

        # >>> dopo il solver, verifica quanti modi sono stati effettivamente salvati nel file .nfa
        if res_path:
            n_found = ctypes.c_long()
            _api_err(st.St7GetNumModesInNFAFile(uID, os.path.abspath(res_path).encode(), ctypes.byref(n_found)))
            print(f"Modi trovati nel file NFA: {n_found.value} (richiesti: {n_modes})")

    finally:
        st.St7CloseFile(uID)                                                                   # :contentReference[oaicite:9]{index=9}
        st.St7Release()

def default_model_path(base_dir, name_without_ext):
    """Costruisce il path al .st7 affiancato agli script."""
    return os.path.join(os.path.abspath(base_dir), f"{name_without_ext}.st7")

def find_model_in(base_dir):
    """Ritorna l'unico .st7 nella cartella. Errore se 0 o >1."""
    cand = glob.glob(os.path.join(os.path.abspath(base_dir), "*.st7"))
    if len(cand) != 1:
        raise FileNotFoundError(f"Attesi 1 file .st7, trovati {len(cand)} in {base_dir}")
    return cand[0]
