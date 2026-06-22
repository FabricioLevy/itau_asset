import anbima_download
import ustreasury_download
import b3_AjustePregao_download
import b3_ContratosAbertosFuturos_download
import datetime

def main (dt):
    anbima_download.main(dt)
    b3_AjustePregao_download.main(dt)
    b3_ContratosAbertosFuturos_download.main(dt)
    ustreasury_download.main(dt)

#%%
if __name__ == "__main__":
    dt = datetime.date(2022, 9, 27)
    try:
        main(dt)
    except Exception as err:
        print(f"\u2620 !!! \u2620  {err}  \u2620 !!! \u2620")
    