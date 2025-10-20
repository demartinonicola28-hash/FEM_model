# plate_geometry.py                                                     # nome modulo
# Costruisce i plate di sezione I per trave e colonna su piani medi.    # descrizione

import math                                                             # funzioni matematiche
import ctypes as ct                                                     # binding C
import St7API as st7                                                    # API Straus7

# ---------- utilità API ------------------------------------------------------

def _ck(code, where=""):                                                # check errori API
    if code != 0:                                                       # 0 = OK
        buf = ct.create_string_buffer(st7.kMaxStrLen)                   # buffer testo errore
        st7.St7GetAPIErrorString(code, buf, st7.kMaxStrLen)             # ottieni messaggio
        raise RuntimeError(f"{where}: {buf.value.decode('utf-8','ignore')}")  # lancia eccezione

def _get_propnum_by_name(uID, name, ptype=st7.ptPLATEPROP):             # trova numero property per nome
    nums = (ct.c_long * st7.kMaxEntityTotals)()                         # array conteggi properties
    last = (ct.c_long * st7.kMaxEntityTotals)()                         # array “last index” (non usato qui)
    _ck(st7.St7GetTotalProperties(uID, nums, last), "GetTotalProperties")  # leggi totali
    n = nums[st7.ipPlatePropTotal]                                      # numero proprietà plate
    buf = ct.create_string_buffer(st7.kMaxStrLen)                       # buffer per nome
    for i in range(1, n+1):                                             # itera per indice
        pnum = ct.c_long()                                              # out: numero proprietà
        _ck(st7.St7GetPropertyNumByIndex(uID, ptype, i, ct.byref(pnum)),
            "GetPropertyNumByIndex(PLATE)")                             # leggi numero
        _ck(st7.St7GetPropertyName(uID, ptype, pnum.value, buf, st7.kMaxStrLen),
            "GetPropertyName(PLATE)")                                   # leggi nome
        if buf.value.decode("utf-8","ignore") == name:                  # confronto esatto
            return int(pnum.value)                                      # ritorna numero
    raise RuntimeError(f"Property plate '{name}' non trovata")           # se non trovata

# ---------- algebra minima ---------------------------------------------------

def _vsub(a,b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])                # vettore a-b
def _vadd(a,b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])                # vettore a+b
def _smul(k,a): return (k*a[0], k*a[1], k*a[2])                         # scalare*k
def _dot(a,b):  return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]                    # prodotto scalare
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])  # vettoriale
def _norm(a):   return math.sqrt(_dot(a,a))                              # norma
def _unit(a):                                                            # versore
    n = _norm(a)                                                         # calcola norma
    if n == 0: raise ValueError("versore nullo")                         # protezione
    return _smul(1.0/n, a)                                               # normalizza

# ---------- primitive Straus7 ------------------------------------------------

def _get_xyz(uID, nid):                                                  # coordinate nodo per ID
    buf = (ct.c_double * 3)()                                            # buffer 3 double
    _ck(st7.St7GetNodeXYZ(uID, int(nid), buf), f"GetNodeXYZ {nid}")      # API read
    return (buf[0], buf[1], buf[2])                                      # tuple xyz

def _new_node(uID, nid, xyz):                                            # crea/imposta nodo
    arr = (ct.c_double * 3)(*xyz)                                        # array double[3]
    _ck(st7.St7SetNodeXYZ(uID, int(nid), arr), f"SetNode {nid}")         # API write

def _next_ids(uID):                                                      # prossimi ID liberi
    tot = ct.c_long()                                                    # contatore
    _ck(st7.St7GetTotal(uID, st7.tyNODE, ct.byref(tot)),  "GetTotal NODE")   # #nodi
    node_next = int(tot.value) + 1                                       # prossimo nodo
    tot = ct.c_long()                                                    # contatore
    _ck(st7.St7GetTotal(uID, st7.tyPLATE, ct.byref(tot)), "GetTotal PLATE")  # #plate
    plate_next = int(tot.value) + 1                                      # prossimo plate
    return node_next, plate_next                                         # ritorna IDs

def _quad4(uID, eid, prop, n1,n2,n3,n4):                                 # crea QUAD4
    conn = (ct.c_long * 5)()                                             # array [n, n1..n4]
    conn[0]=4; conn[1]=n1; conn[2]=n2; conn[3]=n3; conn[4]=n4            # set connettività
    _ck(st7.St7SetElementConnection(uID, st7.tyPLATE, int(eid), int(prop), conn),
        f"SetElementConnection plate {eid}")                              # API set element

