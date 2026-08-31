from dataclasses import dataclass, field
import pandas as pd
import numpy as np
import math
import logging

from Source.read_data import ReadData

@dataclass
class Calculator:
    """
    압력 강하 계산
    """

    # 데이터 받아오기
    df_pipe : pd.DataFrame
    df_joint : pd.DataFrame
    df_comp : pd.DataFrame

    config : dict

    # 주요 상수
    L_flow : float = field(init = False) 
    L_total : float = field(init = False)
    Q : float = field(init = False)      
    rho : float = field(init = False)   
    mu : float = field(init = False)      
    epsilon : float = field(init = False) 

    def __post_init__(self):
        """
        config에서 상수 추출해 변수 초기화
        """

        try:
            self.L_flow = float(self.config['system_requirements']['pipe_flow_length'])
            self.L_total = float(self.config['system_requirements']['pipe_length'])
            self.Q =  float(self.config['system_requirements']['final_flow_rate'])
            self.rho = float(self.config['environment']['density'])
            self.mu = float(self.config['environment']['viscosity'])

        except KeyError as e:
            logging.error(f'config.json에서 key를 찾을 수 없음 : {e}')
            raise

    def delta_P_total(self, symbol):
        """
        특정 파이프(심볼 : symbol)의 파이프 길이에 따른 압력강하(dP) + 부손실에 의한 압력강하 계산

        1. 파이프 심볼의 규격 불러오기
        2. 파이프 규격과 일치하는 부속품 가져오기
        """
        
        pipe_info = self.df_pipe[self.df_pipe['심볼'] == symbol]
        
        if pipe_info.empty:
            logging.error(f'{symbol}이 존재하지 않음.')
            return np.inf
        
        # 1. 파이프 정보 가져오기
        
        pipe_spec = pipe_info.iloc[0]['규격']
        d = pipe_info.iloc[0]['내경(m)'] # 단위 : m
        epsilon = pipe_info.iloc[0]['입실론(m)']

        logging.info(f'pipe {symbol}의 내경 : {d}')

        # config에서 joint의 개수, 손실계수 가져오기 / 실제로 흐르는 부분만
        joint_config = self.config.get('joint', {})
        kl_config = self.config.get('kl', {})

        sigma_K_L = 0.0

        # 2. 파이프와 부속품의 매칭 및 K_L 합산
        for joint_key, count in joint_config.items():
            if count == 0:
                continue

            matched_joint = self.df_joint[
                (self.df_joint['규격'] == pipe_spec) &
                (self.df_joint['부품'] == joint_key)
            ]

            if matched_joint.empty:
                logging.warning(f'규격 {pipe_spec}에 해당하는 부품 {joint_key}가 데이터셋에 존재하지 않음.')
                return np.inf

            k_l = kl_config.get(joint_key, 0.0)
            sigma_K_L += (k_l * count)

        sigma_K_L += kl_config.get('entrance', 0.0)
        sigma_K_L += kl_config.get('exit', 0.0)

        logging.info(f'부차적 손실계수 합 : {sigma_K_L}')


        # 3. 파이프에 의한 압력강하 계산
        pre_term = (8 * self.rho * (self.Q **2)) / (math.pi ** 2)

        roughness_term = ((epsilon / d) / 3.7) ** 1.1
        reynoldes_term = (6.9 * math.pi * self.mu * d) / (4 * self.rho * self.Q)

        f_trem = (-1.8 * math.log10(roughness_term + reynoldes_term)) ** 2

        dP_pipe = pre_term * (self.L_flow / ((d ** 5) * f_trem))


        # 4. 부차적 손실 합계에 의한 압력강하 계산
        pre_term = (8 * self.rho * (self.Q **2)) / (math.pi ** 2)
        dP_joint = pre_term * (sigma_K_L / (d ** 4))

        dP_total = dP_pipe + dP_joint

        logging.info(f'총 압력강하 : {dP_total}')

        return dP_total
    
    def fee_pipe(self, symbol):
        """
        특정 파이프의 구매 비용 계산 (가격/길이 * 총 길이)
        """

        pipe_info = self.df_pipe[self.df_pipe['심볼'] == symbol]
        
        if pipe_info.empty:
            logging.error(f'{symbol}이 존재하지 않음.')
            return 0.0

        fee_pipe = pipe_info.iloc[0]['가격/길이'] * self.L_total
        logging.info(f'pipe {symbol}의 총 파이프 비용 : {fee_pipe}')
        
        return fee_pipe

    def fee_joint(self,symbol):
        """
        모든 부속품의 총 구매비용 계산.
        """

        pipe_info = self.df_pipe[self.df_pipe['심볼'] == symbol]
        
        if pipe_info.empty:
            logging.error(f'{symbol}이 존재하지 않음.')
            return 0.0

        pipe_spec = pipe_info.iloc[0]['규격']

        # joint_config = 실제로 타고 흐르는, exception_config = 타고 흐르지 않는.
        # 두 개를 합쳐줘야함
        joint_config = self.config.get('joint', {})
        exception_config = self.config.get('exception', {})

        total_config = {}
        for joint_key, count in joint_config.items():
            total_config[joint_key] = total_config.get(joint_key, 0) + count
        
        for joint_key, count in exception_config.items():
            total_config[joint_key] = total_config.get(joint_key, 0) + count

        total_joint_fee = 0.0

        # 파이프와 조인트의 매칭
        for joint_key, count in total_config.items():
            if count == 0:
                continue

            matched_joint = self.df_joint[
                (self.df_joint['규격'] == pipe_spec) & 
                (self.df_joint['부품'] == joint_key)
            ]

            if matched_joint.empty:
                continue

            price = matched_joint.iloc[0]['가격']
            total_joint_fee += price * count

        logging.info(f'pipe {symbol}의 총 부속부품 비용 : {total_joint_fee}')

        return total_joint_fee

    def fee_energy(self, require_power):
        """
        실제 전기세 계산.
        """

        if require_power is None:
            return 0.0
        
        tariff = self.config.get('electricity_tariff', {})
        base_rate = tariff.get('base_rate_per_kw', 8230)
        rate_sa = tariff.get('rate_spring_autumn', 89.05)
        rate_su = tariff.get('rate_summer', 121.90)
        rate_wi = tariff.get('rate_winter', 116.89)
        surcharges = tariff.get('surcharges_ratio', 1.137)

        # 한전 연간 기본요금
        annual_base_fee = require_power * base_rate * 12

        # 연간 전력양 요금
        daily_kwh = require_power * 24

        fee_summer = daily_kwh * 92 * rate_su
        fee_winter = daily_kwh * 120 * rate_wi
        fee_spring_autumn = daily_kwh * 153 * rate_sa

        annual_usage_fee = fee_summer + fee_winter + fee_spring_autumn

        # 세금 적용
        annual_total_fee = (annual_base_fee + annual_usage_fee) * surcharges

        # 10년 사용 가정
        total_fee_energy = annual_total_fee * 10
        
        logging.info(f'총 에너지 비용 : {total_fee_energy}')

        return total_fee_energy