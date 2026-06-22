import sys
import os
import tkinter
# import tkMessageBox
top = tkinter.Tk()

def curvas_botao():
    os.system('curves_main_exec.bat')

B = tkinter.Button(top,text="Rotina de Curvas", command = curvas_botao)
B.pack()
top.mainloop()