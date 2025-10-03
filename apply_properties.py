# apply_properties.py
# Imposta due proprietà BEAM (colonne=prop_col, travi=prop_beam) su un modello Straus7:
# - Materiale: modulo E, Poisson ν, densità ρ passati dal main (G derivato da ν)
# - Sezioni: lette dalla libreria di sezioni (.BSL) per nome (accetta anche abbreviazioni, es. "HE 160 A", "IPE 270")
#
# NOTE API (da manuale):
#   St7SetLibraryPath(char* LibraryPath)
#   St7GetNumLibraries(long LibraryType, long* NumLibraries)
#   St7GetLibraryName(long LibraryType, long LibraryID, char* LibraryName, long MaxStringLen)
#   St7GetNumLibraryItems(long LibraryType, long LibraryID, long* NumItems)
#   St7GetLibraryItemName(long LibraryType, long LibraryID, long ItemID, char* ItemName, long MaxStringLen)
#   St7AssignLibraryBeamSection(uID, PropNum, LibraryID, ItemID, long Flags[4])
#   St7NewBeamProperty(uID, PropNum, btBeam, char* PropName)
#   St7SetBeamShearModulusMode(uID, PropNum, smUsePoissonsRatio)
#   St7SetBeamMaterialData(uID, PropNum, double* Data)
#
# Requisiti:
#   - St7API.py accessibile
#   - DLL visibile (Bin64 nel PATH di caricamento)
#   - Il file .st7 esiste già

import os
import ctypes as ct

# Rende visibile la DLL Straus7 (Python 3.8+)
os.add_dll_directory(r"C:\Program Files\Straus7 R31\Bin64")
from St7API import *

# ---------------- utilità base ------------------------------------------------
def _b(s: str) -> bytes:
    return s.encode("utf-8")

def check(rc: int):
    if rc != 0:
        raise RuntimeError(f"St7 error {rc}")

def _decode(b: bytes) -> str:
    # prova UTF-8, poi cp1252, infine latin-1, ignorando byte non mappabili
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return b.decode("cp1252")
        except UnicodeDecodeError:
            return b.decode("latin-1", errors="ignore")

# normalizza stringa: rimuove spazi, trattini e riferimenti “BS/EN/BSL”, case-insensitive
def _norm(s: str) -> str:
    t = s.lower().replace('-', '').replace(' ', '')
    for k in ('bs', 'en', 'bsl'):
        t = t.replace(k, '')
    # uniforma “hea” e “he” per tollerare varianti
    t = t.replace('hea', 'he')
    return t

# ---------------- ricerca sezioni .BSL (permissiva) ---------------------------
def _find_item_in_beam_section_lib(item_name: str):
    """
    Cerca una sezione BEAM nelle librerie .BSL caricate (lbBeamSection).
    Accetta abbreviazioni/varianti: match per SOTTOSTRINGA su stringhe normalizzate.
    Ritorna (LibraryID, ItemID). Se non trova, alza errore con suggerimenti.
    """
    target = _norm(item_name)

    nlib = ct.c_long()
    check(St7GetNumLibraries(lbBeamSection, ct.byref(nlib)))

    lib_name_buf = ct.create_string_buffer(512)
    item_name_buf = ct.create_string_buffer(512)
    suggestions = []

    for lib_id in range(1, nlib.value + 1):
        # nome libreria disponibile (informativo; usa decode tollerante)
        check(St7GetLibraryName(lbBeamSection, lib_id, lib_name_buf, ct.sizeof(lib_name_buf)))
        _ = _decode(lib_name_buf.value)

        # numero di voci nella libreria corrente
        nitems = ct.c_long()
        check(St7GetNumLibraryItems(lbBeamSection, lib_id, ct.byref(nitems)))

        for item_id in range(1, nitems.value + 1):
            check(
                St7GetLibraryItemName(
                    lbBeamSection, lib_id, item_id, item_name_buf, ct.sizeof(item_name_buf)
                )
            )
            raw = _decode(item_name_buf.value)
            norm = _norm(raw)

            # match per sottostringa in entrambe le direzioni
            if target in norm or norm in target:
                return lib_id, item_id

            # raccogli qualche esempio utile
            up = raw.upper()
            if any(k in up for k in ("HE", "HEA", "IPE")) and len(suggestions) < 24:
                suggestions.append(raw)

    hint = f" | Esempi: {', '.join(sorted(set(suggestions))[:12])}" if suggestions else ""
    raise RuntimeError(f"Sezione '{item_name}' non trovata nelle librerie .BSL{hint}")


