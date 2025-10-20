# plate_sections.py
# Costruisce una sezione I con plate tra due nodi esistenti (linea verde).
# Crea 3 proprietà plate (web, flange sup, flange inf) con spessori reali.
# Mesh sulle superfici di mezzeria: flange in piani z=±(D/2 - tf/2), anima in piano y=0.

import ctypes as ct            # binding C
import math                    # norm e prodotti
import os                      # path salvataggio
import St7API as st7           # Straus7 API (il main ha già fatto add_dll_directory)

# --- utilità ---------------------------------------------------------------

def _ck(code, where=""):       # controllo errori API
    if code != 0:              # 0 = OK
        sb = ct.create_string_buffer(st7.kMaxStrLen)                 # buffer stringa errore
        st7.St7GetAPIErrorString(code, sb, st7.kMaxStrLen)           # testo errore
        raise RuntimeError(f"{where}: {sb.value.decode('utf-8','ignore')}")  # eccezione

def _unit(v):                  # normalizza un vettore 3D
    n = math.sqrt(sum(c*c for c in v))                               # norma euclidea
    if n == 0: 
        raise ValueError("vettore nullo")                            # protezione
    return (v[0]/n, v[1]/n, v[2]/n)                                  # versore

def _dot(a,b):                 # prodotto scalare
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]

def _cross(a,b):               # prodotto vettoriale
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _add(a,b):                 # somma vettori
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])

def _scal(k,a):                # prodotto per scalare
    return (k*a[0], k*a[1], k*a[2])

def _get_totals(uID):          # totali entità correnti (nodi, plates)
    # ritorna dict con 'node_last' e 'plate_last' usando St7GetTotal :contentReference[oaicite:3]{index=3}
    i = ct.c_long()                                                # numero
    l = ct.c_long()                                                # ultimo ID
    _ck(st7.St7GetTotal(uID, st7.tyNODE,  ct.byref(i), ct.byref(l)),  "GetTotal NODE")
    node_last  = int(l.value)                                      # ultimo nodo usato
    _ck(st7.St7GetTotal(uID, st7.tyPLATE, ct.byref(i), ct.byref(l)),  "GetTotal PLATE")
    plate_last = int(l.value)                                      # ultimo plate usato
    return {"node_last": node_last, "plate_last": plate_last}      # dict

def _new_node(uID, nid, xyz):  # crea/imposta nodo con St7SetNodeXYZ (crea se non esiste) :contentReference[oaicite:4]{index=4}
    arr = (ct.c_double * 3)(*xyz)                                  # array double[3]
    _ck(st7.St7SetNodeXYZ(uID, int(nid), arr), f"SetNode {nid}")   # scrittura

def _new_quad4(uID, eid, prop, n1,n2,n3,n4):  # crea Quad4 con St7SetElementConnection :contentReference[oaicite:5]{index=5}
    conn = (ct.c_long * (1+4))()                                   # [0]=num nodi, poi nodi
    conn[0] = 4                                                    # Quad4
    conn[1],conn[2],conn[3],conn[4] = int(n1),int(n2),int(n3),int(n4) # connettività
    _ck(st7.St7SetElementConnection(uID, st7.tyPLATE, int(eid), int(prop), conn), f"SetPlate {eid}")  # crea

def _make_plate_prop_iso(uID, prop_num, name, t, E, nu, rho):  # crea proprietà plate isotropa
    # nuova proprietà plate-shell isotropa: St7NewPlateProperty :contentReference[oaicite:6]{index=6}
    _ck(st7.St7NewPlateProperty(uID, int(prop_num), st7.ptPlateShell, st7.mtIsotropic, name.encode("utf-8")), "NewPlateProperty")
    # spessori membrana e flessione: St7SetPlateThickness [0]=mem, [1]=bend :contentReference[oaicite:7]{index=7}
    th = (ct.c_double * 2)(float(t), float(t))                      # uguali
    _ck(st7.St7SetPlateThickness(uID, int(prop_num), th), "SetPlateThickness")
    # materiale isotropo (E,nu,ρ): St7SetPlateIsotropicMaterial :contentReference[oaicite:8]{index=8}
    mat = (ct.c_double * 8)()                                       # inizializza array
    mat[st7.ipPlateIsoModulus]      = float(E)                      # E
    mat[st7.ipPlateIsoPoisson]      = float(nu)                     # ν
    mat[st7.ipPlateIsoDensity]      = float(rho)                    # ρ
    mat[st7.ipPlateIsoAlpha]        = 0.0                           # α termico = 0
    mat[st7.ipPlateIsoViscosity]    = 0.0                           # smorz. viscoso = 0
    mat[st7.ipPlateIsoDampingRatio] = 0.0                           # smorz. modale = 0
    mat[st7.ipPlateIsoConductivity] = 0.0                           # non termico
    mat[st7.ipPlateIsoSpecificHeat] = 0.0                           # non termico
    _ck(st7.St7SetPlateIsotropicMaterial(uID, int(prop_num), mat), "SetPlateIsotropicMaterial")

