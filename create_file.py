# create_file.py
# Funzione che crea un nuovo modello Straus7 (.st7) e imposta le unità di misura.

import os
import ctypes as ct

os.add_dll_directory(r"C:\Program Files\Straus7 R31\Bin64")
from St7API import *

def api_err_str(code: int) -> str:
    buf = (ct.c_char * 256)()
    St7GetAPIErrorString(code, buf, 256)
    return buf.value.decode("utf-8", errors="ignore")

def check(rc: int):
    if rc != 0:
        raise RuntimeError(f"St7 error {rc}: {api_err_str(rc)}")

def create_file(filename: str = "telaio_2d.st7"):
    """Crea un file Straus7 e imposta le unità di misura standard."""
    model_path = os.path.abspath(filename)
    uID = 1
    check(St7Init())
    check(St7NewFile(uID, model_path.encode("utf-8"), b""))

    # unità: m, kN, MPa, kg, °C, kJ
    def c_int_array(n):  return (ct.c_int * n)()
    units = c_int_array(kLastUnit)
    units[ipLENGTHU] = luMETRE
    units[ipFORCEU]  = fuKILONEWTON
    units[ipSTRESSU] = suMEGAPASCAL
    units[ipMASSU]   = muKILOGRAM
    units[ipTEMPERU] = tuCELSIUS
    units[ipENERGYU] = euKILOJOULE
    check(St7SetUnits(uID, units))

    check(St7SaveFile(uID))
    check(St7CloseFile(uID))
    return model_path

# se eseguito direttamente
if __name__ == "__main__":
    path = create_file()
    print(f"Creato: {path}")
