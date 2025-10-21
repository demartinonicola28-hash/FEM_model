*SOLUTION COMMENCED AT 18:06 ON 21/10/2025 
  
 Straus7 [R3.1.6][Solver Build R3.1.6] (64-Bit) 
  
 LICENCED TO                 : PINECA UNIPD 50 POSTI DI LAVORO 
  
 ANALYSIS TYPE               : LINEAR STATIC 
  
 COMPUTER NAME               : PC-106 
 USER LOGON NAME             : demnic15950 
 CPU                         : Intel(R) Core(TM) i7-8700 CPU @ 3.20GHz 
 USABLE PHYSICAL MEMORY      : 15.8 GB 
 USABLE VIRTUAL MEMORY       : 18.2 GB 
  
 MODEL FILE                  : "C:\Users\demnic15950\Downloads\FEM_model\straus7_model\global\telaio_2D.st7" 
 RESULT FILE                 : "C:\Users\demnic15950\Downloads\FEM_model\straus7_model\global\telaio_2D.LSA" 
 SCRATCH PATH                : "C:\Users\demnic15950\Downloads\FEM_model\straus7_model\global\" 
  
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
 FREE SCRATCH SPACE          : 172.4 GB 
  
*WARNING[237]:Default freedom conditions might be over-constrained - one or more elements might require additional freedoms. 
  
 SUMMATION OF APPLIED LOADS  
          Case        FX           FY           FZ           MX           MY           MZ        Case Name 
 Beams       1   +0.00000E+00 -3.07775E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 -1.77636E-15   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +3.63798E-12   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.27374E-13   "3:Q" 
 Total       1   +0.00000E+00 -3.07775E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 -1.77636E-15   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +3.63798E-12   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.27374E-13   "3:Q" 
 Vector      1   +0.00000E+00 -2.75134E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 +5.32907E-15   "1:G1" 
             2   +0.00000E+00 -1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 +3.63798E-12   "2:G2" 
             3   +0.00000E+00 -8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +0.00000E+00   "3:Q" 
  
 SUMMATION OF MOMENTS OF APPLIED LOADS ABOUT THE ORIGIN [Vector]  
          Case        MXo          MYo          MZo       Case Name 
             1   +0.00000E+00 +0.00000E+00 -6.87836E+03   "1:G1" 
             2   +0.00000E+00 +0.00000E+00 -4.37500E+05   "2:G2" 
             3   +0.00000E+00 +0.00000E+00 -2.12500E+05   "3:Q" 
  
 Reducing 36 equations using 128.0 KB RAM for [K] of 1.9 KB... 
  
 MAXIMUM PIVOT               : 5.095067E+08 (Node 13 DY) 
 MINIMUM PIVOT               : 5.890835E+04 (Node 7 DX) 
  
 Results for 3 load cases... 
  
 MAXIMUM NODE DISPLACEMENT MAGNITUDES 
   Case        DX           DY           DZ           RX           RY           RZ       Case Name 
      1    2.97400E-05  4.35214E-04  0.00000E+00  0.00000E+00  0.00000E+00  2.56439E-04  "1:G1" 
      2    6.56374E-03  9.40329E-02  0.00000E+00  0.00000E+00  0.00000E+00  5.65971E-02  "2:G2" 
      3    1.03200E-02  6.99110E-02  0.00000E+00  0.00000E+00  0.00000E+00  4.46537E-02  "3:Q" 
  
 DIRECT SUMMATION OF NODE REACTION FORCES 
   Case        FX           FY           FZ           MX           MY           MZ       Case Name 
      1   -7.10543E-15 +3.07775E+03 +0.00000E+00 +0.00000E+00 +0.00000E+00 -1.63425E-13  "1:G1" 
      2   +0.00000E+00 +1.75000E+05 +0.00000E+00 +0.00000E+00 +0.00000E+00 -3.00133E-11  "2:G2" 
      3   +0.00000E+00 +8.50000E+04 +0.00000E+00 +0.00000E+00 +0.00000E+00 +2.18279E-11  "3:Q" 
  
 TOTAL CPU TIME              : 0.000 Seconds 
  
 
*SUMMARY OF MESSAGES
*Number of Notes    : 0
*Number of Warnings : 1
*Number of Errors   : 0
 
*SOLUTION COMPLETED AT 18:06 ON 21/10/2025 
*SOLUTION TIME: 0 Seconds 
