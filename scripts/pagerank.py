# pagerank_calculator.py
# 用于计算爬取数据的 PageRank 值

import json
import networkx as nx
import time
import os

# 配置
CRAWLED_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'crawled_data_deduplicated.jsonl')
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'pagerank_results.json')
PAGERANK_ALPHA = 0.85  # 阻尼系数


def load_crawled_data(file_path):
    """从 crawled_data.jsonl 加载爬取的页面数据"""
    if not os.path.exists(file_path):
        print(f"错误: 未找到爬取数据文件 {file_path}")
        return None
    
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        print(f"成功加载 {len(data)} 条页面数据")
        return data
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        return None
    except Exception as e:
        print(f"加载文件出错: {e}")
        return None


def build_graph(data):
    """构建有向图"""
    if not data:
        return None
    
    G = nx.DiGraph()
    
    # 第一轮：添加所有节点
    all_urls = {page['url'] for page in data}
    G.add_nodes_from(all_urls)
    print(f"添加了 {len(all_urls)} 个节点")
    
    # 第二轮：添加边
    edge_count = 0
    for page in data:
        source_url = page['url']
        for target_url in page['links']:
            if target_url in all_urls:
                G.add_edge(source_url, target_url)
                edge_count += 1
    print(f"添加了 {edge_count} 条边")
    
    return G


def calculate_pagerank(graph):
    """计算 PageRank"""
    if not graph or graph.number_of_nodes() == 0:
        return None
    
    print("开始计算 PageRank...")
    start_time = time.time()
    
    # 使用 NetworkX 内置的 PageRank 算法
    pagerank_scores = nx.pagerank(graph, alpha=PAGERANK_ALPHA)
    
    print(f"PageRank 计算完成，耗时 {time.time() - start_time:.2f} 秒")
    return pagerank_scores


def save_results(scores, output_file):
    """保存结果到 JSON 文件"""
    if not scores:
        return
    
    # 按 PageRank 值降序排序
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    # 转换为字典格式
    result_dict = {url: score for url, score in sorted_scores}
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)
    
    print(f"结果已保存到 {output_file}")
    
    # 打印前 10 名
    print("\n--- PageRank Top 10 ---")
    for url, score in sorted_scores[:10]:
        print(f"URL: {url}")
        print(f"Score: {score:.6f}")
        print("-" * 60)


def main():
    """主函数"""
    data = load_crawled_data(CRAWLED_FILE)
    if data:
        graph = build_graph(data)
        if graph:
            pagerank_scores = calculate_pagerank(graph)
            if pagerank_scores:
                save_results(pagerank_scores, OUTPUT_FILE)


if __name__ == "__main__":
    main()
