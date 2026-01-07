# 统计Qwen分类结果的占比
import json
import os
from collections import Counter
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LABEL_PATH = os.path.join(BASE_DIR, "../sample_2000_labeled.jsonl")

total_counter = Counter()
primary_counter = Counter()
valid_count = 0

with open(LABEL_PATH, "r", encoding="utf-8") as fin:
    for line in fin:
        try:
            item = json.loads(line)
            label = item.get("qwen_label", "")
            # 兼容多种格式，提取soft_categories
            match = re.search(r'"soft_categories"\s*:\s*\[(.*?)\]', label, re.S)
            if match:
                cats_str = match.group(1)
                cats = re.findall(r'"(.*?)"', cats_str)
                if cats:
                    valid_count += 1
                    # 统计第一类别（主类别）
                    primary_counter[cats[0]] += 1
                    # 统计所有类别
                    for cat in cats:
                        total_counter[cat] += 1
        except:
            continue

print(f"有效数据量: {valid_count}")

print("\n=== 主类别分布 (Primary Category) ===")
primary_total = sum(primary_counter.values())
for cat, count in primary_counter.most_common():
    print(f"{cat}: {count} ({count/primary_total:.2%})")

print("\n=== 全类别分布 (Total Mentions) ===")
total_mentions = sum(total_counter.values())
for cat, count in total_counter.most_common():
    print(f"{cat}: {count} ({count/total_mentions:.2%})")
