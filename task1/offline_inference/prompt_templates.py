# Qwen 提示词模板
# 用于Task 1: 类别发现与离线数据增强

CATEGORY_PROMPT = '''
请根据以下网页内容，将其归入最合适的 1-2 个类别，并生成 3 个用户可能会问的问题，以及一句话摘要。

**严格约束**：
1. **必须**从给定的 3 个类别中选择，**严禁**编造其他类别。
2. soft_categories 中的类别请按相关性从高到低排列。
3. 如果内容仅属于一个类别，请只输出一个，**不要**强行凑数。

类别体系（3 类）：
- News：新闻动态（学校要闻、学院动态、通知公告、学术预告、公示名单、招标信息）
- Research：学术科研（论文、项目、机构介绍、教授主页、实验室、图书馆资源、学术数据库）
- Education：教育服务（课程、招生、就业、学籍管理、行政办事、后勤服务、规章制度、学生活动）

输出格式：
{
  "soft_categories": ["News", "Research"],
  "potential_queries": ["问题1", "问题2", "问题3"],
  "summary": "一句话摘要"
}

网页内容：
{content}
'''

# 转义版本，用于format方法
CATEGORY_PROMPT_SAFE = CATEGORY_PROMPT.replace("{", "{{").replace("}", "}}")
CATEGORY_PROMPT_SAFE = CATEGORY_PROMPT_SAFE.replace("{{content}}", "{content}")
