# Scrapy settings for ruc_search project

BOT_NAME = "ruc_search"

SPIDER_MODULES = ["ruc_search.spiders"]
NEWSPIDER_MODULE = "ruc_search.spiders"

# --- 核心配置 ---

# 禁用 robots.txt 以确保覆盖率 (重要)
ROBOTSTXT_OBEY = False

# 并发控制
CONCURRENT_REQUESTS = 128
CONCURRENT_REQUESTS_PER_DOMAIN = 128
# 延迟设置
DOWNLOAD_DELAY = 0

# 超时设置
DOWNLOAD_TIMEOUT = 8

# 重试设置
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429, 403]

# 深度限制 (足够深以覆盖全站)
DEPTH_LIMIT = 50

# --- 持久化与去重 (重要) ---
# 启用持久化作业目录。这会自动启用：
# 1. 请求队列的磁盘持久化
# 2. 已访问 URL 的去重记录持久化
# 这样即使爬虫停止，下次运行也会从这里继续，且自动去重。
JOBDIR = 'crawls/ruc_spider_state'

# --- 管道 ---
ITEM_PIPELINES = {
   'ruc_search.pipelines.JsonlWriterPipeline': 300,
}

# --- 代理设置 ---
# 警告: 检测到系统环境变量中配置了代理 (http_proxy/https_proxy)，但连接被拒绝。
# 为了防止爬虫因代理失效而无法工作，这里强制禁用 Scrapy 的默认代理中间件。
# 如果后续需要使用代理，请确保代理服务正常运行，并注释掉下面这行。
HTTPPROXY_ENABLED = False

# --- 其他 ---
# 禁用 Cookies 提升性能
COOKIES_ENABLED = False

# 使用通用的 User-Agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'

# 编码
FEED_EXPORT_ENCODING = "utf-8"

# 日志设置：只显示警告及以上级别
LOG_LEVEL = 'WARNING'

# AutoThrottle (已开启，自动调整请求速度以避免封锁)
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0
AUTOTHROTTLE_MAX_DELAY = 10
# 平均并发数目标
AUTOTHROTTLE_TARGET_CONCURRENCY = 32.0
