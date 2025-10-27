# import_tables.py
import os
import glob
import ctypes as ct

# Assicurati che St7API sia importabile
# (main.py aggiunge già la directory DLL al path di sistema)
try:
    import St7API as st7
except ImportError:
    print("ERRORE: Impossibile importare St7API. Assicurati che sia nel path.")
    # Solleva un errore per fermare lo script se l'API non è trovata
    raise

# Importa la funzione 'ck' per il controllo errori
try:
    from analysis.ltd_analysis import ck
except ImportError:
    print("ATTENZIONE: Funzione 'ck' non trovata. Gli errori API non verranno controllati.")
    def ck(result, *args):
        if result != 0:
            print(f"Errore API non gestito (codice {result}) in: {args}")
        pass

# --- COSTANTE API ---
# Dalla documentazione (image_c9a8ba.png), la costante corretta 
# per "Factor vs time" è 'ttVsTime'.
try:
    TABLE_TYPE_FACTOR_VS_TIME = st7.ttVsTime
except (AttributeError, NameError):
    print("="*50)
    print("ERRORE CRITICO: Impossibile trovare la costante 'st7.ttVsTime'.")
    print("                Assicurati che 'St7API as st7' sia importato correttamente.")
    print("                Lo script non può continuare senza questa costante.")
    print("="*50)
    # Ferma l'esecuzione se la costante non può essere trovata
    raise ImportError("Costante API richiesta 'st7.ttVsTime' non trovata.")
# --------------------


def run_import_disp_time_tables(model_path, disp_time_folder):
    """
    Importa tutti i file .txt dalla cartella disp_time come tabelle
    "Factor vs Time" (usando st7.ttVsTime) nel modello Straus7 specificato.
    
    Args:
        model_path (str): Percorso completo a 'local_model.st7'.
        disp_time_folder (str): Percorso completo alla cartella 'disp_time'
                                 che contiene i file .txt.
    """
    
    print(f"\nInizio importazione tabelle Factor vs Time in: {os.path.basename(model_path)}")
    
    if not os.path.exists(model_path):
        print(f"ERRORE: File modello non trovato: {model_path}")
        return
        
    if not os.path.exists(disp_time_folder):
        print(f"ERRORE: Cartella disp_time non trovata: {disp_time_folder}")
        return

    txt_files = glob.glob(os.path.join(disp_time_folder, "*.txt"))
    if not txt_files:
        print(f"ATTENZIONE: Nessun file .txt trovato in {disp_time_folder}. Salto importazione tabelle.")
        return

    print(f"Trovati {len(txt_files)} file .txt da importare (es. {os.path.basename(txt_files[0])})...")

    uID = 1 # ID modello per questa sessione API
    
    ck(st7.St7Init(), "Init API per import tabelle")
    try:
        ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), f"Open local model {model_path}")
        
        current_table_id = 1 
        
        for file_path in txt_files:
            table_name = os.path.splitext(os.path.basename(file_path))[0]
            data_xy = []
            num_entries = 0
            
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                time_val = float(parts[0])
                                factor_val = float(parts[1])
                                data_xy.append(time_val)
                                data_xy.append(factor_val)
                                num_entries += 1
                            except ValueError:
                                print(f"  - Ignorata riga non numerica in {table_name}: '{line.strip()}'")
                
                if num_entries == 0:
                    print(f"  - File '{table_name}.txt' è vuoto o malformato. Saltato.")
                    continue
                    
                doubles_array = (ct.c_double * len(data_xy))(*data_xy)
                
                # Chiama l'API con la costante corretta
                ck(st7.St7NewTableType(
                    uID,
                    TABLE_TYPE_FACTOR_VS_TIME, # <-- Ora usa st7.ttVsTime
                    current_table_id,
                    num_entries,
                    table_name.encode('utf-8'),
                    doubles_array
                ), f"Creazione tabella '{table_name}'")
                
                print(f"  - Tabella '{table_name}' (ID: {current_table_id}) creata con {num_entries} righe.")
                current_table_id += 1

            except Exception as e:
                print(f"  - ERRORE durante elaborazione file '{file_path}': {e}")
        
        if current_table_id > 1:
            ck(st7.St7SaveFile(uID), "Salvataggio modello locale con nuove tabelle")
        
    finally:
        try:
            ck(st7.St7CloseFile(uID), "Close local model")
        finally:
            st7.St7Release()
            
    print("Importazione tabelle Factor vs Time completata.")