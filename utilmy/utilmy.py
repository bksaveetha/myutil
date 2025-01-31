# pylint: disable=C0321,C0103,C0301,E1305,E1121,C0302,C0330,C0111,W0613,W0611,R1705
# -*- coding: utf-8 -*-
import os, sys, time, datetime,inspect, json, yaml, gc


def log(*s):
    print(*s)

###################################################################################################
###### Pandas #####################################################################################
def pd_date_split(df, coldate =  'time_key', prefix_col ="", verbose=False ):
    import pandas as pd

    df = df.drop_duplicates(coldate)
    df['date'] =  pd.to_datetime( df[coldate] )

    ############# dates
    df['year']          = df['date'].apply( lambda x : x.year   )
    df['month']         = df['date'].apply( lambda x : x.month   )
    df['day']           = df['date'].apply( lambda x : x.day   )
    df['weekday']       = df['date'].apply( lambda x : x.weekday()   )
    df['weekmonth']     = df['date'].apply( lambda x : date_weekmonth(x)   )
    df['weekmonth2']    = df['date'].apply( lambda x : date_weekmonth2(x)   )
    df['weekyeariso']   = df['date'].apply( lambda x : x.isocalendar()[1]   )
    df['weekyear2']     = df['date'].apply( lambda x : date_weekyear2( x )  )
    df['quarter']       = df.apply( lambda x :  int( x['month'] / 4.0) + 1 , axis=1  )

    df['yearweek']      = df.apply(  lambda x :  merge1(  x['year']  , x['weekyeariso'] )  , axis=1  )
    df['yearmonth']     = df.apply( lambda x : merge1( x['year'] ,  x['month'] )         , axis=1  )
    df['yearquarter']   = df.apply( lambda x : merge1( x['year'] ,  x['quarter'] )         , axis=1  )

    df['isholiday']     = date_is_holiday( df['date'].values )

    exclude = [ 'date', coldate]
    df.columns = [  prefix_col + x if not x in exclude else x for x in df.columns]
    if verbose : log( "holidays check", df[df['isholiday'] == 1].tail(15)  )
    return df


def pd_merge(df1, df2, on=None, colkeep=None):
  ### Faster merge
  cols = list(df2.columns) if colkeep is None else on + colkeep
  return df1.join( df2[ cols   ].set_index(on), on=on, how='left', rsuffix="2")




def pd_plot_multi(data, cols=[], cols2=[], spacing=.1, **kwargs):
    from pandas import plotting
    from pandas.plotting import _matplotlib

    # Get default color style from pandas - can be changed to any other color list
    if cols is None: cols = data.columns
    if len(cols) == 0: return
    colors = getattr(getattr(plotting, '_matplotlib').style, '_get_standard_colors')(num_colors=len(cols+cols2))

    # First axis
    ax = data.loc[:, cols[0]].plot(label=cols[0], color=colors[0], **kwargs)
    ax.set_ylabel(ylabel=cols[0])
    ##  lines, labels = ax.get_legend_handles_labels()
    lines, labels = [], []

    i1 = len(cols)
    for n in range(1, len(cols)):
        data.loc[:, cols[n]].plot(ax=ax, label=cols[n], color=colors[ (n) % len(colors)], **kwargs)
        line, label = ax.get_legend_handles_labels()
        lines += line
        labels += label

    for n in range(0, len(cols2)):
        # Multiple y-axes
        ax_new = ax.twinx()
        ax_new.spines['right'].set_position(('axes', 1 + spacing * (n - 1)))
        data.loc[:, cols2[n]].plot(ax=ax_new, label=cols2[n], color=colors[ (i1+n) % len(colors)], **kwargs)
        ax_new.set_ylabel(ylabel=cols2[n])

        # Proper legend position
        line, label = ax_new.get_legend_handles_labels()
        lines += line
        labels += label

    ax.legend(lines, labels, loc=0)
    return ax





