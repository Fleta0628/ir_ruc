import scrapy
import json
import os
from scrapy.linkextractors import LinkExtractor
from ..items import RucPageItem
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TimeoutError, TCPTimedOutError

class RucSpider(scrapy.Spider):
    name = 'ruc'
    allowed_domains = ['ruc.edu.cn']
    start_urls = ['https://www.ruc.edu.cn/']
    
    # 种子文件路径
    SEEDS_FILE = 'temp_urls.json'

    def __init__(self, *args, **kwargs):
        super(RucSpider, self).__init__(*args, **kwargs)
        
        # 链接提取器：排除非网页文件
        self.link_extractor = LinkExtractor(
            allow_domains=self.allowed_domains,
            deny_extensions=[
                'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'ico',
                'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                'zip', 'rar', '7z', 'gz', 'tar', 'bz2',
                'mp3', 'mp4', 'avi', 'mkv', 'flv', 'wmv',
                'js', 'css', 'xml', 'json',
                'exe', 'dmg', 'apk'
            ]
        )

    def start_requests(self):
        # 检查是否从断点续爬
        jobdir = self.settings.get('JOBDIR')
        is_resuming = False
        
        if jobdir and os.path.exists(jobdir):
            queue_dir = os.path.join(jobdir, 'requests.queue')
            if os.path.exists(queue_dir):
                # 检查请求队列是否有内容
                queue_files = os.listdir(queue_dir)
                has_active_requests = False
                
                for file in queue_files:
                    file_path = os.path.join(queue_dir, file)
                    if file.endswith('.json') and os.path.getsize(file_path) > 2:  # 大于2字节表示非空数组
                        has_active_requests = True
                        break
                
                if has_active_requests:
                    self.logger.info("Resuming from job directory, skipping seed URLs...")
                    return
        # 首次运行或新的爬取，加载种子URL
        self.logger.info("Job directory empty or no active requests, loading seed URLs...")
        
        # 首次运行或新的爬取，加载种子URL
        # 1. 首先爬取主页
        yield scrapy.Request('https://www.ruc.edu.cn/', self.parse, errback=self.handle_error)

        # 2. 从文件加载种子 URL
        if os.path.exists(self.SEEDS_FILE):
            self.logger.info(f"Loading seeds from {self.SEEDS_FILE}...")
            try:
                with open(self.SEEDS_FILE, 'r', encoding='utf-8') as f:
                    seeds = json.load(f)
                    
                for seed in seeds:
                    url = seed.get('url')
                    if url:
                        # Scrapy 的调度器会自动去重，所以直接 yield 即可
                        yield scrapy.Request(url, self.parse, errback=self.handle_error)
            except Exception as e:
                self.logger.error(f"Error loading seeds: {e}")
        else:
            self.logger.warning(f"Seeds file not found: {self.SEEDS_FILE}")

    # 修复 Scrapy 2.13+ 关于 start() 是 coroutine 的警告
    def start(self):
        return super().start()

    def parse(self, response):
        # 1. 内容类型检查
        content_type = response.headers.get('Content-Type', b'').decode('utf-8').lower()
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            self.logger.debug(f"Skipping non-text content: {response.url}")
            return

        # 2. 提取信息
        item = RucPageItem()
        item['url'] = response.url
        
        # 提取标题
        item['title'] = response.xpath('//title/text()').get(default='').strip()
        
        # 提取正文 (简单清洗：去除 script 和 style，获取 body 下所有文本)
        # 使用 xpath 排除特定标签
        text_fragments = response.xpath('//body//*[not(self::script or self::style)]/text()').getall()
        # 清理空白字符并拼接
        cleaned_text = ' '.join([t.strip() for t in text_fragments if t.strip()])
        item['content'] = cleaned_text

        # 3. 提取链接
        try:
            links_on_page = self.link_extractor.extract_links(response)
            item['links'] = [link.url for link in links_on_page]
        except Exception as e:
            self.logger.warning(f"Link extraction error on {response.url}: {e}")
            item['links'] = []

        yield item

        # 4. 继续爬取发现的链接
        for link in links_on_page:
            yield response.follow(link, callback=self.parse, errback=self.handle_error)

    def handle_error(self, failure):
        # 简单的错误日志，不再写入单独的错误文件以保持简洁
        request_url = failure.request.url
        if failure.check(HttpError):
            response = failure.value.response
            self.logger.warning(f"HttpError {response.status} on {request_url}")
        elif failure.check(DNSLookupError):
            self.logger.warning(f"DNSLookupError on {request_url}")
        elif failure.check(TimeoutError, TCPTimedOutError):
            self.logger.warning(f"TimeoutError on {request_url}")
        else:
            self.logger.warning(f"Error on {request_url}: {failure.value}")
