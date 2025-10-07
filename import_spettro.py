# import_spettro.py
# Obiettivo: creare una NUOVA tabella "Factor vs frequency/period" (ttVsFrequency),
#            rinominarla "design_spectre", impostare asse X = Period e unità fattore = g,
#            quindi caricare i punti (T, Sd/g) letti da TXT.

import os
import ctypes as C
import numpy as np
import re
import St7API as st7  # wrapper ufficiale Straus7

# === Config di default =====================================================
SPECTRUM_TXT = "spettro_ntc18.txt"   # TXT con due colonne: T[s]  Sd[g]
MODEL_UID    = 1                     # uID del modello
TABLE_ID     = 1                   # scegli un ID libero e positivo
TABLE_NAME   = b"design_spectre"     # nome desiderato della tabella (bytes)
# ===========================================================================
# Suggerimento: se 101 è occupato, cambia TABLE_ID o usa un parametro in run().


# ---------------------- util: stringa errore API --------------------------
def _api_error_text() -> str:
    buf = (C.c_char * 256)()
    code = st7.St7GetLastError()
    st7.St7GetAPIErrorString(code, buf, len(buf))
    return f"{code}: {buf.value.decode('ascii', 'ignore')}"


# --------------------------- gestione file --------------------------------
def _open_model(uID: int, model_path: str):
    """St7Init + St7OpenFile. Necessario prima di toccare le tabelle."""
    err = st7.St7Init()
    if err:
        raise RuntimeError(f"St7Init failed: {err}")
    scratch = os.path.dirname(model_path) or "."
    err = st7.St7OpenFile(uID, model_path.encode("utf-8"), scratch.encode("utf-8"))
    if err:
        raise RuntimeError(f"St7OpenFile failed: {err} ({_api_error_text()})")

def _close_model(uID: int):
    """Salva e chiude il file, poi rilascia l’API."""
    st7.St7SaveFile(uID)
    st7.St7CloseFile(uID)
    st7.St7Release()


# ------------------------------ I/O TXT -----------------------------------
def _read_txt(path: str):
    """Ritorna np.ndarray T[s], Sd[g] esattamente come nel file.
       Nessun ordinamento, nessun filtro, nessuna deduplicazione."""
    T, Sd = [], []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            s = ln.strip()
            if not s:
                continue
            # salta header semplici
            if s.startswith("T[") or s[0].isalpha():
                continue
            # parsing tollerante a virgole/; e spazi multipli
            s = s.replace(",", ".")
            s = re.sub(r"[;,\s]+", " ", s)
            parts = s.split()
            if len(parts) < 2:
                continue
            try:
                t = float(parts[0])
                sd = float(parts[1])
            except ValueError:
                continue
            if np.isfinite(t) and np.isfinite(sd):
                T.append(t)
                Sd.append(sd)

    T = np.asarray(T, dtype="d")
    Sd = np.asarray(Sd, dtype="d")
    if T.size == 0:
        raise ValueError("Spettro vuoto.")

    # DEBUG disattivato
    # for i, (t, sd) in enumerate(zip(T, Sd)):
    #     print(f"{i+1:03d}: T={t:.12g}  Sd={sd:.12g}")
    # print("Totale righe importate:", len(T))

    return T, Sd

# ------------------------------ TABLE API ---------------------------------
def _new_table_with_data(uID: int, table_id: int, name: bytes, T: np.ndarray, Sd: np.ndarray):
    """
    Crea *da zero* la tabella ttVsFrequency con i DATI già popolati.
    Questo evita l'errore 71 ("number of table entries is not valid") che può
    verificarsi creando la tabella con NumEntries=0 in alcune build.
      - Cancella eventuale tabella esistente con lo stesso ID
      - Chiama St7NewTableType con NumEntries = n e Doubles interlacciato
      - Imposta/forza il nome tabella
    """
    # elimina se esiste
    st7.St7DeleteTableType(uID, st7.ttVsFrequency, table_id)  # ignora esito

    n = int(T.size)
    if n <= 0:
        raise ValueError("Nessun dato da importare (n=0).")

    # buffer interlacciato [T1,Sd1, T2,Sd2, ...]
    xy = np.empty(2 * n, dtype="d")
    xy[0::2] = T
    xy[1::2] = Sd
    buf = (C.c_double * (2 * n))(*xy)

    # crea tabella con N righe già popolata
    err = st7.St7NewTableType(uID, st7.ttVsFrequency, table_id, n, name, buf)
    if err:
        raise RuntimeError(f"St7NewTableType failed: {err} ({_api_error_text()})")

    # imposta esplicitamente il nome (alcune build lo richiedono)
    err = st7.St7SetTableTypeName(uID, st7.ttVsFrequency, table_id, name)
    if err:
        raise RuntimeError(f"St7SetTableTypeName failed: {err} ({_api_error_text()})")

def _set_axis_and_units(uID: int, table_id: int):
    """
    Imposta la tabella come:
      - asse X = Period (ftPeriod)
      - unità fattore = Acceleration Response (g) (fuAccelResponseG)
    """
    err = st7.St7SetFrequencyPeriodTableType(uID, table_id, st7.ftPeriod)
    if err:
        raise RuntimeError(f"St7SetFrequencyPeriodTableType failed: {err} ({_api_error_text()})")
    err = st7.St7SetFrequencyPeriodTableUnits(uID, table_id, st7.fuAccelResponseG)
    if err:
        raise RuntimeError(f"St7SetFrequencyPeriodTableUnits failed: {err} ({_api_error_text()})")


# ------------------------------- ENTRYPOINT --------------------------------
def run(model_path: str,
        spectrum_txt: str = SPECTRUM_TXT,
        uID: int = MODEL_UID,
        table_id: int = TABLE_ID,
        table_name: bytes = TABLE_NAME):
    """
    Flusso richiesto:
      1) New table  → ttVsFrequency con TableID scelto (CREATA GIÀ CON I DATI)
      2) Set name   → 'design_spectre'
      3) Set type   → asse X = Period
      4) Set units  → Acceleration Response (g)
    """
    _open_model(uID, model_path)
    try:
        # Leggi e prepara i dati
        T, Sd = _read_txt(spectrum_txt)

        # 1) crea tabella GIÀ con i dati
        _new_table_with_data(uID, table_id, table_name, T, Sd)

        # 2)–4) imposta asse/Unità
        _set_axis_and_units(uID, table_id)

        out = {
            "table_id": table_id,
            "name": table_name.decode("ascii", "ignore"),
            "rows": int(T.size),
            "x_axis": "Period [s]",
            "units": "Acceleration Response (g)"
        }
    finally:
        _close_model(uID)
    return out


# Esecuzione diretta facoltativa
if __name__ == "__main__":
    # Esempio:
    # print(run(r"C:\Users\...\telaio_2D.st7"))
    pass
