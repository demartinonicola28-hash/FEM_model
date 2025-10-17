# create_file.py

import os
import ctypes as ct
import St7API as st

def _ck(i, msg=""):
    if i != 0:
        try:
            buf = (ct.c_char * 512)()
            st.St7GetAPIErrorString(i, buf, ct.sizeof(buf))
            e = buf.value.decode("utf-8", errors="ignore")
        except Exception:
            e = str(i)
        raise RuntimeError(f"{msg} | St7 err={e}")

def _linspace_pts(p0, p1, n_mid):
    if n_mid <= 0:
        return []
    x0, y0, z0 = map(float, p0); x1, y1, z1 = map(float, p1)
    pts, denom = [], float(n_mid + 1)
    for k in range(1, n_mid + 1):
        t = k / denom
        pts.append((x0 + t*(x1-x0), y0 + t*(y1-y0), z0 + t*(z1-z0)))
    return pts

def create_st7_with_nodes(
    model_path: str,
    nodes: list[dict],
    keep_ids: bool = False,
    center_index: int = 0,
    n_intermediate: int = 1
) -> dict:
    if not nodes or len(nodes) < 4:
        raise ValueError("Attesi 4 nodi: 1 centrale + 3 periferici.")
    if not (0 <= center_index < len(nodes)):
        raise ValueError("center_index fuori intervallo.")
    os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)

    center_xyz = tuple(nodes[center_index]["xyz"])
    per_indices = [i for i in range(len(nodes)) if i != center_index][:3]
    peripheral_xyz = [tuple(nodes[i]["xyz"]) for i in per_indices]

    uID = 1
    _ck(st.St7Init(), "Init")
    created_base_ids = []
    created_intermediate_ids = [[], [], []]
    created_beam_ids = []
    try:
        _ck(st.St7NewFile(uID, model_path.encode("utf-8"), b""), "NewFile")

        try:
            # --- NODI BASE
            next_num = 1
            for i, nd in enumerate(nodes):
                num = int(nd["id"]) if keep_ids and ("id" in nd) and nd["id"] else next_num
                if not (keep_ids and ("id" in nd) and nd["id"]):
                    next_num += 1
                x, y, z = map(float, nd["xyz"])
                _ck(st.St7SetNodeXYZ(uID, num, (ct.c_double*3)(x, y, z)), f"SetNode {num}")
                created_base_ids.append(num)

            center_id = created_base_ids[center_index]
            per_ids   = [created_base_ids[i] for i in per_indices]

            # --- NODI INTERMEDI
            if n_intermediate > 0:
                for b_idx, p_xyz in enumerate(peripheral_xyz):
                    for pt in _linspace_pts(center_xyz, p_xyz, n_intermediate):
                        num = next_num; next_num += 1
                        _ck(st.St7SetNodeXYZ(uID, num, (ct.c_double*3)(*pt)), f"SetNode mid {num}")
                        created_intermediate_ids[b_idx].append(num)
            else:
                # se non richiesti, creo comunque il punto di mezzeria
                for b_idx, p_xyz in enumerate(peripheral_xyz):
                    mx = tuple((a+b)/2.0 for a,b in zip(center_xyz, p_xyz))
                    num = next_num; next_num += 1
                    _ck(st.St7SetNodeXYZ(uID, num, (ct.c_double*3)(*mx)), f"SetNode mid {num}")
                    created_intermediate_ids[b_idx].append(num)

            # --- CREA 3 BEAM: periferico ↔ nodo di MEZZERIA, Prop = 1 (Columns) o 2 (Beams) in base all’orientamento
            next_beam = 1
            # coord mezzerie per il test dx/dy (calcoliamo da coordinate note)
            mid_xyz_by_branch = []
            for b_idx, p_xyz in enumerate(peripheral_xyz):
                if created_intermediate_ids[b_idx]:
                    # nodo di mezzeria già creato; ricostruiamo la sua XYZ:
                    if n_intermediate > 0:
                        t = 0.5  # “mezzeria” geometrica lungo il segmento centro→periferico
                        mx = tuple(c + t*(p - c) for c, p in zip(center_xyz, p_xyz))
                    else:
                        # caso n_intermediate=0: abbiamo creato proprio il punto medio
                        mx = tuple((c + p) / 2.0 for c, p in zip(center_xyz, p_xyz))
                else:
                    # fallback: punto medio
                    mx = tuple((c + p) / 2.0 for c, p in zip(center_xyz, p_xyz))
                mid_xyz_by_branch.append(mx)

            for b_idx, per_id in enumerate(per_ids):
                mids = created_intermediate_ids[b_idx]
                mid_id = mids[(len(mids)-1)//2]  # nodo in “mezzeria”
                # orientamento: confronta Δx e Δy tra periferico e mezzeria
                px, py, pz = peripheral_xyz[b_idx]
                mx, my, mz = mid_xyz_by_branch[b_idx]
                dx = abs(px - mx)
                dy = abs(py - my)
                prop_num = 2 if dx >= dy else 1   # 2 = Beams (orizzontale), 1 = Columns (verticale)

                conn = (ct.c_long * 4)()
                conn[0] = 2
                conn[1] = per_id
                conn[2] = mid_id
                _ck(st.St7SetElementConnection(uID, st.tyBEAM, next_beam, prop_num, conn),
                    f"SetElementConnection BEAM {next_beam}")
                created_beam_ids.append(next_beam)
                next_beam += 1

            _ck(st.St7SaveFile(uID), "SaveFile")

        finally:
            _ck(st.St7CloseFile(uID), "CloseFile")
    finally:
        st.St7Release()

    return {
        "base_node_ids": created_base_ids,
        "intermediate_ids_by_branch": created_intermediate_ids,
        "beam_ids": created_beam_ids
    }

