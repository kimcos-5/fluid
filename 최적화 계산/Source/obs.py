import json
import logging
import math
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

class PipelineObserver:
    """
    JSON 배관 시퀀스를 1m 단위로 쪼개어 각 지점의 압력 및 동력강하 계산
    """
    def __init__(self, calc, op, symbol, layout_file):
        self.calc = calc
        self.op = op
        self.symbol = symbol
        
        try:
            with open(layout_file, 'r', encoding='utf-8') as f:
                self.layout = json.load(f)
            logging.info(f"배관 레이아웃 1m 단위 분석 준비 완료: {layout_file}")
        except FileNotFoundError:
            logging.error(f"레이아웃 파일을 찾을 수 없습니다: {layout_file}")
            self.layout = []
            
        self.plot_distances = []
        self.plot_pressures = []
        self.plot_powers = []
        
    def analyze(self):
        if not self.layout:
            return

        Q = self.calc.Q
        d = float(self.op.df_pipe[self.op.df_pipe['심볼'] == self.symbol].iloc[0]['내경(m)'])
        
        kl = self.op.config.get('kl', {})
        joint_config = self.op.config.get('joint', {})
        dynamic_p = (8 * self.calc.rho * (Q**2)) / ((math.pi**2) * (d**4))
        
        # config에 정의된 모든 부속품의 총 압력 강하 동적 계산
        total_joint_dp = 0.0
        for joint_key, count in joint_config.items():
            t_kl = kl.get(joint_key, 0.0)
            total_joint_dp += t_kl * count * dynamic_p
            
        # 입구 및 출구 손실 추가
        total_joint_dp += kl.get('entrance', 0.0) * dynamic_p
        total_joint_dp += kl.get('exit', 0.0) * dynamic_p

        # 파이프 1m당 마찰 손실 계산
        total_pipe_length = sum([item['length'] for item in self.layout if item['type'] == 'pipe'])
        total_pipe_dp = self.calc.delta_P_total(self.symbol) - total_joint_dp
        dP_per_m = total_pipe_dp / total_pipe_length if total_pipe_length > 0 else 50.0

        logging.info(f'obs의 total_joint_dp: {total_joint_dp}')
        logging.info(f'obs의 total_pipe_dp: {total_pipe_dp}')

        # 초기 상태 (압축기 직후)
        current_distance = 0.0
        current_pressure = self.op.P_require_outstream
        
        # 데이터 기록 함수
        def record_state():
            self.plot_distances.append(current_distance)
            self.plot_pressures.append(current_pressure)
            self.plot_powers.append((current_pressure * Q) / 1000)

        record_state()
        logging.info(f"\n[ 0.0m 시작 ] 초기 배출 압력: {current_pressure:,.0f} Pa")

        # 리스트를 순회하며 1m 단위 마칭(Marching) 시뮬레이션
        for step in self.layout:
            comp_type = step['type']
            
            if comp_type == "pipe":
                length = step['length']
                steps = int(length)  # 1m 단위 횟수
                remainder = length - steps
                
                # 1m씩 전진하며 압력 강하
                for _ in range(steps):
                    current_distance += 1.0
                    current_pressure -= dP_per_m
                    record_state()
                    
                # 1m로 안 떨어되는 소수점 나머지 길이 처리
                if remainder > 0:
                    current_distance += remainder
                    current_pressure -= (dP_per_m * remainder)
                    record_state()
                    
            elif comp_type in kl:
                comp_kl = kl.get(comp_type, 0.0)
                current_pressure -= comp_kl * dynamic_p
                record_state()
                
            # note가 있는 지점은 콘솔에 위치 출력
            if "note" in step:
                logging.info(f"[ {current_distance:>5.1f}m 통과 ] {step['note']} | 현재 압력: {current_pressure:,.0f} Pa")
                
        logging.info(f"[ 최종 도달 ] 최종 압력: {current_pressure:,.0f} Pa\n")
                    
    def plot_graph(self):
        if not self.plot_distances:
            return
        
        plt.rcParams['font.family'] = 'Malgun Gothic'

        fig, ax1 = plt.subplots(figsize=(14, 7))

        x = self.plot_distances
        ax1.set_xlabel('누적 이동 거리 (m)', fontsize=13, fontweight='bold')
        ax1.set_ylabel('내부 유체 압력 (Pa)', fontsize=13, fontweight='bold')
        
        # 선만 이어서 그림 (1m 단위라 점을 찍으면 너무 빽빽함)
        line1 = ax1.plot(x, self.plot_pressures, linewidth=2.5, label='유체 압력 (Pressure)')
        ax1.tick_params(axis='y')
        ax1.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda val, loc: "{:,}".format(int(val))))

        ax2 = ax1.twinx()  
        ax2.set_ylabel('요구 유체 동력 (kW)', fontsize=13, fontweight='bold')
        line2 = ax2.plot(x, self.plot_powers, linestyle='--', linewidth=2, label='유체 동력 (Power)')
        ax2.tick_params(axis='y')

        plt.title(f'파이프 : {self.symbol}', fontsize=17, fontweight='bold', pad=20)
        
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax1.legend(lines, labels, loc='upper right', fontsize=12)
        
        ax1.grid(True, linestyle='--', alpha=0.4)
        plt.tight_layout()
        plt.show()