def pd_filter(df, filter_dict="shop_id=11, l1_genre_id>600, l2_genre_id<80311," , verbose=False) :
    """
     dfi = pd_filter2(dfa, "shop_id=11, l1_genre_id>600, l2_genre_id<80311," )
     dfi2 = pd_filter(dfa, {"shop_id" : 11} )
     ### Dilter dataframe with basic expr
    """
    #### Dict Filter
    if isinstance(filter_dict, dict) :
       for key,val in filter_dict.items() :
          df =   df[  (df[key] == val) ]
       return df

    # pd_filter(df,  ss="shop_id=11, l1_genre_id>600, l2_genre_id<80311," )
    ss = filter_dict.split(",")
    def x_convert(col, x):
      x_type = str( dict(df.dtypes)[col] )
      if "int" in x_type or "float" in x_type :
         return float(x)
      else :
          return x
    for x in ss :
       x = x.strip()
       if verbose : print(x)
       if len(x) < 3 : continue
       if "=" in x :
           coli= x.split("=")
           df = df[ df[coli[0]] == x_convert(coli[0] , coli[1] )   ]

       if ">" in x :
           coli= x.split(">")
           df = df[ df[coli[0]] > x_convert(coli[0] , coli[1] )   ]

       if "<" in x :
           coli= x.split("<")
           df = df[ df[coli[0]] < x_convert(coli[0] , coli[1] )   ]
    return df


def pd_to_file(df, filei,  check="check", verbose=True,   **kw):
  import os, gc
  from pathlib import Path
  parent = Path(filei).parent
  os.makedirs(parent, exist_ok=True)
  ext  = os.path.splitext(filei)[1]
  if ext == ".pkl" :
      df.to_pickle(filei, **kw)

  if ext == ".parquet" :
      df.to_parquet(filei, **kw)

  if ext == ".csv"  or ext == ".txt" :
      df.to_csv(filei, **kw)

  #if check == "check" :
  #  os_file_check( filei )

  # elif check =="checkfull" :
  #  os_file_check( filei )
  #  dfi = pd_read_file( filei, n_pool=1)   ### Full integrity
  #  log("#######  Reload Check: ",  filei, "\n"  ,  dfi.tail(3).T)
  #  del dfi; gc.collect()
  gc.collect()


