# section_data.py                                                       # Nome modulo

# Estrae le geometrie delle sezioni BEAM da un file Straus7 (.st7)      # Descrizione
# e salva i risultati in CSV e JSON.                                     # Descrizione
# Usa BGL (Beam Geometry Library) quando disponibile per avere i raggi.  # Descrizione
# Esegue fallback alle "standard sections" se BGL non è presente.        # Descrizione

import os, json, ctypes as ct                                           # Import base

# Il percorso delle DLL è già aggiunto in main.py con os.add_dll_directory # Nota
import St7API as st7                                                    # Import API Straus7


def _ck(code, where=""):                                                # Helper per check errori
    if code != 0:                                                       # Se codice errore non nullo
        sb = ct.create_string_buffer(st7.kMaxStrLen)                    # Buffer per messaggio API
        st7.St7GetAPIErrorString(code, sb, st7.kMaxStrLen)              # Converte codice in stringa
        raise RuntimeError(f"{where}: {sb.value.decode('utf-8','ignore')}")  # Lancia eccezione leggibile


# Mappa: indice-array BGL -> nome quota per ciascuna forma               # Commento mappa
_BGL_MAP = {                                                             # Dizionario principale
    st7.bgISection: {                                                    # IPE/HE, ecc.
        0:"D", 1:"B1", 2:"B2", 3:"tw", 4:"tf1", 5:"tf2",                 # Altezza, basi, anima, ali
        6:"Rr1", 7:"Rr2", 8:"Rt1", 9:"Rt2", 10:"Rt3", 11:"Rt4",          # Raggi raccordo e terminali
        12:"alpha1", 13:"alpha2"                                         # Angoli eventuali
    },
    st7.bgTSection: {                                                    # Sezione a T
        0:"D", 1:"B", 2:"tw", 3:"tf", 4:"Rr", 5:"Rt1", 6:"Rt2", 7:"Rt3", # Quote principali + raggi
        8:"alpha1", 9:"alpha2", 10:"Rt1_", 11:"Rt2_", 12:"Rt3_", 13:"Rt4_", # Extra se presenti
        14:"alpha1_", 15:"alpha2_"                                       # Extra se presenti
    },
    st7.bgChannel: {                                                     # C a caldo
        0:"D", 1:"B1", 2:"B2", 3:"tw", 4:"tf1", 5:"tf2",                 # Quote principali
        6:"Rr1", 7:"Rr2", 8:"Rh1", 9:"Rh2"                               # Raggi raccordo/hook
    },
    st7.bgAngle: {                                                       # Angolare
        0:"D", 1:"B", 2:"tw", 3:"tf", 4:"Rr", 5:"Rh",                    # Quote principali
        6:"Rt1", 7:"Rt2", 8:"Rt3", 9:"Rt4", 10:"alpha1", 11:"alpha2"     # Raggi e angoli
    },
    st7.bgRectangularHollow: {                                           # RHS/SHS
        0:"D", 1:"B", 2:"tw", 3:"tf", 4:"Ri", 5:"Ro"                     # Spessori e raggi interno/esterno
    },
    st7.bgBulbFlat: {                                                    # Bulb flat
        0:"D", 1:"B", 2:"t", 3:"Rr", 4:"Rh", 5:"Rt1", 6:"Rt2", 7:"Rt3"   # Quote principali
    },
}

# Chiavi per le “standard sections” restituite da St7GetBeamSectionGeometry  # Commento
_STD_KEYS = ["D1","D2","D3","T1","T2","T3"]                                # Tre distanze e tre spessori


def _shape_name(shape):                                                   # Converte codice forma in stringa
    for k, v in {
        st7.bgISection:"bgISection", st7.bgTSection:"bgTSection",         # Associazioni codice->nome
        st7.bgChannel:"bgChannel", st7.bgAngle:"bgAngle",
        st7.bgRectangularHollow:"bgRectangularHollow", st7.bgBulbFlat:"bgBulbFlat"
    }.items():
        if shape == k:                                                    # Se match
            return v                                                      # Ritorna nome
    return str(int(shape))                                                # Fallback: numero come stringa


