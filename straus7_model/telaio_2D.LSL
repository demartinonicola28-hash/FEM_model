*SOLUTION COMMENCED AT 17:34 ON 14/10/2025 
  
 Straus7 [R3.1.6][Solver Build R3.1.6] (64-Bit) 
  
 LICENCED TO                 : PINECA UNIPD 50 POSTI DI LAVORO 
  
 ANALYSIS TYPE               : LINEAR STATIC 
  
 COMPUTER NAME               : PC-101 
 USER LOGON NAME             : demnic15950 
 CPU                         : Intel(R) Core(TM) i9-14900K 
 USABLE PHYSICAL MEMORY      : 31.7 GB 
 USABLE VIRTUAL MEMORY       : 36.4 GB 
  
 MODEL FILE                  : "C:\Users\demnic15950\Downloads\FEM_model\straus7_model\telaio_2D.st7" 
 RESULT FILE                 : "C:\Users\demnic15950\Downloads\FEM_model\straus7_model\telaio_2D.LSA" 
 SCRATCH PATH                : "C:\Users\demnic15950\Downloads\FEM_model\straus7_model\" 
  
 TOTALS 
 Nodes                       : 14 
 Beams                       : 14 
 Plates                      : 0 
 Bricks                      : 0 
 Links                       : 0 
  
 SOLVER UNITS 
 Length                      : m 
 Mass                        : kg 
 Force                       : N 
 Stress                      : Pa 
  
 FREEDOM CASE                : "1:2D Beam XY" 
  
 LOAD CASES                  : "1:G1" 
                             : "2:G2" 
                             : "3:Q" 
  
 STORAGE SCHEME              : Sparse  
 SORTING METHOD              : AMD  
 SOLUTION TYPE               : Direct  
  
 NUMBER OF EQUATIONS         : 36 
 MATRIX FILL-IN              : 25.8% 
 [K] MATRIX SIZE             : 1.9 KB 
 OPTIMUM RAM NEEDED          : 128.0 KB 
 FREE SCRATCH SPACE          : 158.3 GB 
  
*WARNING[237]:Default freedom conditions might be over-constrained - one or more elements might require additional freedoms. 
  
 SUMMATION OF APPLIED LOADS  
          Case        FX           FY           FZ           MX           MY           MZ        Case Name 
 Beams       1   +0.00000E+00 -5.95534E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.27374E-12   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.53477E-12   "3:Q" 
 Total       1   +0.00000E+00 -5.95534E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.27374E-12   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.53477E-12   "3:Q" 
 Vector      1   +0.00000E+00 -5.47189E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.42109E-14   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.27374E-12   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.42109E-12   "3:Q" 
  
 SUMMATION OF MOMENTS OF APPLIED LOADS ABOUT THE ORIGIN [Vector]  
          Case        MXo          MYo          MZo       Case Name 
             1   +0.00000E+00 +0.00000E+00 -1.36797E+04   "1:G1" 
             2   +0.00000E+00 +0.00000E+00 -4.37500E+05   "2:G2" 
             3   +0.00000E+00 +0.00000E+00 -2.12500E+05   "3:Q" 
  
 Reducing 36 equations using 128.0 KB RAM for [K] of 1.9 KB... 
  
 MAXIMUM PIVOT               : 7.546467E+08 (Node 13 DY) 
 MINIMUM PIVOT               : 3.614936E+05 (Node 7 DX) 
  
 Results for 3 load cases... 
  
 MAXIMUM NODE DISPLACEMENT MAGNITUDES 
   Case        DX           DY           DZ           RX           RY           RZ       Case Name 
      1    2.94409E-05  1.83597E-04  0.00000E+00  0.00000E+00  0.00000E+00  1.00552E-04  "1:G1" 
      2    2.00379E-03  1.18727E-02  0.00000E+00  0.00000E+00  0.00000E+00  6.84370E-03  "2:G2" 
      3    2.27405E-03  8.35289E-03  0.00000E+00  0.00000E+00  0.00000E+00  4.48986E-03  "3:Q" 
  
 DIRECT SUMMATION OF NODE REACTION FORCES 
   Case        FX           FY           FZ           MX           MY           MZ       Case Name 
      1   -1.42109E-14 +5.95534E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 -3.69482E-13  "1:G1" 
      2   +0.00000E+00 +1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 -3.63798E-12  "2:G2" 
      3   +0.00000E+00 +8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 -4.27463E-11  "3:Q" 
  
 TOTAL CPU TIME              : 0.031 Seconds 
  
 
*SUMMARY OF MESSAGES
*Number of Notes    : 0
*Number of Warnings : 1
*Number of Errors   : 0
 
*SOLUTION COMPLETED AT 17:34 ON 14/10/2025 
*SOLUTION TIME: 0 Seconds 