# ---------- start points dagli “intermediate” del locale --------------------

def compute_starts_from_intermediates(model_path, create_nodes_out):     # calcola punti di partenza
    uID = 1                                                              # id sessione
    _ck(st7.St7Init(), "Init")                                           # init API
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open")   # apri file
        buf = (ct.c_double * 3)()                                        # buffer xyz
        cid = int(create_nodes_out["base_node_ids"][0])                  # id nodo centro
        _ck(st7.St7GetNodeXYZ(uID, cid, buf), "GetNodeXYZ center")       # leggi centro
        C = (buf[0], buf[1], buf[2])                                     # coord centro
        cx, cy, _ = C                                                    # x e y centro

        def xyz(nid):                                                    # helper lettura xyz
            _ck(st7.St7GetNodeXYZ(uID, int(nid), buf), f"GetNodeXYZ {nid}")  # API read
            return (buf[0], buf[1], buf[2])                              # tuple xyz

        starts = []                                                      # lista punti intermedi
        for branch in create_nodes_out["intermediate_ids_by_branch"]:    # per ogni raggio
            nid = sorted(branch, key=lambda n: n)[0]                     # prendi il più vicino (id minore)
            starts.append(xyz(nid))                                      # salva punto

        beamP = max(starts, key=lambda p: abs(p[0]-cx))                  # beam = |Δx| maggiore
        rest  = [p for p in starts if p is not beamP]                    # altri due
        topP  = max(rest, key=lambda p: p[1])                            # top = y maggiore
        botP  = min(rest, key=lambda p: p[1])                            # bot = y minore
        return {"beam": beamP, "top": topP, "bot": botP}                 # dict risultati
    finally:
        try:
            st7.St7CloseFile(uID)                                        # chiudi
        finally:
            st7.St7Release()                                             # release

# ---------- mesh sezione I su un segmento -----------------------------------

def _mesh_I_on_segment(uID, P0, P1,
                       D, B1, B2, tw, tf1, tf2,
                       prop_tw, prop_tf1, prop_tf2,
                       nx=1, ny=1, nz=1,
                       ez_hint=None):                     # <-- nuovo argomento
    """
    Plate su piani medi: flange a z=±(D/2 - tf/2), web su y=0.
    Asse locale s = P0→P1.
    """
    ex = _unit(_vsub(P1, P0))                             # asse lungo segmento
    ex = _unit(_vsub(P1, P0))  # asse lungo

    if ez_hint is not None:
        # proietta ez_hint sul piano ortogonale a ex e normalizza
        ezp = _vsub(ez_hint, _smul(_dot(ez_hint, ex), ex))
        ez  = _unit(ezp)
        ey  = _unit(_cross(ez, ex))   # terna destra -> web nel piano {ex, ez}
    else:
        zref = (0.0,0.0,1.0) if abs(_dot(ex,(0.0,0.0,1.0))) < 0.95 else (1.0,0.0,0.0)
        ey = _unit(_cross(zref, ex))
        ez = _unit(_cross(ex, ey))

    L  = _norm(_vsub(P1, P0))                             # lunghezza

    z_top = +(D/2.0 - tf2/2.0)                            # piani medi flange
    z_bot = -(D/2.0 - tf1/2.0)

    def G(s,y,z):                                         # locale→globale
        return _vadd(P0, _vadd(_smul(s,ex), _vadd(_smul(y,ey), _smul(z,ez))))

    next_node, next_plate = _next_ids(uID)                # ID liberi

    sx = [L*i/nx for i in range(nx+1)]                    # griglie
    ys_top = [-B2/2 + B2*j/ny for j in range(ny+1)]
    ys_bot = [-B1/2 + B1*j/ny for j in range(ny+1)]
    zz     = [z_bot + (z_top-z_bot)*k/nz for k in range(nz+1)]

    # flange top
    grid = [[0]*(ny+1) for _ in range(nx+1)]
    for i,s in enumerate(sx):
        for j,y in enumerate(ys_top):
            _new_node(uID, next_node, G(s,y,z_top)); grid[i][j]=next_node; next_node+=1
    for i in range(nx):
        for j in range(ny):
            _quad4(uID, next_plate, prop_tf2, grid[i][j], grid[i+1][j], grid[i+1][j+1], grid[i][j+1]); next_plate+=1

    # flange bottom
    grid = [[0]*(ny+1) for _ in range(nx+1)]
    for i,s in enumerate(sx):
        for j,y in enumerate(ys_bot):
            _new_node(uID, next_node, G(s,y,z_bot)); grid[i][j]=next_node; next_node+=1
    for i in range(nx):
        for j in range(ny):
            _quad4(uID, next_plate, prop_tf1, grid[i][j], grid[i+1][j], grid[i+1][j+1], grid[i][j+1]); next_plate+=1

    # web
    grid = [[0]*(nz+1) for _ in range(nx+1)]
    for i,s in enumerate(sx):
        for k,z in enumerate(zz):
            _new_node(uID, next_node, G(s,0.0,z)); grid[i][k]=next_node; next_node+=1
    for i in range(nx):
        for k in range(nz):
            _quad4(uID, next_plate, prop_tw, grid[i][k], grid[i+1][k], grid[i+1][k+1], grid[i][k+1]); next_plate+=1

