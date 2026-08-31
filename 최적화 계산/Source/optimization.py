import logging
import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass

from Source.calculate import Calculator

@dataclass
class optimization:
    """
    최적화 알고리즘
    """

    calc : Calculator
    
    df_pipe : pd.DataFrame
    df_joint : pd.DataFrame
    df_comp : pd.DataFrame

    dP_total : float

    config : dict

    P_require_outstream : float = 0.0
    required_power_kw : float = 0.0
    comp_price : float = 0.0
    comp_power : float = 0.0
    charge : float = 0.0

    def __post_init__(self):
        """
        클래스 생성시 카탈로그 전체 압축기의 효율을 미리 계산해 추가.
        """

        p_inlet = 100000.0  # 흡입 대기압 (1 bar = 100,000 Pa)
        q = self.df_comp['최대생산유량(m^3/h)'] / 3600.0  # m^3/h -> m^3/s
        p_outlet = (self.df_comp['최대작동압력(bar)'] + 1.0) * 100000.0  # 절대압 변환
        
        k = 1.4  # 공기의 비열비

        isentropic_power = (k / (k - 1)) * p_inlet * q * ((p_outlet / p_inlet)**((k - 1) / k) - 1.0)
        motor_power = self.df_comp['장착 모터 동력'] * 1000.0  # kW -> W

        # 효율 역산
        self.df_comp['역산효율'] = isentropic_power / motor_power

    def require_Pressure_outstream(self):
        """
        설계 조건을 고려하여 압축강하를 고려한 압축기 필요 배출 압력(Pa)의 반환
        """
        
        final_pressure = float(self.config['system_requirements']['final_pressure'])

        self.P_require_outstream = self.dP_total + final_pressure * 101325 # atm -> Pa로 단위변환하여 넣음.
        logging.info(f'압축기에 요구되는 배출 압력 : {self.P_require_outstream}')

        return self.P_require_outstream
    
    def matching(self):
        """
        압축기 효율을 반영해 실제 요구 동력의 계산 후 최적의 압축기를 매칭하는 알고리즘.
        매칭된 압축기의 심볼을 반환.
        """

        require_Q = self.calc.Q * 3600 # 시스템 요구 유량을 카탈로그의 단위와 일치, m^3/s * 3600 = m^3/h
        p_inlet = 100000.0
        k = 1.4

        ideal_power_required = (k / (k - 1)) * p_inlet * self.calc.Q * ((self.P_require_outstream / p_inlet)**((k - 1) / k) - 1.0)

        # 실제 가동 동력 (kW) 산출
        self.df_comp['실제운전동력_kw'] = (ideal_power_required / self.df_comp['역산효율']) / 1000.0
        
        # 2. 압축기 필터링. 

        # 조건 : 
        # 1) 최소생성유량이 요구조건보다 높아야 함.
        # 2) 압축기의 최대 작동 압력이 시스템의 요구 배출 압력보다 높아야 함.
        # 3) 압축기의 최대 작동 동력이 계산된 실제 운전 동력보다 높아야 함.
        matched_comp = self.df_comp[
            # 조건 1 : 최소생산유량 <= 요구유량 <= 최대생산유량
            (self.df_comp['최소생산유량(m^3/h)'] <= require_Q) & (require_Q <= self.df_comp['최대생산유량(m^3/h)']) &

            # 조건 2 : 압축기의 최대 작동압력 >= 시스템의 요구 배출압력
            ((self.df_comp['최대작동압력(bar)'] + 1.0) * 100000 >= self.P_require_outstream) &

            # 조건 3 : 압축기의 모터 동력 >= 실제 필요한 운전 동력
            (self.df_comp['장착 모터 동력'] >= self.df_comp['실제운전동력_kw'])
            ]
        
        if matched_comp.empty:
            logging.warning(f'요구 유량 {require_Q}, 요구 압력{self.P_require_outstream}을 처리할 수 있는 압축기가 존재하지 않음.')
            return None
        
        matched_comp = matched_comp.sort_values('가격').iloc[0] # 매칭된 압축기 중 가장 저렴한것 선택

        comp_symbol = str(matched_comp['심볼'])

        self.comp_power = float(matched_comp['실제운전동력_kw'])
        self.comp_price = float(matched_comp['가격'])

        logging.info(f"매칭된 압축기: {comp_symbol} (용량: {self.comp_power}kW, 가격: {self.comp_price}원)")
        return matched_comp
    
    def fee_total(self, symbol):

        fee_pipe = self.calc.fee_pipe(symbol)
        fee_joint = self.calc.fee_joint(symbol)
        fee_energy = self.calc.fee_energy(self.comp_power)

        self.charge = fee_pipe + fee_joint + fee_energy + self.comp_price

        logging.info(f'{symbol}의 총 비용 합산 | 배관 : {fee_pipe}원, 조인트 : {fee_joint}원, 압축기 : {self.comp_price}원, 에너지 : {fee_energy}원')

        return float(self.charge)