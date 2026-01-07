# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

from itemadapter import ItemAdapter
import json
from ruc_search.items import RucPageItem

class JsonlWriterPipeline:
    def __init__(self):
        self.item_count = 0
    
    def open_spider(self, spider):
        # 使用 'a' 模式追加，支持断点续爬
        self.file = open('crawled_data.jsonl', 'a', encoding='utf-8', buffering=1)

    def close_spider(self, spider):
        self.file.close()

    def process_item(self, item, spider):
        if not isinstance(item, RucPageItem):
            return item
        
        # 将 item 转换为字典并写入一行 JSON
        line_data = ItemAdapter(item).asdict()
        line = json.dumps(line_data, ensure_ascii=False)
        self.file.write(line + "\n")
        
        # 每爬到10000个网页打印一次
        self.item_count += 1
        if self.item_count % 10000 == 0:
            # 使用 warning 级别以确保在 LOG_LEVEL=WARNING 时能显示
            spider.logger.warning(f"已爬取 {self.item_count} 个网页")
        
        return item