def _mesh_panel_web(uID, C, ex, ez, half_len_ex, z_bot, z_top, prop, nx=2, nz=2):
        # ex = verso trave; ez = verso colonna; il pannello sta nel piano {ex, ez}
        ex = _unit(ex)
        ez = _unit(ez)

        # generatori punti: C + s*ex + z*ez
        def G(s, z): 
            return _vadd(C, _vadd(_smul(s, ex), _smul(z, ez)))

        next_node, next_plate = _next_ids(uID)

        # coordinate lungo ex e ez
        sx = [-half_len_ex + 2.0*half_len_ex*i/nx for i in range(nx+1)]       # da -L/2 a +L/2
        zz = [z_bot + (z_top - z_bot)*k/nz for k in range(nz+1)]              # da z_bot a z_top

        # nodi griglia
        grid = [[0]*(nz+1) for _ in range(nx+1)]
        for i, s in enumerate(sx):
            for k, z in enumerate(zz):
                _new_node(uID, next_node, G(s, z))
                grid[i][k] = next_node
                next_node += 1

        # QUAD4 con property `prop`
        for i in range(nx):
            for k in range(nz):
                _quad4(uID, next_plate, prop,
                    grid[i][k], grid[i+1][k], grid[i+1][k+1], grid[i][k+1])
                next_plate += 1

# ---------- API principale ---------------------------------------------------

