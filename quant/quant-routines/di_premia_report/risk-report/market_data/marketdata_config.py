import os
import yaml

def get_config(args=[], 
               repository='market_data'):
    
    path_config = os.path.expanduser('~/Documents/Github/')
    
    with open(f"{path_config}/{repository}/config/report.config", 'r') as f:
        d = yaml.full_load(f)
        
    if args:
        if type(args) == str:
            ret_value = d.get(args, None)
        else:
            ret_value =  [d.get(i, None) for i in args]
    else:
        ret_value =  d
        
    return ret_value

#%%    
if __name__ == "__main__":
    
     print(get_config('dt'))
   