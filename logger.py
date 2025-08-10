import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

class LogCollector(logging.Handler):
    def __init__(self, maxlen=1000):
        super().__init__()
        self.records = []
        self.maxlen = maxlen

    def emit(self, record):
        msg = self.format(record)
        self.records.append(msg)
        if len(self.records) > self.maxlen:
            self.records = self.records[-self.maxlen:]

    def get_logs(self):
        return list(self.records)

    def clear(self):
        self.records.clear()

# 1. 日志格式
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s",
                              datefmt="%m-%d %H:%M:%S"
                                )

# 2. 控制台 Handler
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

# 3. 内存Handler（供前端调用）
collector = LogCollector()
collector.setFormatter(formatter)

# 4. 文件归档Handler（可选，推荐加）
file_handler = RotatingFileHandler(
    'ws-td.log', maxBytes=2*1024*1024, backupCount=30, encoding='utf-8'
)
file_handler.setFormatter(formatter)

# 5. 全局 logger
logger = logging.getLogger("ws-td")
logger.addHandler(stream_handler)
logger.addHandler(collector)
logger.addHandler(file_handler)   # 文件日志归档，最大5个2M的文件
logger.setLevel(logging.INFO)

# 6. 暴露接口
def get_logs():
    return collector.get_logs()

def clear_logs():
    collector.clear()