def _canonical_B(record):                                                 # Ricava larghezza unica B
    if "B" in record and record["B"]:                                     # Se B già presente e non nullo
        return record["B"]                                                # Restituisci
    b1 = record.get("B1", None); b2 = record.get("B2", None)              # Leggi B1 e B2 se esistono
    if b1 is None or b2 is None:                                          # Se manca uno dei due
        return None                                                       # Nessuna B canonica
    # Se B1 e B2 sono praticamente uguali, adotta B1 come B unica         # Criterio uguaglianza
    return b1 if abs(b1 - b2) <= 1e-9*max(1.0, abs(b1), abs(b2)) else None


def _as_float(x):                                                         # Cast sicuro a float
    try:
        return float(x)                                                   # Converte
    except Exception:
        return None                                                       # Fallback None


def export_section_data(model_path, out_csv=None, out_json=None, only_props=None):  # Funzione principale
    """
    model_path : path del file .st7                                       # Parametri docstring
    out_csv    : percorso CSV; se None salva accanto al .st7               # Parametri docstring
    out_json   : percorso JSON; se None salva accanto al .st7              # Parametri docstring
    only_props : lista/set di numeri proprietà da estrarre; None = tutte   # Parametri docstring
    return     : dict con percorsi file e dati                             # Parametri docstring
    """
    uID = 1                                                                # ID sessione modello
    data = {}                                                              # Dizionario risultati

    _ck(st7.St7Init(), "Init")                                             # Inizializza API
    try:
        # Apertura in sola lettura per evitare lock quando la GUI è aperta # Spiegazione apertura RO
        _ck(st7.St7OpenFileReadOnly(uID, model_path.encode("utf-8"), b""), "Open (read-only)")  # Open RO

        # Recupera conteggi proprietà; ci serve il numero di proprietà BEAM   # Spiegazione
        nums = (ct.c_long * st7.kMaxEntityTotals)()                        # Array conteggi
        last = (ct.c_long * st7.kMaxEntityTotals)()                        # Array “ultimo indice”
        _ck(st7.St7GetTotalProperties(uID, nums, last), "GetTotalProperties")  # Chiamata API
        n_beam = nums[st7.ipBeamPropTotal]                                 # Numero di beam properties

        prop_numbers = []                                                  # Lista numeri proprietà
        for idx in range(1, n_beam + 1):                                   # Itera sugli indici 1..n_beam
            pn = ct.c_long()                                               # Variabile di output
            _ck(st7.St7GetPropertyNumByIndex(uID, st7.ptBEAMPROP, idx, ct.byref(pn)),  # Num by index
                "GetPropertyNumByIndex")
            prop_numbers.append(int(pn.value))                             # Aggiungi numero proprietà

        if only_props:                                                     # Se filtro richiesto
            only = set(int(p) for p in only_props)                         # Normalizza a set di int
            prop_numbers = [p for p in prop_numbers if p in only]          # Filtra lista

        name_buf = ct.create_string_buffer(st7.kMaxStrLen)                 # Buffer nome proprietà

        for pnum in prop_numbers:                                          # Loop su ogni proprietà selezionata
            bt = ct.c_long()                                               # Tipo beam
            _ck(st7.St7GetBeamPropertyType(uID, pnum, ct.byref(bt)), "GetBeamPropertyType")  # Leggi tipo
            if bt.value != st7.btBeam:                                     # Escludi spring/cable/etc.
                continue                                                   # Salta proprietà non BEAM

            _ck(st7.St7GetPropertyName(uID, st7.ptBEAMPROP, pnum, name_buf, st7.kMaxStrLen), # Leggi nome
                "GetPropertyName")
            prop_name = name_buf.value.decode("utf-8", "ignore")           # Decodifica nome

            shape = ct.c_long()                                            # Codice forma BGL
            dims  = (ct.c_double * st7.kMaxBGLDimensions)()                # Array dimensioni BGL
            err = st7.St7GetBeamSectionGeometryBGL(uID, pnum, ct.byref(shape), dims)  # Prova BGL

            rec = {"prop_num": pnum, "prop_name": prop_name, "source": None, "shape": None}  # Record base

            if err == 0 and shape.value in _BGL_MAP:                       # Caso: BGL valido e mappato
                rec["source"] = "BGL"                                      # Indica origine BGL
                rec["shape"]  = _shape_name(shape.value)                   # Nome forma

                for idx, key in _BGL_MAP[shape.value].items():             # Itera mappa indici->nomi
                    val = _as_float(dims[idx])                             # Leggi valore double
                    if val is not None and val != 0.0:                     # Salva solo non nulli
                        rec[key] = val                                     # Inserisci nel record

                rec["B"] = rec.get("B", _canonical_B(rec))                 # Calcola B canonica se serve

            else:                                                          # Fallback: sezioni standard
                sec_type = ct.c_long()                                     # Codice tipo standard
                arr6 = (ct.c_double * 6)()                                 # Sei parametri standard
                _ck(st7.St7GetBeamSectionGeometry(uID, pnum, ct.byref(sec_type), arr6),  # Chiamata fallback
                    "GetBeamSectionGeometry")

                rec["source"] = "STANDARD"                                 # Origine standard
                rec["shape"]  = int(sec_type.value)                        # Codice forma numerico
                for i, k in enumerate(_STD_KEYS):                          # Mappa D1..T3
                    v = _as_float(arr6[i])                                 # Cast a float
                    if v is not None and v != 0.0:                         # Salva solo non nulli
                        rec[k] = v                                         # Inserisci

                if sec_type.value == st7.bsISection:                       # Heuristica per I standard
                    rec["B1"], rec["B2"], rec["D"] = rec.get("D1"), rec.get("D2"), rec.get("D3")  # Rimappa
                    rec["tw"], rec["tf1"], rec["tf2"] = rec.get("T1"), rec.get("T2"), rec.get("T3")  # Rimappa
                    rec["B"] = _canonical_B(rec)                           # Calcola B canonica

            data[pnum] = rec                                               # Registra record per prop_num

        if out_csv is None:                                                # Se CSV non passato
            out_csv = os.path.join(os.path.dirname(model_path), "section_data.csv")  # Default path
        if out_json is None:                                               # Se JSON non passato
            out_json = os.path.join(os.path.dirname(model_path), "section_data.json")  # Default path

        header = [                                                         # Ordine colonne CSV
            "prop_num","prop_name","source","shape",
            "D","B","B1","B2","tw","tf","tf1","tf2",
            "Rr","Rr1","Rr2","Rt1","Rt2","Rt3","Rt4",
            "Ri","Ro","Rh","Rh1","Rh2",
            "alpha1","alpha2"
        ]

        with open(out_csv, "w", encoding="utf-8") as f:                    # Apertura CSV
            f.write(";".join(header) + "\n")                               # Riga intestazione
            for p in sorted(data):                                         # Ordina per numero prop
                rec = data[p]                                              # Record corrente
                row = []                                                   # Inizia riga CSV
                for k in header:                                           # Per ogni colonna
                    v = rec.get(k, "")                                     # Valore o stringa vuota
                    row.append(str(v if v is not None else ""))            # Converte a stringa
                f.write(";".join(row) + "\n")                              # Scrive riga

        with open(out_json, "w", encoding="utf-8") as f:                   # Apertura JSON
            json.dump(data, f, ensure_ascii=False, indent=2)               # Serializza con indentazione

        return {"csv": out_csv, "json": out_json, "data": data}            # Ritorna percorsi e dati

    finally:                                                               # Chiusura garantita
        try:
            st7.St7CloseFile(uID)                                          # Chiudi il file .st7
        finally:
            st7.St7Release()                                               # Rilascia le API
