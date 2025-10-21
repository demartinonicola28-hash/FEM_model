# freedom_cases.py
# Crea 9 Freedom Cases per i 3 nodi periferici:
#   "node<ID>_DX", "node<ID>_DY", "node<ID>_DZ"
# In ciascun case impone SOLO lo spostamento unitario (1.0) del DOF indicato
# sul nodo target. Tutto il resto rimane libero. Al termine elimina il case
# di default se presente.

import ctypes as ct
from typing import List, Dict
import St7API as st7

# -------------------- utilità base -------------------------------------------

def _b(s: str) -> bytes:                         # str -> UTF-8 bytes
    return s.encode("utf-8")

def _ck(rc: int, where: str):                    # check codice ritorno API
    if rc != 0:
        buf = ct.create_string_buffer(st7.kMaxStrLen)
        st7.St7GetAPIErrorString(rc, buf, st7.kMaxStrLen)
        raise RuntimeError(f"{where}: {buf.value.decode('utf-8','ignore')}")

def _find_case_by_name(uID: int, name: str) -> int:
    """Ritorna il numero del Freedom Case con nome 'name', 0 se assente."""
    n = ct.c_long()
    _ck(st7.St7GetNumFreedomCase(uID, ct.byref(n)), "GetNumFreedomCase")
    tmp = ct.create_string_buffer(st7.kMaxStrLen)
    for i in range(1, n.value + 1):
        _ck(st7.St7GetFreedomCaseName(uID, i, tmp, st7.kMaxStrLen), f"GetFreedomCaseName {i}")
        if tmp.value.decode("utf-8", "ignore") == name:
            return i
    return 0

def _new_case(uID: int, name: str) -> int:
    """Crea il Freedom Case col nome dato. Se esiste, lo riusa."""
    num = _find_case_by_name(uID, name)
    if num:
        return num
    _ck(st7.St7NewFreedomCase(uID, _b(name)), f"NewFreedomCase '{name}'")
    num = _find_case_by_name(uID, name)
    if not num:
        raise RuntimeError(f"Freedom case '{name}' non trovato dopo la creazione")
    return num

def _clear_case(uID: int, case_num: int):
    """Rende tutti i nodi liberi nel freedom case specificato."""
    tot = ct.c_long()
    _ck(st7.St7GetTotal(uID, st7.tyNODE, ct.byref(tot)), "GetTotal NODE")
    R0 = (ct.c_long * 6)(0, 0, 0, 0, 0, 0)         # nessun DOF vincolato
    U0 = (ct.c_double * 6)(0, 0, 0, 0, 0, 0)       # spostamenti imposti = 0
    for nid in range(1, tot.value + 1):
        # firma corretta: (uID, NodeNum, CaseNum, UCSId, long* Status, double* Doubles)
        _ck(st7.St7SetNodeRestraint6(uID, nid, case_num, 1, R0, U0),
            f"Clear node {nid} case {case_num}")

def _try_delete_case(uID: int, case_num: int):
    """Prova a cancellare un case; se l'API non esiste, lo svuota e lo rinomina."""
    try:
        fn = getattr(st7, "St7DeleteFreedomCase")
    except AttributeError:
        # fallback: svuota e rinomina
        _clear_case(uID, case_num)
        _ck(st7.St7SetFreedomCaseName(uID, case_num, _b("_deleted")), f"Rename case {case_num}")
        return
    _ck(fn(uID, case_num), f"DeleteFreedomCase {case_num}")

# -------------------- API principale -----------------------------------------

def create_unit_disp_freedom_cases(
    model_path: str,
    outer_node_ids: List[int],        # i 3 nodi periferici da usare
    delete_default: bool = True
) -> Dict[str, int]:
    """
    Crea 9 freedom case:
      per ciascun nodo in 'outer_node_ids' -> node<ID>_{DX,DY,DZ}
    Nel case si impone ONLY 1.0 sul DOF indicato del nodo target.
    Ritorna: {case_name: case_num}.
    """
    if len(outer_node_ids) != 3:
        raise ValueError("Servono esattamente 3 nodi periferici.")

    # mapping nome DOF -> indice 0..5 (DX,DY,DZ,RX,RY,RZ)
    DOF_IDX = {"DX": 0, "DY": 1, "DZ": 2}

    _ck(st7.St7Init(), "Init")
    try:
        _ck(st7.St7OpenFile(1, _b(model_path), b""), "Open")
        uID = 1

        result: Dict[str, int] = {}

        # crea/riusa i 9 case e imposta il vincolo unitario sul nodo target
        for nid in map(int, outer_node_ids):
            for dof_name, dof_i in DOF_IDX.items():
                case_name = f"node{nid}_{dof_name}"           # es. "node7_DX"
                case_num  = _new_case(uID, case_name)         # crea se assente
                _clear_case(uID, case_num)                    # nessun vincolo residuo

                # prepara vettori 6 DOF: solo il dof richiesto è "prescribed" = 1.0
                R = (ct.c_long * 6)(0, 0, 0, 0, 0, 0)
                U = (ct.c_double * 6)(0, 0, 0, 0, 0, 0)
                R[dof_i] = 1
                U[dof_i] = 1.0

                # UCSId = 1 (globale). Tutto il resto resta libero.
                _ck(st7.St7SetNodeRestraint6(uID, nid, case_num, 1, R, U),
                    f"SetNodeRestraint6 node {nid} case {case_num}")

                result[case_name] = case_num

        # elimina il case di default, se richiesto e se esiste
        if delete_default:
            n = ct.c_long()
            _ck(st7.St7GetNumFreedomCase(uID, ct.byref(n)), "GetNumFreedomCase")
            # euristica: il "default" è spesso il case 1 e di nome diverso dai nostri
            if n.value >= 1:
                name_buf = ct.create_string_buffer(st7.kMaxStrLen)
                _ck(st7.St7GetFreedomCaseName(uID, 1, name_buf, st7.kMaxStrLen), "GetFreedomCaseName 1")
                name1 = name_buf.value.decode("utf-8", "ignore")
                if name1 not in result:   # non è uno dei nostri
                    _try_delete_case(uID, 1)

        _ck(st7.St7SaveFile(uID), "Save")
        return result
    finally:
        try:
            st7.St7CloseFile(1)
        finally:
            st7.St7Release()