def pd_read_file(path_glob="*.pkl", ignore_index=True,  cols=None, verbose=False, nrows=-1, concat_sort=True, n_pool=1, 
                 drop_duplicates=None, col_filter=None,  col_filter_val=None, dtype=None,  **kw):
  """  Read file in parallel from disk : very Fast
  :param path_glob: list of pattern, or sep by ";"
  :return:
  """
  import glob, gc,  pandas as pd, os
  def log(*s, **kw):
      print(*s, flush=True, **kw)
  readers = {
          ".pkl"     : pd.read_pickle,
          ".parquet" : pd.read_parquet,
          ".tsv"     : pd.read_csv,
          ".csv"     : pd.read_csv,
          ".txt"     : pd.read_csv,
          ".zip"     : pd.read_csv,
          ".gzip"    : pd.read_csv,
          ".gz"      : pd.read_csv,
   }
  from multiprocessing.pool import ThreadPool

  #### File
  if isinstance(path_glob, list):  path_glob = ";".join(path_glob)
  path_glob  = path_glob.split(";")
  file_list = []
  for pi in path_glob :
      file_list.extend( sorted( glob.glob(pi) ) )
  file_list = sorted(list(set(file_list)))
  n_file    = len(file_list)
  if verbose: log(file_list)

  #### Pool count
  if n_pool < 1 :  n_pool = 1
  if n_file <= 0:  m_job  = 0
  elif n_file <= 2:
    m_job  = n_file
    n_pool = 1
  else  :
    m_job  = 1 + n_file // n_pool  if n_file >= 3 else 1
  if verbose : log(n_file,  n_file // n_pool )

  pool   = ThreadPool(processes=n_pool)
  dfall  = pd.DataFrame()
  for j in range(0, m_job ) :
      if verbose : log("Pool", j, end=",")
      job_list = []
      for i in range(n_pool):
         if n_pool*j + i >= n_file  : break
         filei         = file_list[n_pool*j + i]
         ext           = os.path.splitext(filei)[1]
         if ext == None or ext == '':
           continue

         pd_reader_obj = readers[ext]
         if pd_reader_obj == None:
           continue

         ### TODO : use with kewyword arguments
         job_list.append( pool.apply_async(pd_reader_obj, (filei, )))
         if verbose : log(j, filei)

      for i in range(n_pool):
        if i >= len(job_list): break
        dfi   = job_list[ i].get()

        if dtype is not None      : dfi = pd_dtype_reduce(dfi, int0 ='int32', float0 = 'float32')
        if col_filter is not None : dfi = dfi[ dfi[col_filter] == col_filter_val ]
        if cols is not None :       dfi = dfi[cols]
        if nrows > 0        :       dfi = dfi.iloc[:nrows,:]
        if drop_duplicates is not None  : dfi = dfi.drop_duplicates(drop_duplicates)
        gc.collect()

        dfall = pd.concat( (dfall, dfi), ignore_index=ignore_index, sort= concat_sort)
        #log("Len", n_pool*j + i, len(dfall))
        del dfi; gc.collect()

  if m_job>0 and verbose : log(n_file, j * n_file//n_pool )
  return dfall


def pd_sample_strat(df, col, n):
  ### Stratified sampling
  # n   = min(n, df[col].value_counts().min())
  df_ = df.groupby(col).apply(lambda x: x.sample(n = n, replace=True))
  df_.index = df_.index.droplevel(0)
  return df_


def pd_cartesian(df1, df2) :
  ### Cartesian preoduct
  import pandas as pd
  col1 =  list(df1.columns)
  col2 =  list(df2.columns)
  df1['xxx'] = 1
  df2['xxx'] = 1
  df3 = pd.merge(df1, df2,on='xxx')[ col1 + col2 ]
  del df3['xxx']
  return df3


def pd_histogram(dfi, path_save=None, nbin=20.0, q5=0.005, q95=0.995, nsample= -1, show=False, clear=True) :
    ### Plot histogram
    from matplotlib import pyplot as plt
    import numpy as np, os, time
    q0 = dfi.quantile(q5)
    q1 = dfi.quantile(q95)

    if nsample < 0 :
        dfi.hist( bins=np.arange( q0, q1,  (  q1 - q0 ) /nbin  ) )
    else :
        dfi.sample(n=nsample, replace=True ).hist( bins=np.arange( q0, q1,  (  q1 - q0 ) /nbin  ) )
    plt.title( path_save.split("/")[-1] )

    if show :
      plt.show()

    if path_save is not None :
      os.makedirs(os.path.dirname(path_save), exist_ok=True)
      plt.savefig( path_save )
      print(path_save )
    if clear :
        # time.sleep(5)
        plt.close()


def pd_qcut(df, col, nbins=5):
  ### Shortcuts for easy bin of numerical values
  import pandas as pd, numpy as np
  assert nbins < 256, 'nbins< 255'
  return pd.qcut(df[col], q=nbins,labels= np.arange(0, nbins, 1)).astype('int8')


def pd_dtype_reduce(dfm, int0 ='int32', float0 = 'float32') :
    import numpy as np
    for c in dfm.columns :
        if dfm[c].dtype ==  np.dtype(np.int32) :       dfm[c] = dfm[c].astype( int0 )
        elif   dfm[c].dtype ==  np.dtype(np.int64) :   dfm[c] = dfm[c].astype( int0 )
        elif dfm[c].dtype ==  np.dtype(np.float64) :   dfm[c] = dfm[c].astype( float0 )
    return dfm


def pd_dtype_count_unique(df, col_continuous=[]):
    """Learns the number of categories in each variable and standardizes the data.
        ----------
        data: pd.DataFrame
        continuous_ids: list of ints
            List containing the indices of known continuous variables. Useful for
            discrete data like age, which is better modeled as continuous.
        Returns
        -------
        ncat:  number of categories of each variable. -1 if the variable is  continuous.
    """
    import numpy as np
    def gef_is_continuous(data, dtype):
        """ Returns true if data was sampled from a continuous variables, and false
        """
        if dtype == "Object":
            return False

        observed = data[~np.isnan(data)]  # not consider missing values for this.
        rules = [np.min(observed) < 0,
                 np.sum((observed) != np.round(observed)) > 0,
                 len(np.unique(observed)) > min(30, len(observed)/3)]
        if any(rules):
            return True
        else:
            return False

    cols = list(df.columns)
    ncat = {}

    for coli in cols:
        is_cont = gef_is_continuous( df[coli].sample( n=min(3000, len(df)) ).values , dtype = df[coli].dtype )
        if coli in col_continuous or is_cont:
            ncat[coli] =  -1
        else:
            ncat[coli] =  len( df[coli].unique() )
    return ncat


def pd_dtype_to_category(df, col_exclude, treshold=0.5):
  """
    Convert string to category
  """
  import pandas as pd
  if isinstance(df, pd.DataFrame):
    for col in df.select_dtypes(include=['object']):
        if col not in col_exclude :
            num_unique_values = len(df[col].unique())
            num_total_values  = len(df[col])
            if float(num_unique_values) / num_total_values < treshold:
                df[col] = df[col].astype('category')
        else:
            df[col] = pd.to_datetime(df[col])
    return df
  else:
    print("Not dataframe")


def pd_dtype_getcontinuous(df, cols_exclude:list=[], nsample=-1) :
    ### Return continuous variable
    clist = {}
    for ci in df.columns :
        ctype   = df[ci].dtype
        if nsample == -1 :
            nunique = len(df[ci].unique())
        else :
            nunique = len(df.sample(n= nsample, replace=True)[ci].unique())
        if 'float' in  str(ctype) and ci not in cols_exclude and nunique > 5 :
           clist[ci] = 1
        else :
           clist[ci] = nunique
    return clist


def pd_del(df, cols:list):
    ### Delete columns without errors
    for col in cols :
        try:
            del df[col]
        except : pass
    return df


def pd_add_noise(df, level=0.05, cols_exclude:list=[]) :
    import numpy as np, pandas as pd
    df2 = pd.DataFrame()
    colsnum = pd_dtype_getcontinuous(df, cols_exclude)
    for ci in df.columns :
        if ci in colsnum :
           print(f'adding noise {ci}')
           sigma = level * (df[ci].quantile(0.95) - df[ci].quantile(0.05)  )
           df2[ci] = df[ci] + np.random.normal(0.0, sigma, [len(df)])
        else :
           df2[ci] = df[ci]
    return df2


def pd_cols_unique_count(df, cols_exclude:list=[], nsample=-1) :
    ### Return cadinat=lity
    clist = {}
    for ci in df.columns :
        ctype   = df[ci].dtype
        if nsample == -1 :
            nunique = len(df[ci].unique())
        else :
            nunique = len(df.sample(n= nsample, replace=True)[ci].unique())

        if 'float' in  str(ctype) and ci not in cols_exclude and nunique > 5 :
           clist[ci] = 0
        else :
           clist[ci] = nunique

    return clist


def pd_show(df, nrows=100, **kw):
    """ Show from Dataframe
    """
    import pandas as pd
    fpath = 'ztmp/ztmp_dataframe.csv'
    os_makedirs(fpath)
    df.iloc[:nrows,:].to_csv(fpath, sep=",", mode='w')


    ## In Windows
    cmd = f"notepad.exe {fpath}"
    os.system(cmd)





#########################################################################################################
##### Utils numpy, list #################################################################################
class dict_to_namespace(object):
    #### Dict to namespace
    def __init__(self, d):
        self.__dict__ = d


def to_dict(**kw):
  ## return dict version of the params
  return kw


def to_timeunix(datex="2018-01-16"):
  if isinstance(datex, str)  :
     return int(time.mktime(datetime.datetime.strptime(datex, "%Y-%m-%d").timetuple()) * 1000)

  if isinstance(datex, datetime)  :
     return int(time.mktime( datex.timetuple()) * 1000)


def to_datetime(x) :
  import pandas as pd
  return pd.to_datetime( str(x) )


def np_list_intersection(l1, l2) :
  return [x for x in l1 if x in l2]


def np_add_remove(set_, to_remove, to_add):
    # a function that removes list of elements and adds an element from a set
    result_temp = set_.copy()
    for element in to_remove:
        result_temp.remove(element)
    result_temp.add(to_add)
    return result_temp


def to_float(x):
    try :
        return float(x)
    except :
        return float("NaN")


def to_int(x):
    try :
        return int(x)
    except :
        return float("NaN")




########################################################################################################
##### OS, cofnfig ######################################################################################
def os_get_function_name():
    ### Get ane,
    import sys, socket
    ss = str(os.getpid()) # + "-" + str( socket.gethostname())
    ss = ss + "," + str(__name__)
    try :
        ss = ss + "," + __class__.__name__
    except :
        ss = ss + ","
    ss = ss + "," + str(  sys._getframe(1).f_code.co_name)
    return ss

def os_variable_init(ll, globs):
    for x in ll :
        try :
          globs[x]
        except :
          globs[x] = None


def os_import(mod_name="offline.config.genre_l2_model", globs=None, verbose=True):
    ### Import in Current Python Session a module   from module import *
    ### from mod_name import *
    module = __import__(mod_name, fromlist=['*'])
    if hasattr(module, '__all__'):
        all_names = module.__all__
    else:
        all_names = [name for name in dir(module) if not name.startswith('_')]

    all_names2 = []
    no_list    = ['os', 'sys' ]
    for t in all_names :
        if t not in no_list :
          ### Mot yet loaded in memory  , so cannot use Global
          #x = str( globs[t] )
          #if '<class' not in x and '<function' not in x and  '<module' not in x :
          all_names2.append(t)
    all_names = all_names2

    if verbose :
      print("Importing: ")
      for name in all_names :
         print( f"{name}=None", end=";")
      print("")
    globs.update({name: getattr(module, name) for name in all_names})


def os_variable_exist(x ,globs, msg="") :
    x_str = str(globs.get(x, None))
    if "None" in x_str:
        log("Using default", x)
        return False
    else :
        log("Using ", x)
        return True


def os_variable_check(ll, globs=None, do_terminate=True):
  import sys
  for x in ll :
      try :
         a = globs[x]
         if a is None : raise Exception("")
      except :
          log("####### Vars Check,  Require: ", x  , "Terminating")
          if do_terminate:
                 sys.exit(0)


def os_clean_memory( varlist , globx):
  for x in varlist :
    try :
       del globx[x]
       gc.collect()
    except : pass


def os_system_list(ll, logfile=None, sleep_sec=10):
   ### Execute a sequence of cmd
   import time, sys
   n = len(ll)
   for ii,x in enumerate(ll):
        try :
          log(x)
          if sys.platform == 'win32' :
             cmd = f" {x}   "
          else :
             cmd = f" {x}   2>&1 | tee -a  {logfile} " if logfile is not None else  x

          os.system(cmd)

          # tx= sum( [  ll[j][0] for j in range(ii,n)  ]  )
          # log(ii, n, x,  "remaining time", tx / 3600.0 )
          #log('Sleeping  ', x[0])
          time.sleep(sleep_sec)
        except Exception as e:
            log(e)


def os_file_check(fp):
   import os, time
   try :
       log(fp,  os.stat(fp).st_size*0.001, time.ctime(os.path.getmtime(fp)) )
   except :
       log(fp, "Error File Not exist")


def os_to_file( txt="", filename="ztmp.txt",  mode='a'):
    with open(filename, mode=mode) as fp:
        fp.write(txt + "\n")


def os_platform_os():
    #### get linux or windows
    return sys.platform


def os_cpu():
    ### Nb of cpus cores
    return os.cpu_count()


def os_platform_ip():
    ### IP
    pass


def os_memory():
    """ Get node total memory and memory usage in linux
    """
    with open('/proc/meminfo', 'r') as mem:
        ret = {}
        tmp = 0
        for i in mem:
            sline = i.split()
            if str(sline[0]) == 'MemTotal:':
                ret['total'] = int(sline[1])
            elif str(sline[0]) in ('MemFree:', 'Buffers:', 'Cached:'):
                tmp += int(sline[1])
        ret['free'] = tmp
        ret['used'] = int(ret['total']) - int(ret['free'])
    return ret


def os_removedirs(path):
    """  issues with no empty Folder
    # Delete everything reachable from the directory named in 'top',
    # assuming there are no symbolic links.
    # CAUTION:  This is dangerous!  For example, if top == '/', it could delete all your disk files.
    """
    if len(path) < 3 :
        print("cannot delete root folder")
        return False

    import os
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            try :
              os.remove(os.path.join(root, name))
            except :
              pass
        for name in dirs:
            try :
              os.rmdir(os.path.join(root, name))
            except: pass
    try :
      os.rmdir(path)
    except: pass
    return True


def os_getcwd():
    ## This is for Windows Path normalized As Linux /
    root = os.path.abspath(os.getcwd()).replace("\\", "/") + "/"
    return  root


def os_system(cmd, doprint=False):
  """ get values
       os_system( f"   ztmp ",  doprint=True)
  """
  import subprocess
  try :
    p          = subprocess.run( cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, )
    mout, merr = p.stdout.decode('utf-8'), p.stderr.decode('utf-8')
    if doprint:
      l = mout  if len(merr) < 1 else mout + "\n\nbash_error:\n" + merr
      print(l)

    return mout, merr
  except Exception as e :
    print( f"Error {cmd}, {e}")


def os_makedirs(dir_or_file):
    if os.path.isfile(dir_or_file) or "." in dir_or_file.split("/")[-1] :
        os.makedirs(os.path.dirname(os.path.abspath(dir_or_file)), exist_ok=True)
    else :
        os.makedirs(os.path.abspath(dir_or_file), exist_ok=True)




####################################################################################################
##### Utilities for date  ##########################################################################
def date_now(fmt="%Y-%m-%d %H:%M:%S %Z%z", add_days=0, timezone='Asia/Tokyo'):
    from pytz import timezone
    from datetime import datetime
    # Current time in UTC
    now_utc = datetime.now(timezone('UTC'))
    now_new = now_utc+ datetime.timedelta(days=add_days)

    # Convert to US/Pacific time zone
    now_pacific = now_new.astimezone(timezone(timezone))
    return now_pacific.strftime(fmt)


def date_is_holiday(array):
    """
      is_holiday([ pd.to_datetime("2015/1/1") ] * 10)

    """
    import holidays , numpy as np
    jp_holidays = holidays.CountryHoliday('JP')
    return np.array( [ 1 if x.astype('M8[D]').astype('O') in jp_holidays else 0 for x in array]  )


def date_weekmonth2(d):
     w = (d.day-1)//7+1
     if w < 0 or w > 5 :
         return -1
     else :
         return w


def date_weekmonth(date_value):
     """  Incorrect """
     w = (date_value.isocalendar()[1] - date_value.replace(day=1).isocalendar()[1] + 1)
     if w < 0 or w > 6 :
         return -1
     else :
         return w


def date_weekyear2(dt) :
 return ((dt - datetime.datetime(dt.year,1,1)).days // 7) + 1


def date_weekday_excel(x) :
 import arrow
 wday= arrow.get( str(x) , "YYYYMMDD").isocalendar()[2]
 if wday != 7 : return wday+1
 else :    return 1


def date_weekyear_excel(x) :
 import arrow
 dd= arrow.get( str(x) , "YYYYMMDD")
 wk1= dd.isocalendar()[1]

 # Excel Convention
 # dd0= arrow.get(  str(dd.year) + "0101", "YYYYMMDD")
 dd0_weekday= date_weekday_excel( dd.year *10000 + 101  )
 dd_limit= dd.year*10000 + 100 + (7-dd0_weekday+1) +1

 ddr= arrow.get( str(dd.year) + "0101" , "YYYYMMDD")
 # print dd_limit
 if    int(x) < dd_limit :
    return 1
 else :
     wk2= 2 + int(((dd-ddr ).days  - (7-dd0_weekday +1 ) )   /7.0 )
     return wk2


def date_generate(start='2018-01-01', ndays=100) :
 from dateutil.relativedelta import relativedelta
 start0 = datetime.datetime.strptime(start, "%Y-%m-%d")
 date_list = [start0 + relativedelta(days=x) for x in range(0, ndays)]
 return date_list



################################################################################################
################################################################################################
def global_verbosity(cur_path, path_relative="/../../config.json",
                   default=5, key='verbosity',):
    """ Get global verbosity
    verbosity = global_verbosity(__file__, "/../../config.json", default=5 )

    verbosity = global_verbosity("repo_root", "config/config.json", default=5 )

    :param cur_path:
    :param path_relative:
    :param key:
    :param default:
    :return:
    """
    try   :
      if 'repo_root' == cur_path  :
          cur_path =  git_repo_root()

      if '.json' in path_relative :
         dd = json.load(open(os.path.dirname(os.path.abspath(cur_path)) + path_relative , mode='r'))

      elif '.yaml' in path_relative or '.yml' in path_relative :
         import yaml
         dd = yaml.load(open(os.path.dirname(os.path.abspath(cur_path)) + path_relative , mode='r'))

      else :
          raise Exception( path_relative + " not supported ")
      verbosity = int(dd[key])

    except Exception as e :
      verbosity = default
      #raise Exception(f"{e}")
    return verbosity




######################################################################################################
########Git ##########################################################################################
def git_repo_root():
    try :
      cmd = "git rev-parse --show-toplevel"
      mout, merr = os_system(cmd)
      path = mout.split("\n")[0]
      if len(path) < 1:  return None
    except : return None
    return path


def git_current_hash(mode='full'):
   import subprocess
   # label = subprocess.check_output(["git", "describe", "--always"]).strip();
   label = subprocess.check_output([ 'git', 'rev-parse', 'HEAD' ]).strip();
   label = label.decode('utf-8')
   return label




######################################################################################################
###### Plot ##########################################################################################
def plot_to_html(dir_input="*.png", out_file="graph.html", title="", verbose=False):
    """
      plot_to_html( model_path + "/graph_shop_17_past/*.png" , model_path + "shop_17.html" )

    """
    import matplotlib.pyplot as plt
    import base64
    from io import BytesIO
    import glob
    html = f'<html><body><h2>{title}</h2>'
    flist = glob.glob(dir_input)
    flist.sorted()
    for fp in flist :
        if verbose : print(fp,end=",")
        with open(fp, mode="rb" ) as fp2 :
            tmpfile =fp2.read()
        encoded = base64.b64encode( tmpfile ) .decode('utf-8')
        html =  html + f'<p><img src=\'data:image/png;base64,{encoded}\'> </p>\n'
    html = html + "</body></html>"
    with open(out_file,'w') as f:
        f.write(html)







################################################################################################
################################################################################################
class Session(object) :
    """ Save Python Interpreter session on disk
      from util import Session
      sess = Session("recsys")
      sess.save( globals() )
    """
    def __init__(self, dir_session="ztmp/session/",) :
      os.makedirs(dir_session, exist_ok=True)
      self.dir_session =  dir_session
      self.cur_session =  None
      print(self.dir_session)

    def show(self) :
       import glob
       flist = glob.glob(self.dir_session + "/*" )
       print(flist)

    def save(self, name, glob=None, tag="") :
       path = f"{self.dir_session}/{name}{tag}/"
       self.cur_session = path
       os.makedirs(self.cur_session, exist_ok=True)
       save_session(self.cur_session, glob)

    def load(self, name, glob:dict=None, tag="") :
      path = f"{self.dir_session}/{name}{tag}/"
      self.cur_session = path
      print(self.cur_session)
      load_session(self.cur_session , glob )


def save_session(folder , globs, tag="" ) :
  import pandas as pd
  os.makedirs( folder , exist_ok= True)
  lcheck = [ "<class 'pandas.core.frame.DataFrame'>", "<class 'list'>", "<class 'dict'>",
             "<class 'str'>" ,  "<class 'numpy.ndarray'>" ]
  lexclude = {   "In", "Out" }
  gitems = globs.items()
  for x, _ in gitems :
     if not x.startswith('_') and  x not in lexclude  :
        x_type =  str(type(globs.get(x) ))
        fname  =  folder  + "/" + x + ".pkl"
        try :
          if "pandas.core.frame.DataFrame" in x_type :
              pd.to_pickle( globs[x], fname)

          elif x_type in lcheck or x.startswith('clf')  :
              save( globs[x], fname )

          print(fname)
        except Exception as e:
              print(x, x_type, e)


def load_session(folder, globs=None) :
  """
  """
  print(folder)
  for dirpath, subdirs, files in os.walk( folder ):
    for x in files:
       filename = os.path.join(dirpath, x)
       x = x.replace(".pkl", "")
       try :
         globs[x] = load(  filename )
         print(filename)
       except Exception as e :
         print(filename, e)


def save(dd, to_file="", verbose=False):
  import pickle, os
  os.makedirs(os.path.dirname(to_file), exist_ok=True)
  pickle.dump(dd, open(to_file, mode="wb") , protocol=pickle.HIGHEST_PROTOCOL)
  #if verbose : os_file_check(to_file)


def load(to_file=""):
  import pickle
  dd =   pickle.load(open(to_file, mode="rb"))
  return dd




###################################################################################################
###### Debug ######################################################################################
def log_break(msg="", dump_path="", globs=None):
    print(msg)
    import pdb;
    pdb.set_trace()

def profiler_start():
    ### Code profiling
    from pyinstrument import Profiler
    global profiler
    profiler = Profiler()
    profiler.start()


def profiler_stop():
    global profiler
    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))




###################################################################################################
if __name__ == "__main__":
    import fire
    fire.Fire()