def build_joint_plates(
    model_path,                                                         # percorso .st7 locale
    nodes_info,                                                         # dict con centro+vicini (dallo step 13)
    beam_dims,                                                          # dimensioni trave dict
    col_dims,                                                           # dimensioni colonna dict
    prop_names,                                                         # nomi property plate
    meshing=None,                                                       # parametri mesh opzionali
    starts=None                                                         # dict opzionale con punti start locali
):
    """
    Crea:
      - trave: START_beam → centro
      - colonna alta: START_top → quota z_top della trave al centro
      - colonna bassa: START_bot → quota z_bot della trave al centro
    Tutto su piani medi.
    """
    nx = (meshing or {}).get("nx", 1)                                  # suddivisioni lungo
    ny = (meshing or {}).get("ny", 1)                                   # suddivisioni larghezza
    nz = (meshing or {}).get("nz", 1)                                   # suddivisioni altezza

    uID = 1                                                             # id sessione
    _ck(st7.St7Init(), "Init")                                          # init API
    try:
        _ck(st7.St7OpenFile(uID, model_path.encode("utf-8"), b""), "Open")  # apri .st7

        C = tuple(nodes_info["ref_node"]["xyz"])                        # coordinate nodo centrale

        if starts:                                                      # se passati i tre start locali
            H = tuple(starts["beam"])                                   # start trave
            T = tuple(starts["top"])                                    # start colonna alta
            B = tuple(starts["bot"])                                    # start colonna bassa
        else:                                                           # fallback: usa i vicini del global
            cx, cy, _ = C                                               # centro x,y
            neigh = nodes_info["neighbors"]                             # tre vicini
            h_neigh = max(neigh, key=lambda n: abs(n["xyz"][0] - cx))   # più orizzontale
            others  = [n for n in neigh if n is not h_neigh]            # gli altri due
            top_neigh = max(others, key=lambda n: n["xyz"][1])          # sopra
            bot_neigh = min(others, key=lambda n: n["xyz"][1])          # sotto
            H = tuple(h_neigh["xyz"])                                   # coord start trave
            T = tuple(top_neigh["xyz"])                                 # coord start colonna alta
            B = tuple(bot_neigh["xyz"])                                 # coord start colonna bassa

        pb_tw  = _get_propnum_by_name(uID, prop_names["beam"]["tw"])    # numero prop web trave
        pb_tf1 = _get_propnum_by_name(uID, prop_names["beam"]["tf1"])   # numero prop flange inf trave
        pb_tf2 = _get_propnum_by_name(uID, prop_names["beam"]["tf2"])   # numero prop flange sup trave
        pc_tw  = _get_propnum_by_name(uID, prop_names["col"]["tw"])     # numero prop web colonna
        pc_tf1 = _get_propnum_by_name(uID, prop_names["col"]["tf1"])    # numero prop flange inf colonna
        pc_tf2 = _get_propnum_by_name(uID, prop_names["col"]["tf2"])    # numero prop flange sup colonna

        # vettori
        ex_beam = _unit(_vsub(C, H))   # direzione trave
        ez_col  = _unit(_vsub(T, C))   # asse colonna

        # vettori
        ex_beam = _unit(_vsub(C, H))   # direzione trave
        ez_col  = _unit(_vsub(T, C))   # asse colonna

        # 1) TRAVE: H -> end_beam (stop a metà D colonna)
        end_beam = _vadd(C, _smul(-0.5*col_dims["D"]+col_dims["tf1"]/2, ex_beam))
        _mesh_I_on_segment(
            uID, H, end_beam,
            beam_dims["D"], beam_dims["B1"], beam_dims["B2"],
            beam_dims["tw"], beam_dims["tf1"], beam_dims["tf2"],
            prop_tw=pb_tw, prop_tf1=pb_tf1, prop_tf2=pb_tf2,
            nx=nx, ny=ny, nz=nz,
            ez_hint=ez_col                 # web standard
        )

        # 2) COLONNA: web contenente la direzione della trave
        ez_hint = ex_beam               # voglio il piano {ex_col, ez_hint} // beam

        P_end_top = _vadd(C, _smul(+(beam_dims["D"]/2.0 - beam_dims["tf2"]/2.0), ez_col))
        _mesh_I_on_segment(
            uID, T, P_end_top,
            col_dims["D"], col_dims["B1"], col_dims["B2"],
            col_dims["tw"], col_dims["tf1"], col_dims["tf2"],
            prop_tw=pc_tw, prop_tf1=pc_tf1, prop_tf2=pc_tf2,
            nx=nx, ny=ny, nz=max(nz,2),
            ez_hint=ez_hint             # <--- orientamento corretto
        )

        P_end_bot = _vadd(C, _smul(-(beam_dims["D"]/2.0 - beam_dims["tf1"]/2.0), ez_col))
        _mesh_I_on_segment(
            uID, B, P_end_bot,
            col_dims["D"], col_dims["B1"], col_dims["B2"],
            col_dims["tw"], col_dims["tf1"], col_dims["tf2"],
            prop_tw=pc_tw, prop_tf1=pc_tf1, prop_tf2=pc_tf2,
            nx=nx, ny=ny, nz=max(nz,2),
            ez_hint=ez_hint             # <--- orientamento corretto
        )

        # --- PANNELLO NODALE: nel piano delle anime, property "t_panel.modale" (ID 7)
        panel_prop = _get_propnum_by_name(uID, "t_panel.modale")   # creato nello step 19
        Wpanel = float(col_dims["D"]) - col_dims["tf1"] - col_dims["tf2"]  # larghezza = D_colonna / 2
        _mesh_panel_web(
            uID,
            C=C,                      # centro giunto
            ex=ex_beam,               # asse trave
            ez=ez_col,                # asse colonna
            half_len_ex=Wpanel/2,        # ± D_col/2 lungo ex
            z_bot=-(beam_dims["D"]/2.0 - beam_dims["tf1"]/2.0),   # piano medio flange inf trave
            z_top= +(beam_dims["D"]/2.0 - beam_dims["tf2"]/2.0),  # piano medio flange sup trave
            prop=panel_prop,
            nx=2, nz=2                # 2 in x, 2 in y (ex, ez)
        )


        _ck(st7.St7SaveFile(uID), "Save")                               # salva file
    finally:
        try:
            st7.St7CloseFile(uID)                                       # chiudi file
        finally:
            st7.St7Release()                                            # release API
