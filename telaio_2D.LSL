*SOLUTION COMMENCED AT 09:48 ON 09/10/2025 
  
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
 FREE SCRATCH SPACE          : 166.4 GB 
  
*WARNING[237]:Default freedom conditions might be over-constrained - one or more elements might require additional freedoms. 
  
 SUMMATION OF APPLIED LOADS  
          Case        FX           FY           FZ           MX           MY           MZ        Case Name 
 Beams       1   +0.00000E+00 -7.71516E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +5.68434E-14   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.53477E-12   "3:Q" 
 Total       1   +0.00000E+00 -7.71516E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +5.68434E-14   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.53477E-12   "3:Q" 
 Vector      1   +0.00000E+00 -7.11777E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.84217E-14   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 -9.09495E-13   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +1.42109E-12   "3:Q" 
  
 SUMMATION OF MOMENTS OF APPLIED LOADS ABOUT THE ORIGIN [Vector]  
          Case        MXo          MYo          MZo       Case Name 
             1   +0.00000E+00 +0.00000E+00 -1.77944E+04   "1:G1" 
             2   +0.00000E+00 +0.00000E+00 -4.37500E+05   "2:G2" 
             3   +0.00000E+00 +0.00000E+00 -2.12500E+05   "3:Q" 
  
 Reducing 36 equations using 128.0 KB RAM for [K] of 1.9 KB... 
  
 MAXIMUM PIVOT               : 9.324933E+08 (Node 13 DY) 
 MINIMUM PIVOT               : 6.240339E+05 (Node 7 DX) 
  
 Results for 3 load cases... 
  
 MAXIMUM NODE DISPLACEMENT MAGNITUDES 
   Case        DX           DY           DZ           RX           RY           RZ       Case Name 
      1    2.37262E-05  1.40932E-04  0.00000E+00  0.00000E+00  0.00000E+00  7.56674E-05  "1:G1" 
      2    1.17507E-03  6.52640E-03  0.00000E+00  0.00000E+00  0.00000E+00  3.74752E-03  "2:G2" 
      3    1.25831E-03  4.57526E-03  0.00000E+00  0.00000E+00  0.00000E+00  2.53382E-03  "3:Q" 
  
 DIRECT SUMMATION OF NODE REACTION FORCES 
   Case        FX           FY           FZ           MX           MY           MZ       Case Name 
      1   -1.42109E-14 +7.71516E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 -1.44951E-12  "1:G1" 
      2   +0.00000E+00 +1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 -6.00267E-11  "2:G2" 
      3   +0.00000E+00 +8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.91038E-11  "3:Q" 
  
 TOTAL CPU TIME              : 0.031 Seconds 
  
 
*SUMMARY OF MESSAGES
*Number of Notes    : 0
*Number of Warnings : 1
*Number of Errors   : 0
 
*SOLUTION COMPLETED AT 09:48 ON 09/10/2025 
*SOLUTION TIME: 0 Seconds 
