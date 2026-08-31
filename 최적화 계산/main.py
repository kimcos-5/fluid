from pathlib import Path
import logging

import numpy as np

# 파일 경로 설정

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "Data" / "data.xlsx" # 데이터 테이블 경로
CONFIG_ROOT = PROJECT_ROOT / "Data" / "config.json" # config 경로
LOG_ROOT = PROJECT_ROOT / "Logs" # 로그 파일 경로
PIPELINE_ROOT = PROJECT_ROOT / "Data" / "pipeline.json" # 배관 구조 파일 경로

from Source.read_data import ReadData
from Source.logger import setup_logging
from Source.calculate import Calculator
from Source.optimization import optimization
from Source.visualization import visualization
from Source.obs import PipelineObserver

def main():

    setup_logging(LOG_ROOT)

    # 카탈로그 및 상수 불러오기
    data_reader = ReadData(data_path = DATA_ROOT, config_path = CONFIG_ROOT)
    df_pipe, df_joint, df_comp = data_reader.read_data()
    config = data_reader.read_config()

    calc = Calculator(df_pipe = df_pipe, df_joint = df_joint, df_comp = df_comp, config = config)
    
    # 최적화 계산

    fee_min = -1
    symbol_min = None

    result_symbol = list()
    result_fee = list()
    result_dim = list()

    for index, row in df_pipe.iterrows():
        symbol = row['심볼']

        logging.info(f'symbol : {symbol}')

        # 1. dP 계산
        dP_total = calc.delta_P_total(symbol)

        if dP_total == np.inf:
            logging.info(f'파이프 {symbol}의 규격에 일치하는 부품이 존재하지 않습니다.')
            logging.info('')
            continue

        # 2. 압축기 요구 스펙 계산, 기관효율 70% 가정
        op = optimization(config = config, calc = calc, 
                          df_pipe = df_pipe, df_joint = df_joint, df_comp = df_comp,
                          dP_total = dP_total)
        
        op.require_Pressure_outstream()
        matched_comp = op.matching()
        if matched_comp is None:
            continue
        
        fee_total = op.fee_total(symbol)

        logging.info(f'dP_total = {dP_total}, fee_total = {fee_total}')
        logging.info(f' ')

        result_symbol.append(symbol)
        result_fee.append(fee_total)
        result_dim.append(df_pipe[df_pipe['심볼'] == symbol].iloc[0]['내경(mm)'])

        if fee_min == -1 or fee_total < fee_min:
            symbol_min = symbol
            fee_min = fee_total

    logging.info(f'결과: {symbol_min} : {fee_min}원으로 가장 저렴.')

    vis = visualization(result_symbol = result_symbol, result_fee = result_fee, result_dim = result_dim)
    vis.make_graph()

    # 지점별 분석 시행
    if symbol_min is not None:
        best_symbol = symbol_min
        
        # 최적 배관의 마찰 손실(dP)을 다시 계산
        best_dP = calc.delta_P_total(best_symbol)
        
        # 최적 배관의 조건으로 op 객체 재생성 및 압축기 매칭
        best_op = optimization(config = config, calc = calc, 
                               df_pipe = df_pipe, df_joint = df_joint, df_comp = df_comp,
                               dP_total = best_dP)
        best_op.require_Pressure_outstream()
        best_op.matching()
        
        observer = PipelineObserver(calc=calc, op=best_op, symbol=best_symbol, layout_file=PIPELINE_ROOT)
        observer.analyze()
        observer.plot_graph()

if __name__ == "__main__":

    main()