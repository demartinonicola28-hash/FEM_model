# gui.py  (carichi input in kN/m²)

import os, ctypes as ct, tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

os.add_dll_directory(r"C:\Program Files\Straus7 R31\Bin64")
from St7API import *

def _b(s:str)->bytes: return s.encode("utf-8")

def _check(rc:int):
    if rc!=0:
        buf=(ct.c_char*256)()
        try:
            St7GetAPIErrorString(rc,buf,256)
            msg=buf.value.decode("utf-8","ignore")
        except Exception:
            msg=""
        raise RuntimeError(f"St7 error {rc}: {msg}")

def _load_all_beam_sections_british(library_root:str)->list[str]:
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

FAMILY_FILTERS={
    "HE (HE/HEA/HEB/HEM)":[" BS EN - HE "," HE "," HEA "," HEB "," HEM "],
    "IPE":[" BS EN - IPE "," IPE "],
    "UPN (canali)":[" UPN "," PFC "],
    "L (angolari)":[" EQUAL ANGLES "," ANGLE "," L "],
    "Tutte (British)":[]
}
def _filter_by_family(items, family):
    toks=FAMILY_FILTERS.get(family, [])
    if not toks:
        return items
    up=[(s,s.upper()) for s in items]
    res=[s for s,u in up if any(tok in u for tok in toks)]
    return res or items

def run_gui(image_path: str = r"C:/Users/demnic15950/Downloads/FEM_model/geometry_scheme.png") -> dict | None:
    try:
        ALL = _load_all_beam_sections_british(r"C:\ProgramData\Straus7 R31\Data")
    except Exception:
        ALL = [
            "BS EN - HE 160 A - BS EN 10365-2017 BSL",
            "BS EN - HE 180 A - BS EN 10365-2017 BSL",
            "BS EN - IPE 240 - BS EN 10365-2017 BSL",
            "BS EN - IPE 270 - BS EN 10365-2017 BSL",
        ]

    root = tk.Tk()
    root.title("Input Dati della Struttura")
    root.geometry("980x700")

    PAD = {"padx": 10, "pady": 6}
    root.columnconfigure(0, weight=1, minsize=480)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)

    LABEL_W = 22
    def _row(parent, r, label_text, widget):
        ttk.Label(parent, text=label_text, width=LABEL_W, anchor="e").grid(row=r, column=0, sticky="e", **PAD)
        widget.grid(row=r, column=1, sticky="ew", **PAD)

    left = tk.Frame(root); left.grid(row=0, column=0, sticky="nsew"); left.columnconfigure(0, weight=1)

    # Geometria
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

    # Materiale
    fm = ttk.LabelFrame(left, text="Materiale (acciaio)")
    fm.grid(row=1, column=0, sticky="nsew", **PAD); fm.columnconfigure(1, weight=1)
    e_E   = ttk.Entry(fm); e_E.insert(0, "206000")
    e_nu  = ttk.Entry(fm); e_nu.insert(0, "0.30")
    e_rho = ttk.Entry(fm); e_rho.insert(0, "7850")
    _row(fm, 0, "E [MPa]",   e_E)
    _row(fm, 1, "ν [-]",     e_nu)
    _row(fm, 2, "ρ [kg/m³]", e_rho)

    # Sezioni
    fs = ttk.LabelFrame(left, text="Sezioni (BS EN)")
    fs.grid(row=2, column=0, sticky="nsew", **PAD); fs.columnconfigure(1, weight=1)
    cb_he_fam = ttk.Combobox(fs, state="readonly", values=list(FAMILY_FILTERS.keys())); cb_he_fam.set("HE (HE/HEA/HEB/HEM)")
    _row(fs, 0, "Famiglia colonne", cb_he_fam)
    cb_he = ttk.Combobox(fs, state="readonly", values=_filter_by_family(ALL, cb_he_fam.get()))
    if cb_he["values"]: cb_he.current(0)
    _row(fs, 1, "Sezione colonne", cb_he)
    cb_ipe_fam = ttk.Combobox(fs, state="readonly", values=list(FAMILY_FILTERS.keys())); cb_ipe_fam.set("IPE")
    _row(fs, 2, "Famiglia travi", cb_ipe_fam)
    cb_ipe = ttk.Combobox(fs, state="readonly", values=_filter_by_family(ALL, cb_ipe_fam.get()))
    if cb_ipe["values"]: cb_ipe.current(0)
    _row(fs, 3, "Sezione travi", cb_ipe)

    # Carichi superficiali in kN/m²
    fl = ttk.LabelFrame(left, text="Carichi distribuiti [kN/m²]")
    fl.grid(row=3, column=0, sticky="nsew", padx=10, pady=10); fl.columnconfigure(1, weight=1)
    def _e(parent, r, txt, defv):
        e = ttk.Entry(parent); e.insert(0, defv); _row(parent, r, txt, e); return e
    # default coerenti con i valori precedenti su L=5 m:
    e_g2_int_m2  = _e(fl, 0, "G2 piani interni", "3.50")
    e_g2_roof_m2 = _e(fl, 1, "G2 copertura",         "3.50")
    e_q_int_m2   = _e(fl, 2, "Q  piani interni", "3.00")
    e_q_roof_m2  = _e(fl, 3, "Q  copertura",         "0.40")

    note_label = ttk.Label(fl, text="(carico verso il basso con segno positivo)",
                       font=("TkDefaultFont", 8, "italic"), foreground="gray")
    note_label.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=(4, 0))

    # Pulsanti
    fbtn = ttk.Frame(left); fbtn.grid(row=4, column=0, sticky="e", padx=10, pady=20)
    res = {"ok": False}
    def _cancel(event=None):
        res.clear(); res["ok"] = False; root.destroy()
    def on_ok():
        try:
            res.update({
                "h_story": float(e_h.get()), "span": float(e_L.get()),
                "n_floors": int(e_np.get()), "offset": float(e_off.get()),
                "E": float(e_E.get()), "nu": float(e_nu.get()), "rho": float(e_rho.get()),
                "section_columns": cb_he.get().strip(), "section_beams": cb_ipe.get().strip(),
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

    # Immagine destra
    right = tk.Frame(root); right.grid(row=0, column=1, sticky="nsew")
    right.rowconfigure(0, weight=1); right.columnconfigure(0, weight=1)
    img_label = tk.Label(right, bd=1, relief="solid", bg="white")
    img_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    def _load_and_fit(p):
        if not os.path.exists(p):
            img_label.config(text=f"(Immagine non trovata)\n{p}", justify="center", bg="white"); return
        if _HAS_PIL:
            w = max(360, right.winfo_width() - 20 or 480)
            h = max(500, right.winfo_height() - 40 or 700)
            im = Image.open(p); im.thumbnail((w, h), Image.LANCZOS)
            img_label._img = ImageTk.PhotoImage(im)
        else:
            img_label._img = tk.PhotoImage(file=p)
        img_label.config(image=img_label._img)
    root.after(50, lambda: _load_and_fit(image_path))
    right.bind("<Configure>", lambda e: _load_and_fit(image_path))

    root.mainloop()
    return res if res.get("ok") else None
