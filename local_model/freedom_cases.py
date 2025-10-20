# freedom_cases.py                                                     # nome file
# Crea 9 Freedom Cases nel modello locale, uno per ciascuna             # scopo
# combinazione {DX,DY,DZ}×{3 nodi esterni}.                             # riepilogo

import ctypes as ct                                                     # tipi C
import St7API as st7                                                    # API Straus7

# ---------- utilità base ------------------------------------------------------

def _b(s: str) -> bytes:                                                # str -> bytes
    return s.encode("utf-8")                                            # codifica UTF-8

def _ck(rc: int, where: str):                                           # check codice errore
    if rc != 0:                                                         # 0 = OK
        buf = ct.create_string_buffer(st7.kMaxStrLen)                   # buffer messaggio
        st7.St7GetAPIErrorString(rc, buf, st7.kMaxStrLen)               # testo errore
        raise RuntimeError(f"{where}: {buf.value.decode('utf-8','ignore')}")  # eccezione

# ---------- API principale ----------------------------------------------------

def create_unit_disp_freedom_cases(                                     # funzione pubblica
    model_path: str,                                                    # percorso .st7 locale
    center_node_id: int,                                                # ID nodo centrale (lasciato libero)
    outer_node_ids: list[int],                                          # 3 ID nodi esterni (intermedi)
    start_fcase: int = 10                                               # ignorato: numerazione gestita da Straus7
) -> dict:                                                              # ritorna mappa {nome:numero}
    """
    Crea 9 freedom cases:
      - per ognuno dei 3 nodi in outer_node_ids impone DX=1, DY=1, DZ=1.
      - i due nodi esterni non target sono incastrati (6 DOF bloccati).
      - il nodo centrale resta libero.
    Ritorna: dict { "DX_nodeN": case_num, ... }.
    """
    DOF_IDX = {"DX": 0, "DY": 1, "DZ": 2}                               # indici DOF per array a 6

    if len(outer_node_ids) != 3:                                        # validazione input
        raise ValueError("outer_node_ids deve contenere esattamente 3 ID nodo")

    _ck(st7.St7Init(), "Init")                                          # avvia sessione API
    try:
        _ck(st7.St7OpenFile(1, _b(model_path), b""), "Open")            # apre il modello
        uID = 1                                                         # ID file Straus7
        out: dict[str, int] = {}                                        # mapping nome->numero case

        for nid in outer_node_ids:                                      # loop nodi esterni
            for dof_name, dof_i in DOF_IDX.items():                     # loop DX,DY,DZ
                case_name = f"{dof_name}_node{nid}"                     # es. "DX_node7"

                case_num_c = ct.c_long(0)                               # alloc long per ID case
                _ck(st7.St7NewFreedomCase(uID, ct.byref(case_num_c)),   # crea case -> riempie puntatore
                    "NewFreedomCase")
                case_num = int(case_num_c.value)                        # numero assegnato da Straus7

                _ck(st7.St7SetFreedomCaseName(uID, case_num, _b(case_name)),  # assegna nome case
                    f"SetFreedomCaseName {case_num}")

                R_fix = (ct.c_long * 6)(1,1,1, 1,1,1)                   # 6 DOF bloccati
                U_fix = (ct.c_double * 6)(0.0,0.0,0.0, 0.0,0.0,0.0)     # spostamenti imposti = 0

                for nid_fix in (n for n in outer_node_ids if n != nid): # blocca gli altri due nodi
                    _ck(st7.St7SetNodeRestraint6(uID, case_num, int(nid_fix), R_fix),
                        f"SetNodeRestraint6 node {nid_fix} case {case_num}")
                    _ck(st7.St7SetNodeDisplacement6(uID, case_num, int(nid_fix), U_fix),
                        f"SetNodeDisplacement6 node {nid_fix} case {case_num}")

                R_tgt = (ct.c_long * 6)(1,1,1, 1,1,1)                   # target vincolato su 6 DOF
                U_tgt = (ct.c_double * 6)(0.0,0.0,0.0, 0.0,0.0,0.0)     # vettore imposti
                U_tgt[dof_i] = 1.0                                      # unità sul DOF richiesto

                _ck(st7.St7SetNodeRestraint6(uID, case_num, int(nid), R_tgt),  # applica vincoli
                    f"SetNodeRestraint6 node {nid} case {case_num}")
                _ck(st7.St7SetNodeDisplacement6(uID, case_num, int(nid), U_tgt),# impone spostamento
                    f"SetNodeDisplacement6 node {nid} case {case_num}")

                # Nodo centrale: nessuna chiamata -> resta libero           # esplicito in commento

                out[case_name] = case_num                                # salva mapping per il chiamante

        _ck(st7.St7SaveFile(uID), "Save")                                # salva il modello
        return out                                                       # ritorna i numeri case
    finally:
        try:
            st7.St7CloseFile(1)                                          # chiude file
        finally:
            st7.St7Release()                                             # rilascia API
