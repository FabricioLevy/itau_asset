import schedule
import time

import datetime
import anbima_download

def download_anbima():
    # dt = datetime.date(2021, 7, 20)
    dt = datetime.date.today()
    try:
        anbima_download.main(dt, True)
    except ValueError:
        print('\n!!! ERRO !!!')
    

schedule.every().day.at("19:35").do(download_anbima)

while True:
    schedule.run_pending()
    time.sleep(1)

# if __name__ == "__main__":
#     dt = datetime.date(2021, 7, 20)
#     try:
#         main(dt)
#     except ValueError:
#         print('\n!!! ERRO !!!')
