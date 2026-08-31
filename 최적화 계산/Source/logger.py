from pathlib import Path
import logging

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

def setup_logging(run_dir: Path):
    logging.basicConfig(level = logging.INFO, 
                        format = LOG_FORMAT, 
                        handlers = [logging.StreamHandler()])
    
    set_logging_path(run_dir)

def set_logging_path(run_dir: Path):

    run_dir.mkdir(parents=True, exist_ok=True)
    log_file = run_dir / f"log_{_get_next_run_id(run_dir)}.log"

    file_handler = logging.FileHandler(log_file, encoding= 'utf-8')
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    file_handler.setLevel(logging.INFO)

    logging.getLogger().addHandler(file_handler)

    logging.info(f'로깅 설정 완료. 로그 파일 저장 위치 : {log_file}')

def _get_next_run_id(run_dir: Path) -> int:
        
        if not run_dir.exists():
            return 1

        log_files = list(p for p in run_dir.glob('log_*.log') if p.is_file())
  
        last_num = 0
        for d in log_files:
            try:
                num = int(d.stem.split('_')[1])
                if num > last_num:
                    last_num = num

            except(IndexError, ValueError):
                continue

        return last_num + 1