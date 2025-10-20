# plate_properties.py
# Crea/aggiorna proprietà plate per tw, tf1, tf2 di trave e colonna.
# Apre anche una GUI che mostra D,B1,B2,tw,tf1,tf2 (sola lettura) e chiede:
#   - spessore pannello ndale
#   - spessore fazzoletti
# Se inseriti, crea due nuove property: "t_panel.modanodalele" e "t_fazzoletti".

import ctypes as ct                           # binding C
import St7API as st7                          # API Straus7

# --- utilità di base --------------------------------------------------------

def _ck(code, where=""):                      # controllo errori API
    if code != 0:                             # 0 = OK
        buf = ct.create_string_buffer(st7.kMaxStrLen)         # buffer testo
        st7.St7GetAPIErrorString(code, buf, st7.kMaxStrLen)   # messaggio
        raise RuntimeError(f"{where}: {buf.value.decode('utf-8','ignore')}")  # eccezione

def _existing_plate_props(uID):
    """Ritorna mappa {nome->numero} e lista numeri esistenti."""
    nums = (ct.c_long * st7.kMaxEntityTotals)()               # conteggi
    last = (ct.c_long * st7.kMaxEntityTotals)()               # last ids (non usato)
    _ck(st7.St7GetTotalProperties(uID, nums, last), "GetTotalProperties")  # leggi totali
    n_plate = int(nums[st7.ipPlatePropTotal])                 # quante plate prop

    name_to_num = {}                                          # mappa nome->num
    numbers = []                                              # lista numeri
    namebuf = ct.create_string_buffer(st7.kMaxStrLen)         # buffer nome
    for i in range(1, n_plate + 1):                           # loop su proprietà
        pnum = ct.c_long()                                    # out numero
        _ck(st7.St7GetPropertyNumByIndex(uID, st7.ptPLATEPROP, i, ct.byref(pnum)),
            "GetPropertyNumByIndex(PLATE)")                   # numero da indice
        num = int(pnum.value)                                 # cast int
        _ck(st7.St7GetPropertyName(uID, st7.ptPLATEPROP, num, namebuf, st7.kMaxStrLen),
            "GetPropertyName(PLATE)")                         # nome proprietà
        name = namebuf.value.decode("utf-8", "ignore")        # decode
        name_to_num[name] = num                               # salva mappa
        numbers.append(num)                                   # salva lista
    return name_to_num, numbers                               # ritorna

def _ensure_plate_prop(uID, name, t, E, nu, rho, prefer_num=None):
    """
    Se esiste 'name' -> aggiorna spessore/materiale. Altrimenti crea nuova property.
    Ritorna numero della property.
    """
    assert t and t > 0.0, f"Spessore non valido per {name}"   # validazione

    name_to_num, numbers = _existing_plate_props(uID)         # leggi esistenti
    if name in name_to_num:                                   # già presente
        num = name_to_num[name]                               # numero esistente
        th = (ct.c_double * 2)(float(t), float(t))            # spessori (top/bot)
        _ck(st7.St7SetPlateThickness(uID, num, th), f"SetPlateThickness {name}")  # aggiorna
    else:                                                     # nuova property
        num = prefer_num if prefer_num else (max(numbers) + 1 if numbers else 1)  # nuovo id
        _ck(st7.St7NewPlateProperty(
            uID, num, st7.ptPlateShell, st7.mtIsotropic, name.encode("utf-8")),
            f"NewPlateProperty {name}")                       # crea
        th = (ct.c_double * 2)(float(t), float(t))            # spessori
        _ck(st7.St7SetPlateThickness(uID, num, th), f"SetPlateThickness {name}")  # set

    # materiale isotropo uguale ai beam
    mat = (ct.c_double * 8)()                                 # array materiale
    mat[st7.ipPlateIsoModulus]      = float(E)                # E
    mat[st7.ipPlateIsoPoisson]      = float(nu)               # ν
    mat[st7.ipPlateIsoDensity]      = float(rho)              # ρ
    mat[st7.ipPlateIsoAlpha]        = 0.0                     # dilatazione termica
    mat[st7.ipPlateIsoViscosity]    = 0.0                     # viscosità
    mat[st7.ipPlateIsoDampingRatio] = 0.0                     # smorzamento
    mat[st7.ipPlateIsoConductivity] = 0.0                     # conducibilità
    mat[st7.ipPlateIsoSpecificHeat] = 0.0                     # calore specifico
    _ck(st7.St7SetPlateIsotropicMaterial(uID, num, mat),
        f"SetPlateIsotropicMaterial {name}")                  # applica materiale

    return num                                                # ritorna numero

