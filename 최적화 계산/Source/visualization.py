import matplotlib.pyplot as plt
from dataclasses import dataclass
import pandas as pd

@dataclass
class visualization:
    """
    결과 시각화
    """

    result_symbol : list
    result_fee : list
    result_dim : list

    def make_graph(self):

        plt.rcParams['font.family'] = 'Malgun Gothic'

        fig, axes = plt.subplots(1,1, figsize=(15,12))

        axes.plot(self.result_dim, self.result_fee, label='Total Cost', marker='o', color='blue', linewidth=2)

        for dim, fee, sym in zip(self.result_dim, self.result_fee, self.result_symbol):
            axes.annotate(f'{sym}', (dim, fee), 
                             textcoords="offset points", xytext=(0, 10), 
                             ha='center', fontsize=12, fontweight='bold', color='darkred')

        axes.set_title('total cost', fontsize=16)
        axes.set_xlabel('pipe dim', fontsize=12)
        axes.set_ylabel('total cost', fontsize=12)
        axes.grid(True, linestyle='--', alpha=0.7)
        axes.legend()

        plt.tight_layout()
        plt.show()