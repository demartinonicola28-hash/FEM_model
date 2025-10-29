# local_model/mesh_plate.py
# Step 1: PLATE -> FACE  |  Step 2: FACE -> Surface AutoMesh
# Compatibile con varianti API (firme 4/5 argomenti) e con entity tyGEOMETRYFACE.

import os
import ctypes as ct
import St7API as st7

# --------------------------- Helpers comuni ---------------------------------
def ck(code, msg=""):
    if code != 0:
        # messaggio API facoltativo
        buf = (ct.c_char * 512)()
        try:
            st7.St7GetAPIErrorString(int(code), buf, 512)
            err = buf.value.decode(errors="ignore")
        except Exception:
            err = "n/a"
        raise RuntimeError(f"{msg} (St7 err={code}: {err})")

def _get_gint(index: int) -> int:
    v = ct.c_long()
    ck(st7.St7GetGlobalIntegerValue(index, ct.byref(v)), f"GetGlobalIntegerValue({index})")
    return int(v.value)

def _count(uID: int, etype: int) -> int:
    n = ct.c_long()
    ck(st7.St7GetTotal(uID, etype, ct.byref(n)), "GetTotal")
    return int(n.value)

# --------------------------- Step 1: Plate -> Face --------------------------
def _select_all_plates(uID: int):
    """Seleziona TUTTI i plate con St7SetAllEntitySelectState."""
    fn = st7.St7SetAllEntitySelectState
    try:
        fn.argtypes = [ct.c_long, ct.c_long, ct.c_long]  # uID, Entity, Selected
        ck(fn(uID, st7.tyPLATE, st7.btTrue), "SetAllEntitySelectState tyPLATE")
    except TypeError:
        fn.argtypes = [ct.c_long, ct.c_long, ct.c_long, ct.c_long]
        ck(fn(uID, st7.tyPLATE, st7.btTrue, 0), "SetAllEntitySelectState tyPLATE (4 args)")

def _face_from_plate(uID: int):
    """Chiama St7FaceFromPlate con firma a 5 o 4 argomenti."""
    fn = st7.St7FaceFromPlate
    try:
        fn.argtypes = [ct.c_long, ct.c_long, ct.c_long, ct.c_long, ct.c_void_p]
        ck(fn(uID, st7.btTrue, st7.btTrue, st7.btFalse, ct.c_void_p(0)), "FaceFromPlate (5 args)")
    except TypeError:
        fn.argtypes = [ct.c_long, ct.c_long, ct.c_long, ct.c_long]
        ck(fn(uID, st7.btTrue, st7.btTrue, st7.btFalse), "FaceFromPlate (4 args)")

def plates_to_faces(uID: int, delete_sources: bool = True) -> int:
    """Converte tutti i PLATE in GEOMETRYFACE. Ritorna #FACE create."""
    ck(st7.St7ClearGlobalIntegerValues(), "ClearGlobalIntegerValues")

    nplates = _count(uID, st7.tyPLATE)
    print(f"[INFO] PLATE presenti: {nplates}")
    if nplates == 0:
        raise RuntimeError("Nessun PLATE presente nel modello")

    _select_all_plates(uID)  # selezione completa

    if delete_sources:
        ck(st7.St7SetSourceAction(uID, st7.saDelete), "SetSourceAction(saDelete)")

    _face_from_plate(uID)

    faces_created = _get_gint(st7.ivFacesCreated)
    tess_fail     = _get_gint(st7.ivTessellationsFailed)
    nfaces        = _count(uID, st7.tyGEOMETRYFACE)  # attenzione: GEOMETRYFACE
    print(f"[FaceFromPlate] facesCreated={faces_created} tessFail={tess_fail} GEOMETRYFACE totali={nfaces}")
    return faces_created

def run_plates_to_faces(model_path: str, delete_sources: bool = True) -> int:
    """Apre -> PLATE→FACE -> salva -> chiude. Ritorna #FACE create."""
    uID = 11
    ck(st7.St7Init(), "Init API")
    try:
        ck(st7.St7OpenFile(uID, os.fspath(model_path).encode("utf-8"), b""), "Open model")
        made = plates_to_faces(uID, delete_sources=delete_sources)
        ck(st7.St7SaveFile(uID), "Save")
        return made
    finally:
        try:
            ck(st7.St7CloseFile(uID), "Close")
        finally:
            st7.St7Release()

