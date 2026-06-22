import datetime
 
import cme.cme_ed_price
import cme.cme_ff_price
import cme.cme_sr1_price
import cme.cme_sr3_price

def main(dt):
    
        cme.cme_ed_price.main(dt)
        cme.cme_ff_price.main(dt) 
        cme.cme_sr1_price.main(dt) 
        cme.cme_sr3_price.main(dt) 

#%%    
if __name__ == "__main__":
    dt = datetime.date(2022, 12, 12)
    main(dt)