# --- helper per estrarre spessori da record di section_data ------------------

def extract_I_thicknesses(rec):
    """Ritorna dict {'tw','tf1','tf2'} da record section_data (BGL o standard)."""
    return {
        "tw":  rec.get("tw",  rec.get("T1")),                # anima
        "tf1": rec.get("tf1", rec.get("T2", rec.get("tf"))), # flangia inferiore
        "tf2": rec.get("tf2", rec.get("T3", rec.get("tf"))), # flangia superiore
    }

# --- GUI: mostra quote e chiede spessori extra -------------------------------

def ask_panel_gusset_thicknesses(beam_dims, col_dims, panel_default="", gusset_default=""):
    """
    Colonna 1: TRAVE (D,B1,B2,tw,tf1,tf2) read-only
    Colonna 2: COLONNA (D,B1,B2,tw,tf1,tf2) read-only
    Colonna 3: EXTRA (read-only: H pannello = D_trave, L pannello = D_colonna;
                      checkbox + entry: sp. pannello nodale, sp. fazzoletti)
    Ritorna {'panel_thk': float|None, 'gusset_thk': float|None}.
    """
    import tkinter as tk
    from tkinter import ttk

    def _fmt(v):
        try: return f"{float(v):.6g}"
        except Exception: return ""

    out = {}

    root = tk.Tk()
    root.title("Proprietà plate – sezioni e spessori")
    root.resizable(False, False)
    pad = {"padx": 6, "pady": 4}

    # --- TRAVE (colonna 0) ---------------------------------------------------
    lf_beam = ttk.Labelframe(root, text="Sezione TRAVE")
    lf_beam.grid(row=0, column=0, sticky="n", **pad)
    for r, k in enumerate(("D","B1","B2","tw","tf1","tf2")):
        ttk.Label(lf_beam, text=k, width=10).grid(row=r, column=0, sticky="e", **pad)
        e = ttk.Entry(lf_beam, width=14)
        e.grid(row=r, column=1, **pad)
        e.insert(0, _fmt(beam_dims.get(k)))
        e.state(["disabled"])

    # --- COLONNA (colonna 1) -------------------------------------------------
    lf_col = ttk.Labelframe(root, text="Sezione COLONNA")
    lf_col.grid(row=0, column=1, sticky="n", **pad)
    for r, k in enumerate(("D","B1","B2","tw","tf1","tf2")):
        ttk.Label(lf_col, text=k, width=10).grid(row=r, column=0, sticky="e", **pad)
        e = ttk.Entry(lf_col, width=14)
        e.grid(row=r, column=1, **pad)
        e.insert(0, _fmt(col_dims.get(k)))
        e.state(["disabled"])

    # --- EXTRA (colonna 2) ---------------------------------------------------
    lf_extra = ttk.Labelframe(root, text="Extra (TRAVE)")
    lf_extra.grid(row=0, column=2, sticky="n", **pad)

    # Read-only: dimensioni pannello nodale
    ttk.Label(lf_extra, text="H pannello nodale").grid(row=0, column=0, sticky="e", **pad)
    ent_hpan = ttk.Entry(lf_extra, width=14)
    ent_hpan.grid(row=0, column=1, **pad)
    ent_hpan.insert(0, _fmt(beam_dims.get("D")))   # = altezza trave
    ent_hpan.state(["disabled"])

    ttk.Label(lf_extra, text="L pannello nodale").grid(row=1, column=0, sticky="e", **pad)
    ent_lpan = ttk.Entry(lf_extra, width=14)
    ent_lpan.grid(row=1, column=1, **pad)
    ent_lpan.insert(0, _fmt(col_dims.get("D")))    # = altezza colonna
    ent_lpan.state(["disabled"])

    # Checkbox + entry: sp. pannello nodale
    var_panel = tk.IntVar(value=0)
    cb_panel = ttk.Checkbutton(lf_extra, text="sp. pannello nodale", variable=var_panel)
    cb_panel.grid(row=2, column=0, sticky="w", **pad)
    ent_panel = ttk.Entry(lf_extra, width=14, state="disabled")
    ent_panel.grid(row=2, column=1, **pad)
    ent_panel.insert(0, str(panel_default))

    def _toggle_panel(*_):
        ent_panel.configure(state=("normal" if var_panel.get() else "disabled"))
    var_panel.trace_add("write", _toggle_panel)

    # Checkbox + entry: sp. fazzoletti
    var_gusset = tk.IntVar(value=0)
    cb_gusset = ttk.Checkbutton(lf_extra, text="sp. fazzoletti", variable=var_gusset)
    cb_gusset.grid(row=3, column=0, sticky="w", **pad)
    ent_gusset = ttk.Entry(lf_extra, width=14, state="disabled")
    ent_gusset.grid(row=3, column=1, **pad)
    ent_gusset.insert(0, str(gusset_default))

    def _toggle_gusset(*_):
        ent_gusset.configure(state=("normal" if var_gusset.get() else "disabled"))
    var_gusset.trace_add("write", _toggle_gusset)

    # --- Pulsanti -------------------------------------------------------------
    def _ok():
        s1 = ent_panel.get().strip().replace(",", ".") if var_panel.get() else ""
        s2 = ent_gusset.get().strip().replace(",", ".") if var_gusset.get() else ""
        out["panel_thk"]  = (float(s1) if s1 else None)  # None => usa tw colonna
        out["gusset_thk"] = (float(s2) if s2 else None)  # None => non creare property
        root.destroy()

    def _cancel():
        out.clear()
        root.destroy()

    btns = ttk.Frame(root)
    btns.grid(row=1, column=0, columnspan=3, sticky="e", **pad)
    ttk.Button(btns, text="Annulla", command=_cancel).grid(row=0, column=0, **pad)
    ttk.Button(btns, text="OK", command=_ok).grid(row=0, column=1, **pad)

    root.mainloop()
    return out



