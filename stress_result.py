# stress_result.py
# Requisito: modulo St7API.py sul PYTHONPATH e St7API.dll accessibile.
# Unità: fornire fy nelle stesse unità di sforzo del modello Straus7.

from St7API import (
    St7Init, St7CloseFile, St7UnLoad, St7SetResultUserEquation,
    St7StoreResultUserEquation, St7GetResultUserEquation,
    tyBEAM, auRadian
)
import ctypes as ct

def set_beam_util_equation(uID: int, fy: float, name: str = "UTIL_N+M+V") -> None:
    """
    Definisce e attiva un'equazione di verifica per beam:
      σ_ext = [AxF]/[Area] + max(|[BM1]/[Z11p]|, |[BM1]/[Z11n]|) + max(|[BM2]/[Z22p]|, |[BM2]/[Z22n]|)
      τ_eq  = sqrt( ([SF1]/[SA1])^2 + ([SF2]/[SA2])^2 )
      η     = sqrt( σ_ext^2 + 3*τ_eq^2 ) / fy  <= 1

    Dove:
      [AxF], [BM1], [BM2], [SF1], [SF2] = forze/momenti interni del beam
      [Area], [Z11p/n], [Z22p/n], [SA1], [SA2] = proprietà di sezione disponibili come variabili primarie
    L’equazione è memorizzata e impostata come attiva per i risultati dei beam (contour). 
    Riferimenti API/variabili: St7SetResultUserEquation; elenco “Beam Primary Variables”. 
    """

    # Costruzione stringa equazione con fy numerico
    eq = (
        "SQRT(("
        "[AxF]/[Area] + MAX(ABS([BM1]/[Z11p]),ABS([BM1]/[Z11n])) "
        "+ MAX(ABS([BM2]/[Z22p]),ABS([BM2]/[Z22n]))"
        ")^2 + 3*SQR(SQRT(SQR([SF1]/[SA1]) + SQR([SF2]/[SA2]))))"
        f"/{fy}"
    )

    # Preparazione argomenti C
    eq_bytes = ct.create_string_buffer(eq.encode('utf-8'))
    name_bytes = ct.create_string_buffer(name.encode('utf-8'))

    # 1) Imposta l'equazione attiva per i BEAM (TrigType irrilevante qui, uso radianti)
    ierr = St7SetResultUserEquation(uID, tyBEAM, eq_bytes, auRadian)
    if ierr != 0:
        raise RuntimeError(f"St7SetResultUserEquation failed, iErr={ierr}")

    # 2) Salva l'equazione nell’archivio del modello con un nome
    ierr = St7StoreResultUserEquation(uID, tyBEAM, name_bytes, eq_bytes, auRadian)
    if ierr != 0:
        raise RuntimeError(f"St7StoreResultUserEquation failed, iErr={ierr}")

def demo_attach(uID: int) -> None:
    """Esempio rapido: definisce fy e chiama la configurazione. Integra nel tuo main."""
    fy = 355.0  # MPa, esempio. Allineare alle unità del modello.
    set_beam_util_equation(uID, fy, name="UTIL_NMV_355")

# Note operative:
# - L’equazione è usabile nel contour dei Beam Results subito dopo l’impostazione. :contentReference[oaicite:2]{index=2}
# - Variabili primarie usate: [AxF],[BM1],[BM2],[SF1],[SF2],[Area],[Z11p/n],[Z22p/n],[SA1],[SA2]. :contentReference[oaicite:3]{index=3}
