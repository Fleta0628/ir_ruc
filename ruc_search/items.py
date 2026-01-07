# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class RucPageItem(scrapy.Item):
    url = scrapy.Field()      # 页面 URL
    links = scrapy.Field()    # 页面上的出站链接列表
    title = scrapy.Field()    # 页面标题
    content = scrapy.Field()  # 页面正文内容 (清洗后)
