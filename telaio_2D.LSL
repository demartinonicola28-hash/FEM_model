*SOLUTION COMMENCED AT 18:49 ON 03/10/2025 
  
 Straus7 [R3.1.6][Solver Build R3.1.6] (64-Bit) 
  
 LICENCED TO                 : PINECA UNIPD 50 POSTI DI LAVORO 
  
 ANALYSIS TYPE               : LINEAR STATIC 
  
 COMPUTER NAME               : PC-101 
 USER LOGON NAME             : demnic15950 
 CPU                         : Intel(R) Core(TM) i9-14900K 
 USABLE PHYSICAL MEMORY      : 31.7 GB 
 USABLE VIRTUAL MEMORY       : 36.4 GB 
  
 MODEL FILE                  : "C:\Users\demnic15950\Downloads\FEM_model\telaio_2D.st7" 
 RESULT FILE                 : "C:\Users\demnic15950\Downloads\FEM_model\telaio_2D.LSA" 
 SCRATCH PATH                : "C:\Users\demnic15950\Downloads\FEM_model\" 
  
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
  
 FREEDOM CASE                : "1:2d plane XY" 
  
 LOAD CASES                  : "1:G1" 
                             : "2:G2" 
                             : "3:Q" 
  
 STORAGE SCHEME              : Sparse  
 SORTING METHOD              : AMD  
 SOLUTION TYPE               : Direct  
  
 NUMBER OF EQUATIONS         : 72 
 MATRIX FILL-IN              : 26.9% 
 [K] MATRIX SIZE             : 7.3 KB 
 OPTIMUM RAM NEEDED          : 128.0 KB 
 FREE SCRATCH SPACE          : 168.5 GB 
  
 SUMMATION OF APPLIED LOADS  
          Case        FX           FY           FZ           MX           MY           MZ        Case Name 
 Beams       1   +0.00000E+00 -7.71516E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +8.52651E-14   "1:G1" 
             2   +0.00000E+00 -2.62500E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "2:G2" 
             3   +0.00000E+00 -1.27500E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 -7.95808E-13   "3:Q" 
 Total       1   +0.00000E+00 -7.71516E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +8.52651E-14   "1:G1" 
             2   +0.00000E+00 -2.62500E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "2:G2" 
             3   +0.00000E+00 -1.27500E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 -7.95808E-13   "3:Q" 
 Vector      1   +0.00000E+00 -7.11777E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +4.26326E-14   "1:G1" 
             2   +0.00000E+00 -2.62500E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "2:G2" 
             3   +0.00000E+00 -1.27500E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 -1.13687E-12   "3:Q" 
  
 SUMMATION OF MOMENTS OF APPLIED LOADS ABOUT THE ORIGIN [Vector]  
          Case        MXo          MYo          MZo       Case Name 
             1   +0.00000E+00 +0.00000E+00 -1.77944E+04   "1:G1" 
             2   +0.00000E+00 +0.00000E+00 -6.56250E+05   "2:G2" 
             3   +0.00000E+00 +0.00000E+00 -3.18750E+05   "3:Q" 
  
 Reducing 72 equations using 128.0 KB RAM for [K] of 7.3 KB... 
  
 MAXIMUM PIVOT               : 9.053333E+08 (Node 13 DY) 
 MINIMUM PIVOT               : 1.050975E+04 (Node 14 RY) 
  
 Results for 3 load cases... 
  
 MAXIMUM NODE DISPLACEMENT MAGNITUDES 
   Case        DX           DY           DZ           RX           RY           RZ       Case Name 
      1    2.44380E-05  1.45160E-04  0.00000E+00  0.00000E+00  0.00000E+00  7.79375E-05  "1:G1" 
      2    1.81548E-03  1.00833E-02  0.00000E+00  0.00000E+00  0.00000E+00  5.78992E-03  "2:G2" 
      3    1.94409E-03  7.06878E-03  0.00000E+00  0.00000E+00  0.00000E+00  3.91475E-03  "3:Q" 
  
 DIRECT SUMMATION OF NODE REACTION FORCES 
   Case        FX           FY           FZ           MX           MY           MZ       Case Name 
      1   +0.00000E+00 +7.71516E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 -7.24754E-13  "1:G1" 
      2   +0.00000E+00 +2.62500E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 -3.18323E-11  "2:G2" 
      3   +0.00000E+00 +1.27500E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.00089E-11  "3:Q" 
  
 TOTAL CPU TIME              : 0.219 Seconds 
  
 
*SUMMARY OF MESSAGES
*Number of Notes    : 0
*Number of Warnings : 0
*Number of Errors   : 0
 
*SOLUTION COMPLETED AT 18:49 ON 03/10/2025 
*SOLUTION TIME: 0 Seconds 