# --- costruzione sezione I su una linea ------------------------------------

def build_I_section_between(
    model_path,              # path .st7 da aprire
    n1, n2,                  # nodi estremi della linea verde
    D, B1, B2, tw, tf1, tf2, # dimensioni sezione I (lunghezze nelle unità del modello)
    E, nu, rho,              # materiale isotropo per tutte le piastre
    nx=8, ny=4, nz=6,        # suddivisioni mesh: lungo x, larghezza flange, altezza web
    prop_start=1000,         # ID iniziale per proprietà plate da creare
    save=True                # salva file a fine operazione
):
    uID = 1                                                       # ID modello
    _ck(st7.St7Init(), "Init")                                    # inizializza API
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open")  # apre modello
        try:
            # === Leggi coordinate dei due nodi estremi =====================================
            X = (ct.c_double * 3)()                                # buffer
            _ck(st7.St7GetNodeXYZ(uID, int(n1), X), "GetNodeXYZ n1")        # coord n1
            p1 = (X[0], X[1], X[2])                                # tuple
            _ck(st7.St7GetNodeXYZ(uID, int(n2), X), "GetNodeXYZ n2")        # coord n2
            p2 = (X[0], X[1], X[2])                                # tuple

            # === Sistema locale della linea: ex lungo n1->n2, ez ~ Z globale, ey = ez×ex ===
            ex = _unit((p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2]))    # asse lungo la linea
            zref = (0.0,0.0,1.0)                                   # direzione preferita "su"
            if abs(_dot(ex, zref)) > 0.95:                         # quasi paralleli?
                zref = (1.0,0.0,0.0)                               # usa X globale alternativa
            ey = _unit(_cross(zref, ex))                           # trasversale “larghezza”
            ez = _unit(_cross(ex, ey))                             # verticale della sezione

            # === Quote dei piani di mezzeria =================================================
            z_top =  + (D/2.0 - tf2/2.0)                           # quota flange sup (mezzeria)
            z_bot =  - (D/2.0 - tf1/2.0)                           # quota flange inf (mezzeria)

            # === Crea 3 proprietà plate: web, top, bottom ===================================
            # scegli ID liberi a partire da prop_start
            props = {"web":prop_start, "top":prop_start+1, "bot":prop_start+2}  # mapping
            _make_plate_prop_iso(uID, props["web"], b"WEB", tw,  E,nu,rho)      # proprietà anima
            _make_plate_prop_iso(uID, props["top"], b"FLANGE_TOP", tf2, E,nu,rho) # proprietà flange sup
            _make_plate_prop_iso(uID, props["bot"], b"FLANGE_BOT", tf1, E,nu,rho) # proprietà flange inf

            # === Numerazione: prossimo nodo e prossimo plate =================================
            totals = _get_totals(uID)                              # ultimi ID occupati
            next_node  = totals["node_last"]  + 1                  # primo nodo nuovo
            next_plate = totals["plate_last"] + 1                  # primo plate nuovo

            # === Funzione per convertire coord locali -> globali =============================
            def L2G(s, y, z):                                      # s=0..L (lungo), y larghezza, z altezza
                return _add(p1, _add(_scal(s, ex), _add(_scal(y, ey), _scal(z, ez))))  # p1 + s*ex + y*ey + z*ez

            # === Lunghezza segmento e passi lungo la linea ==================================
            L = math.sqrt(sum((p2[i]-p1[i])**2 for i in range(3))) # lunghezza segmento
            sx = [L*i/nx for i in range(nx+1)]                     # suddivisione lungo x

            # === Mesh flange superiore =======================================================
            ys_top = [-B2/2.0 + B2*j/ny for j in range(ny+1)]      # griglia in larghezza
            grid_top = [[None]*(ny+1) for _ in range(nx+1)]        # matrici ID nodi
            for i, s in enumerate(sx):                             # loop lungo
                for j, y in enumerate(ys_top):                     # loop larghezza
                    xyz = L2G(s, y, z_top)                         # punto su piano z_top
                    nid = next_node                                # assegna nuovo ID
                    _new_node(uID, nid, xyz)                       # crea nodo
                    grid_top[i][j] = nid                           # salva ID
                    next_node += 1                                 # incrementa ID
            # crea Quad4 per ciascuna cella
            for i in range(nx):                                    # celle lungo x
                for j in range(ny):                                # celle in larghezza
                    n11 = grid_top[i][j]                           # 4 nodi del quad
                    n12 = grid_top[i+1][j]
                    n22 = grid_top[i+1][j+1]
                    n21 = grid_top[i][j+1]
                    _new_quad4(uID, next_plate, props["top"], n11,n12,n22,n21) # plate
                    next_plate += 1                                 # prossimo

            # === Mesh flange inferiore =======================================================
            ys_bot = [-B1/2.0 + B1*j/ny for j in range(ny+1)]      # griglia in larghezza
            grid_bot = [[None]*(ny+1) for _ in range(nx+1)]        # matrici ID nodi
            for i, s in enumerate(sx):                             # loop lungo
                for j, y in enumerate(ys_bot):                     # loop larghezza
                    xyz = L2G(s, y, z_bot)                         # punto su piano z_bot
                    nid = next_node                                # nuovo nodo
                    _new_node(uID, nid, xyz)                       # crea nodo
                    grid_bot[i][j] = nid                           # salva
                    next_node += 1                                 # incrementa
            for i in range(nx):                                    # celle lungo x
                for j in range(ny):                                # celle in larghezza
                    n11 = grid_bot[i][j]                           # 4 nodi del quad
                    n12 = grid_bot[i+1][j]
                    n22 = grid_bot[i+1][j+1]
                    n21 = grid_bot[i][j+1]
                    _new_quad4(uID, next_plate, props["bot"], n11,n12,n22,n21) # plate
                    next_plate += 1                                 # prossimo

            # === Mesh anima (piano y=0) ======================================================
            zz = [z_bot + (z_top - z_bot)*k/nz for k in range(nz+1)] # suddivisione in altezza
            grid_web = [[None]*(nz+1) for _ in range(nx+1)]        # matrice ID nodi
            for i, s in enumerate(sx):                             # loop lungo
                for k, z in enumerate(zz):                         # loop altezza
                    xyz = L2G(s, 0.0, z)                           # punto su piano y=0
                    nid = next_node                                # nuovo nodo
                    _new_node(uID, nid, xyz)                       # crea nodo
                    grid_web[i][k] = nid                           # salva
                    next_node += 1                                 # incrementa
            for i in range(nx):                                    # celle lungo x
                for k in range(nz):                                # celle in altezza
                    n11 = grid_web[i][k]                           # 4 nodi del quad (ordine CCW guardando +ey)
                    n12 = grid_web[i+1][k]
                    n22 = grid_web[i+1][k+1]
                    n21 = grid_web[i][k+1]
                    _new_quad4(uID, next_plate, props["web"], n11,n12,n22,n21) # plate
                    next_plate += 1                                 # prossimo

            # === Salva ================================================================
            if save:                                               # se richiesto
                _ck(st7.St7SaveFile(uID), "Save")                  # salva file

            # === Ritorna riepilogo ====================================================
            return {
                "props": props,                                    # ID proprietà create
                "last_node": next_node-1,                          # ultimo nodo scritto
                "last_plate": next_plate-1,                        # ultimo plate scritto
                "z_top": z_top, "z_bot": z_bot,                    # quote usate
                "L": L                                             # lunghezza
            }

        finally:
            _ck(st7.St7CloseFile(uID), "Close")                    # chiude .st7
    finally:
        st7.St7Release()                                           # rilascia API