# --- API principale ----------------------------------------------------------

def create_plate_properties(model_path, beam_thk, col_thk, E, nu, rho, extra=None):
    """
    model_path : .st7 locale da modificare
    beam_thk  : dict {'tw','tf1','tf2'} per trave
    col_thk   : dict {'tw','tf1','tf2'} per colonna
    E,nu,rho  : materiale isotropo identico ai beam del global
    extra     : opzionale dict {'panel_thk':..., 'gusset_thk':...}
    Ritorna: dict nome->numero proprietà create/aggiornate
    """
    uID = 1                                                     # id sessione
    out = {}                                                    # mappa nome->numero

    _ck(st7.St7Init(), "Init")                                  # init API
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open")  # apri .st7

        # Trave: tre proprietà per I
        out["tw_sez.trave"]  = _ensure_plate_prop(uID, "tw_sez.trave",  float(beam_thk["tw"]),  E,nu,rho)
        out["tf1_sez.trave"] = _ensure_plate_prop(uID, "tf1_sez.trave", float(beam_thk["tf1"]), E,nu,rho)
        out["tf2_sez.trave"] = _ensure_plate_prop(uID, "tf2_sez.trave", float(beam_thk["tf2"]), E,nu,rho)

        # Colonna: tre proprietà per I
        out["tw_sez.colonna"]  = _ensure_plate_prop(uID, "tw_sez.colonna",  float(col_thk["tw"]),  E,nu,rho)
        out["tf1_sez.colonna"] = _ensure_plate_prop(uID, "tf1_sez.colonna", float(col_thk["tf1"]), E,nu,rho)
        out["tf2_sez.colonna"] = _ensure_plate_prop(uID, "tf2_sez.colonna", float(col_thk["tf2"]), E,nu,rho)

        # Extra opzionali: pannello nodale e fazzoletti
                # Extra: pannello nodale (sempre creato) + fazzoletti (solo se spuntati)
        tp = extra.get("panel_thk") if extra else None                   # sp. pannello da GUI
        # se non fornito o non positivo -> usa tw colonna
        t_panel = float(tp) if (tp is not None and float(tp) > 0.0) else float(col_thk["tw"])
        out["t_panel.modale"] = _ensure_plate_prop(
            uID, "t_panel.modale", t_panel, E, nu, rho
        )

        tg = extra.get("gusset_thk") if extra else None                  # sp. fazzoletti da GUI
        if tg is not None and float(tg) > 0.0:                           # crea solo se spuntato
            out["t_fazzoletti"] = _ensure_plate_prop(
                uID, "t_fazzoletti", float(tg), E, nu, rho
            )


        _ck(st7.St7SaveFile(uID), "Save")                        # salva
        return out                                               # ritorna mappa
    finally:
        try:
            st7.St7CloseFile(uID)                                # chiudi
        finally:
            st7.St7Release()                                     # release API
