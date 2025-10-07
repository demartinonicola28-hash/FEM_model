*SOLUTION COMMENCED AT 18:16 ON 07/10/2025 
  
 Straus7 [R3.1.6][Solver Build R3.1.6] (64-Bit) 
  
 LICENCED TO                 : PINECA UNIPD 50 POSTI DI LAVORO 
  
 ANALYSIS TYPE               : LINEAR STATIC 
  
 COMPUTER NAME               : PC-103 
 USER LOGON NAME             : demnic15950 
 CPU                         : Intel(R) Core(TM) i7-8700 CPU @ 3.20GHz 
 USABLE PHYSICAL MEMORY      : 15.8 GB 
 USABLE VIRTUAL MEMORY       : 18.2 GB 
  
 MODEL FILE                  : "C:\Users\demnic15950\Downloads\FEM_model\telaio_2D.st7" 
 RESULT FILE                 : "C:\Users\demnic15950\Downloads\FEM_model\telaio_2D.LSA" 
 SCRATCH PATH                : "C:\Users\demnic15950\Straus7 R31\Tmp\" 
  
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
 FREE SCRATCH SPACE          : 176.1 GB 
  
*WARNING[237]:Default freedom conditions might be over-constrained - one or more elements might require additional freedoms. 
  
 SUMMATION OF APPLIED LOADS  
          Case        FX           FY           FZ           MX           MY           MZ        Case Name 
 Beams       1   +0.00000E+00 -1.04634E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +5.68434E-14   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.53477E-12   "3:Q" 
 Total       1   +0.00000E+00 -1.04634E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +5.68434E-14   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.53477E-12   "3:Q" 
 Vector      1   +0.00000E+00 -9.47343E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.84217E-14   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 -9.09495E-13   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.42109E-12   "3:Q" 
  
 SUMMATION OF MOMENTS OF APPLIED LOADS ABOUT THE ORIGIN [Vector]  
          Case        MXo          MYo          MZo       Case Name 
             1   +0.00000E+00 +0.00000E+00 -2.36836E+04   "1:G1" 
             2   +0.00000E+00 +0.00000E+00 -4.37500E+05   "2:G2" 
             3   +0.00000E+00 +0.00000E+00 -2.12500E+05   "3:Q" 
  
 Reducing 36 equations using 128.0 KB RAM for [K] of 1.9 KB... 
  
 MAXIMUM PIVOT               : 1.545343E+09 (Node 13 DY) 
 MINIMUM PIVOT               : 1.249871E+06 (Node 7 DX) 
  
 Results for 3 load cases... 
  
 MAXIMUM NODE DISPLACEMENT MAGNITUDES 
   Case        DX           DY           DZ           RX           RY           RZ       Case Name 
      1    9.24501E-06  9.72150E-05  0.00000E+00  0.00000E+00  0.00000E+00  4.12853E-05  "1:G1" 
      2    4.57870E-04  4.36125E-03  0.00000E+00  0.00000E+00  0.00000E+00  2.04470E-03  "2:G2" 
      3    5.92174E-04  3.01616E-03  0.00000E+00  0.00000E+00  0.00000E+00  1.54800E-03  "3:Q" 
  
 DIRECT SUMMATION OF NODE REACTION FORCES 
   Case        FX           FY           FZ           MX           MY           MZ       Case Name 
      1   +2.84217E-14 +1.04634E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 -1.13687E-13  "1:G1" 
      2   +0.00000E+00 +1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.00044E-10  "2:G2" 
      3   -9.09495E-13 +8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 -3.18323E-11  "3:Q" 
  
 TOTAL CPU TIME              : 0.484 Seconds 
  
 
*SUMMARY OF MESSAGES
*Number of Notes    : 0
*Number of Warnings : 1
*Number of Errors   : 0
 
*SOLUTION COMPLETED AT 18:16 ON 07/10/2025 
*SOLUTION TIME: 2 Seconds 
