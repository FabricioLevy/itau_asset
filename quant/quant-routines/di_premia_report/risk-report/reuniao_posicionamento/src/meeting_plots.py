import meeting_plot_DD
import meeting_plot_VaR_diversification
import meeting_plot_hist_var_vol
import meeting_plot_peers
import var_semanal
import var_graph

import sys
sys.path.insert(1, '../../risk_report/src')
import fund_utils as fu
import fund_data

def main(data, nav, dt_1w):
    
    f = meeting_plot_hist_var_vol.main(data)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_trader_var_vol.pdf"
    f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    f = meeting_plot_peers.main(data)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_peers_vol.pdf"
    f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    f = meeting_plot_VaR_diversification.main(data)
    f.set_size_inches(6, 6)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_diversification.pdf"
    f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    f = meeting_plot_VaR_diversification.main(data, 'Traders')
    f.set_size_inches(6, 6)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_diversification_PM.pdf"
    f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    f = meeting_plot_DD.main(data, figsize=(13, 6))
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_dd_PM.pdf"
    f.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    f1, f2, f3 = var_semanal.main(data, dt_1w)
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_hist_var.pdf"
    f1.savefig(fig_file, bbox_inches = 'tight', pad_inches = 0)
    
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_hist_var_geo.pdf"
    f2.savefig(fig_file, bbox_inches = "tight", pad_inches = 0)
    
    fig_file = f"../tex/{dt:%Y_%m_%d}/figuras/{dt:%Y%m%d}_var_breakdown.pdf"
    f3.savefig(fig_file, bbox_inches = "tight", pad_inches = 0)
    
    dic_figs = var_graph.main(data, nav)
    for str_fig, fig in dic_figs.items():
        fig_file = f"../../reuniao_posicionamento/tex/{data._dt:%Y_%m_%d}/figuras/{data._dt:%Y%m%d}_{str_fund}_riskTree_{str_fig}.pdf"
        fig.savefig(fig_file, bbox_inches = "tight")   


#%%
if __name__ == "__main__":

    dt, str_fund, dt_1w = fu.get_config(['dt', 'str_fund', 'dt_1w'])
    nav = fu.get_NAV(dt, str_fund)
    
    data = fund_data.db_data(dt, str_fund, verbose=True)
    
    main(data, nav, dt_1w)
    
