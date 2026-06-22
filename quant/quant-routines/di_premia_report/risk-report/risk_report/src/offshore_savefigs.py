import datetime
import fund_utils as fu

import offshore_performance
import offshore_risco

def main(dt, str_fund, nav):
    
    path_figs = '../output/temp_figs/offshore'
    
    #===== offshore_risco ==========
    figPM, figRisk, figFX, figEqty, figIR = offshore_risco.main(dt, str_fund, nav)  
    
    fig_file = f"{path_figs}/{dt:%Y%m%d}_{str_fund}_varTrader.pdf"
    figPM.savefig(fig_file,
                  bbox_inches = 'tight', #facecolor='silver',
                  pad_inches = 0)    
    
    fig_file = f"{path_figs}/{dt:%Y%m%d}_{str_fund}_varRisk.pdf"
    figRisk.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0) 
    
    fig_file = f"{path_figs}/{dt:%Y%m%d}_{str_fund}_deltaFX.pdf"
    figFX.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0) 
    
    fig_file = f"{path_figs}/{dt:%Y%m%d}_{str_fund}_deltaEquity.pdf" 
    figEqty.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0) 
    
    fig_file = f"{path_figs}/{dt:%Y%m%d}_{str_fund}_deltaIR.pdf" 
    figIR.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0) 
    
    #===== offshore_performance ==========    
    figPerf, figComp, figNAV = offshore_performance.main(dt, str_fund) 
    
    fig_file = f"{path_figs}/{dt:%Y%m%d}_{str_fund}_performance.pdf"
    figPerf.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0)
    
    fig_file = f"{path_figs}/{dt:%Y%m%d}_{str_fund}_composition.pdf"
    figComp.savefig(fig_file,
                bbox_inches = 'tight', #facecolor='silver',
                pad_inches = 0)  
    
    fig_file = f"{path_figs}/{dt:%Y%m%d}_{str_fund}_treemap_nav.pdf"
    figNAV.savefig(fig_file,
                bbox_inches = 'tight',#facecolor='silver',
                pad_inches = 0) 
    

#%%
if __name__ == "__main__":
    
    dt, str_fund = fu.get_config(['dt', 'str_fund_offshore'])
    nav = fu.get_NAV(dt, str_fund)    
    main(dt, str_fund, nav)
 