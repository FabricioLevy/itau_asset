import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data

sys.path.insert(1, '../../reuniao_posicionamento/src')
import meeting_plot_VaR_diversification
import meeting_plot_DD


def main(data):
    
    fig_file_path = f"../tex/{dt:%Y_%m}/figuras/{dt:%Y%m}_"
    
    f = meeting_plot_VaR_diversification.main(data)
    f.set_size_inches(6, 6)
    fig_file = fig_file_path + "diversification.pdf"
    f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    f = meeting_plot_VaR_diversification.main(data, 'Traders')
    f.set_size_inches(6, 6)
    fig_file = fig_file_path + "diversification_PM.pdf"
    f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    f = meeting_plot_DD.main(data, figsize=(13, 6))
    fig_file = fig_file_path + "dd_PM.pdf"
    f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    

#%%
if __name__ == "__main__":

    dt, str_fund = fu.get_config(['dt_eom', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund)
      
    data = fund_data.db_data(dt, str_fund, verbose=True)
    
    main(data)

    