# ---------------- materiale proprietà BEAM -----------------------------------
def _set_beam_material(uID: int, prop: int, E: float, nu: float, rho: float):
    """
    Imposta E, ν, ρ per una proprietà BEAM. G calcolato automaticamente da ν.
    Indici usati: ipBeamModulus, ipBeamPoisson, ipBeamDensity (wrapper St7API.py).
    """
    check(St7SetBeamShearModulusMode(uID, prop, smUsePoissonsRatio))  # usa ν per G
    mat = (ct.c_double * 9)()
    mat[ipBeamModulus] = E
    mat[ipBeamPoisson] = nu
    mat[ipBeamDensity] = rho
    check(St7SetBeamMaterialData(uID, prop, mat))

# ---------------- API principale ---------------------------------------------
def apply_properties(
    model_path: str,
    # materiale dal main:
    E: float,                # MPa
    nu: float,               # [-]
    rho: float,              # kg/m^3
    # sezioni da libreria .BSL:
    section_columns: str,    # es. "HE 160 A" oppure nome completo
    section_beams: str,      # es. "IPE 270"  oppure nome completo
    prop_col: int = 1,
    prop_beam: int = 2,
    library_dir_bsl: str = r"C:\ProgramData\Straus7 R31\Data",
    uID: int = 1,
):
    r"""
    model_path      : percorso .st7
    E, nu, rho      : proprietà elastiche per entrambe le proprietà BEAM
    section_columns : nome sezione colonne (accetta abbreviazioni)
    section_beams   : nome sezione travi   (accetta abbreviazioni)
    prop_col        : ID proprietà colonne
    prop_beam       : ID proprietà travi
    library_dir_bsl : cartella contenente i file .BSL (puntare direttamente a ...\BSL)
    """

    p = os.path.abspath(model_path)

    # apri modello
    check(St7Init())
    check(St7OpenFile(uID, _b(p), b""))

    # imposta cartella radice delle librerie (…\Data). Da qui Straus7 vede .BSL, .MAT, ecc.
    check(St7SetLibraryPath(_b(os.path.abspath(library_dir_bsl))))
    # diagnostica: quante librerie di sezioni sono caricate
    cnt = ct.c_long()
    check(St7GetNumLibraries(lbBeamSection, ct.byref(cnt)))
    if cnt.value == 0:
        raise RuntimeError("0 librerie di tipo 'lbBeamSection' caricate. Verifica il percorso: deve essere ...\\Data")

    # crea/assicurati delle proprietà BEAM
    check(St7NewBeamProperty(uID, prop_col,  btBeam, _b("Columns")))
    check(St7NewBeamProperty(uID, prop_beam, btBeam, _b("Beams")))

    # materiale su entrambe le proprietà
    _set_beam_material(uID, prop_col,  E, nu, rho)
    _set_beam_material(uID, prop_beam, E, nu, rho)

    # flags per import sezione: [ImportMaterial=0, CalcNulls=1, ImportDamping=0, ReplaceName=1]
    flags = (ct.c_long * 4)(0, 1, 0, 1)

    # sezione colonne
    lib_col, id_col = _find_item_in_beam_section_lib(section_columns)
    check(St7AssignLibraryBeamSection(uID, prop_col, lib_col, id_col, flags))

    # sezione travi
    lib_beam, id_beam = _find_item_in_beam_section_lib(section_beams)
    check(St7AssignLibraryBeamSection(uID, prop_beam, lib_beam, id_beam, flags))

    # salva e chiudi
    check(St7SaveFile(uID))
    check(St7CloseFile(uID))

    return {
        "model_path": p,
        "E": E, "nu": nu, "rho": rho,
        "section_columns": section_columns,
        "section_beams": section_beams,
        "prop_col": prop_col,
        "prop_beam": prop_beam,
        "library_dir_bsl": os.path.abspath(library_dir_bsl),
        "lib_id_columns": lib_col,
        "item_id_columns": id_col,
        "lib_id_beams": lib_beam,
        "item_id_beams": id_beam,
    }