# --------------------------- Step 2: Face -> Surface AutoMesh ----------------
def _surface_mesh_call(uID, IntA, DblA, mode):
    """Chiama St7SurfaceMesh provando 5 arg, poi 4."""
    fn = st7.St7SurfaceMesh
    try:
        fn.argtypes = [ct.c_long, ct.POINTER(ct.c_long), ct.POINTER(ct.c_double), ct.c_long, ct.c_void_p]
        ck(fn(uID, IntA, DblA, mode, ct.c_void_p(0)), "SurfaceMesh (5 args)")
    except TypeError:
        fn.argtypes = [ct.c_long, ct.POINTER(ct.c_long), ct.POINTER(ct.c_double), ct.c_long]
        ck(fn(uID, IntA, DblA, mode), "SurfaceMesh (4 args)")

def faces_automesh(uID: int, mesh_size_abs: float):
    """Surface AutoMesh su tutte le GEOMETRYFACE con i parametri richiesti."""
    if not (isinstance(mesh_size_abs, (int, float)) and mesh_size_abs > 0):
        raise ValueError("mesh_size_abs non valido")

    nfaces = _count(uID, st7.tyGEOMETRYFACE)
    if nfaces == 0:
        raise RuntimeError("Nessuna GEOMETRYFACE presente")

    # Integers[0..10]
    IntA = (ct.c_long * 11)()
    IntA[st7.ipSurfaceMeshMode]                  = st7.mmCustom
    IntA[st7.ipSurfaceMeshSizeMode]              = st7.smAbsolute
    IntA[st7.ipSurfaceMeshTargetNodes]           = 4                # quad target
    IntA[st7.ipSurfaceMeshTargetPropertyID]      = -1               # usa la property della Face
    IntA[st7.ipSurfaceMeshAutoCreateProperties]  = st7.btFalse
    IntA[st7.ipSurfaceMeshMinEdgesPerCircle]     = 4
    IntA[st7.ipSurfaceMeshApplyTransitioning]    = st7.btTrue
    IntA[st7.ipSurfaceMeshApplySurfaceCurvature] = st7.btTrue
    IntA[st7.ipSurfaceMeshAllowUserStop]         = st7.btFalse
    IntA[st7.ipSurfaceMeshConsiderNearVertex]    = st7.btTrue
    IntA[st7.ipSurfaceMeshSelectedFaces]         = st7.btFalse      # tutte le Face



    # Doubles[0..3]
    DblA = (ct.c_double * 4)()
    DblA[st7.ipSurfaceMeshSize]                  = float(mesh_size_abs)
    DblA[st7.ipSurfaceMeshLengthRatio]           = 1.0
    DblA[st7.ipSurfaceMeshMaximumIncrease]       = 0.25
    DblA[st7.ipSurfaceMeshOnEdgesLongerThan]     = 0.0

    ck(st7.St7ClearGlobalIntegerValues(), "ClearGlobalIntegerValues")
    _surface_mesh_call(uID, IntA, DblA, st7.ieQuietRun)  # nessuna progress bar

    meshed  = _get_gint(st7.ivFacesMeshed)
    pmeshed = _get_gint(st7.ivFacesPartiallyMeshed)
    nmeshed = _get_gint(st7.ivFacesNotMeshed)
    print(f"[SurfaceMesh] in={nfaces} meshed={meshed} partial={pmeshed} notMeshed={nmeshed}")
    return meshed, pmeshed, nmeshed

def run_faces_automesh(model_path: str, mesh_size_abs: float):
    """Apre -> AutoMesh Face -> elimina tutte le GEOMETRYFACE -> salva -> chiude."""
    uID = 12
    ck(st7.St7Init(), "Init API")
    try:
        ck(st7.St7OpenFile(uID, os.fspath(model_path).encode("utf-8"), b""), "Open model")
        faces_automesh(uID, mesh_size_abs)
        _purge_geometry_faces(uID)   # invalida e cancella le Face dopo il mesh
        ck(st7.St7SaveFile(uID), "Save")
    finally:
        try:
            ck(st7.St7CloseFile(uID), "Close")
        finally:
            st7.St7Release()

# --------------------------- Delete GEOMETRYFACE -----------------------------
def _invalidate_all_geometry_faces(uID: int) -> int:
    nfaces = _count(uID, st7.tyGEOMETRYFACE)
    if nfaces == 0:
        return 0
    st7.St7InvalidateGeometryFace.argtypes = [ct.c_long, ct.c_long]
    for f in range(1, nfaces + 1):
        ck(st7.St7InvalidateGeometryFace(uID, f), f"InvalidateGeometryFace({f})")
    return nfaces

def _purge_geometry_faces(uID: int) -> int:
    marked = _invalidate_all_geometry_faces(uID)
    if marked:
        st7.St7DeleteInvalidGeometry.argtypes = [ct.c_long]
        ck(st7.St7DeleteInvalidGeometry(uID), "DeleteInvalidGeometry")
    left = _count(uID, st7.tyGEOMETRYFACE)
    print(f"[PurgeFaces] invalidated={marked} remaining={left}")
    return marked
