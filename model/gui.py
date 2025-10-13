# gui.py  (carichi input in kN/m²)

import os, ctypes as ct, tkinter as tk
from tkinter import ttk, messagebox

# Caricamento opzionale di Pillow (per scalare immagini con qualità migliore)
try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

# Rende visibile a Python la cartella dei DLL di Straus7
os.add_dll_directory(r"C:\Program Files\Straus7 R31\Bin64")
from St7API import *

# Utility: stringa -> bytes per le funzioni C dell’API
def _b(s:str)->bytes: 
    """Converte str in bytes UTF-8 per chiamate St7."""
    return s.encode("utf-8")

# Gestione errori API St7
def _check(rc:int):
    """Alza un'eccezione Python con il testo dell'errore St7 se rc != 0."""
    if rc!=0:
        buf=(ct.c_char*256)()
        try:
            St7GetAPIErrorString(rc,buf,256)
            msg=buf.value.decode("utf-8","ignore")
        except Exception:
            msg=""
        raise RuntimeError(f"St7 error {rc}: {msg}")

# Lettura di tutte le sezioni trave "British" presenti nella libreria di Straus7
def _load_all_beam_sections_british(library_root:str)->list[str]:
    """Legge le sezioni trave dalla libreria di Straus7 e filtra quelle 'BS EN'."""
    _check(St7Init())
    _check(St7SetLibraryPath(_b(os.path.abspath(library_root))))
    nlib=ct.c_long()
    _check(St7GetNumLibraries(lbBeamSection, ct.byref(nlib)))
    item_buf=ct.create_string_buffer(512)
    out=[]
    for lib_id in range(1, nlib.value+1):
        nitems=ct.c_long()
        _check(St7GetNumLibraryItems(lbBeamSection, lib_id, ct.byref(nitems)))
        for item_id in range(1, nitems.value+1):
            _check(St7GetLibraryItemName(lbBeamSection, lib_id, item_id, item_buf, ct.sizeof(item_buf)))
            s=item_buf.value.decode("utf-8", errors="ignore")
            su=s.upper()
            if "BS EN" in su or su.startswith("BS EN -"):
                out.append(s)
    return sorted(set(out))

# Dizionario di famiglie per filtrare le sezioni
FAMILY_FILTERS={
    "HE (HE/HEA/HEB/HEM)":[" BS EN - HE "," HE "," HEA "," HEB "," HEM "],
    "IPE":[" BS EN - IPE "," IPE "],
    "UPN (canali)":[" UPN "," PFC "],
    "L (angolari)":[" EQUAL ANGLES "," ANGLE "," L "],
    "Tutte (British)":[]
}

def _filter_by_family(items, family):
    """Ritorna solo le sezioni compatibili con la famiglia scelta; se vuoto, ritorna l'intera lista."""
    toks=FAMILY_FILTERS.get(family, [])
    if not toks:
        return items
    up=[(s,s.upper()) for s in items]
    res=[s for s,u in up if any(tok in u for tok in toks)]
    return res or items


