import numpy as np
import pandas as pd
import yaml
from atomic_experiment import evaluate
from generate_configurations import generate
from tqdm import tqdm

import logging
logging.basicConfig(level=logging.INFO)
import argparse

import dask
import time
from dask.distributed import Client, progress

    
class ParaRun :
    def __init__(self, gen_func, eval_func, params='params.yaml') :
        if type(params) == str :
            param_file = params
            logging.info(f" Reading parameters from {param_file}.")
            with open(param_file) as file:
                self._params = yaml.load(file, Loader=yaml.FullLoader)
        else :
            self._params = params

        self._out = pd.DataFrame()
        self._npartitions = 4
        self._func = eval_func

        self._conf = pd.DataFrame(gen_func(self._params['nMonte'],
                                     self._params['variables'])
        )
        logging.info(f"Generated {len(self._conf)} configurations.")
    
        
    def run(self) :
        """
        Apply atomic expriment function to each row in configuration table

        Args:
        -----
        func    atomic experiment function
        """
        logging.info(f" Running...")

        results = []
        job_ids = []
        itr = 0
        for params in tqdm(self._conf.iterrows()) :
            r = self._func(*params[1])
            results.append(r)
            itr += 1
            job_ids += [itr]
        
        self._out = self._conf.join(pd.DataFrame(results), how='left')
        logging.info(f" Completed.")

    def Dask_run(self, client) :
        """
        Apply atomic expriment function to each row in configuration table

        Args:
        -----
        func    atomic experiment function

        """

        logging.info(f" Running on Dask.")

        logging.info(" Mapping to futures...")

        variables = self._conf.columns.tolist()
        self._conf.loc[:,'job_id'] = 'null'
        futures=[]

        df_vars = self._conf.filter(items=variables)
        for r in df_vars.iterrows() :
            fut = client.submit(self._func, **r[1])
            self._conf.loc[r[0], 'job_id'] = fut.key
            futures += [fut]
        logging.info(" Gathering...")
        
        progress(futures)
        
        keys = [fut.key for fut in futures]
        results = pd.DataFrame(client.gather(futures), index=keys)
        logging.info(" Terminating client...")
        client.close()
    
        self._out = self._conf.set_index('job_id').join(results, how='left')


        #ddf = dd.from_pandas(self._conf.iloc[:,1:], npartitions=self._npartitions)
        #x = ddf.apply(lambda row : self._func(*row), axis=1, meta=dict)    

        # fut = client.map(func, )
        # progress(fut)
        # res = client.gather(fut)
        # y = x.compute()
        # self._out = pd.DataFrame(y)
        

    def to_file(self, filename="results.csv") :
        if self._out.empty :
            logging.warning(" No output." 
            "Did the experiment complete running?")
        if self._conf.empty :
            logging.warning(" No configuration detected."
            "Did call gen_conf_table() ")

        logging.info(f" Saving results...")
        logging.info(f" Saved {len(self._out)} records in {filename}.")
        self._out.to_csv(filename)    

def main() :
    parser = argparse.ArgumentParser(description='Launch experiment')
    parser.add_argument('-o', type=str, help='output file', default='')
    parser.add_argument('-p', type=str, help='yaml parameters file.', default='params.yaml')
    parser.add_argument('--dask', action='store_true')
    parser.add_argument('--address', type=str, default="")
    args = parser.parse_args()
    #
    

    if args.dask :
        logging.info(f" Using Dask:")
        if args.address == "" :
            logging.info(f" Starting a local cluster")
            client = Client()
        else :
            logging.info(f" Connecting to existing cluster at {args.address}")
            client = Client(args.address)
        logging.info(f" Dashboard at {client.dashboard_link}")
        exper = ParaRun(generate, evaluate, args.p)
        exper.Dask_run(client)
            
    else :
        exper = ParaRun(generate, evaluate, args.p)
        exper.run()

    output_filename=args.o
    if output_filename == "":
        import pdb; pdb.set_trace()
        dig = hash(str(exper._params))
        output_filename = f"results_{dig}.csv"

    exper.to_file(output_filename)
    

if __name__ == '__main__':
    main()
