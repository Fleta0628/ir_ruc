# 服务器迁移改进建议

## 1. 配置文件优化

### 路径配置
确保所有文件路径使用相对路径，避免硬编码绝对路径：

```python
# 在 settings.py 中使用相对路径
JOBDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'crawls', 'ruc_spider_state')
SEEDS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'temp_urls.json')
CRAWLED_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'crawled_data.jsonl')
```

### 并发设置
根据服务器的 CPU 核心数和内存进行调整：

```python
# settings.py 并发配置建议
CONCURRENT_REQUESTS = 128
CONCURRENT_REQUESTS_PER_DOMAIN = 32
```

### 服务器代理配置
如果服务器需要使用代理，配置代理服务器：

```python
# settings.py 代理配置
HTTPPROXY_ENABLED = True
PROXY_LIST = 'proxies.txt'  # 代理列表文件
```

## 2. 数据持久化改进

### 存储到数据库
考虑将数据存储到 MySQL 或 PostgreSQL 而不是 JSONL 文件：

```python
# pipelines.py 数据库存储示例
import MySQLdb
from itemadapter import ItemAdapter

class MySQLPipeline:
    def open_spider(self, spider):
        self.conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='password',
            db='ruc_crawl'
        )
        self.cursor = self.conn.cursor()
    
    def close_spider(self, spider):
        self.conn.close()
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        sql = "INSERT INTO pages (url, title, content, links) VALUES (%s, %s, %s, %s)"
        values = (
            adapter['url'],
            adapter['title'],
            adapter['content'],
            json.dumps(adapter['links'])
        )
        self.cursor.execute(sql, values)
        self.conn.commit()
        return item
```

### 分块存储
将 large 数据分成多个 JSONL 文件存储：

```python
# pipelines.py 分块存储示例
import json
import os
from itemadapter import ItemAdapter

class SplitJsonlPipeline:
    def __init__(self):
        self.file_count = 0
        self.item_count = 0
        self.max_items_per_file = 100000
        self.file = None
    
    def open_spider(self, spider):
        self.open_new_file()
    
    def close_spider(self, spider):
        if self.file:
            self.file.close()
    
    def process_item(self, item, spider):
        if self.item_count >= self.max_items_per_file:
            self.file.close()
            self.open_new_file()
        
        line = json.dumps(ItemAdapter(item).asdict(), ensure_ascii=False)
        self.file.write(line + "\n")
        self.item_count += 1
        return item
    
    def open_new_file(self):
        filename = f'crawled_data_{self.file_count}.jsonl'
        self.file = open(filename, 'a', encoding='utf-8')
        self.file_count += 1
        self.item_count = 0
```

## 3. 监控与日志

### 日志配置
增强日志记录，方便调试和监控：

```python
# settings.py 日志配置
LOG_FILE = 'scrapy.log'
LOG_LEVEL = 'INFO'  # DEBUG/INFO/WARNING/ERROR/CRITICAL
```

### 进度监控
在 pipeline 中添加进度监控：

```python
# pipelines.py 进度监控
import logging
from itemadapter import ItemAdapter

class ProgressPipeline:
    def __init__(self):
        self.crawl_count = 0
    
    def process_item(self, item, spider):
        self.crawl_count += 1
        if self.crawl_count % 100 == 0:
            logging.info(f"Crawled {self.crawl_count} pages so far...")
        return item
```

## 4. 性能优化

### 压缩存储
将 crawled_data.jsonl 文件压缩存储：

```bash
# 压缩 JSONL 文件
gzip crawled_data.jsonl

# 解压缩
gzip -d crawled_data.jsonl.gz
```

### 去重优化
使用 BloomFilter 进行更高效的去重：

```python
# 安装 bloom-filter
pip install bloom-filter

# settings.py
DUPEFILTER_CLASS = 'scrapy.dupefilters.BloomFilterDupeFilter'
```

## 5. 服务器部署

### 安装依赖
```bash
# 安装 Python 和 Scrapy
apt-get update && apt-get install -y python3 python3-pip python3-venv
pip install scrapy
```

### 创建虚拟环境
```bash
python3 -m venv ruc_crawl_env
source ruc_crawl_env/bin/activate
pip install scrapy
```

### 启动爬虫
```bash
# 后台运行爬虫并将日志输出到文件
nohup scrapy crawl ruc > crawl.log 2>&1 &

# 查看爬虫状态
ps aux | grep scrapy

# 查看日志
tail -f crawl.log
