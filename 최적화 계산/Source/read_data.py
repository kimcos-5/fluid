from dataclasses import dataclass
from pathlib import Path
import json

import pandas as pd
import numpy as np

@dataclass
class ReadData:
    """
    데이터 읽기 및 전처리

    pipe : 심볼, 규격, 바깥지름(mm), 두께(mm), 단중(kg/m), 수압시험압력(kg/cm^2), 내경(mm), 내경(m), 입실론(m), 가격출처, 판매가(세금별도) * 6M, 가격/길이
    joint : 부품, 심볼, 규격, 외경(mm), 가격, 가격출처
    compressor : 심볼, 최대작동압력(bar), 최소생산유량(m^3/h), 최대생산유량(m^3/h), 장착 모터 동력, 운전 소음(dB), 가격, 가격 출처

    config : {enviorment : {Temp, density, vicosity, speed_of_sound}, system_requirments : {final_flow_rate, pipe_length}, joint : {elbow_90, gate_valve, angle_valve}, constraints : {max_mach_num}}
    """

    data_path: Path
    config_path : Path
        
    def read_data(self):
        
        df_all = pd.read_excel(self.data_path, sheet_name = None)

        df_pipe = df_all['pipe']
        df_joint = df_all['joint']
        df_compressor = df_all['compressor']

        # 데이터 전처리

        # 가격 데이터가 없는 경우 삭제
        df_pipe = df_pipe.dropna(subset = ['가격/길이'])
        df_joint = df_joint.dropna(subset = ['가격']) 
        df_compressor = df_compressor.dropna(subset = ['가격'])

        return df_pipe, df_joint, df_compressor
    
    def read_config(self):

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        return config

if __name__ == "__main__":

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    DATA_ROOT = PROJECT_ROOT / "Data" / "data.xlsx"
    CONFIG_ROOT = PROJECT_ROOT / "Data" / "config.json"

    data_reader = ReadData(DATA_ROOT, CONFIG_ROOT)

    pipe_df, join_df, comp_df = data_reader.read_data()

    print(pipe_df)
    print(" ")

    config = data_reader.read_config()
    print(config)