def run_gui(image_path: str = r"C:/Users/demnic15950/Downloads/FEM_model/utils/geometry_scheme.png") -> dict | None:
    """
    Crea e mostra la GUI per l’input dei dati.
    Ritorna un dict con i valori inseriti se l’utente preme OK, altrimenti None.
    """
    # Carica l'elenco completo di sezioni da Straus7; se fallisce usa un fallback ridotto
    try:
        ALL = _load_all_beam_sections_british(r"C:\ProgramData\Straus7 R31\Data")
    except Exception:
        ALL = [
            "BS EN - HE 160 A - BS EN 10365-2017 BSL",
            "BS EN - HE 180 A - BS EN 10365-2017 BSL",
            "BS EN - IPE 240 - BS EN 10365-2017 BSL",
            "BS EN - IPE 270 - BS EN 10365-2017 BSL",
        ]

    # Funzione interna: aggiorna la combobox "sezione" in base alla combobox "famiglia"
    # Nota: definita QUI dentro così può usare direttamente la variabile ALL
    def _update_cb_sections(cb_family: ttk.Combobox, cb_section: ttk.Combobox):
        """
        Legge la famiglia selezionata, filtra ALL con _filter_by_family
        e popola la combobox delle sezioni con il primo valore selezionato.
        """
        fam = cb_family.get()
        vals = _filter_by_family(ALL, fam)
        cb_section.configure(values=vals)
        if vals:
            cb_section.current(0)
        else:
            cb_section.set("")

    # --- finestra principale ---
    root = tk.Tk()
    root.title("Input Dati della Struttura")
    root.geometry("1200x850")   # larghezza x altezza
    # Imposta l'icona della finestra
    root.iconbitmap(r"C:\Users\demnic15950\Downloads\FEM_model\utils\icona.ico")  # percorso icona

    PAD = {"padx": 10, "pady": 6}
    root.columnconfigure(0, weight=0, minsize=400)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)

    LABEL_W = 25
    def _row(parent, r, label_text, widget):
        """Utility layout: etichetta a sinistra, widget a destra nella riga r."""
        ttk.Label(parent, text=label_text, width=LABEL_W, anchor="e").grid(row=r, column=0, sticky="e", **PAD)
        widget.grid(row=r, column=1, sticky="ew", **PAD)

    left = tk.Frame(root); left.grid(row=0, column=0, sticky="nsew"); left.columnconfigure(0, weight=1)

    # --- Geometria ---
    fg = ttk.LabelFrame(left, text="Geometria")
    fg.grid(row=0, column=0, sticky="nsew", **PAD); fg.columnconfigure(1, weight=1)
    e_h   = ttk.Entry(fg); e_h.insert(0, "3.50")
    e_L   = ttk.Entry(fg); e_L.insert(0, "5.00")
    e_np  = ttk.Entry(fg); e_np.insert(0, "2")
    e_off = ttk.Entry(fg); e_off.insert(0, "1.50")
    _row(fg, 0, "Altezza interpiano [m]", e_h)
    _row(fg, 1, "Luce trave [m]",         e_L)
    _row(fg, 2, "Numero piani",           e_np)
    _row(fg, 3, "Offset giunti [m]",      e_off)

    # --- Materiale ---
    fm = ttk.LabelFrame(left, text="Materiale (acciaio)")
    fm.grid(row=1, column=0, sticky="nsew", **PAD); fm.columnconfigure(1, weight=1)

    # Proprietà meccaniche acciai standard
    STEELS = {
        "S 275": {"fy": 270, "fu": 430},
        "S 355": {"fy": 355, "fu": 510},
        "S 450": {"fy": 440, "fu": 550},
    }

    cb_acc = ttk.Combobox(fm, state="readonly", values=list(STEELS.keys()))
    cb_acc.set("S 355")

    e_E   = ttk.Entry(fm);  e_E.insert(0, "206000")
    e_nu  = ttk.Entry(fm);  e_nu.insert(0, "0.30")
    e_rho = ttk.Entry(fm);  e_rho.insert(0, "7850")

    # fy, fu in sola lettura; γM0 editabile
    e_fy = ttk.Entry(fm, state="readonly")
    e_fu = ttk.Entry(fm, state="readonly")
    e_gamma_M0 = ttk.Entry(fm); e_gamma_M0.insert(0, "1.05")

    def _update_strengths(event=None):
        """Aggiorna fy e fu quando cambia la classe di acciaio."""
        g = cb_acc.get()
        fy = STEELS[g]["fy"]; fu = STEELS[g]["fu"]
        e_fy.config(state="normal"); e_fu.config(state="normal")
        e_fy.delete(0, "end"); e_fu.delete(0, "end")
        e_fy.insert(0, str(fy)); e_fu.insert(0, str(fu))
        e_fy.config(state="readonly"); e_fu.config(state="readonly")

    cb_acc.bind("<<ComboboxSelected>>", _update_strengths)

    # Layout materiale
    _row(fm, 0, "Acciaio", cb_acc)
    _row(fm, 1, "fy [MPa]",  e_fy)
    _row(fm, 2, "fu [MPa]",  e_fu)
    _row(fm, 3, "E [MPa]",   e_E)
    _row(fm, 4, "ν [-]",     e_nu)
    _row(fm, 5, "ρ [kg/m³]", e_rho)
    _row(fm, 7, "γᴍ₀ [-]", e_gamma_M0)
    _update_strengths()  # inizializza fy/fu

    # --- Sezioni ---
    fs = ttk.LabelFrame(left, text="Sezioni (BS EN)")
    fs.grid(row=2, column=0, sticky="nsew", **PAD); fs.columnconfigure(1, weight=1)

    # Colonne: famiglia + sezione (sezione aggiornata dinamicamente)
    cb_he_fam = ttk.Combobox(fs, state="readonly", values=list(FAMILY_FILTERS.keys()))
    cb_he_fam.set("HE (HE/HEA/HEB/HEM)")
    _row(fs, 0, "Famiglia colonne", cb_he_fam)

    cb_he = ttk.Combobox(fs, state="readonly")
    _row(fs, 1, "Sezione colonne", cb_he)

    # Travi: famiglia + sezione (sezione aggiornata dinamicamente)
    cb_ipe_fam = ttk.Combobox(fs, state="readonly", values=list(FAMILY_FILTERS.keys()))
    cb_ipe_fam.set("IPE")
    _row(fs, 2, "Famiglia travi", cb_ipe_fam)

    cb_ipe = ttk.Combobox(fs, state="readonly")
    _row(fs, 3, "Sezione travi", cb_ipe)

    # Binding: al cambio famiglia aggiorna le rispettive sezioni
    cb_he_fam.bind("<<ComboboxSelected>>", lambda e: _update_cb_sections(cb_he_fam, cb_he))
    cb_ipe_fam.bind("<<ComboboxSelected>>", lambda e: _update_cb_sections(cb_ipe_fam, cb_ipe))

    # Popolamento iniziale delle combobox sezione coerenti con le famiglie preimpostate
    _update_cb_sections(cb_he_fam, cb_he)
    _update_cb_sections(cb_ipe_fam, cb_ipe)

    # --- Carichi superficiali (in kN/m²) ---
    fl = ttk.LabelFrame(left, text="Carichi distribuiti [kN/m²]")
    fl.grid(row=3, column=0, sticky="nsew", padx=10, pady=10); fl.columnconfigure(1, weight=1)

    def _e(parent, r, txt, defv):
        """Utility per creare una entry con valore di default."""
        e = ttk.Entry(parent); e.insert(0, defv); _row(parent, r, txt, e); return e

    # Default coerenti con i valori precedenti su L=5 m:
    e_g2_int_m2  = _e(fl, 0, "G2 piani interni", "3.50")
    e_g2_roof_m2 = _e(fl, 1, "G2 copertura",         "3.50")
    e_q_int_m2   = _e(fl, 2, "Q  piani interni", "3.00")
    e_q_roof_m2  = _e(fl, 3, "Q  copertura",         "0.40")

    note_label = ttk.Label(fl, text="(carico verso il basso con segno positivo)",
                       font=("TkDefaultFont", 8, "italic"), foreground="gray")
    note_label.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=(4, 0))

    # --- Pulsanti OK/Annulla e raccolta risultati ---
    fbtn = ttk.Frame(left); fbtn.grid(row=4, column=0, sticky="e", padx=10, pady=20)
    res = {"ok": False}

    def _cancel(event=None):
        """Chiude la finestra senza salvare."""
        res.clear(); res["ok"] = False; root.destroy()

    def on_ok():
        """Valida e raccoglie i dati dalla GUI nel dict 'res', poi chiude."""
        try:
            res.update({
                "h_story": float(e_h.get()), "span": float(e_L.get()),
                "n_floors": int(e_np.get()), "offset": float(e_off.get()),
                "steel_grade": cb_acc.get(),
                "fy": float(e_fy.get()),
                "fu": float(e_fu.get()),
                "E": float(e_E.get()),
                "nu": float(e_nu.get()),
                "rho": float(e_rho.get()),
                "gamma_M0":float(e_gamma_M0.get()),
                "section_columns": cb_he.get().strip(),
                "section_beams": cb_ipe.get().strip(),
                # superfici in kN/m²
                "G2_int_kNm2":  float(e_g2_int_m2.get()),
                "G2_roof_kNm2": float(e_g2_roof_m2.get()),
                "Q_int_kNm2":   float(e_q_int_m2.get()),
                "Q_roof_kNm2":  float(e_q_roof_m2.get()),
            })
            res["ok"] = True
            root.destroy()
        except Exception as ex:
            messagebox.showerror("Errore input", f"Controlla i valori.\n{ex}")

    ttk.Button(fbtn, text="Annulla", command=_cancel).grid(row=0, column=0, padx=10)
    ttk.Button(fbtn, text="OK", command=on_ok).grid(row=0, column=1, padx=10)
    root.protocol("WM_DELETE_WINDOW", _cancel); root.bind("<Escape>", _cancel)

    # --- Pannello immagine a destra ---
    right = tk.Frame(root)
    right.grid(row=0, column=1, sticky="nsew")
    right.rowconfigure(0, weight=1)
    right.columnconfigure(0, weight=1)

    # Cornice bianca fissa che contiene l'immagine
    IMG_W, IMG_H = 2000, 1500  # spazio totale bianco
    frame_img = tk.Frame(right, width=IMG_W, height=IMG_H, bg="white", relief="solid", bd=1)
    frame_img.grid(row=0, column=0, padx=12, pady=12)
    frame_img.grid_propagate(False)  # impedisce al frame di ridimensionarsi

    # Label centrata per l'immagine
    img_label = tk.Label(frame_img, bg="white")
    img_label.place(relx=0.5, rely=0.5, anchor="center")

    # Dimensioni massime SOLO per l'immagine
    MAX_W, MAX_H = 800, 600

    def _load_and_fit(p):
        """Carica l'immagine dal percorso p e la adatta entro MAX_W x MAX_H."""
        if not os.path.exists(p):
            img_label.config(text=f"(Immagine non trovata)\n{p}", justify="center", bg="white", image="")
            return

        if _HAS_PIL:
            im = Image.open(p)
            im.thumbnail((MAX_W, MAX_H), Image.LANCZOS)
            img = ImageTk.PhotoImage(im)
        else:
            # Fallback Tkinter puro (solo PNG/GIF)
            tmp = tk.PhotoImage(file=p)
            fx = max(1, (tmp.width()  + MAX_W  - 1) // MAX_W)
            fy = max(1, (tmp.height() + MAX_H - 1) // MAX_H)
            img = tmp.subsample(max(fx, fy))

        # Evita il garbage collection mantenendo un riferimento
        img_label._img = img
        img_label.config(image=img, text="")

    # Primo render dopo il layout
    root.after(100, lambda: _load_and_fit(image_path))

    # Ricarica l'immagine quando il pannello cambia dimensione (debounced)
    _pending = None
    def _on_conf(e):
        """Debounce del ridisegno immagine per evitare refresh continui durante il resize."""
        nonlocal _pending
        if _pending:
            root.after_cancel(_pending)
        _pending = root.after(120, lambda: _load_and_fit(image_path))

    right.bind("<Configure>", _on_conf)

    # Avvia la GUI
    root.mainloop()
    return res if res.get("ok") else None
