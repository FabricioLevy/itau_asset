import jinja2
import datetime
import os
import shutil
import pathlib
import fund_utils as fu

import offshore_savefigs


def main(dt, str_fund= 'A1 Hedge SP'):

    str_path = os.path.abspath('.') + "/../tex/"
    str_new_path = str_path + f"{dt:%Y%m%d}/"
    pathlib.Path(str_new_path).mkdir(exist_ok=True)
    pathlib.Path(str_new_path + 'figuras/').mkdir(exist_ok=True)
    
    latex_files = ['logo_Asset1.pdf', 
                   'BeamerColorThemeAsset1.sty',
                   'jinja_offshore_template.tex']
    for f in latex_files:
        shutil.copy(str_path + f, 
                   str_new_path + f)
    
    str_temp_figs = '../output/temp_figs/offshore/'
    for pic in os.listdir(str_temp_figs):
         if pic[0:8] == "{:%Y%m%d}".format(dt):
             os.replace(str_temp_figs + pic, 
                        str_new_path + 'figuras/' + pic)           
    
    
    str_date = f"{dt:%Y%m%d}"
    str_longdate = f"{dt:%d-%b-%Y}" 
    str_template = 'jinja_offshore_template.tex'
    
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
                             strFund=str_fund)
    
    str_file = f"{str_date}_{str_fund}.tex"
    str_path_template = os.path.dirname(template.filename) + '/'
    with open(str_path_template  + str_file, 'w') as f:
        f.write(output)
    
    # os.chdir('../tex/')
    
    os.chdir(str_path_template)
    
    # subprocess.run(f"lualatex.exe -synctex=1 -interaction=nonstopmode \"{str_file}\"", shell=True)
    for _ in [1, 2]:
        os.system(f"lualatex.exe -synctex=1 -interaction=nonstopmode \"{str_file}\"")
    
#%%
if __name__ == "__main__":
    
    dt, str_fund = fu.get_config(['dt', 'str_fund_offshore'])
    nav = fu.get_NAV(dt, str_fund)    
    offshore_savefigs.main(dt, str_fund, nav)
    main(dt, str_fund)
 