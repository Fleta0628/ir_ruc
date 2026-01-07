# 采样分布验证脚本
# 随机采样5000条，输出到 sample_5000.jsonl
import json
import random

INPUT_PATH = '../crawled_data_deduplicated.jsonl' if __name__ == '__main__' else None  # 兼容原用法
import os
INPUT_PATH = os.path.join(os.path.dirname(__file__), '../../crawled_data_deduplicated.jsonl')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '../sample_2000.jsonl')
SAMPLE_SIZE = 2000

def sample_jsonl(input_path, output_path, sample_size):
    # 首次遍历统计总行数
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    total = len(lines)
    print(f"总数据量: {total}")
    idxs = random.sample(range(total), min(sample_size, total))
    idxs_set = set(idxs)
    with open(output_path, 'w', encoding='utf-8') as out:
        for i, line in enumerate(lines):
            if i in idxs_set:
                out.write(line)
    print(f"已采样 {len(idxs)} 条，输出到 {output_path}")

if __name__ == '__main__':
    sample_jsonl(INPUT_PATH, OUTPUT_PATH, SAMPLE_SIZE)
