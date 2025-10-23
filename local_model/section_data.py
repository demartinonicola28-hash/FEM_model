# section_data.py  — estrazione geometrie BEAM con BGL e fallback STANDARD

import os, json, ctypes as ct
import St7API as st7

def _ck(code, where=""):
    if code != 0:
        sb = ct.create_string_buffer(st7.kMaxStrLen)
        st7.St7GetAPIErrorString(code, sb, st7.kMaxStrLen)
        raise RuntimeError(f"{where}: {sb.value.decode('utf-8','ignore')}")

_BGL_MAP = {
    # BGL I-section: index -> name (vedi manuale)
    st7.bgISection: {0:"D", 1:"B1", 2:"B2", 3:"tw", 4:"tf1", 5:"tf2",
                     6:"Rr1", 7:"Rr2", 8:"Rt1", 9:"Rt2", 10:"Rt3", 11:"Rt4",
                     12:"alpha1", 13:"alpha2"},
    st7.bgTSection: {0:"D", 1:"B", 2:"tw", 3:"tf", 4:"Rr", 5:"Rt1", 6:"Rt2", 7:"Rt3",
                     8:"alpha1", 9:"alpha2", 10:"Rt1_", 11:"Rt2_", 12:"Rt3_", 13:"Rt4_",
                     14:"alpha1_", 15:"alpha2_"},
    st7.bgChannel:  {0:"D", 1:"B1", 2:"B2", 3:"tw", 4:"tf1", 5:"tf2", 6:"Rr1", 7:"Rr2", 8:"Rh1", 9:"Rh2"},
    st7.bgAngle:    {0:"D", 1:"B", 2:"tw", 3:"tf", 4:"Rr", 5:"Rh", 6:"Rt1", 7:"Rt2", 8:"Rt3", 9:"Rt4",
                     10:"alpha1", 11:"alpha2"},
    st7.bgRectangularHollow: {0:"D", 1:"B", 2:"tw", 3:"tf", 4:"Ri", 5:"Ro"},
    st7.bgBulbFlat: {0:"D", 1:"B", 2:"t", 3:"Rr", 4:"Rh", 5:"Rt1", 6:"Rt2", 7:"Rt3"},
}

_STD_KEYS = ["D1","D2","D3","T1","T2","T3"]

def _shape_name(shape):
    for k, v in {
        st7.bgISection:"bgISection", st7.bgTSection:"bgTSection",
        st7.bgChannel:"bgChannel", st7.bgAngle:"bgAngle",
        st7.bgRectangularHollow:"bgRectangularHollow", st7.bgBulbFlat:"bgBulbFlat"
    }.items():
        if shape == k:
            return v
    return str(int(shape))

def _canonical_B(record):
    if record.get("B"): return record["B"]
    b1 = record.get("B1"); b2 = record.get("B2")
    if b1 is None or b2 is None: return None
    return b1 if abs(b1 - b2) <= 1e-9*max(1.0, abs(b1), abs(b2)) else None

def _as_float(x):
    try: return float(x)
    except Exception: return None

def export_section_data(model_path, out_csv=None, out_json=None, only_props=None):
    uID = 1
    data = {}

    _ck(st7.St7Init(), "Init")
    try:
        _ck(st7.St7OpenFileReadOnly(uID, model_path.encode("utf-8"), b""), "Open (read-only)")

        nums = (ct.c_long * st7.kMaxEntityTotals)()
        last = (ct.c_long * st7.kMaxEntityTotals)()
        _ck(st7.St7GetTotalProperties(uID, nums, last), "GetTotalProperties")
        n_beam = nums[st7.ipBeamPropTotal]

        prop_numbers = []
        for idx in range(1, n_beam + 1):
            pn = ct.c_long()
            _ck(st7.St7GetPropertyNumByIndex(uID, st7.ptBEAMPROP, idx, ct.byref(pn)),
                "GetPropertyNumByIndex")
            prop_numbers.append(int(pn.value))

        if only_props:
            only = set(int(p) for p in only_props)
            prop_numbers = [p for p in prop_numbers if p in only]

        name_buf = ct.create_string_buffer(st7.kMaxStrLen)

        for pnum in prop_numbers:
            bt = ct.c_long()
            _ck(st7.St7GetBeamPropertyType(uID, pnum, ct.byref(bt)), "GetBeamPropertyType")
            if bt.value != st7.btBeam:
                continue

            _ck(st7.St7GetPropertyName(uID, st7.ptBEAMPROP, pnum, name_buf, st7.kMaxStrLen),
                "GetPropertyName")
            prop_name = name_buf.value.decode("utf-8", "ignore")

            shape = ct.c_long()
            dims  = (ct.c_double * st7.kMaxBGLDimensions)()
            err = st7.St7GetBeamSectionGeometryBGL(uID, pnum, ct.byref(shape), dims)

            rec = {"prop_num": pnum, "prop_name": prop_name, "source": None, "shape": None}

            if err == 0 and shape.value in _BGL_MAP:
                rec["source"] = "BGL"
                rec["shape"]  = _shape_name(shape.value)
                for idx, key in _BGL_MAP[shape.value].items():
                    val = _as_float(dims[idx])
                    if val not in (None, 0.0):
                        rec[key] = val
                rec["B"] = rec.get("B", _canonical_B(rec))

            else:
                sec_type = ct.c_long()
                arr6 = (ct.c_double * 6)()
                _ck(st7.St7GetBeamSectionGeometry(uID, pnum, ct.byref(sec_type), arr6),
                    "GetBeamSectionGeometry")

                rec["source"] = "STANDARD"
                rec["shape"]  = int(sec_type.value)
                for i, k in enumerate(_STD_KEYS):
                    v = _as_float(arr6[i])
                    if v not in (None, 0.0):
                        rec[k] = v

                # MAPPING CORRETTO per I-section STANDARD:
                # D1 -> B1, D2 -> B2, D3 -> D,  T1 -> tf1, T2 -> tf2, T3 -> tw
                if sec_type.value == st7.bsISection:
                    rec["B1"] = rec.get("D1")
                    rec["B2"] = rec.get("D2")
                    rec["D"]  = rec.get("D3")
                    rec["tf1"] = rec.get("T1")
                    rec["tf2"] = rec.get("T2")
                    rec["tw"]  = rec.get("T3")
                    rec["B"] = _canonical_B(rec)

            data[pnum] = rec

        if out_csv is None:
            out_csv = os.path.join(os.path.dirname(model_path), "section_data.csv")
        if out_json is None:
            out_json = os.path.join(os.path.dirname(model_path), "section_data.json")

        header = [
            "prop_num","prop_name","source","shape",
            "D","B","B1","B2","tw","tf","tf1","tf2",
            "Rr","Rr1","Rr2","Rt1","Rt2","Rt3","Rt4",
            "Ri","Ro","Rh","Rh1","Rh2",
            "alpha1","alpha2"
        ]

        with open(out_csv, "w", encoding="utf-8") as f:
            f.write(";".join(header) + "\n")
            for p in sorted(data):
                rec = data[p]
                row = [str(rec.get(k, "") if rec.get(k, "") is not None else "") for k in header]
                f.write(";".join(row) + "\n")

        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return {"csv": out_csv, "json": out_json, "data": data}

    finally:
        try:
            st7.St7CloseFile(uID)
        finally:
            st7.St7Release()
