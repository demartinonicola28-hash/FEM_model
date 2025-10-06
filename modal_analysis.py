# --------------------- modal_analysis.py ---------------------------------
import St7API as st7

def run_nfa(uID: int,
            num_modes: int = 20,
            shift_hz: float = 0.0,
            calc_participation: bool = True,
            wait: bool = True,
            show_progress: bool = False) -> None:
    """
    Avvia l'analisi di frequenza naturale sul modello Straus7 già aperto.
    Parametri:
        uID                -> ID del modello attivo
        num_modes          -> numero di modi propri da calcolare
        shift_hz           -> valore di shift in Hz (0.0 se non serve)
        calc_participation -> calcola i fattori di partecipazione di massa
        wait               -> True se si vuole attendere la fine del solver
        show_progress      -> True per mostrare la finestra del solver
    """

    # ----------------------------------------------------------------------
    # Imposta il numero di modi propri da calcolare
    # API: St7SetNFANumModes(uID, NumModes)
    # ----------------------------------------------------------------------
    err = st7.St7SetNFANumModes(uID, num_modes)
    if err:
        raise RuntimeError(f"St7SetNFANumModes failed: {err}")

    # ----------------------------------------------------------------------
    # Imposta eventuale shift di frequenza in Hz
    # API: St7SetNFAShift(uID, ShiftValue)
    # ----------------------------------------------------------------------
    if shift_hz != 0.0:
        err = st7.St7SetNFAShift(uID, float(shift_hz))
        if err:
            raise RuntimeError(f"St7SetNFAShift failed: {err}")

    # ----------------------------------------------------------------------
    # Abilita o disabilita il calcolo dei fattori di partecipazione
    # API: St7SetNFAModeParticipationCalculate(uID, bOnOff)
    # ----------------------------------------------------------------------
    err = st7.St7SetNFAModeParticipationCalculate(
        uID,
        st7.btTrue if calc_participation else st7.btFalse
    )
    if err:
        raise RuntimeError(f"St7SetNFAModeParticipationCalculate failed: {err}")

    # ----------------------------------------------------------------------
    # Esegue il solver per l'analisi di frequenza naturale
    # API: St7RunSolver(uID, SolverType, RunMode, WaitFlag)
    #   - SolverType = stNaturalFrequency (analisi modale)
    #   - RunMode = smProgressRun (con finestra) o smNormalCloseRun (senza)
    #   - WaitFlag = btTrue per bloccare fino al termine
    # ----------------------------------------------------------------------
    mode = st7.smProgressRun if show_progress else st7.smNormalCloseRun
    err = st7.St7RunSolver(
        uID,
        st7.stNaturalFrequency,            # tipo solver = Natural Frequency
        mode,
        st7.btTrue if wait else st7.btFalse
    )
    if err:
        raise RuntimeError(f"St7RunSolver(NFA) failed: {err}")
