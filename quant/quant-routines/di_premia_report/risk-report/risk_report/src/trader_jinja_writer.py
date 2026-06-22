import jinja2
import datetime
import os
import shutil
import pathlib

import fund_utils as fu
import fund_data
import trader_var_delta_hypopnl

def main(data, nav):

    
    dt = data._dt
    str_path = os.path.abspath('.') + "/../tex/"
    str_new_path = str_path + f"{dt:%Y%m%d}/"
    pathlib.Path(str_new_path).mkdir(exist_ok=True)
    pathlib.Path(str_new_path + 'figuras/').mkdir(exist_ok=True)
    
    latex_files = ['logo_Asset1.pdf', 
                    'BeamerColorThemeAsset1.sty',
                    'jinja_trader_template.tex']
    for f in latex_files:
        shutil.copy(str_path + f, 
                    str_new_path + f)
     
     
    dic_f = trader_var_delta_hypopnl.main(data, nav)
    for t, files in dic_f.items():
        for i, f in enumerate(files):
            fig_file = f"{str_new_path}figuras/{dt:%Y%m%d}_{t}_{i:0.0f}.pdf"
            f.savefig(fig_file, #facecolor='silver',
                      bbox_inches = 'tight')
    
    str_date = f"{dt:%Y%m%d}"
    str_longdate = f"{dt:%d-%b-%Y}" 
    str_template = 'jinja_trader_template.tex'
    str_traders = ",".join(["{" +k + "/" + v +"}" for (k, v) in fu.get_traders(data._dt).items() if k in dic_f.keys()])
    
    latex_jinja_env = jinja2.Environment(
     	block_start_string = '\BLOCK{',
     	block_end_string = '}',
     	variable_start_string = '\VAR{',
     	variable_end_string = '}',
     	comment_start_string = '\#{',
     	comment_end_string = '}',
     	line_statement_prefix = '%%',
     	line_comment_prefix = '%#',
     	trim_blocks = True,
     	autoescape = False,
     	loader = jinja2.FileSystemLoader(str_new_path)
    )
    
    template = latex_jinja_env.get_template(str_template)
    
    output = template.render(strDate=str_date,
                              strLongDate=str_longdate,
                              strFund=str_fund,
                              strTraders = str_traders)
    
    str_file = f"{str_date}_{str_fund}.tex"
    str_path_template = os.path.dirname(template.filename) + '/'
    with open(str_path_template  + str_file, 'w') as f:
        f.write(output)
    
    os.chdir(str_path_template)
    for _ in [1, 2]:
        os.system(f"lualatex.exe -synctex=1 -interaction=nonstopmode \"{str_file}\"")
    
#%%
if __name__ == "__main__":
    
    dt, str_fund = fu.get_config(['dt', 'str_fund'])
    nav = fu.get_NAV(dt, str_fund) 
    data = fund_data.db_data(dt, str_fund, verbose=True) 
    main(data, nav)
 