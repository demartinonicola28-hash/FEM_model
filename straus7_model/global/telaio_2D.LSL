*SOLUTION COMMENCED AT 18:11 ON 27/10/2025 
  
 Straus7 [R3.1.6][Solver Build R3.1.6] (64-Bit) 
  
 LICENCED TO                 : PINECA UNIPD 50 POSTI DI LAVORO 
  
 ANALYSIS TYPE               : LINEAR STATIC 
  
 COMPUTER NAME               : PC-105 
 USER LOGON NAME             : demnic15950 
 CPU                         : Intel(R) Core(TM) i7-8700 CPU @ 3.20GHz 
 USABLE PHYSICAL MEMORY      : 15.8 GB 
 USABLE VIRTUAL MEMORY       : 18.2 GB 
  
 MODEL FILE                  : "C:\Users\demnic15950\Downloads\FEM_model\straus7_model\global\telaio_2D.st7" 
 RESULT FILE                 : "C:\Users\demnic15950\Downloads\FEM_model\straus7_model\global\telaio_2D.LSA" 
 SCRATCH PATH                : "C:\Users\demnic15950\Downloads\FEM_model\straus7_model\global\" 
  
 TOTALS 
 Nodes                       : 30 
 Beams                       : 32 
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
  
 NUMBER OF EQUATIONS         : 84 
 MATRIX FILL-IN              : 30.1% 
 [K] MATRIX SIZE             : 4.9 KB 
 OPTIMUM RAM NEEDED          : 128.0 KB 
 FREE SCRATCH SPACE          : 177.5 GB 
  
*WARNING[237]:Default freedom conditions might be over-constrained - one or more elements might require additional freedoms. 
  
 SUMMATION OF APPLIED LOADS  
          Case        FX           FY           FZ           MX           MY           MZ        Case Name 
 Beams       1   +0.00000E+00 -1.19107E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "1:G1" 
             2   +0.00000E+00 -3.50000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +4.54747E-12   "2:G2" 
             3   +0.00000E+00 -2.35000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +3.63798E-12   "3:Q" 
 Total       1   +0.00000E+00 -1.19107E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "1:G1" 
             2   +0.00000E+00 -3.50000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +4.54747E-12   "2:G2" 
             3   +0.00000E+00 -2.35000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +3.63798E-12   "3:Q" 
 Vector      1   +0.00000E+00 -1.14272E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "1:G1" 
             2   +0.00000E+00 -3.50000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +4.09273E-12   "2:G2" 
             3   +0.00000E+00 -2.35000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +3.18323E-12   "3:Q" 
  
 SUMMATION OF MOMENTS OF APPLIED LOADS ABOUT THE ORIGIN [Vector]  
          Case        MXo          MYo          MZo       Case Name 
             1   +0.00000E+00 +0.00000E+00 -2.85681E+04   "1:G1" 
             2   +0.00000E+00 +0.00000E+00 -8.75000E+05   "2:G2" 
             3   +0.00000E+00 +0.00000E+00 -5.87500E+05   "3:Q" 
  
 Reducing 84 equations using 128.0 KB RAM for [K] of 4.9 KB... 
  
 MAXIMUM PIVOT               : 1.724907E+09 (Node 22 DY) 
 MINIMUM PIVOT               : 3.750915E+05 (Node 5 DX) 
  
 Results for 3 load cases... 
  
 MAXIMUM NODE DISPLACEMENT MAGNITUDES 
   Case        DX           DY           DZ           RX           RY           RZ       Case Name 
      1    3.27803E-05  2.37897E-04  0.00000E+00  0.00000E+00  0.00000E+00  1.02919E-04  "1:G1" 
      2    2.23108E-03  1.36990E-02  0.00000E+00  0.00000E+00  0.00000E+00  7.00482E-03  "2:G2" 
      3    1.96827E-03  8.85417E-03  0.00000E+00  0.00000E+00  0.00000E+00  3.94950E-03  "3:Q" 
  
 DIRECT SUMMATION OF NODE REACTION FORCES 
   Case        FX           FY           FZ           MX           MY           MZ       Case Name 
      1   +1.42109E-14 +1.19107E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 -1.40687E-12  "1:G1" 
      2   +9.09495E-13 +3.50000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.63709E-11  "2:G2" 
      3   +9.09495E-13 +2.35000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.09184E-11  "3:Q" 
  
 TOTAL CPU TIME              : 0.016 Seconds 
  
 
*SUMMARY OF MESSAGES
*Number of Notes    : 0
*Number of Warnings : 1
*Number of Errors   : 0
 
*SOLUTION COMPLETED AT 18:11 ON 27/10/2025 
*SOLUTION TIME: 0 Seconds 
