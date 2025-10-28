# ltd_analysis_local.py

# Import standard library
import ctypes as ct	# Tipi C (long, double, array)
import sys	# Per argv se lanciato diretto

# Import API Straus7
import St7API as st7	# Wrapper ufficiale

# ---- Utility ---------------------------------------------------------------

def ck(err, msg):	# Check errori API
	if err != 0:	# 0 = OK
		raise RuntimeError(f"{msg} (St7 err={err})")# Eccezione con codice

def _resolve_fvt_table_id(uID, table_name):	# Accetta ID int o nome str
	"""Risolve l'ID di una tabella Factor vs Time dal suo nome."""
	if isinstance(table_name, int):	# Se è già un ID
		return int(table_name)	# Ritorna l’ID
	
	TableID = ct.c_long(0)	# Alloca out param
	name_b = str(table_name).encode("utf-8")	# Nome in bytes
	
	# Cerca una tabella di tipo Factor vs Time
	ck(st7.St7GetTableID(uID, int(st7.ttFactorVsTime), name_b, ct.byref(TableID)),
		f"St7GetTableID (FactorVsTime) ('{table_name}')")
	
	if TableID.value == 0: # St7GetTableID restituisce 0 se non trova
		raise RuntimeError(f"Tabella Factor vs Time non trovata: '{table_name}'")
	
	return TableID.value	# ID tabella

# ---- Configurazione e run LTD (Modello Locale) ----------------------------

def run_LTD_local(uID):	# Funzione principale LTD locale
	# 0) Solver DLL (integrazione in-process)
	try:
		ck(st7.St7SetUseSolverDLL(st7.btTrue), "Use solver DLL")
	except Exception:
		pass

	# 1) Metodo tempo: Newmark
	try:
		ck(st7.St7SetLTAMethod(uID, st7.ltNewmark), "Set Newmark")
	except Exception:
		pass

	# 2) Solution type: Full System
	set_full_ok = False
	try:
		ck(st7.St7SetLTASolutionType(uID, st7.stFullSystem), "Set FullSystem")
		set_full_ok = True
	except Exception:
		try:
			ck(st7.St7SetSolverDefaultsLogical(uID, st7.spFullSystemTransient, st7.btTrue),
				"Force FullSystem via defaults")
			set_full_ok = True
		except Exception:
			pass
	if not set_full_ok:
		print("ATTENZIONE: Full System non impostato esplicitamente.")

	# 3) Condizioni iniziali: none
	try:
		ck(st7.St7SetTransientInitialConditionsType(uID, st7.icNone), "Set IC none")
	except Exception:
		pass

	# 4) Base excitation = None (come richiesto)
	ck(st7.St7SetTransientBaseExcitation(uID, st7.beNone), "Base = None")

	# 5) Associa tabelle Factor vs Time ai Freedom Cases
	# Si assume che il nome del Freedom Case corrisponda al nome della tabella FvT
	print("Associazione tabelle Factor vs Time ai Freedom Cases...")
	num_fc = ct.c_long(0)
	ck(st7.St7GetNumFreedomCase(uID, ct.byref(num_fc)), "Get Num Freedom Cases")
	
	if num_fc.value == 0:
		print("ATTENZIONE: Nessun Freedom Case trovato nel modello.")
	
	for i in range(1, num_fc.value + 1):
		CaseNum = i
		CaseName = ct.create_string_buffer(st7.kMaxStr) # Alloca buffer
		ck(st7.St7GetFreedomCaseName(uID, CaseNum, CaseName), f"Get FC Name ({CaseNum})")
		
		fc_name = CaseName.value.decode('utf-8')
		if not fc_name:
			print(f"ATTENZIONE: Freedom Case {CaseNum} non ha nome. Impossibile associare tabella.")
			continue

		try:
			# Il nome del FC è uguale al nome della tabella FvT
			table_name = fc_name
			print(f"  - Freedom Case {CaseNum} ('{fc_name}'):")
			
			# 5.1) Risolvi ID tabella FvT
			table_id = _resolve_fvt_table_id(uID, table_name)
			print(f"    -> Trovata tabella '{table_name}' (ID={table_id})")

			# 5.2) Applica la tabella al Freedom Case
			# Non aggiungere time steps dalla tabella (usa quelli globali)
			add_steps = st7.btFalse 
			ck(st7.St7SetTransientFreedomTimeTable(uID, CaseNum, table_id, add_steps),
				f"SetTransientFreedomTimeTable for FC {CaseNum} ('{fc_name}')")
			print(f"    -> Associata al Freedom Case {CaseNum}.")

		except Exception as e:
			print(f"ERRORE nell'associare FC {CaseNum} ('{fc_name}'): {e}")
			# Continua con gli altri FC anche se uno fallisce
			pass
	
	print("Associazione tabelle completata.")

	# 6) Time stepping: uID, Row, NumSteps, SaveEvery, TimeStep
	# (Uguale all'analisi globale, come richiesto)
	ck(st7.St7SetTimeStepUnit(uID, st7.tuSec), "Time unit = sec")
	ck(st7.St7SetTimeStepData(uID, 1, 250, 1, ct.c_double(0.1)),
		"Time step data")

	# 7) Massa beam consistente
	try:
		ck(st7.St7SetSolverDefaultsLogical(uID, st7.spLumpedMassBeam, st7.btFalse),
			"Beam mass consistent")
	except Exception:
		pass

	# 8) Avvio solver LTD (firma a 4 argomenti)
	print("Avvio solver Linear Transient Dynamic...")
	ck(st7.St7RunSolver(uID, st7.stLinearTransientDynamic, st7.smBackgroundRun, st7.btTrue),
		"Run LTD")
	print("Solver completato.")

# ---- Esecuzione diretta opzionale -----------------------------------------

if __name__ == "__main__":	# Se lanci questo file
	uid = int(sys.argv[1]) if len(sys.argv) > 1 else 1	# uID da argv o 1
	print(f"Avvio analisi LTD (locale) per uID={uid}...")
	try:
		run_LTD_local(uid)
		print(f"LTD (locale) completata con successo per uID={uid}.")
	except Exception as e:
		print(f"\nERRORE DURANTE L'ESECUZIONE per uID={uid}:")
		print(e)
		sys.exit(1) # Esce con codice di errore