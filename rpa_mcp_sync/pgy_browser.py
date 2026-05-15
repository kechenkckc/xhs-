from __future__ import annotations

import csv
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from .config_store import ROOT
from .creator_store import _threshold_from_text

CDP_URL = "http://127.0.0.1:9222/json/version"
PGY_KOL_URL = "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol"
PGY_ALL_NON_LIVE_METRICS = "全部非直播指标"
PGY_DETAIL_SCREENSHOT_DIR = ROOT / "runtime" / "pgy_detail_screenshots"

PGY_DISPLAY_METRICS = [
    PGY_ALL_NON_LIVE_METRICS,
]

PGY_REQUIRED_NON_LIVE_METRICS = [
    "粉丝数",
    "粉丝量变化幅度",
    "活跃粉丝占比",
    "互动粉丝占比",
    "曝光中位数（日常）",
    "阅读中位数（日常）",
    "互动中位数（日常）",
    "图文阅读中位数（日常）",
    "视频阅读中位数（日常）",
    "曝光中位数（合作）",
    "阅读中位数（合作）",
    "互动中位数（合作）",
    "外溢进店单价",
    "图文预估阅读单价",
    "图文预估互动单价",
    "视频预估阅读单价",
    "视频预估互动单价",
    "邀约48h回复率",
]


PGY_EXPORT_FIELD_ALIASES = {
    "nickname": ["达人昵称", "博主昵称", "昵称", "博主名称"],
    "pgy_url": ["蒲公英链接", "详情页链接", "主页链接", "博主链接"],
    "xiaohongshu_id": ["小红书号", "小红书ID", "小红书id"],
    "followers_count": ["粉丝数", "粉丝量"],
    "quote_price": ["全部报价", "报价", "图文报价", "图文笔记一口价"],
    "video_quote_price": ["视频报价", "视频笔记一口价"],
    "liked_collected_count": ["获赞与收藏", "赞藏数", "赞藏量"],
    "female_fans_ratio": ["粉丝女性用户占比", "女性粉丝占比"],
    "male_fans_ratio": ["粉丝男性用户占比", "男性粉丝占比"],
    "fans_18_24_ratio": ["粉丝年龄18-24占比", "18-24占比"],
    "fans_25_34_ratio": ["粉丝年龄25-34占比", "25-34占比"],
    "fans_35_44_ratio": ["粉丝年龄35-44占比", "35-44占比"],
    "fans_44_plus_ratio": ["粉丝年龄44岁以上占比", "44岁以上占比"],
    "active_fans_ratio": ["活跃粉丝占比"],
    "fans_growth_ratio": ["粉丝量变化幅度"],
    "read_fans_ratio": ["阅读粉丝占比"],
    "interaction_fans_ratio": ["互动粉丝占比"],
    "order_fans_ratio": ["下单粉丝占比"],
    "daily_exposure_median": ["曝光中位数（日常）", "日常曝光中位数"],
    "daily_read_median": ["阅读中位数（日常）", "日常阅读中位数"],
    "daily_interaction_median": ["互动中位数（日常）", "日常互动中位数"],
    "daily_thousand_like_note_ratio": ["千赞笔记比例", "千赞笔记比例（日常）"],
    "daily_hundred_like_note_ratio": ["百赞笔记比例", "百赞笔记比例（日常）"],
    "image_daily_exposure_median": ["图文曝光中位数（日常）"],
    "image_daily_read_median": ["图文阅读中位数（日常）"],
    "image_daily_interaction_median": ["图文互动中位数（日常）"],
    "image_daily_thousand_like_note_ratio": ["图文千赞笔记比例"],
    "image_daily_hundred_like_note_ratio": ["图文百赞笔记比例"],
    "video_daily_exposure_median": ["视频曝光中位数（日常）"],
    "video_daily_read_median": ["视频阅读中位数（日常）"],
    "video_daily_interaction_median": ["视频互动中位数（日常）"],
    "video_daily_thousand_like_note_ratio": ["视频千赞笔记比例"],
    "video_daily_hundred_like_note_ratio": ["视频百赞笔记比例"],
    "video_completion_rate": ["视频完播率"],
    "cooperation_exposure_median": ["曝光中位数（合作）", "合作曝光中位数"],
    "cooperation_read_median": ["阅读中位数（合作）", "合作阅读中位数"],
    "cooperation_interaction_median": ["互动中位数（合作）", "合作互动中位数"],
    "overflow_store_median": ["外溢进店中位数"],
    "overflow_store_unit_price": ["外溢进店单价"],
    "image_cpm": ["图文预估CPM价格", "预估图文CPM"],
    "image_read_unit_price": ["图文预估阅读单价", "图文笔记阅读单价"],
    "image_interaction_unit_price": ["图文预估互动单价", "图文笔记互动单价"],
    "video_cpm": ["视频预估CPM价格", "预估视频CPM"],
    "video_read_unit_price": ["视频预估阅读单价", "视频笔记阅读单价"],
    "video_interaction_unit_price": ["视频预估互动单价", "视频笔记互动单价"],
    "reply_rate_48h": ["邀约48h回复率", "邀约48小时回复率"],
    "live_30d_count": ["近30天直播场次"],
    "live_avg_viewers": ["场均观看人数", "场均观播人数"],
    "live_avg_sales": ["场均销售额"],
}

PGY_TABLE_TO_PAYLOAD_FIELDS = {
    "粉丝数": "followers_count",
    "全部报价": "quote_price",
    "图文笔记一口价": "quote_price",
    "视频报价": "video_quote_price",
    "视频笔记一口价": "video_quote_price",
    "获赞与收藏": "liked_collected_count",
    "赞藏数": "liked_collected_count",
    "赞藏量": "liked_collected_count",
    "粉丝女性用户占比": "female_fans_ratio",
    "女性粉丝占比": "female_fans_ratio",
    "粉丝年龄25-34占比": "fans_25_34_ratio",
    "活跃粉丝占比": "active_fans_ratio",
    "粉丝量变化幅度": "fans_growth_ratio",
    "阅读粉丝占比": "read_fans_ratio",
    "互动粉丝占比": "interaction_fans_ratio",
    "下单粉丝占比": "order_fans_ratio",
    "曝光中位数（日常）": "daily_exposure_median",
    "阅读中位数（日常）": "daily_read_median",
    "互动中位数（日常）": "daily_interaction_median",
    "千赞笔记比例": "daily_thousand_like_note_ratio",
    "千赞笔记比例（日常）": "daily_thousand_like_note_ratio",
    "百赞笔记比例": "daily_hundred_like_note_ratio",
    "百赞笔记比例（日常）": "daily_hundred_like_note_ratio",
    "图文曝光中位数（日常）": "image_daily_exposure_median",
    "图文阅读中位数（日常）": "image_daily_read_median",
    "图文互动中位数（日常）": "image_daily_interaction_median",
    "图文千赞笔记比例": "image_daily_thousand_like_note_ratio",
    "图文百赞笔记比例": "image_daily_hundred_like_note_ratio",
    "视频曝光中位数（日常）": "video_daily_exposure_median",
    "视频阅读中位数（日常）": "video_daily_read_median",
    "视频互动中位数（日常）": "video_daily_interaction_median",
    "视频千赞笔记比例": "video_daily_thousand_like_note_ratio",
    "视频百赞笔记比例": "video_daily_hundred_like_note_ratio",
    "视频完播率": "video_completion_rate",
    "曝光中位数（合作）": "cooperation_exposure_median",
    "阅读中位数（合作）": "cooperation_read_median",
    "互动中位数（合作）": "cooperation_interaction_median",
    "外溢进店中位数": "overflow_store_median",
    "外溢进店单价": "overflow_store_unit_price",
    "图文预估CPM价格": "image_cpm",
    "预估图文CPM": "image_cpm",
    "图文预估阅读单价": "image_read_unit_price",
    "图文笔记阅读单价": "image_read_unit_price",
    "图文预估互动单价": "image_interaction_unit_price",
    "图文笔记互动单价": "image_interaction_unit_price",
    "视频预估CPM价格": "video_cpm",
    "预估视频CPM": "video_cpm",
    "视频预估阅读单价": "video_read_unit_price",
    "视频笔记阅读单价": "video_read_unit_price",
    "视频预估互动单价": "video_interaction_unit_price",
    "视频笔记互动单价": "video_interaction_unit_price",
    "邀约48h回复率": "reply_rate_48h",
    "邀约48小时回复率": "reply_rate_48h",
    "近30天直播场次": "live_30d_count",
    "场均观播人数": "live_avg_viewers",
    "场均观看人数": "live_avg_viewers",
    "场均销售额": "live_avg_sales",
}

PGY_NON_LIVE_ROW_METRIC_FIELDS = [
    ("followers_count", "粉丝数"),
    ("fans_growth_ratio", "粉丝量变化幅度"),
    ("active_fans_ratio", "活跃粉丝占比"),
    ("interaction_fans_ratio", "互动粉丝占比"),
    ("daily_exposure_median", "曝光中位数（日常）"),
    ("daily_read_median", "阅读中位数（日常）"),
    ("daily_interaction_median", "互动中位数（日常）"),
    ("daily_thousand_like_note_ratio", "千赞笔记比例"),
    ("daily_hundred_like_note_ratio", "百赞笔记比例"),
    ("image_daily_exposure_median", "图文曝光中位数（日常）"),
    ("image_daily_read_median", "图文阅读中位数（日常）"),
    ("image_daily_interaction_median", "图文互动中位数（日常）"),
    ("image_daily_thousand_like_note_ratio", "图文千赞笔记比例"),
    ("image_daily_hundred_like_note_ratio", "图文百赞笔记比例"),
    ("video_daily_exposure_median", "视频曝光中位数（日常）"),
    ("video_daily_read_median", "视频阅读中位数（日常）"),
    ("video_daily_interaction_median", "视频互动中位数（日常）"),
    ("video_daily_thousand_like_note_ratio", "视频千赞笔记比例"),
    ("video_daily_hundred_like_note_ratio", "视频百赞笔记比例"),
    ("video_completion_rate", "视频完播率"),
    ("cooperation_exposure_median", "曝光中位数（合作）"),
    ("cooperation_read_median", "阅读中位数（合作）"),
    ("cooperation_interaction_median", "互动中位数（合作）"),
    ("overflow_store_median", "外溢进店中位数"),
    ("overflow_store_unit_price", "外溢进店单价"),
    ("image_cpm", "图文预估CPM价格"),
    ("image_read_unit_price", "图文预估阅读单价"),
    ("image_interaction_unit_price", "图文预估互动单价"),
    ("video_cpm", "视频预估CPM价格"),
    ("video_read_unit_price", "视频预估阅读单价"),
    ("video_interaction_unit_price", "视频预估互动单价"),
    ("reply_rate_48h", "邀约48h回复率"),
]

PGY_ROW_METRIC_FIELDS_WITH_LIVE = [
    *PGY_NON_LIVE_ROW_METRIC_FIELDS[:4],
    ("live_avg_viewers", "场均观播人数"),
    ("live_avg_sales", "场均销售额"),
    *PGY_NON_LIVE_ROW_METRIC_FIELDS[4:],
]


PGY_FILTER_ALIASES = {
    "北京/上海优先": ["北京", "上海"],
    "35岁以上优先": ["35-44岁", "35岁以上", "35-44"],
    "35岁以上≥40%": ["35-44岁", "35岁以上", "35-44"],
    "报价≤20000": ["1w-2w", "1万-2万", "2万以下", "≤2万"],
    "CPC<2/CPE<20": ["预估阅读单价", "预估互动单价"],
    "预估阅读/互动单价": ["预估阅读单价", "预估互动单价"],
}

PGY_METRIC_ALIASES = {
    "曝光中位数": ["曝光中位数（日常）", "曝光中位数"],
    "阅读中位数": ["阅读中位数（日常）", "阅读中位数"],
    "互动中位数": ["互动中位数（日常）", "互动中位数"],
    "全部报价": ["全部报价"],
}

PGY_COUNT_RANGE_OPTIONS = ["100万以上", "50万～100万", "10万～50万", "1万～10万", "0.5万～1万", "0.1万～0.5万"]
PGY_NOTE_COUNT_RANGE_OPTIONS = ["5万以上", "1万～5万", "0.5万～1万", "0.1万～0.5万"]
PGY_INTERACTION_RANGE_OPTIONS = ["2000以上", "1000～2000", "500～1000", "200～500", "100～200"]
PGY_RATE_RANGE_OPTIONS = ["40%以上", "30%～40%", "20%～30%", "10%～20%", "10%以下"]
PGY_PRICE_RANGE_OPTIONS = ["5万及以上", "1万～5万", "0.5万～1万", "0.1万～0.5万", "0.1万以下"]
PGY_UNIT_PRICE_OPTIONS = ["0.5以下", "0.5～1.0", "1.0～1.5", "1.5～2.0", "2.0以上"]
PGY_FAMILY_IDENTITY_GROUPS = [
    {"label": "家庭角色", "options": ["妈妈", "萌娃", "爸爸", "奶奶"]},
    {"label": "出镜人关系", "options": ["情侣", "夫妻", "家庭", "闺蜜", "兄弟"]},
    {"label": "母婴阶段", "options": ["备孕中", "孕期中", "0-6个月", "6-12个月", "1-3岁", "3-6岁", "6-12岁", "12岁以上"]},
]
PGY_CAREER_IDENTITY_GROUPS = [
    {"label": "传统行业", "options": ["工程师", "销售", "HR"]},
    {"label": "互联网", "options": ["主播", "运营", "产品经理", "程序员"]},
    {"label": "教育科研", "options": ["学生"]},
    {"label": "金融法律", "options": ["金融从业者"]},
    {"label": "企业创业", "options": ["创业者", "品牌创始人", "公益人"]},
    {"label": "时尚美妆", "options": ["模特", "化妆师", "造型师", "服装设计师", "珠宝设计师", "发型设计师"]},
    {"label": "食品饮料", "options": ["甜点师", "厨师", "咖啡师", "调酒师"]},
    {"label": "文化传媒", "options": ["编辑", "记者", "翻译", "作家", "娱评人", "影评人", "乐评人"]},
    {"label": "医疗健康", "options": ["营养师", "医生", "康复师"]},
    {"label": "艺术设计", "options": ["摄影师", "插画师", "室内设计师", "画家", "平面设计师", "建筑设计师", "非遗传承人", "涂鸦艺术家", "数字艺术家"]},
    {"label": "影视娱乐", "options": ["主持人", "导演", "制片人", "编剧", "经纪人", "真人秀嘉宾", "虚拟偶像", "rapper"]},
    {"label": "运动健身", "options": ["教练", "运动员", "舞蹈老师"]},
    {"label": "专业服务", "options": ["空乘", "花艺师", "整理师", "民宿主", "育婴师"]},
]
PGY_SPECIAL_BACKGROUND_GROUPS = [
    {"label": "生活背景", "options": ["留学背景", "海外华人", "铲屎官", "孕妈", "独居人群", "外国人", "混血儿"]},
    {"label": "备考经验", "options": ["考公过来人", "考研过来人", "法考过来人", "注会过来人"]},
    {"label": "兴趣爱好", "options": ["户外爱好者", "数码爱好者", "手账爱好者", "二次元人群", "汉服爱好者", "手办爱好者", "模型爱好者", "街舞爱好者", "骑行爱好者", "飞盘爱好者", "书法爱好者"]},
]
PGY_AUDIENCE_20_GROUPS = [
    {"label": "自在户外", "options": ["挑战极限者", "野趣探索家", "短逃离自愈派", "心灵远行客", "户外显眼包", "户外欢聚团"]},
    {"label": "自由畅行", "options": ["都市漫游家", "静奢新贵", "爆改浓人", "出行精算师"]},
    {"label": "运动焕活", "options": ["轻松健体派", "线条雕塑家", "寻乐运动派", "好动局内人", "自我超越者", "身心觉察师"]},
    {"label": "孕育学习", "options": ["科研育儿党", "松驰爸妈", "友伴式父母", "积进式父母", "好孕预备役", "稳孕选手"]},
    {"label": "娱乐放松", "options": ["放松乐子人", "沉浸式“戏”迷", "娱乐交友派", "真爱忠粉"]},
    {"label": "优奢享法", "options": ["奢派生活家", "悦己摘星人", "潮奢风格家", "静奢知识分子", "奢品入门人", "奢交体面人"]},
    {"label": "养身韧体", "options": ["爆肝青年", "高能青年", "娇宠彼得潘", "高消耗中年", "稳定守成中年", "探索人生的中年玩家", "熟龄悦己中年", "活力夕阳红"]},
    {"label": "虚拟人生", "options": ["审美收藏控", "高能“偷闲”客", "沉浸式畅“游”人", "竞技大神", "通关小机灵", "联结小“玩伴”", "“游”文化信徒"]},
    {"label": "美力加成", "options": ["美养佳人", "风格日抛党", "精养奢美族", "变美练习生", "气场精英", "美研尖子生"]},
    {"label": "心灵奇旅", "options": ["亲密学习父母", "恋爱修炼家", "实用信徒", "野生玄学家", "精进修心客"]},
    {"label": "文艺沉浸", "options": ["情绪捕手", "美学鉴赏家", "规律钻研党", "热门玩家", "世界狂想家"]},
    {"label": "数智未来", "options": ["效能领航员", "灵感创想客", "未来原住民", "品质感官控", "数码时髦精"]},
    {"label": "舌尖盛宴", "options": ["好味饕客", "精算稳妥人", "食饮养生族", "吃喝欢聚派", "逐潮尝新客", "拓圈商务客", "专味信徒", "“怪味”猎手", "“乐养”零食客", "囤粮“小馋猫”", "生活“增味”家", "“纵情”高压党"]},
    {"label": "看世界", "options": ["轻松舒心派", "热门追踪党", "同心群游党", "求索漫旅人", "野地探险家", "圣地巡礼者", "追爱忠粉", "山水避世客"]},
    {"label": "家有萌宠", "options": ["自然“动物学家”", "同行伙伴", "宠溺“爸妈”", "爱宠观赏派", "流浪动物保护党"]},
    {"label": "家生活", "options": ["游牧青年", "筑巢青年", "全能生活家", "居家策展人"]},
    {"label": "发现附近", "options": ["下楼享受派", "社区玩咖", "市井“街溜子”", "圈层专研人", "“速联”社交狂", "举家“撒欢”党", "城郊出走族"]},
    {"label": "成长进阶", "options": ["争渡“上岸”人", "资格证“卷王”", "进阶专业精英", "职场闯关人", "兴趣研学家", "精英培优家", "“社会人”教练", "因材施教师", "尽责陪练员"]},
    {"label": "时尚态度", "options": ["追新之乐", "弄潮先锋", "IP狂人", "街头潮客", "三坑玩家", "质感男士", "社会新鲜人", "气场大女主"]},
]
PGY_SKILLED_CONTENT_GROUPS = [
    {"label": "形式", "options": ["vlog", "探店", "测评", "ootd", "合集", "plog", "开箱", "教程", "成分解析", "彩妆试色", "仿妆", "沉浸式"]},
    {"label": "风格", "options": ["韩系", "日系", "欧美风", "氛围感", "纯欲", "甜酷", "复古", "高级感", "校园风", "中性风"]},
    {"label": "生活方式", "options": ["职场生活", "自律生活", "露营徒步", "极简主义", "低脂低卡"]},
    {"label": "肤质肤色", "options": ["油皮", "干皮", "混合肌", "敏感肌", "痘痘肌", "瑕疵皮", "白皮", "黄皮"]},
    {"label": "皮肤养护", "options": ["保湿补水", "美白", "淡斑", "祛黄", "抗氧化", "抗老", "祛皱", "抗炎", "修复", "祛痘祛闭口", "隔离防晒", "控油", "眼部护理"]},
]
PGY_CONTENT_SUBJECT_GROUPS = [
    {"label": "汽车特色", "options": ["沉浸式开车", "汽车美图"]},
    {"label": "通用", "options": ["大字报", "干货分享", "街头采访", "口播", "长文", "知识科普", "变装", "访谈", "梗图", "好物分享", "幽默搞笑", "挑战"]},
]
PGY_INDUSTRY_PORTRAIT_OPTIONS = ["家居家装", "日化家清", "多行业适用", "教育培训", "母婴", "汽车出行", "服饰鞋包", "美妆个护", "出行旅游", "珠宝配饰", "文玩娱乐", "奢侈品", "食品饮料", "到店综合", "宠物", "3C数码", "互联网", "家用电器", "运动户外", "本地生活", "行业通用人群", "家具", "家居百货", "灯饰光源", "装修设计与工程服务", "家居建材零售", "智能家居", "家装主材", "场景", "风格", "产品", "卧室兴趣人群", "餐厅兴趣人群", "客厅场景人群", "阳台兴趣用户", "厨房兴趣人群", "儿童房兴趣人群", "自我充电卧室", "多边形卧室", "高敏感卧室", "客厅兴趣人群", "浴室兴趣人群", "玄关兴趣人群", "造型卧室"]
PGY_CONSUMPTION_BEHAVIOR_GROUPS = [
    {"label": "预估车主作者", "options": ["Porsche", "ORA", "MINI", "MAZDA", "BYD", "萤火虫", "一汽红旗", "一汽奥迪", "小鹏", "五菱", "蔚来", "特斯拉", "坦克", "斯巴鲁", "上汽大众", "梅赛德斯-奔驰", "路虎", "领克", "铃木", "理想", "雷克萨斯", "兰博基尼", "捷途", "江铃福特", "极越", "极氪", "吉普", "吉利银河", "哈弗", "广汽丰田", "福特", "宾利", "宝马", "奥迪", "阿维塔"]},
]


def _extract_brands_after_labels(brief: str, labels: list[str]) -> list[str]:
    brands: list[str] = []
    stop_keywords = ["使用", "行业推荐", "推荐博主", "需要", "要求", "达人", "博主", "筛选", "人群目标", "找相似", "相似人群", "粉丝推荐"]
    for label in labels:
        for match in re.findall(rf"{label}[：: ]*([^\n。；;]{{2,120}})", brief):
            for part in re.split(r"[、,，/]+|\s+", match):
                brand = part.strip(" ：:，,、；;。")
                if not brand or any(keyword in brand for keyword in stop_keywords):
                    continue
                brands.append(brand)
    return list(dict.fromkeys(brands))

PGY_MARKETING_GOAL_GROUPS = [
    {"label": "曝光", "options": ["曝光表现", "阅读表现"]},
    {"label": "种草", "options": ["互动表现"]},
    {"label": "转化", "options": ["外溢进店表现"]},
]
PGY_MARKETING_GOAL_DEFAULT_METRIC = {
    "曝光": "曝光表现",
    "种草": "互动表现",
    "转化": "外溢进店表现",
}
PGY_MARKETING_GOAL_METRIC_PARENT = {
    metric: group["label"]
    for group in PGY_MARKETING_GOAL_GROUPS
    for metric in group["options"]
}

PGY_FILTER_CATALOG = [
    {
        "field": "营销目标",
        "control_type": "marketing_goal_metric",
        "parent_options": [group["label"] for group in PGY_MARKETING_GOAL_GROUPS],
        "option_groups": PGY_MARKETING_GOAL_GROUPS,
        "options": [value for group in PGY_MARKETING_GOAL_GROUPS for value in group["options"]],
        "notes": "先点击曝光/种草/转化父级，再在弹层内选择对应指标；低优先级筛选，不作为必备条件。",
    },
    {
        "field": "按博主粉丝推荐",
        "control_type": "brand_search_recommendation",
        "input_fields": ["brand_name_or_id", "competitor_brand_name_or_id"],
        "notes": "右上角“智能推荐博主/请选择您的合作品牌”入口；可搜索合作品牌，也可输入竞品/对标品牌，用该品牌粉丝画像推荐博主。",
    },
    {
        "field": "博主类目",
        "control_type": "tag",
        "options": [
            "美妆",
            "护肤",
            "个人护理",
            "母婴",
            "时尚",
            "美食",
            "家居家装",
            "影视综资讯",
            "运动健身",
            "宠物",
            "文化艺术",
            "兴趣爱好",
            "生活记录",
            "教育",
            "职场",
            "情感",
            "摄影",
            "游戏",
            "科技数码",
            "出行旅游",
            "音乐",
            "搞笑",
            "健康养生",
            "汽车",
            "婚嫁",
            "商业财经",
            "素材",
            "其他",
        ],
        "notes": "一层标签，可直接点击。",
    },
    {
        "field": "家庭身份",
        "control_type": "checkbox_popover",
        "option_groups": PGY_FAMILY_IDENTITY_GROUPS,
        "options": [value for group in PGY_FAMILY_IDENTITY_GROUPS for value in group["options"]],
        "notes": "打开后是多选弹层，需要点确定。",
    },
    {
        "field": "职业身份",
        "control_type": "checkbox_popover",
        "option_groups": PGY_CAREER_IDENTITY_GROUPS,
        "options": [value for group in PGY_CAREER_IDENTITY_GROUPS for value in group["options"]],
        "notes": "打开后是多选弹层，需要点确定。",
    },
    {
        "field": "特色背景",
        "control_type": "checkbox_popover",
        "option_groups": PGY_SPECIAL_BACKGROUND_GROUPS,
        "options": [value for group in PGY_SPECIAL_BACKGROUND_GROUPS for value in group["options"]],
        "notes": "打开后是多选弹层，需要点确定。",
    },
    {
        "field": "性别",
        "control_type": "dropdown_single",
        "options": ["不限", "男", "女"],
        "notes": "博主性别，打开后选择单项。",
    },
    {
        "field": "地域",
        "control_type": "three_level_cascade_checkbox_popover",
        "levels": ["国家/地区", "省/直辖市", "城市/区"],
        "options": ["中国", "美国", "日本", "澳大利亚", "英国", "加拿大", "韩国", "法国", "德国", "新加坡", "其他"],
        "notes": "中国地域需先选国家，再选省/市，再按需选城市/区；外国国家/地区可在第一列直接勾选。支持多选。",
    },
    {
        "field": "二十大人群",
        "control_type": "checkbox_popover",
        "option_groups": PGY_AUDIENCE_20_GROUPS,
        "options": [value for group in PGY_AUDIENCE_20_GROUPS for value in group["options"]],
        "notes": "页面显示为“新 二十大人群”，打开后是两列级联多选，需要点确定。",
    },
    {
        "field": "行业特色画像",
        "control_type": "checkbox_popover",
        "options": PGY_INDUSTRY_PORTRAIT_OPTIONS,
        "notes": "页面显示为“新 行业特色画像”，打开后是行业级联多选；选项会随行业列继续展开。",
    },
    {
        "field": "预估消费行为",
        "control_type": "checkbox_popover",
        "option_groups": PGY_CONSUMPTION_BEHAVIOR_GROUPS,
        "options": [value for group in PGY_CONSUMPTION_BEHAVIOR_GROUPS for value in group["options"]],
        "notes": "页面显示为“新 预估消费行为”，当前可在汽车/预估车主作者下选择品牌。",
    },
    {
        "field": "签约情况",
        "control_type": "dropdown_single",
        "options": ["不限", "个人博主", "机构博主"],
        "notes": "打开后选择博主属性。",
    },
    {
        "field": "擅长内容",
        "control_type": "checkbox_popover",
        "option_groups": PGY_SKILLED_CONTENT_GROUPS,
        "options": [value for group in PGY_SKILLED_CONTENT_GROUPS for value in group["options"]],
        "notes": "打开后是多选弹层，需要点确定。",
    },
    {
        "field": "内容题材",
        "control_type": "checkbox_popover",
        "option_groups": PGY_CONTENT_SUBJECT_GROUPS,
        "options": [value for group in PGY_CONTENT_SUBJECT_GROUPS for value in group["options"]],
        "notes": "页面显示为“新 内容题材”，当前汽车类目下包含汽车特色与通用题材。",
    },
    {
        "field": "粉丝量",
        "control_type": "preset_or_number_range",
        "options": PGY_COUNT_RANGE_OPTIONS,
        "input_fields": ["min", "max"],
        "notes": "打开后可选预设粉丝量档位，也可填写自定义最小/最大值。",
    },
    {
        "field": "粉丝年龄",
        "control_type": "dropdown",
        "options": ["<18 占比高", "18～24 占比高", "25～34 占比高", "35～44 占比高", ">44 占比高"],
        "notes": "打开后是下拉项。",
    },
    {
        "field": "粉丝性别",
        "control_type": "dropdown",
        "options": ["男性占比高", "女性占比高"],
        "notes": "打开后是下拉项。",
    },
    {
        "field": "粉丝地域",
        "control_type": "three_level_cascade_checkbox_popover",
        "levels": ["国家/地区", "省/直辖市", "城市"],
        "options": ["中国", "美国", "日本", "澳大利亚", "英国", "加拿大", "韩国", "法国", "德国", "新加坡", "其他"],
        "notes": "打开后是国家/省/城市三级级联，可多选，需要点确定。",
    },
    {
        "field": "婚恋状态",
        "control_type": "dropdown_single",
        "options": ["不限", "未婚", "已婚"],
        "notes": "打开后选择单项。",
    },
    {
        "field": "消费水平",
        "control_type": "dropdown_single",
        "options": ["不限", "低消费", "中消费", "高消费"],
        "notes": "打开后选择单项。",
    },
    {
        "field": "母婴阶段",
        "control_type": "checkbox_popover",
        "options": ["备孕", "0-6月", "7-12月", "1-3岁", "4-6岁", "7-12岁", "孕早期", "孕晚期"],
        "notes": "打开后是多选弹层，需要点确定。",
    },
    {
        "field": "手机价格",
        "control_type": "checkbox_popover",
        "options": ["0-999", "1000-1999", "2000-2999", "3000-3999", "4000-4999", "5000-5999", "6000-6999", "7000-7999", "8000+"],
        "notes": "打开后是多选弹层，需要点确定。",
    },
    {
        "field": "手机品牌",
        "control_type": "checkbox_popover",
        "options": ["苹果", "华为", "OPPO", "VIVO", "荣耀", "小米", "一加", "魅族", "中兴", "联想"],
        "notes": "打开后是多选弹层，需要点确定。",
    },
    {
        "field": "曝光中位数",
        "control_type": "preset_or_number_range",
        "options": PGY_NOTE_COUNT_RANGE_OPTIONS,
        "input_fields": ["min", "max"],
        "notes": "打开后可选预设曝光档位，也可填写自定义区间。",
    },
    {
        "field": "阅读中位数",
        "control_type": "preset_or_number_range",
        "options": PGY_NOTE_COUNT_RANGE_OPTIONS,
        "input_fields": ["min", "max"],
        "notes": "打开后可选预设阅读档位，也可填写自定义区间。",
    },
    {
        "field": "互动中位数",
        "control_type": "preset_or_number_range",
        "options": PGY_INTERACTION_RANGE_OPTIONS,
        "input_fields": ["min", "max"],
        "notes": "打开后可选预设互动档位，也可填写自定义区间。",
    },
    {
        "field": "千赞笔记比例",
        "control_type": "preset_or_percent_range",
        "options": PGY_RATE_RANGE_OPTIONS,
        "input_fields": ["min_percent", "max_percent"],
        "notes": "打开后可选预设比例，也可填写百分比区间。",
    },
    {
        "field": "笔记类型",
        "control_type": "dropdown_single",
        "options": ["不限", "图文笔记为主", "视频笔记为主"],
        "notes": "打开后选择单项。",
    },
    {
        "field": "合作报价",
        "control_type": "subfield_preset_or_number_range",
        "sub_fields": ["图文笔记", "视频笔记"],
        "options": PGY_PRICE_RANGE_OPTIONS,
        "input_fields": ["min", "max"],
        "notes": "打开后分别选择图文/视频笔记，再在子下拉中选报价档位或填自定义区间。",
    },
    {
        "field": "合作信用度",
        "control_type": "subfield_preset_or_percent_range",
        "sub_fields": ["邀约48h回复率"],
        "input_fields": ["min_percent", "max_percent"],
        "notes": "打开后选择邀约48h回复率，再选预设或填百分比区间。",
    },
    {
        "field": "合作订单数",
        "control_type": "number_range",
        "input_fields": ["min", "max"],
        "notes": "打开后填写最小/最大订单数。",
    },
    {
        "field": "近期合作行业",
        "control_type": "dropdown",
        "options": ["美妆个护", "食品饮料", "母婴", "3c及电器", "日用百货", "服装配饰", "互联网", "生活服务", "家居建材", "汽车"],
        "notes": "打开后是近期合作行业下拉项。",
    },
    {
        "field": "近期合作品牌",
        "control_type": "searchable_multi_select_with_exclude",
        "input_fields": ["brands"],
        "min_items": 3,
        "options": ["剔除上述品牌已合作博主"],
        "notes": "打开后是可搜索品牌下拉，页面提示至少选择3个品牌，可勾选剔除上述品牌已合作博主。",
    },
    {
        "field": "传播规模",
        "control_type": "multi_subfield_preset_or_number_range",
        "sub_fields": ["曝光中位数", "阅读中位数", "互动中位数", "外溢进店中位数"],
        "input_fields": ["min", "max"],
        "notes": "打开后每个子字段都有下拉档位和自定义区间。",
    },
    {
        "field": "预估CPM",
        "control_type": "subfield_preset_or_number_range",
        "sub_fields": ["预估图文CPM", "预估视频CPM"],
        "input_fields": ["min", "max"],
        "notes": "打开后分别选择图文/视频CPM，再选预设或填自定义区间。",
    },
    {
        "field": "预估阅读单价",
        "control_type": "subfield_preset_or_number_range",
        "sub_fields": ["图文笔记阅读单价", "视频笔记阅读单价"],
        "options": PGY_UNIT_PRICE_OPTIONS,
        "input_fields": ["min", "max"],
        "notes": "打开后分别选择图文/视频阅读单价，再在子下拉中选档位或填自定义区间。",
    },
    {
        "field": "预估互动单价",
        "control_type": "subfield_preset_or_number_range",
        "sub_fields": ["图文笔记互动单价", "视频笔记互动单价"],
        "options": PGY_UNIT_PRICE_OPTIONS,
        "input_fields": ["min", "max"],
        "notes": "打开后分别选择图文/视频互动单价，再在子下拉中选档位或填自定义区间。",
    },
    {
        "field": "外溢进店单价",
        "control_type": "preset_or_number_range",
        "options": ["0.5以下", "0.5～1.0", "1.0～1.5", "1.5～2.5", "2.5～4.0"],
        "input_fields": ["min", "max"],
        "notes": "打开后可选预设档位，也可填写自定义区间。",
    },
    {
        "field": "近30天直播场次",
        "control_type": "checkbox_popover",
        "options": ["0次", "1～5次", "6～10次", "10次以上"],
        "notes": "打开后是多选档位，需要点确定。",
    },
    {
        "field": "场均观播人数",
        "control_type": "checkbox_popover",
        "options": ["0~5k", "5k~1w", "1w~10w", "10w~50w", "50w以上"],
        "notes": "打开后是多选档位，需要点确定。",
    },
    {
        "field": "场均销售额",
        "control_type": "checkbox_popover",
        "options": ["5千以下", "5千～1万", "1万～10万", "10万～50万", "50万～100万", "100万～200万", "200万～500万", "500万以上"],
        "notes": "打开后是多选档位，需要点确定。",
    },
    {
        "field": "平台推荐",
        "control_type": "checkbox",
        "options": ["明星", "优质博主", "新锐博主", "笔记+直播均可合作", "意向行业匹配"],
        "notes": "一层复选框，可直接勾选。",
    },
    {
        "field": "行业推荐博主",
        "control_type": "nested_select_popover",
        "sub_fields": ["我的行业"],
        "notes": "打开后仍有“我的行业 / 请选择”的子下拉选择，需要继续选择行业后确定。",
    },
    {
        "field": "常规剔除",
        "control_type": "checkbox",
        "options": ["剔除低活博主", "剔除掉粉博主", "剔除已合作博主", "剔除已邀约博主"],
        "notes": "一层复选框，可直接勾选。",
    },
]


def _number_from_text(value: str) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"-", "--"}:
        return None
    match = re.search(r"-?\d[\d,，]*(?:\.\d+)?\s*(?:万|w|W)?", text)
    if not match:
        return None
    token = match.group(0).strip()
    multiplier = 10000 if re.search(r"(?:万|w)\s*$", token, flags=re.I) else 1
    text = re.sub(r"[^\d.\-]", "", token.replace(",", "").replace("，", ""))
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _format_filter_number(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        number = float(str(value).replace(",", "").replace("，", ""))
        return str(int(number)) if number.is_integer() else f"{number:g}"
    except Exception:
        return str(value)


def _range_numbers_from_text(value: str) -> tuple[float | None, float | None]:
    text = str(value or "")
    text = text.split("：", 1)[-1]
    parts = [part.strip() for part in re.split(r"～|~|至|到|-", text) if part.strip()]
    if len(parts) >= 2:
        return _number_from_text(parts[0]), _number_from_text(parts[1])
    if re.search(r"(?:及以上|以上)$", text.strip()):
        return _number_from_text(text), None
    if re.search(r"(?:及以下|以下)$", text.strip()):
        return None, _number_from_text(text)
    max_match = re.search(r"[≤<]\s*([0-9][0-9,，]*(?:\.\d+)?\s*(?:万|w|W)?)", text)
    if max_match:
        return None, _number_from_text(max_match.group(1))
    min_match = re.search(r"[≥>]\s*([0-9][0-9,，]*(?:\.\d+)?\s*(?:万|w|W)?)", text)
    if min_match:
        return _number_from_text(min_match.group(1)), None
    return None, None


def _split_filter_values(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;；\n]+", str(value or "")) if part.strip()]


def _subfield_names_from_item(item: dict[str, Any], default: str | list[str] = "图文笔记") -> list[str]:
    raw_values: list[Any] = []
    for key in ("sub_fields", "subFields"):
        value = item.get(key)
        if isinstance(value, list):
            raw_values.extend(value)
        elif value:
            raw_values.append(value)
    for key in ("sub_field", "subField"):
        if item.get(key):
            raw_values.append(item.get(key))
    names: list[str] = []
    for raw in raw_values:
        for part in re.split(r"[、,，/;；|]+", str(raw)):
            part = part.strip()
            if part:
                names.append(part)
    text = str(item.get("value") or "")
    if not names:
        if "图文笔记" in text:
            names.append("图文笔记")
        if "视频笔记" in text:
            names.append("视频笔记")
    if not names and default:
        if isinstance(default, list):
            names.extend(default)
        else:
            names.append(default)
    return list(dict.fromkeys(names))


def _range_for_subfield(item: dict[str, Any], sub_field: str) -> tuple[Any, Any]:
    ranges = item.get("sub_ranges") or item.get("subRanges") or {}
    if isinstance(ranges, dict):
        config = ranges.get(sub_field)
        if isinstance(config, dict):
            return config.get("min", item.get("min", "")), config.get("max", item.get("max", ""))
        if isinstance(config, (list, tuple)) and len(config) >= 2:
            return config[0], config[1]
    text = str(item.get("value") or "")
    for segment in _split_filter_values(text):
        if sub_field in segment:
            parsed_min, parsed_max = _range_numbers_from_text(segment)
            return (
                item.get("min", parsed_min if parsed_min is not None else 0),
                item.get("max", parsed_max if parsed_max is not None else ""),
            )
    parsed_min, parsed_max = _range_numbers_from_text(text)
    return (
        item.get("min", parsed_min if parsed_min is not None else 0),
        item.get("max", parsed_max if parsed_max is not None else ""),
    )


def _ratio_from_text(value: str) -> float | None:
    match = re.search(r"([0-9.]+)\s*%", value or "")
    if not match:
        return None
    try:
        return float(match.group(1)) / 100
    except ValueError:
        return None


def _label_value(lines: list[str], label: str) -> str:
    try:
        index = lines.index(label)
    except ValueError:
        prefix = next((line for line in lines if line.startswith(label)), "")
        return prefix[len(label) :].strip() if prefix else ""
    return lines[index + 1] if index + 1 < len(lines) else ""


def _metric_value_after(lines: list[str], label: str) -> float | None:
    return _number_from_text(_label_value(lines, label))


def _ratio_after_label(lines: list[str], label: str) -> float | None:
    try:
        index = lines.index(label)
    except ValueError:
        return None
    window = " ".join(lines[index + 1 : index + 4])
    return _ratio_from_text(window)


def _ratio_near_label(lines: list[str], label: str) -> float | None:
    for index, line in enumerate(lines):
        if label not in line:
            continue
        direct = _ratio_from_text(line)
        if direct is not None:
            return direct
        window = " ".join(lines[index + 1 : index + 4])
        value = _ratio_from_text(window)
        if value is not None:
            return value
    return None


def _line_between(lines: list[str], start: str, end: str) -> str:
    try:
        start_index = lines.index(start)
    except ValueError:
        return ""
    try:
        end_index = lines.index(end, start_index + 1)
    except ValueError:
        return ""
    return "".join(lines[start_index + 1 : end_index]).strip()


def _gender_ratio(lines: list[str], gender: str) -> float | None:
    for index, line in enumerate(lines):
        if gender not in line:
            continue
        window = " ".join(lines[max(0, index - 2) : index + 4])
        value = _ratio_from_text(window)
        if value is not None:
            return value
    return None


def _merge_ratio_metric(target: dict[str, Any], key: str, value: Any) -> None:
    parsed = _ratio_from_text(str(value)) if isinstance(value, str) else None
    if parsed is None:
        try:
            number = float(value)
            parsed = number / 100 if number > 1 else number
        except (TypeError, ValueError):
            parsed = None
    if parsed is not None:
        target[key] = min(max(parsed, 0), 1)


def _collect_audience_profile_chart_metrics(page: Any) -> dict[str, Any]:
    try:
        payload = page.evaluate(
            """
            () => {
              const normalize = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const ratio = value => {
                if (value === null || value === undefined || value === '') return null;
                if (typeof value === 'number') return value > 1 ? value / 100 : value;
                const match = String(value).match(/([0-9]+(?:\\.[0-9]+)?)\\s*%/);
                return match ? Number(match[1]) / 100 : null;
              };
              const keyFor = name => {
                const text = normalize(name);
                if (/(<\\s*18|18\\s*岁?以下)/.test(text)) return 'fans_under_18_ratio';
                if (/18\\s*[-~～至到]\\s*24/.test(text)) return 'fans_18_24_ratio';
                if (/25\\s*[-~～至到]\\s*34/.test(text)) return 'fans_25_34_ratio';
                if (/35\\s*[-~～至到]\\s*44/.test(text)) return 'fans_35_44_ratio';
                if (/(>\\s*44|44\\s*岁?以上|44\\+)/.test(text)) return 'fans_44_plus_ratio';
                if (/女性/.test(text)) return 'female_fans_ratio';
                if (/男性/.test(text)) return 'male_fans_ratio';
                return '';
              };
              const put = (out, name, value, source) => {
                const key = keyFor(name);
                const val = ratio(value);
                if (key && val !== null && out[key] === undefined) {
                  out[key] = val;
                  out.sources.push({ key, name: normalize(name), value, source });
                }
              };
              const walk = (node, visit, seen = new Set()) => {
                if (node === null || node === undefined || seen.has(node)) return;
                seen.add(node);
                visit(node);
                if (Array.isArray(node)) {
                  node.forEach(item => walk(item, visit, seen));
                } else if (typeof node === 'object') {
                  Object.values(node).forEach(item => walk(item, visit, seen));
                }
              };
              const collectOption = (out, option, source) => {
                walk(option, item => {
                  if (!item || typeof item !== 'object' || Array.isArray(item)) return;
                  if (item.name !== undefined && item.value !== undefined) put(out, item.name, item.value, source);
                  if (item.label !== undefined && item.value !== undefined) put(out, item.label, item.value, source);
                });
                const series = Array.isArray(option?.series) ? option.series : [];
                for (const item of series) {
                  const data = Array.isArray(item?.data) ? item.data : [];
                  const xData = Array.isArray(option?.xAxis) ? option.xAxis.flatMap(axis => axis?.data || []) : (option?.xAxis?.data || []);
                  const yData = Array.isArray(option?.yAxis) ? option.yAxis.flatMap(axis => axis?.data || []) : (option?.yAxis?.data || []);
                  const names = [...xData, ...yData];
                  data.forEach((entry, index) => {
                    if (typeof entry === 'number') put(out, names[index], entry, source);
                    if (entry && typeof entry === 'object') put(out, entry.name ?? names[index], entry.value, source);
                  });
                }
              };
              const out = { sources: [] };
              const wrappers = Array.from(document.querySelectorAll('.age-chart__wrapper, .sex-chart__wrapper'))
                .filter(el => normalize(el.innerText).includes('分布'));
              for (const wrapper of wrappers) {
                const text = normalize(wrapper.innerText);
                const isAgeWrapper = wrapper.matches('.age-chart__wrapper') || text.includes('年龄分布');
                const isGenderWrapper = wrapper.matches('.sex-chart__wrapper') || text.includes('性别分布');
                const dominant = text.match(/(<\\s*18|18\\s*岁?以下|18\\s*[-~～至到]\\s*24|25\\s*[-~～至到]\\s*34|35\\s*[-~～至到]\\s*44|>\\s*44|44\\s*岁?以上|女性|男性)\\s*居多[^0-9%]{0,12}占比\\s*([0-9]+(?:\\.[0-9]+)?)\\s*%/);
                if (dominant && isAgeWrapper) out.audience_age_dominant = { label: normalize(dominant[1]), ratio: Number(dominant[2]) / 100 };
                if (dominant && isGenderWrapper) out.audience_gender_dominant = { label: normalize(dominant[1]), ratio: Number(dominant[2]) / 100 };
                const descMatches = text.matchAll(/(<\\s*18|18\\s*岁?以下|18\\s*[-~～至到]\\s*24|25\\s*[-~～至到]\\s*34|35\\s*[-~～至到]\\s*44|>\\s*44|44\\s*岁?以上|女性|男性)[^0-9%]{0,12}占比\\s*([0-9]+(?:\\.[0-9]+)?)\\s*%/g);
                for (const match of descMatches) put(out, match[1], `${match[2]}%`, 'visible_desc');
                const chartNodes = Array.from(wrapper.querySelectorAll('[_echarts_instance_], canvas, [aria-label], [title]'));
                for (const node of chartNodes) {
                  for (const attr of ['aria-label', 'title']) {
                    const value = node.getAttribute?.(attr);
                    if (!value) continue;
                    for (const match of normalize(value).matchAll(/(<\\s*18|18\\s*岁?以下|18\\s*[-~～至到]\\s*24|25\\s*[-~～至到]\\s*34|35\\s*[-~～至到]\\s*44|>\\s*44|44\\s*岁?以上|女性|男性)[^0-9%]{0,16}([0-9]+(?:\\.[0-9]+)?)\\s*%/g)) {
                      put(out, match[1], `${match[2]}%`, attr);
                    }
                  }
                  const chartRoot = node.closest?.('[_echarts_instance_]') || (node.hasAttribute?.('_echarts_instance_') ? node : null);
                  if (chartRoot && window.echarts?.getInstanceByDom) {
                    const instance = window.echarts.getInstanceByDom(chartRoot);
                    if (instance?.getOption) collectOption(out, instance.getOption(), 'echarts_option');
                  }
                }
              }
              return out;
            }
            """
        )
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, Any] = {
        "audience_age_distribution": {
            "segments": [
                {"label": "<18", "key": "fans_under_18_ratio", "ratio": payload.get("fans_under_18_ratio")},
                {"label": "18-24", "key": "fans_18_24_ratio", "ratio": payload.get("fans_18_24_ratio")},
                {"label": "25-34", "key": "fans_25_34_ratio", "ratio": payload.get("fans_25_34_ratio")},
                {"label": "35-44", "key": "fans_35_44_ratio", "ratio": payload.get("fans_35_44_ratio")},
                {"label": ">44", "key": "fans_44_plus_ratio", "ratio": payload.get("fans_44_plus_ratio")},
            ],
            "dominant": payload.get("audience_age_dominant") or "",
            "source": "dom_echarts",
        },
        "audience_gender_distribution": {
            "segments": [
                {"label": "女性", "key": "female_fans_ratio", "ratio": payload.get("female_fans_ratio")},
                {"label": "男性", "key": "male_fans_ratio", "ratio": payload.get("male_fans_ratio")},
            ],
            "dominant": payload.get("audience_gender_dominant") or "",
            "source": "dom_echarts",
        },
        "raw_payload": {
            "audience_profile_chart_metrics": {
                "source": "dom_echarts",
                "metrics": {key: value for key, value in payload.items() if key != "sources"},
                "sources": payload.get("sources") or [],
            }
        }
    }
    for key in [
        "female_fans_ratio",
        "male_fans_ratio",
        "fans_under_18_ratio",
        "fans_18_24_ratio",
        "fans_25_34_ratio",
        "fans_35_44_ratio",
        "fans_44_plus_ratio",
    ]:
        if key in payload:
            _merge_ratio_metric(result, key, payload.get(key))
    for distribution_key in ["audience_age_distribution", "audience_gender_distribution"]:
        segments = []
        for item in result[distribution_key]["segments"]:
            parsed = _ratio_from_text(str(item.get("ratio"))) if isinstance(item.get("ratio"), str) else item.get("ratio")
            try:
                parsed = float(parsed)
            except (TypeError, ValueError):
                parsed = None
            if parsed is not None:
                parsed = parsed / 100 if parsed > 1 else parsed
                segments.append({**item, "ratio": min(max(parsed, 0), 1)})
        result[distribution_key]["segments"] = segments
    return result


def _extract_note_cases(lines: list[str]) -> list[dict[str, Any]]:
    if "笔记案例" not in lines:
        return []
    try:
        start = lines.index("仅展示跨域合作笔记") + 1
    except ValueError:
        start = lines.index("笔记案例") + 1
    try:
        end = lines.index("前往TA的小红书APP主页", start)
    except ValueError:
        end = min(len(lines), start + 120)
    cases: list[dict[str, Any]] = []
    index = start
    while index < end and len(cases) < 12:
        if index + 1 >= end:
            break
        brand = lines[index]
        title = lines[index + 1]
        if brand in {"1", "2", "3", "4"} or title in {"阅读", "点赞", "收藏", "发布时间"}:
            index += 1
            continue
        case: dict[str, Any] = {"brand": brand, "title": title}
        cursor = index + 2
        if cursor < end and lines[cursor] == "含推广流量":
            case["has_promoted_traffic"] = True
            cursor += 1
        fields = {"阅读": "read_count", "点赞": "like_count", "收藏": "save_count"}
        while cursor < end:
            current = lines[cursor]
            if current in fields and cursor + 1 < end:
                case[fields[current]] = _number_from_text(lines[cursor + 1])
                cursor += 2
                continue
            if current == "发布时间" and cursor + 1 < end:
                case["published_at"] = lines[cursor + 1]
                cursor += 2
                break
            cursor += 1
        if case.get("published_at"):
            cases.append(case)
            index = cursor
        else:
            index += 1
    return cases


def _compact_ratio(value: float) -> str:
    if value >= 10:
        return f"{value:.0f}"
    if value >= 1:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _note_interaction_count(case: dict[str, Any]) -> float | None:
    total = 0.0
    found = False
    for key in ["like_count", "save_count", "comment_count", "share_count"]:
        value = _number_from_text(str(case.get(key) or ""))
        if value is None:
            continue
        total += value
        found = True
    return total if found else None


def _case_title_key(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip().lower()


def _extract_note_case_dom_assets(page: Any) -> list[dict[str, Any]]:
    try:
        assets = page.evaluate(
            """
            () => {
              const normalize = value => String(value || '').replace(/\\s+/g, '\\n').trim();
              const inline = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const visible = el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              const absolutize = value => {
                if (!value) return '';
                try { return new URL(value, location.href).href; } catch { return value; }
              };
              const imageFor = node => {
                const img = node.querySelector('img');
                if (img?.currentSrc || img?.src) return absolutize(img.currentSrc || img.src);
                for (const el of [node, ...Array.from(node.querySelectorAll('*'))]) {
                  const style = window.getComputedStyle(el);
                  const bg = style.backgroundImage || '';
                  const match = bg.match(/url\\(["']?([^"')]+)["']?\\)/);
                  if (match?.[1]) return absolutize(match[1]);
                }
                return '';
              };
              const linkFor = node => {
                const anchors = [
                  node.closest?.('a'),
                  ...Array.from(node.querySelectorAll('a')),
                ].filter(Boolean);
                const preferred = anchors.find(anchor => /xiaohongshu\\.com\\/(?:explore|discovery|search_result|user\\/profile)/.test(anchor.href || ''))
                  || anchors.find(anchor => anchor.href && !/javascript:void|^#$/.test(anchor.getAttribute('href') || ''));
                return preferred ? absolutize(preferred.href) : '';
              };
              const wrappers = Array.from(document.querySelectorAll('.note-case-wrapper, [class*="note-case"], [class*="case-wrapper"], section, div'))
                .filter(visible)
                .filter(el => (el.innerText || '').includes('笔记案例'));
              const wrapper = wrappers.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length)[0];
              if (!wrapper) return [];
              let candidates = Array.from(wrapper.querySelectorAll('article, li, a, [class*="card"], [class*="item"], [class*="note"]'))
                .filter(visible)
                .map(node => ({ node, text: normalize(node.innerText || node.textContent || '') }))
                .filter(item => item.text.includes('阅读') && item.text.includes('点赞') && item.text.includes('收藏') && item.text.includes('发布时间'))
                .filter(item => item.text.length >= 20 && item.text.length <= 900);
              candidates = candidates.filter(item => !candidates.some(other => other.node !== item.node && item.node.contains(other.node) && other.text.length < item.text.length));
              const seen = new Set();
              return candidates.map((item, index) => {
                const lines = item.text.split('\\n').map(line => line.trim()).filter(Boolean);
                const title = lines.find((line, i) => i > 0 && !['阅读', '点赞', '收藏', '发布时间', '含推广流量'].includes(line) && !/^\\d+$/.test(line)) || '';
                const payload = {
                  index,
                  title,
                  raw_text: inline(item.text),
                  cover_url: imageFor(item.node),
                  note_url: linkFor(item.node),
                  source_url: location.href,
                };
                const key = `${payload.title}|${payload.cover_url}|${payload.note_url}|${payload.raw_text.slice(0, 80)}`;
                if (seen.has(key)) return null;
                seen.add(key);
                return payload;
              }).filter(Boolean);
            }
            """
        )
    except Exception:
        return []
    return [item for item in assets if isinstance(item, dict)]


def _merge_note_case_assets(cases: list[dict[str, Any]], assets: list[dict[str, Any]], source_url: str = "") -> list[dict[str, Any]]:
    if not cases:
        return []
    unused = list(enumerate(assets or []))
    merged: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        title_key = _case_title_key(case.get("title"))
        match_pos = next(
            (
                pos
                for pos, (_, asset) in enumerate(unused)
                if title_key
                and (
                    title_key in _case_title_key(asset.get("title") or asset.get("raw_text"))
                    or _case_title_key(asset.get("title") or asset.get("raw_text")) in title_key
                )
            ),
            None,
        )
        if match_pos is None:
            match_pos = next((pos for pos, (asset_index, _) in enumerate(unused) if asset_index == index), None)
        asset = unused.pop(match_pos)[1] if match_pos is not None else {}
        next_case = {**case}
        for source_key, target_key in [
            ("cover_url", "cover_url"),
            ("note_url", "note_url"),
            ("source_url", "source_url"),
        ]:
            if asset.get(source_key) and not next_case.get(target_key):
                next_case[target_key] = asset[source_key]
        if source_url and not next_case.get("source_url"):
            next_case["source_url"] = source_url
        merged.append(next_case)
    return merged


def _annotate_note_cases_with_traffic_reference(detail: dict[str, Any]) -> dict[str, Any]:
    raw = detail.get("raw_payload")
    if not isinstance(raw, dict):
        return detail
    read_median = detail.get("cooperation_read_median") or detail.get("daily_read_median")
    interaction_median = detail.get("cooperation_interaction_median") or detail.get("daily_interaction_median")
    reference_source = "cooperation" if detail.get("cooperation_read_median") or detail.get("cooperation_interaction_median") else "daily"
    read_median = _number_from_text(str(read_median or ""))
    interaction_median = _number_from_text(str(interaction_median or ""))
    if not read_median and not interaction_median:
        return detail

    def annotate(case: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(case, dict):
            return case
        next_case = {**case}
        comparisons: list[str] = []
        is_clear = False
        read_count = _number_from_text(str(next_case.get("read_count") or next_case.get("readCount") or ""))
        if read_count is not None and read_median:
            ratio = read_count / read_median
            next_case["read_vs_median"] = round(ratio, 3)
            comparisons.append(f"阅读为{_compact_ratio(ratio)}倍")
            is_clear = is_clear or ratio >= 1.5 or ratio <= 0.67
        interaction_count = _note_interaction_count(next_case)
        if interaction_count is not None and interaction_median:
            ratio = interaction_count / interaction_median
            next_case["interaction_count"] = interaction_count
            next_case["interaction_vs_median"] = round(ratio, 3)
            comparisons.append(f"互动为{_compact_ratio(ratio)}倍")
            is_clear = is_clear or ratio >= 1.5 or ratio <= 0.67
        if comparisons:
            next_case["traffic_median_reference"] = {
                "source": reference_source,
                "read_median": read_median,
                "interaction_median": interaction_median,
            }
            next_case["traffic_comparison"] = "，".join(comparisons)
            next_case["has_clear_median_contrast"] = is_clear
        return next_case

    for key in ["note_cases", "recent_note_cases", "recent_notes", "cooperation_note_cases", "notes"]:
        if isinstance(raw.get(key), list):
            raw[key] = [annotate(case) for case in raw[key]]
    pages = raw.get("cooperation_note_case_pages")
    if isinstance(pages, list):
        for page in pages:
            if isinstance(page, dict) and isinstance(page.get("cases"), list):
                page["cases"] = [annotate(case) for case in page["cases"]]
    detail["raw_payload"] = raw
    return detail


def _value_after_label(lines: list[str], label: str) -> str:
    try:
        index = lines.index(label)
    except ValueError:
        return ""
    stop_labels = {
        "曝光中位数",
        "阅读中位数",
        "互动中位数",
        "外溢进店中位数",
        "预估CPM",
        "预估CPM(图文)",
        "预估CPM(视频)",
        "预估阅读单价",
        "预估阅读单价(图文)",
        "预估阅读单价(视频)",
        "预估互动单价",
        "预估互动单价(图文)",
        "预估互动单价(视频)",
        "预估外溢进店单价(图文)",
        "预估外溢进店单价(视频)",
        "外溢进店单价",
        "中位点赞量",
        "中位收藏量",
        "中位评论量",
        "中位分享量",
        "中位关注量",
        "互动率",
        "视频完播率",
        "图文3秒阅读率",
        "千赞笔记比例",
        "百赞笔记比例",
    }
    unit_lines = {"元/千次曝光", "元/阅读", "元/互动", "元/进店"}
    parts: list[str] = []
    for item in lines[index + 1 : index + 4]:
        if item in stop_labels or item in {"优于", "同行", "按规模", "按成本", "日常笔记", "合作笔记", "其他指标", "核心指标"}:
            break
        if item.startswith("优于"):
            break
        parts.append(item)
        if _number_from_text(item) is not None or "%" in item or item == "-":
            if len(parts) >= 2 and item in unit_lines:
                break
            if len(parts) == 1:
                next_index = index + 2
                if next_index < len(lines) and lines[next_index] in unit_lines:
                    continue
            break
    return "".join(parts).strip()


def _metrics_from_lines(lines: list[str], labels: list[str]) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for label in labels:
        value = _value_after_label(lines, label)
        if value:
            metrics[label] = value
    return metrics


def _extract_overview_note_state(text: str) -> dict[str, Any]:
    lines = _visible_text_lines(text)
    try:
        service_index = lines.index("服务表现")
    except ValueError:
        service_index = len(lines)
    note_indexes = [index for index, line in enumerate(lines[:service_index]) if line == "笔记数据"]
    start = note_indexes[-1] if note_indexes else max(0, service_index - 40)
    block = lines[start:service_index]
    labels = [
        "曝光中位数",
        "阅读中位数",
        "互动中位数",
        "外溢进店中位数",
        "预估CPM",
        "预估CPM(图文)",
        "预估CPM(视频)",
        "预估阅读单价",
        "预估阅读单价(图文)",
        "预估阅读单价(视频)",
        "预估互动单价",
        "预估互动单价(图文)",
        "预估互动单价(视频)",
        "预估外溢进店单价(图文)",
        "预估外溢进店单价(视频)",
        "外溢进店单价",
    ]
    return {"text": "\n".join(block), "metrics": _metrics_from_lines(block, labels)}


def _extract_performance_state(text: str) -> dict[str, Any]:
    lines = _visible_text_lines(text)
    try:
        start = lines.index("数据表现")
    except ValueError:
        start = 0
    try:
        end = lines.index("粉丝分析", start + 1)
    except ValueError:
        end = min(len(lines), start + 160)
    block = lines[start:end]
    labels = [
        "曝光中位数",
        "阅读中位数",
        "互动中位数",
        "外溢进店中位数",
        "预估CPM",
        "预估阅读单价",
        "预估互动单价",
        "预估外溢进店单价(图文)",
        "预估外溢进店单价(视频)",
        "外溢进店单价",
        "中位点赞量",
        "中位收藏量",
        "中位评论量",
        "中位分享量",
        "中位关注量",
        "互动率",
        "视频完播率",
        "图文3秒阅读率",
        "千赞笔记比例",
        "百赞笔记比例",
    ]
    return {"text": "\n".join(block), "metrics": _metrics_from_lines(block, labels)}


def _body_text(page: Any, timeout: int = 5000) -> str:
    try:
        return page.locator("body").inner_text(timeout=timeout)
    except Exception:
        return ""


def _container_text(page: Any, selector: str, contains: list[str] | None = None, occurrence: str = "first") -> str:
    try:
        return page.evaluate(
            """
            ({ selector, contains, occurrence }) => {
              const normalized = value => String(value || '').replace(/\\s+/g, '\\n').trim();
              const isVisibleEnough = el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
              };
              const items = Array.from(document.querySelectorAll(selector))
                .filter(isVisibleEnough)
                .filter(el => {
                  const text = el.innerText || '';
                  return (contains || []).every(item => text.includes(item));
                })
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.left - br.left;
                });
              const target = occurrence === 'last' ? items[items.length - 1] : items[0];
              return target ? normalized(target.innerText || target.textContent || '') : '';
            }
            """,
            {"selector": selector, "contains": contains or [], "occurrence": occurrence},
        )
    except Exception:
        return ""


def _scroll_container(page: Any, selector: str, contains: list[str] | None = None, occurrence: str = "first") -> bool:
    try:
        scrolled = page.evaluate(
            """
            ({ selector, contains, occurrence }) => {
              const items = Array.from(document.querySelectorAll(selector))
                .filter(el => {
                  const rect = el.getBoundingClientRect();
                  const style = window.getComputedStyle(el);
                  const text = el.innerText || '';
                  return rect.width > 0 && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && (contains || []).every(item => text.includes(item));
                })
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.left - br.left;
                });
              const target = occurrence === 'last' ? items[items.length - 1] : items[0];
              if (!target) return false;
              target.scrollIntoView({ block: 'center', inline: 'nearest' });
              return true;
            }
            """,
            {"selector": selector, "contains": contains or [], "occurrence": occurrence},
        )
        if scrolled:
            page.wait_for_timeout(700)
            return True
    except Exception:
        pass
    return False


def _click_in_container(
    page: Any,
    container_selector: str,
    label: str,
    contains: list[str] | None = None,
    container_occurrence: str = "first",
    target_occurrence: str = "first",
) -> bool:
    _scroll_container(page, container_selector, contains, container_occurrence)
    try:
        box = page.evaluate(
            """
            ({ containerSelector, label, contains, containerOccurrence, targetOccurrence }) => {
              const normalized = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const visible = el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                  && style.display !== 'none'
                  && style.visibility !== 'hidden'
                  && rect.bottom >= 0
                  && rect.top <= window.innerHeight;
              };
              const containers = Array.from(document.querySelectorAll(containerSelector))
                .filter(el => {
                  const rect = el.getBoundingClientRect();
                  const style = window.getComputedStyle(el);
                  const text = el.innerText || '';
                  return rect.width > 0 && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && (contains || []).every(item => text.includes(item));
                })
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.left - br.left;
                });
              const container = containerOccurrence === 'last' ? containers[containers.length - 1] : containers[0];
              if (!container) return false;
              const selector = [
                'button',
                '[role="button"]',
                '[role="tab"]',
                '.d-tabs-header',
                '.d-radio-button',
                '.d-segment-item',
                '.d-segmented-item',
                '.d-pagination-page',
                'label',
                'span',
                'div'
              ].join(',');
              const targets = Array.from(container.querySelectorAll(selector))
                .filter(visible)
                .filter(el => normalized(el.innerText || el.textContent) === label)
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.left - br.left;
                });
              let target = targetOccurrence === 'last' ? targets[targets.length - 1] : targets[0];
              if (!target) return false;
              target = target.closest('button,[role="button"],[role="tab"],.d-tabs-header,.d-radio-button,.d-segment-item,.d-segmented-item,.d-pagination-page,label') || target;
              const rect = target.getBoundingClientRect();
              return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
            }
            """,
            {
                "containerSelector": container_selector,
                "label": label,
                "contains": contains or [],
                "containerOccurrence": container_occurrence,
                "targetOccurrence": target_occurrence,
            },
        )
        if box and isinstance(box, dict):
            page.mouse.click(float(box["x"]), float(box["y"]))
            page.wait_for_timeout(1000)
            return True
    except Exception:
        pass
    return False


def _scroll_to_visible_text(page: Any, label: str, occurrence: str = "first") -> bool:
    try:
        locator = page.locator(f"text={label}")
        count = locator.count()
        if not count:
            return False
        target = locator.last if occurrence == "last" else locator.first
        target.scroll_into_view_if_needed(timeout=3000)
        page.wait_for_timeout(600)
        return True
    except Exception:
        return False


def _click_visible_text(page: Any, label: str, occurrence: str = "first", viewport_only: bool = True) -> bool:
    try:
        clicked = page.evaluate(
            """
            ({ label, occurrence, viewportOnly }) => {
              const normalized = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const isVisible = el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (!rect.width || !rect.height) return false;
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                if (!viewportOnly) return true;
                return rect.bottom >= 0 && rect.top <= window.innerHeight && rect.right >= 0 && rect.left <= window.innerWidth;
              };
              const selector = [
                'button',
                '[role="button"]',
                '[role="tab"]',
                '.d-tabs-tab',
                '.d-radio-button',
                '.d-segmented-item',
                '.d-dropdown-menu-item',
                '.d-select-option',
                '.d-pagination-page',
                'label',
                'span',
                'div'
              ].join(',');
              const candidates = Array.from(document.querySelectorAll(selector))
                .filter(isVisible)
                .filter(el => normalized(el.innerText || el.textContent) === label)
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.left - br.left;
                });
              if (!candidates.length) return false;
              const target = occurrence === 'last' ? candidates[candidates.length - 1] : candidates[0];
              target.click();
              return true;
            }
            """,
            {"label": label, "occurrence": occurrence, "viewportOnly": viewport_only},
        )
        if clicked:
            page.wait_for_timeout(900)
            return True
    except Exception:
        pass
    try:
        locator = page.locator(f"text={label}")
        target = locator.last if occurrence == "last" else locator.first
        target.click(timeout=2000)
        page.wait_for_timeout(900)
        return True
    except Exception:
        return False


def _click_detail_tab(page: Any, section_label: str, tab_label: str, section_occurrence: str = "first", tab_occurrence: str = "first") -> bool:
    _scroll_to_visible_text(page, section_label, section_occurrence)
    return _click_visible_text(page, tab_label, tab_occurrence, viewport_only=True)


def _click_note_case_page(page: Any, page_no: int) -> bool:
    _scroll_container(page, ".note-case-wrapper", ["笔记案例"], "first")
    try:
        clicked = page.evaluate(
            """
            pageNo => {
              const normalized = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const isVisible = el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                  && style.display !== 'none'
                  && style.visibility !== 'hidden'
                  && rect.bottom >= 0
                  && rect.top <= window.innerHeight;
              };
              const pages = Array.from(document.querySelectorAll('.d-pagination-page'))
                .filter(isVisible)
                .filter(el => normalized(el.innerText || el.textContent).split(' ')[0] === String(pageNo))
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.left - br.left;
                });
              const target = pages[pages.length - 1];
              if (!target) return false;
              target.click();
              return true;
            }
            """,
            page_no,
        )
        if clicked:
            page.wait_for_timeout(1400)
            return True
    except Exception:
        pass
    return False


def _case_key(case: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(case.get("brand") or "").strip(),
        str(case.get("title") or "").strip(),
        str(case.get("published_at") or "").strip(),
    )


def _collect_note_case_pages(page: Any, max_cases: int = 24) -> dict[str, Any]:
    _click_in_container(page, ".note-case-wrapper", "合作笔记", contains=["笔记案例"], target_occurrence="first")
    collected: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for page_no in range(1, 4):
        if page_no > 1:
            if not _click_note_case_page(page, page_no):
                break
        text = _container_text(page, ".note-case-wrapper", ["笔记案例"], "first") or _body_text(page)
        lines = _visible_text_lines(text)
        cases = _merge_note_case_assets(_extract_note_cases(lines), _extract_note_case_dom_assets(page), page.url)
        pages.append({"page": page_no, "count": len(cases), "cases": cases})
        before = len(collected)
        for case in cases:
            key = _case_key(case)
            if key in seen:
                continue
            seen.add(key)
            collected.append(case)
            if len(collected) >= max_cases:
                break
        if len(collected) >= max_cases:
            break
        if page_no > 1 and len(collected) == before:
            break
    return {"cooperation_note_cases": collected, "cooperation_note_case_pages": pages}


def _collect_overview_note_states(page: Any) -> dict[str, Any]:
    states: dict[str, Any] = {}
    selector = ".detail-item"
    contains = ["笔记数据", "按规模", "按成本"]
    for note_type in ["日常笔记", "合作笔记"]:
        _click_in_container(page, selector, "按规模", contains=contains, target_occurrence="first")
        if not _click_in_container(page, selector, note_type, contains=contains, target_occurrence="first"):
            _scroll_container(page, selector, contains, "first")
            _click_visible_text(page, note_type, "first", viewport_only=True)
        for mode in ["按规模", "按成本"]:
            if not _click_in_container(page, selector, mode, contains=contains, target_occurrence="first"):
                _scroll_container(page, selector, contains, "first")
                _click_visible_text(page, mode, "first", viewport_only=True)
            text = _container_text(page, selector, contains, "first") or _body_text(page)
            key = "daily" if note_type == "日常笔记" else "cooperation"
            mode_key = "scale" if mode == "按规模" else "cost"
            states.setdefault(key, {})[mode_key] = _extract_overview_note_state(text)
    return states


def _collect_performance_states(page: Any) -> dict[str, Any]:
    states: dict[str, Any] = {}
    selector = ".trans-data-wrapper"
    contains = ["数据表现", "日常笔记", "合作笔记"]
    _scroll_to_visible_text(page, "数据表现", "last")
    _click_visible_text(page, "合作笔记", "last", viewport_only=True)
    for mode in ["按规模", "按成本"]:
        _scroll_to_visible_text(page, "数据表现", "last")
        _click_visible_text(page, mode, "last", viewport_only=True)
        text = _container_text(page, selector, contains, "first") or _body_text(page)
        states.setdefault("cooperation", {})["scale" if mode == "按规模" else "cost"] = _extract_performance_state(text)
    return states


def _collect_detail_interaction_states(page: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    try:
        raw["overview_note_data"] = _collect_overview_note_states(page)
    except Exception as exc:
        raw["overview_note_data_error"] = str(exc)
    try:
        raw.update(_collect_note_case_pages(page))
    except Exception as exc:
        raw["cooperation_note_cases_error"] = str(exc)
    try:
        raw["data_performance"] = _collect_performance_states(page)
    except Exception as exc:
        raw["data_performance_error"] = str(exc)
    result: dict[str, Any] = {"raw_payload": raw}
    scale_metrics = (
        raw.get("data_performance", {})
        .get("cooperation", {})
        .get("scale", {})
        .get("metrics", {})
        if isinstance(raw.get("data_performance"), dict)
        else {}
    )
    cost_metrics = (
        raw.get("data_performance", {})
        .get("cooperation", {})
        .get("cost", {})
        .get("metrics", {})
        if isinstance(raw.get("data_performance"), dict)
        else {}
    )
    field_map = {
        "cooperation_exposure_median": scale_metrics.get("曝光中位数"),
        "cooperation_read_median": scale_metrics.get("阅读中位数"),
        "cooperation_interaction_median": scale_metrics.get("互动中位数"),
        "overflow_store_median": scale_metrics.get("外溢进店中位数"),
        "overflow_store_unit_price": cost_metrics.get("外溢进店单价"),
    }
    result.update({key: value for key, value in field_map.items() if value not in ("", None)})
    return result


def _safe_filename(value: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", str(value or "").strip(), flags=re.U)
    return text.strip("._")[:80] or "unknown"


def _normalize_export_header(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("\ufeff", "")).strip()


def _export_value(row: dict[str, Any], aliases: list[str]) -> Any:
    normalized = {_normalize_export_header(key): value for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(_normalize_export_header(alias))
        if value not in (None, ""):
            return value
    return None


def _read_export_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw = path.read_bytes()
        for encoding in ["utf-8-sig", "gb18030", "utf-16"]:
            try:
                text = raw.decode(encoding)
                return [dict(row) for row in csv.DictReader(text.splitlines())]
            except Exception:
                continue
        return []
    if suffix in {".xlsx", ".xls"}:
        try:
            from openpyxl import load_workbook
        except ImportError:
            return []
        workbook = load_workbook(path, read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(value or "").strip() for value in rows[0]]
        return [
            {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
            for row in rows[1:]
            if any(value not in (None, "") for value in row)
        ]
    return []


def _normalize_export_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {"source": "pgy", "raw_payload": {"export_row": row}}
    for field, aliases in PGY_EXPORT_FIELD_ALIASES.items():
        value = _export_value(row, aliases)
        if value not in (None, ""):
            normalized[field] = value
    if not normalized.get("creator_id"):
        seed = "|".join(
            str(normalized.get(key) or "")
            for key in ["xiaohongshu_id", "pgy_url", "nickname", "followers_count", "quote_price"]
        )
        if seed.strip("|"):
            normalized["creator_id"] = f"pgy-export:{seed}"
    return normalized


def parse_export_file(path: str | Path) -> dict[str, Any]:
    export_path = Path(path)
    if not export_path.exists():
        return {"status": "failed", "message": "导出文件不存在", "path": str(export_path), "creators": []}
    rows = _read_export_rows(export_path)
    creators = [_normalize_export_row(row) for row in rows]
    creators = [creator for creator in creators if creator.get("nickname") or creator.get("pgy_url") or creator.get("xiaohongshu_id")]
    return {
        "status": "parsed",
        "message": f"已解析导出文件 {len(creators)} 行",
        "path": str(export_path),
        "row_count": len(rows),
        "creators": creators,
    }


def _merge_filters(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for group in groups:
        for item in group or []:
            field = str(item.get("field") or "")
            value = str(item.get("value") or "")
            sub_field = str(item.get("sub_field") or item.get("subField") or "")
            if not field or not value:
                continue
            key = (field, value, sub_field)
            if key in seen:
                continue
            seen.add(key)
            merged.append({**item, "field": field, "value": value, "reason": str(item.get("reason") or "")})
    return merged


def _brief_emphasizes_region(text: str) -> bool:
    normalized = _clean_text(text).lower()
    if not any(keyword in normalized for keyword in ["地域", "地区", "城市", "ip", "北京", "上海", "一线", "省份"]):
        return False
    emphasis_keywords = [
        "地域要求",
        "地区要求",
        "城市要求",
        "ip要求",
        "地域优先",
        "地区优先",
        "城市优先",
        "ip优先",
        "优先北京",
        "优先上海",
        "北京优先",
        "上海优先",
        "重点城市",
        "核心城市",
        "指定城市",
        "必须",
        "限定",
        "限制",
        "只要",
        "仅限",
        "重点覆盖",
        "地域强调",
        "地区强调",
        "本地",
        "同城",
    ]
    return any(keyword in normalized for keyword in emphasis_keywords)


def _hard_filters_to_pgy_filters(hard_filters: list[dict[str, Any]]) -> list[dict[str, str]]:
    filters: list[dict[str, str]] = []

    def add(field: str, value: str, reason: str, **extra: Any) -> None:
        filters.append({"field": field, "value": value, "reason": reason, **{key: val for key, val in extra.items() if val not in (None, "", [])}})

    def add_marketing_goal(value: str, reason: str) -> None:
        parent = str(value or "").strip()
        metric = PGY_MARKETING_GOAL_DEFAULT_METRIC.get(parent) or parent
        parent = PGY_MARKETING_GOAL_METRIC_PARENT.get(metric) or parent
        if not parent or not metric:
            return
        add(
            "营销目标",
            metric,
            reason,
            control_type="marketing_goal_metric",
            goal=parent,
            parent_value=parent,
            priority="low",
        )

    for item in hard_filters or []:
        if item.get("required") is False:
            continue
        field = str(item.get("field") or item.get("standard") or "")
        value = str(item.get("value") or "")
        pgy_field = str(item.get("pgyField") or "")
        text = f"{field} {pgy_field} {value}".lower()
        reason = f"硬性条件：{field}{item.get('condition') or ''}{value}"
        value_control = str(item.get("valueControl") or "")
        sub_field = str(item.get("subField") or "")
        if pgy_field == "营销目标" and value:
            for part in [part.strip() for part in re.split(r"[、,，/]+", value) if part.strip()]:
                add_marketing_goal(part, reason)
            continue
        if pgy_field in {"博主类目", "粉丝量", "粉丝年龄", "家庭身份", "职业身份", "特色背景", "母婴阶段", "地域", "粉丝地域"} and value:
            if pgy_field == "粉丝年龄":
                age_values = []
                if any(keyword in value for keyword in ["35", "34", "40", "家长", "父母", ">44", "44岁以上"]):
                    age_values.append("35～44 占比高")
                    if ">44" in value or "44岁以上" in value or "35岁以上" in value:
                        age_values.append(">44 占比高")
                for age_value in age_values or [value]:
                    add(pgy_field, age_value, reason, control_type="dropdown")
                continue
            if pgy_field == "粉丝量" and "、" in value:
                for part in [part.strip() for part in re.split(r"[、,，/]+", value) if part.strip()]:
                    add(pgy_field, part, reason, control_type="preset_or_number_range")
                continue
            add(pgy_field, value, reason, control_type=value_control or "checkbox_popover")
            continue
        if pgy_field in {"合作报价", "预估阅读单价", "预估互动单价", "阅读中位数", "互动中位数", "曝光中位数"} and value:
            if pgy_field == "合作报价":
                parsed_min, parsed_max = _range_numbers_from_text(value)
                min_quote = item.get("min", parsed_min if parsed_min is not None else 1000)
                max_quote = item.get("max", parsed_max if parsed_max is not None else (_threshold_from_text(value, "quote", 20000) or 20000))
                next_sub_field = sub_field or ("视频笔记" if "视频笔记" in value else "图文笔记")
                display_value = value if next_sub_field in value else f"{next_sub_field}：{value}"
                add(pgy_field, display_value, reason, control_type="subfield_preset_or_number_range", sub_field=next_sub_field, min=min_quote, max=max_quote)
                continue
            if pgy_field == "预估阅读单价":
                cpc_max = _threshold_from_text(value, "cpc", 2) or _threshold_from_text(value, "generic", 2) or 2
                add(pgy_field, f"{sub_field or '图文笔记阅读单价'}≤{cpc_max:g}", reason, control_type="subfield_preset_or_number_range", sub_field=sub_field or "图文笔记阅读单价", max=cpc_max)
                continue
            if pgy_field == "预估互动单价":
                cpe_max = _threshold_from_text(value, "cpe", 20) or _threshold_from_text(value, "generic", 20) or 20
                add(pgy_field, f"{sub_field or '图文笔记互动单价'}≤{cpe_max:g}", reason, control_type="subfield_preset_or_number_range", sub_field=sub_field or "图文笔记互动单价", max=cpe_max)
                continue
            add(pgy_field, value, reason, control_type="subfield_preset_or_number_range", sub_field=sub_field or "图文笔记")
            continue
        if any(keyword in text for keyword in ["报价", "预算", "合作价格", "平台价格"]):
            max_quote = _threshold_from_text(value, "quote", 20000) or 20000
            add("合作报价", f"图文笔记：0.1万～{max_quote / 10000:g}万", reason, control_type="subfield_preset_or_number_range", sub_field="图文笔记", min=1000, max=max_quote)
        if any(keyword in text for keyword in ["35", "34", "粉丝年龄", "宝妈", "家长"]):
            add("粉丝年龄", "35～44 占比高", reason, control_type="dropdown")
        if any(keyword in text for keyword in ["cpc", "cpe", "阅读单价", "互动单价"]):
            cpc_max = _threshold_from_text(value, "cpc", 2) or 2
            cpe_max = _threshold_from_text(value, "cpe", 20) or 20
            add("预估阅读单价", f"图文笔记阅读单价≤{cpc_max:g}", reason, control_type="subfield_preset_or_number_range", sub_field="图文笔记阅读单价", max=cpc_max)
            add("预估互动单价", f"图文笔记互动单价≤{cpe_max:g}", reason, control_type="subfield_preset_or_number_range", sub_field="图文笔记互动单价", max=cpe_max)
        if any(keyword in text for keyword in ["孩子年级", "小升初", "初中", "高中", "大孩"]):
            add("内容场景", "小升初/初中/高中", reason)
        if _brief_emphasizes_region(f"{field} {value}"):
            add("地域", value or "北京/上海优先", reason, control_type="three_level_cascade_checkbox_popover")
        if any(keyword in text for keyword in ["限流", "违规", "流量稳定", "异常"]):
            add("常规剔除", "剔除低活博主", reason, control_type="checkbox")
            add("常规剔除", "剔除掉粉博主", reason, control_type="checkbox")
    return _merge_filters(filters)


def _normalize_pgy_filter_item(item: dict[str, Any]) -> dict[str, Any]:
    field = str(item.get("field") or "")
    value = str(item.get("value") or "")
    normalized = {**item, "field": field, "value": value, "reason": str(item.get("reason") or "")}
    if field == "营销目标":
        parent = str(item.get("goal") or item.get("parent_value") or item.get("parentValue") or "").strip()
        metric = value.strip()
        if metric in PGY_MARKETING_GOAL_DEFAULT_METRIC:
            parent = metric
            metric = PGY_MARKETING_GOAL_DEFAULT_METRIC.get(parent) or metric
        if not parent:
            parent = PGY_MARKETING_GOAL_METRIC_PARENT.get(metric) or ""
        return {
            **normalized,
            "value": metric,
            "control_type": "marketing_goal_metric",
            "goal": parent,
            "parent_value": parent,
            "priority": normalized.get("priority") or "low",
        }
    if field == "博主人设":
        mapping = {
            "家庭身份": {"field": "家庭身份", "value": "妈妈", "control_type": "checkbox_popover"},
            "职业身份": {"field": "职业身份", "value": "教育科研", "control_type": "checkbox_popover"},
            "特色背景": {"field": "特色背景", "value": "备考经验", "control_type": "checkbox_popover"},
        }
        return {**normalized, **mapping.get(value, {})}
    if field == "数据表现" and value in {"预估阅读/互动单价", "CPC<2/CPE<20"}:
        return {
            **normalized,
            "field": "预估阅读单价",
            "value": "图文笔记阅读单价≤2",
            "control_type": "subfield_preset_or_number_range",
            "sub_field": "图文笔记阅读单价",
            "max": 2,
            "pending_detail": "预估互动单价需作为独立条件补充",
        }
    if field == "报价":
        return {**normalized, "field": "合作报价", "value": "0.1万～2万", "control_type": "subfield_preset_or_number_range", "sub_field": "", "sub_fields": ["图文笔记", "视频笔记"], "min": 1000, "max": 20000}
    if field == "合作报价":
        parsed_min, parsed_max = _range_numbers_from_text(value)
        sub_names = _subfield_names_from_item(normalized, default=["图文笔记", "视频笔记"])
        sub_field = sub_names[0] if len(sub_names) == 1 else ""
        has_explicit_min = normalized.get("min") not in (None, "")
        has_explicit_max = normalized.get("max") not in (None, "")
        min_value = normalized.get("min") if has_explicit_min else parsed_min
        max_value = normalized.get("max") if has_explicit_max else parsed_max
        if min_value is None and max_value is None:
            min_value, max_value = 1000, 20000
        elif min_value is None:
            min_value = ""
        elif max_value is None:
            max_value = ""
        return {
            **normalized,
            "control_type": normalized.get("control_type") or "subfield_preset_or_number_range",
            "sub_field": sub_field,
            "sub_fields": sub_names,
            "min": min_value,
            "max": max_value,
        }
    if field == "粉丝年龄" and value in {"35岁以上优先", "35岁以上≥40%"}:
        return {**normalized, "value": "35～44 占比高", "control_type": "dropdown"}
    if field == "粉丝量":
        return {**normalized, "control_type": normalized.get("control_type") or "preset_or_number_range"}
    if field == "粉丝年龄":
        return {**normalized, "control_type": normalized.get("control_type") or "dropdown"}
    if field == "地域" and "优先" in value:
        return {**normalized, "control_type": "three_level_cascade_checkbox_popover"}
    if field == "常规剔除" and value in {"低风险/流量稳定", "规避限流异常", "流量稳定"}:
        return {**normalized, "value": "剔除低活博主", "control_type": "checkbox"}
    return normalized


def _normalize_pgy_filters(filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in filters or []:
        current = _normalize_pgy_filter_item(item)
        normalized.append(current)
        original_field = str(item.get("field") or "")
        original_value = str(item.get("value") or "")
        if original_field == "数据表现" and original_value in {"预估阅读/互动单价", "CPC<2/CPE<20"}:
            normalized.append(
                {
                    "field": "预估互动单价",
                    "value": "图文笔记互动单价≤20",
                    "reason": str(item.get("reason") or ""),
                    "control_type": "subfield_preset_or_number_range",
                    "sub_field": "图文笔记互动单价",
                    "max": 20,
                }
            )
        if original_field == "常规剔除" and original_value in {"低风险/流量稳定", "规避限流异常", "流量稳定"}:
            normalized.append(
                {
                    "field": "常规剔除",
                    "value": "剔除掉粉博主",
                    "reason": str(item.get("reason") or ""),
                    "control_type": "checkbox",
                }
            )
    return _merge_filters(normalized)


def build_collection_plan(brief: str = "", screening_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(screening_plan, dict) and isinstance(screening_plan.get("pgyCollectionPlan"), dict):
        plan = screening_plan["pgyCollectionPlan"]
        hard_filters = screening_plan.get("collectionHardFilters") or plan.get("hard_filters") or screening_plan.get("hardFilters") or []
        schemes = plan.get("schemes") or []
        default_filters = plan.get("filters") or []
        if not default_filters and schemes and isinstance(schemes[0], dict):
            default_filters = schemes[0].get("filters") or []
        active_scheme = bool(plan.get("active_scheme_id"))
        derived_filters = [] if active_scheme else _hard_filters_to_pgy_filters(hard_filters)
        metrics = plan.get("display_metrics") or PGY_DISPLAY_METRICS
        if PGY_ALL_NON_LIVE_METRICS not in metrics:
            metrics = [PGY_ALL_NON_LIVE_METRICS]
        return {
            "strategy": plan.get("strategy") or "",
            "target_count_range": plan.get("target_count_range") or "",
            "schemes": schemes,
            "filters": _normalize_pgy_filters(_merge_filters(derived_filters, default_filters)),
            "hard_filters": hard_filters,
            "display_metrics": metrics,
            "detail_fields": plan.get("detail_fields") or ["基础画像", "粉丝画像", "报价", "合作表现", "内容表现"],
            "filter_catalog": plan.get("filter_catalog") or PGY_FILTER_CATALOG,
        }

    text = f"{brief} {screening_plan or ''}".lower()
    filters: list[dict[str, str]] = []

    def add(field: str, value: str, reason: str, **extra: Any) -> None:
        if not any(item["field"] == field and item["value"] == value for item in filters):
            filters.append({"field": field, "value": value, "reason": reason, **{key: val for key, val in extra.items() if val not in (None, "", [])}})

    if any(keyword in text for keyword in ["曝光", "声量", "阅读", "播放"]):
        add("营销目标", "曝光表现", "Brief 提到曝光/声量目标", control_type="marketing_goal_metric", goal="曝光", parent_value="曝光", priority="low")
    if any(keyword in text for keyword in ["种草", "口碑", "测评", "内容"]):
        add("营销目标", "互动表现", "Brief 提到种草或内容测评", control_type="marketing_goal_metric", goal="种草", parent_value="种草", priority="low")
    if any(keyword in text for keyword in ["转化", "销售", "进店", "下单"]):
        add("营销目标", "外溢进店表现", "Brief 提到转化目标", control_type="marketing_goal_metric", goal="转化", parent_value="转化", priority="low")

    category_map = [
        ("教育", ["教育", "学习", "升学", "初中", "高中", "答疑", "教辅", "老师"]),
        ("母婴", ["母婴", "亲子", "妈妈", "孩子", "儿童", "大孩"]),
        ("家居家装", ["家居", "家装", "装修"]),
        ("科技数码", ["数码", "智能", "硬件", "电子"]),
    ]
    for category, keywords in category_map:
        if any(keyword in text for keyword in keywords):
            add("博主类目", category, f"Brief 命中 {category} 场景")

    persona_map = [
        ("家庭身份", ["家庭", "亲子", "妈妈", "爸爸", "孩子"]),
        ("职业身份", ["老师", "教师", "专家", "医生", "博士"]),
        ("特色背景", ["高知", "中产", "精英", "升学"]),
    ]
    for field, keywords in persona_map:
        if any(keyword in text for keyword in keywords):
            add("博主人设", field, f"Brief 命中 {field} 画像")
    if any(keyword in text for keyword in ["妈妈", "宝妈", "母亲", "亲子", "萌娃", "爸爸", "父母"]):
        add("家庭身份", "妈妈", "Brief 命中家庭/亲子身份", control_type="checkbox_popover")
    if any(keyword in text for keyword in ["老师", "教师", "专家", "医生", "博士", "教育科研"]):
        add("职业身份", "教育科研", "Brief 命中教育科研/专家职业身份", control_type="checkbox_popover")
    if any(keyword in text for keyword in ["高知", "升学", "备考", "留学", "考研"]):
        add("特色背景", "备考经验", "Brief 命中特色背景", control_type="checkbox_popover")

    if _brief_emphasizes_region(brief):
        add("地域", "北京/上海优先", "Brief 明确强调地域/IP/城市要求", control_type="three_level_cascade_checkbox_popover")
    if any(keyword in text for keyword in ["35岁", "35 岁", "34岁", "家长", "父母"]):
        add("粉丝年龄", "35～44 占比高", "Brief 要求家长/35岁以上粉丝", control_type="dropdown")
    if any(keyword in text for keyword in ["cpe", "cpc", "阅读单价", "互动单价"]):
        add("预估阅读单价", "图文笔记阅读单价≤2", "Brief 要求控制 CPC", control_type="subfield_preset_or_number_range", sub_field="图文笔记阅读单价", max=2)
        add("预估互动单价", "图文笔记互动单价≤20", "Brief 要求控制 CPE", control_type="subfield_preset_or_number_range", sub_field="图文笔记互动单价", max=20)
    cooperation_brands = _extract_brands_after_labels(brief, ["近期合作品牌", "合作品牌", "已合作品牌"])
    competitor_brands = _extract_brands_after_labels(brief, ["竞品", "竞品品牌", "对标品牌", "类似品牌", "参考品牌"])
    recommendation_brands = _extract_brands_after_labels(brief, ["按博主粉丝推荐", "人群目标品牌", "目标品牌", "合作品牌", "竞品", "对标品牌", "类似品牌", "参考品牌"])
    if cooperation_brands or competitor_brands:
        brands = list(dict.fromkeys([*cooperation_brands, *competitor_brands]))
        add(
            "近期合作品牌",
            "、".join(brands[:6]) or "待补品牌",
            "Brief 提到近期合作品牌/竞品，需要记录品牌并可剔除已合作博主",
            control_type="searchable_multi_select_with_exclude",
            input_values=brands[:6],
            min_items=3,
            pending_detail="至少补足3个品牌",
        )
    if recommendation_brands or any(keyword in text for keyword in ["按博主粉丝推荐", "人群目标", "竞品粉丝", "品牌粉丝", "对标品牌"]):
        brands = recommendation_brands[:6]
        add(
            "按博主粉丝推荐",
            "、".join(brands) or "待选择合作品牌/竞品",
            "Brief 提到品牌/竞品粉丝人群，可通过右上角智能推荐博主入口搜索品牌或竞品",
            control_type="brand_search_recommendation",
            input_values=brands,
            competitor_values=competitor_brands[:6],
            pending_detail="在右上角合作品牌搜索框输入品牌名或ID；竞品也可作为搜索品牌输入",
        )
    if any(keyword in text for keyword in ["行业推荐", "推荐博主", "意向行业"]):
        add("行业推荐博主", "我的行业", "Brief 提到行业推荐/行业匹配", control_type="nested_select_popover", pending_detail="打开后继续选择我的行业")

    return {
        "filters": _merge_filters(_hard_filters_to_pgy_filters((screening_plan or {}).get("collectionHardFilters") or (screening_plan or {}).get("hardFilters") or []), filters),
        "hard_filters": (screening_plan or {}).get("collectionHardFilters") or (screening_plan or {}).get("hardFilters") or [],
        "display_metrics": PGY_DISPLAY_METRICS,
        "detail_fields": ["基础画像", "粉丝画像", "报价", "合作表现", "内容表现"],
        "filter_catalog": PGY_FILTER_CATALOG,
    }


PGY_EMPTY_RESULT_HINTS = [
    "暂未找到相关博主",
    "暂未发现相关博主",
    "试试按行业找博主",
    "放宽条件才能找到更多的博主",
    "放宽条件才能找到更多博主",
    "未发现相关博主",
    "没有找到相关博主",
    "暂无相关博主",
    "暂无数据",
]

PGY_BROAD_KEEP_FIELDS = {"营销目标", "博主类目"}
PGY_INVALID_ROW_NAMES = {"暂无数据", "暂无相关博主", "暂未找到相关博主", "暂未发现相关博主", "没有找到相关博主"}


def _visible_text_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _page_empty_result_hint(page: Any) -> str:
    try:
        text = page.locator("body").inner_text(timeout=2500)
    except Exception:
        return ""
    normalized = _clean_text(text)
    for hint in PGY_EMPTY_RESULT_HINTS:
        if hint in normalized:
            return hint
    return ""


def _relaxed_collection_plan(plan: dict[str, Any], stage: str) -> dict[str, Any] | None:
    filters = [item for item in plan.get("filters") or [] if isinstance(item, dict)]
    if not filters:
        return None
    if stage == "broad":
        kept = [item for item in filters if str(item.get("field") or "") in PGY_BROAD_KEEP_FIELDS]
        if len(kept) == len(filters):
            return None
        strategy = "页面无结果，自动放宽为基础类目/目标条件"
    elif stage == "unfiltered":
        kept = []
        strategy = "基础类目/目标仍无结果，清空蒲公英页面筛选后采集，再由本地筛选工作台标记"
    else:
        return None
    removed = [
        item
        for item in filters
        if not any(
            str(item.get("field") or "") == str(next_item.get("field") or "")
            and str(item.get("value") or "") == str(next_item.get("value") or "")
            for next_item in kept
        )
    ]
    return {
        **plan,
        "filters": kept,
        "auto_relaxed": True,
        "relaxation": {
            "stage": stage,
            "strategy": strategy,
            "original_filter_count": len(filters),
            "relaxed_filter_count": len(kept),
            "removed_filters": removed,
            "kept_filters": kept,
        },
    }


def _merge_plan_results(base: dict[str, Any], retry: dict[str, Any], relaxation: dict[str, Any]) -> dict[str, Any]:
    removed_skips = [
        {**item, "message": relaxation.get("strategy") or "页面无结果，自动放宽该筛选项"}
        for item in relaxation.get("removed_filters") or []
    ]
    return {
        "applied_filters": retry.get("applied_filters") or [],
        "skipped_filters": [
            *(base.get("skipped_filters") or []),
            *removed_skips,
            *(retry.get("skipped_filters") or []),
        ],
        "selected_metrics": retry.get("selected_metrics") or base.get("selected_metrics") or [],
        "skipped_metrics": [
            *(base.get("skipped_metrics") or []),
            *(retry.get("skipped_metrics") or []),
        ],
    }


def _is_visible(locator: Any) -> bool:
    try:
        box = locator.bounding_box(timeout=700)
        return bool(box and box.get("width", 0) > 0 and box.get("height", 0) > 0)
    except Exception:
        return False


def _click_first_visible(locator: Any, timeout: int = 1500) -> bool:
    try:
        count = min(locator.count(), 30)
    except Exception:
        return False
    for index in range(count):
        candidate = locator.nth(index)
        if not _is_visible(candidate):
            continue
        try:
            candidate.scroll_into_view_if_needed(timeout=timeout)
            candidate.click(timeout=timeout)
            return True
        except Exception:
            continue
    return False


def _click_locator(page: Any, locator: Any, timeout: int = 1500) -> bool:
    try:
        locator.scroll_into_view_if_needed(timeout=timeout)
    except Exception:
        pass
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        pass
    try:
        locator.evaluate("node => node.click()")
        return True
    except Exception:
        pass
    try:
        box = locator.bounding_box(timeout=800)
        if not box:
            return False
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        return True
    except Exception:
        return False


def _selected_filter_text(page: Any) -> str:
    selected = page.locator(".selected-box").first
    if not selected.count():
        return ""
    try:
        return selected.inner_text(timeout=1200)
    except Exception:
        return ""


def _item_selection_value(item: dict[str, Any]) -> str:
    value = str(item.get("value") or "")
    sub_field = str(item.get("sub_field") or item.get("subField") or "")
    if sub_field:
        for sep in ("：", ":"):
            prefix = f"{sub_field}{sep}"
            if value.startswith(prefix):
                return value[len(prefix):].strip()
    return value.strip()


def _filter_value_candidates(item: dict[str, Any]) -> list[str]:
    raw_value = str(item.get("value") or "").strip()
    selection_value = _item_selection_value(item)
    candidates = [selection_value, raw_value]
    if str(item.get("field") or "") == "营销目标":
        parent = str(item.get("goal") or item.get("parent_value") or item.get("parentValue") or "").strip()
        if selection_value in PGY_MARKETING_GOAL_DEFAULT_METRIC:
            candidates.append(PGY_MARKETING_GOAL_DEFAULT_METRIC[selection_value])
        if parent:
            candidates.append(parent)
    for value in [selection_value, raw_value]:
        candidates.extend(PGY_FILTER_ALIASES.get(value) or [])
    return list(dict.fromkeys([candidate for candidate in candidates if candidate]))


def _catalog_option_groups(field: str) -> list[dict[str, Any]]:
    for catalog_item in PGY_FILTER_CATALOG:
        if catalog_item.get("field") == field:
            groups = catalog_item.get("option_groups") or catalog_item.get("optionGroups") or []
            return groups if isinstance(groups, list) else []
    return []


def _infer_option_group(field: str, value: str) -> str:
    for group in _catalog_option_groups(field):
        options = group.get("options") or []
        if value in options:
            return str(group.get("label") or "")
    return ""


def _filter_already_selected(page: Any, item: dict[str, str]) -> bool:
    selected_text = _clean_text(_selected_filter_text(page))
    field = _clean_text(item.get("field") or "")
    values = [_clean_text(candidate) for candidate in _filter_value_candidates(item)]
    values = [value for value in values if value]
    if not selected_text or not values:
        return False
    if any(value in selected_text for value in values):
        return True
    return bool(field and field in selected_text and any(value and value in selected_text for value in values))


def _parse_row_text(text: str, page_url: str, table_payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    lines = _visible_text_lines(text)
    if not lines or any("skeleton-block" in line for line in lines):
        return None
    cleaned_text = _clean_text(text)
    if any(hint in cleaned_text for hint in PGY_EMPTY_RESULT_HINTS):
        return None
    stop_words = {"添加合作", "发起邀约", "更多操作"}
    lines = [line for line in lines if line not in {"合作", "\t"}]
    if not lines:
        return None
    nickname = lines[0]
    if nickname in stop_words or nickname in PGY_INVALID_ROW_NAMES or len(nickname) > 60:
        return None

    quote_index = next((i for i, line in enumerate(lines) if line in {"¥", "￥"}), -1)
    quote_price = _number_from_text(lines[quote_index + 1]) if quote_index >= 0 and quote_index + 1 < len(lines) else None
    before_quote = lines[:quote_index] if quote_index >= 0 else lines
    row_metrics: dict[str, str] = {}
    metric_label_values: dict[str, str] = {}
    metric_start = -1
    for index in range(2, len(before_quote)):
        value = before_quote[index]
        if re.fullmatch(r"\d+(?:\.\d+)?\s*(?:w|万)", value, flags=re.I):
            metric_start = index
            break
    if metric_start >= 0:
        remaining_metric_count = len(before_quote) - metric_start
        metric_fields = (
            PGY_ROW_METRIC_FIELDS_WITH_LIVE
            if remaining_metric_count >= len(PGY_ROW_METRIC_FIELDS_WITH_LIVE)
            else PGY_NON_LIVE_ROW_METRIC_FIELDS
        )
        metric_values = before_quote[metric_start : metric_start + len(metric_fields)]
        profile_lines = before_quote[:metric_start]
        for (field, label), value in zip(metric_fields, metric_values):
            row_metrics[field] = value
            metric_label_values[label] = value
    else:
        metrics = [line for line in before_quote if _number_from_text(line) is not None or line == "--"]
        followers = metrics[-3] if len(metrics) >= 3 else None
        read_median = metrics[-2] if len(metrics) >= 2 else None
        interaction_median = metrics[-1] if len(metrics) >= 1 else None
        profile_lines = before_quote[: max(1, len(before_quote) - len(metrics))]
        if followers is not None:
            row_metrics["followers_count"] = followers
            metric_label_values["粉丝数"] = followers
        if read_median is not None:
            row_metrics["daily_read_median"] = read_median
            metric_label_values["阅读中位数（日常）"] = read_median
        if interaction_median is not None:
            row_metrics["daily_interaction_median"] = interaction_median
            metric_label_values["互动中位数（日常）"] = interaction_median
    followers = _number_from_text(row_metrics.get("followers_count") or "")
    read_median = _number_from_text(row_metrics.get("daily_read_median") or "")
    interaction_median = _number_from_text(row_metrics.get("daily_interaction_median") or "")
    location = profile_lines[1] if len(profile_lines) > 1 else ""
    tags = [line for line in profile_lines[2:] if not line.startswith("期待与") and line not in stop_words]
    cooperation_hint = next((line for line in profile_lines if line.startswith("期待与")), "")
    table_payload = table_payload or {}
    if not any([followers, read_median, interaction_median, table_payload.get("pgy_url"), table_payload.get("xiaohongshu_id")]) and len(lines) <= 3:
        return None
    raw_payload = {
        "text": text,
        "lines": lines,
        "metrics": metric_label_values,
        "read_median": read_median,
        "interaction_median": interaction_median,
        "cooperation_hint": cooperation_hint,
    }
    if table_payload.get("raw_table"):
        raw_payload["raw_table"] = table_payload["raw_table"]
    creator_id_seed = f"pgy:list:{nickname}:{location}"
    creator = {
        "creator_id": creator_id_seed,
        "source": "pgy",
        "nickname": nickname,
        "pgy_url": "",
        "profile_url": "" if "/solar/pre-trade/note/kol" in page_url else page_url,
        "followers_count": followers,
        "quote_price": quote_price,
        "ip_city": location,
        "persona_tags": "/".join(tags),
        "raw_payload": raw_payload,
        **row_metrics,
    }
    for key, value in table_payload.items():
        if key == "raw_table":
            continue
        if value not in (None, ""):
            creator[key] = value
    if table_payload.get("followers_count") not in (None, ""):
        creator["followers_count"] = _number_from_text(str(table_payload["followers_count"]))
    if table_payload.get("quote_price") not in (None, ""):
        creator["quote_price"] = _number_from_text(str(table_payload["quote_price"]))
    return creator


def _extract_table_headers(page: Any) -> list[str]:
    selectors = [
        ".blogger-list_list .d-new-table thead th",
        ".blogger-list_list table thead th",
    ]
    for selector in selectors:
        try:
            headers = [
                _clean_text(item)
                for item in page.locator(selector).evaluate_all(
                    "(nodes) => nodes.map((node) => node.innerText || node.textContent || '')"
                )
            ]
        except Exception:
            headers = []
        if any(headers):
            return headers
    return []


def _extract_row_table_payload(row: Any, headers: list[str]) -> dict[str, Any]:
    if not headers:
        return {}
    try:
        values = [
            _clean_text(item)
            for item in row.locator("td").evaluate_all(
                "(nodes) => nodes.map((node) => node.innerText || node.textContent || '')"
            )
        ]
    except Exception:
        values = []
    if not values:
        return {}
    pairs = dict(zip(headers, values))
    payload: dict[str, Any] = {"raw_table": pairs}
    for header, value in pairs.items():
        if not header or not value:
            continue
        payload[header] = value
        normalized_header = _normalize_export_header(header)
        field = PGY_TABLE_TO_PAYLOAD_FIELDS.get(header) or PGY_TABLE_TO_PAYLOAD_FIELDS.get(normalized_header)
        if not field:
            field = next(
                (
                    target
                    for target, aliases in PGY_EXPORT_FIELD_ALIASES.items()
                    if normalized_header in {_normalize_export_header(alias) for alias in aliases}
                ),
                "",
            )
        if field:
            payload[field] = value
    return payload


def _extract_detail_fields(text: str, url: str) -> dict[str, Any]:
    lines = _visible_text_lines(text)

    def after(label: str) -> str:
        return _label_value(lines, label)

    nickname = ""
    if "笔记主页" in lines:
        index = lines.index("笔记主页")
        nickname = lines[index + 2] if index + 2 < len(lines) and lines[index + 1] == "直播主页" else ""
    xhs_id = after("小红书号：")
    pgy_blogger_id = ""
    blogger_match = re.search(r"/blogger-detail/([^?/#]+)", url)
    if blogger_match:
        pgy_blogger_id = blogger_match.group(1)
    fans_35_plus_ratio = None
    age_line = next((line for line in lines if "35-44" in line and "占比" in line), "")
    match = re.search(r"占比\s*([0-9.]+)%", age_line)
    if match:
        fans_35_plus_ratio = float(match.group(1)) / 100
    if fans_35_plus_ratio is None:
        fans_35_plus_ratio = _ratio_after_label(lines, "35-44")
    topic_point = ""
    interest_line = next((line for line in lines if "用户最感兴趣的内容类型为" in line), "")
    if interest_line:
        topic_point = interest_line.replace("用户最感兴趣的内容类型为", "").strip()
    personal_intro = ""
    for label in ("个人简介：", "个人简介", "简介：", "简介"):
        personal_intro = after(label)
        if personal_intro:
            break
    quote_price = _number_from_text(after("图文笔记一口价"))
    video_quote = _number_from_text(after("视频笔记一口价"))
    followers = _number_from_text(after("粉丝数"))
    liked_collected = _number_from_text(after("获赞与收藏"))
    persona_tags = ""
    ip_city = ""
    mcn_status = ""
    home_city = ""
    primary_categories: list[str] = []
    if nickname and nickname in lines:
        name_index = lines.index(nickname)
        persona_tags = lines[name_index + 3] if name_index + 3 < len(lines) and lines[name_index + 1] == "小红书号：" else ""
        ip_city = lines[name_index + 4] if name_index + 4 < len(lines) and lines[name_index + 1] == "小红书号：" else ""
        mcn_status = lines[name_index + 5] if name_index + 5 < len(lines) and lines[name_index + 1] == "小红书号：" else ""
        home_city = lines[name_index + 6] if name_index + 6 < len(lines) and lines[name_index + 1] == "小红书号：" else ""
        categories_start = name_index + 7 if name_index + 1 < len(lines) and lines[name_index + 1] == "小红书号：" else name_index + 1
        for line in lines[categories_start:]:
            if line == "粉丝数":
                break
            primary_categories.append(line)
    note_case_items = _extract_note_cases(lines)
    note_performance = {
        "exposure_median": _metric_value_after(lines, "曝光中位数"),
        "read_median": _metric_value_after(lines, "阅读中位数"),
        "interaction_median": _metric_value_after(lines, "互动中位数"),
        "median_like_count": _metric_value_after(lines, "中位点赞量"),
        "median_save_count": _metric_value_after(lines, "中位收藏量"),
        "median_comment_count": _metric_value_after(lines, "中位评论量"),
        "median_share_count": _metric_value_after(lines, "中位分享量"),
        "median_follow_count": _metric_value_after(lines, "中位关注量"),
        "interaction_rate": _ratio_after_label(lines, "互动率"),
        "video_completion_rate": _ratio_after_label(lines, "视频完播率"),
        "thousand_like_note_ratio": _ratio_after_label(lines, "千赞笔记比例"),
        "hundred_like_note_ratio": _ratio_after_label(lines, "百赞笔记比例"),
    }
    note_performance = {key: value for key, value in note_performance.items() if value is not None}
    fan_analysis = {
        "fan_growth": _metric_value_after(lines, "粉丝增量"),
        "fan_growth_ratio": _ratio_after_label(lines, "粉丝量变化幅度"),
        "active_fans_ratio": _ratio_after_label(lines, "活跃粉丝占比"),
        "read_fans_ratio": _ratio_after_label(lines, "阅读粉丝占比"),
        "interaction_fans_ratio": _ratio_after_label(lines, "互动粉丝占比"),
        "order_fans_ratio": _ratio_after_label(lines, "下单粉丝占比"),
        "female_fans_ratio": _gender_ratio(lines, "女性"),
        "male_fans_ratio": _gender_ratio(lines, "男性"),
        "fans_18_24_ratio": _ratio_near_label(lines, "18-24"),
        "fans_25_34_ratio": _ratio_near_label(lines, "25-34"),
        "fans_35_44_ratio": _ratio_near_label(lines, "35-44"),
        "fans_44_plus_ratio": _ratio_near_label(lines, ">44") or _ratio_near_label(lines, "44岁以上"),
        "gender_distribution": _line_between(lines, "性别分布", "年龄分布"),
        "age_distribution": _line_between(lines, "年龄分布", "地域分布"),
        "region_distribution": _line_between(lines, "地域分布", "按省份"),
        "device_distribution": _line_between(lines, "用户设备分布", "用户兴趣"),
    }
    fan_analysis = {key: value for key, value in fan_analysis.items() if value not in ("", None)}
    services = {
        "active_days_7d": _metric_value_after(lines, "近7天活跃天数"),
        "reply_rate_48h": _ratio_after_label(lines, "邀约48小时回复率"),
    }
    services = {key: value for key, value in services.items() if value is not None}
    overview_match = re.search(r"博主优势(.*?)笔记数据", text, flags=re.S)
    blogger_advantage = ""
    if overview_match:
        blogger_advantage = re.sub(r"\s+", "", overview_match.group(1))
    raw_detail = {
        "detail_url": url,
        "detail_text": text[:12000],
        "lines": lines,
        "data_updated_to": after("数据更新至："),
        "personal_intro": personal_intro,
        "blogger_advantage": blogger_advantage,
        "video_quote_price": video_quote,
        "note_performance": note_performance,
        "fan_analysis": fan_analysis,
        "service_performance": services,
        "note_cases": note_case_items,
        "fans_age_line": age_line,
        "interest_line": interest_line,
        "active_fans_ratio": after("活跃粉丝占比"),
        "read_fans_ratio": after("阅读粉丝占比"),
        "interaction_fans_ratio": after("互动粉丝占比"),
    }
    result = {
        "pgy_url": url,
        "profile_url": url,
        "xiaohongshu_id": xhs_id,
        "pgy_blogger_id": pgy_blogger_id,
        "raw_payload": raw_detail,
    }
    if nickname:
        result["nickname"] = nickname
    if followers is not None:
        result["followers_count"] = followers
    if liked_collected is not None:
        result["liked_collected_count"] = liked_collected
    if quote_price is not None:
        result["quote_price"] = quote_price
    if video_quote is not None:
        result["video_quote_price"] = video_quote
    if persona_tags:
        result["persona_tags"] = persona_tags
    if ip_city:
        result["ip_city"] = ip_city
    if primary_categories:
        result["creator_type"] = "/".join(primary_categories)
    if topic_point:
        result["topic_point"] = topic_point
    if personal_intro:
        result["personal_intro"] = personal_intro
    metric_mapping = {
        "daily_exposure_median": note_performance.get("exposure_median"),
        "daily_read_median": note_performance.get("read_median"),
        "daily_interaction_median": note_performance.get("interaction_median"),
        "daily_thousand_like_note_ratio": note_performance.get("thousand_like_note_ratio"),
        "daily_hundred_like_note_ratio": note_performance.get("hundred_like_note_ratio"),
        "video_completion_rate": note_performance.get("video_completion_rate"),
        "active_fans_ratio": fan_analysis.get("active_fans_ratio"),
        "female_fans_ratio": fan_analysis.get("female_fans_ratio"),
        "male_fans_ratio": fan_analysis.get("male_fans_ratio"),
        "fans_18_24_ratio": fan_analysis.get("fans_18_24_ratio"),
        "fans_25_34_ratio": fan_analysis.get("fans_25_34_ratio"),
        "fans_35_44_ratio": fan_analysis.get("fans_35_44_ratio"),
        "fans_44_plus_ratio": fan_analysis.get("fans_44_plus_ratio"),
        "fans_growth_ratio": fan_analysis.get("fan_growth_ratio"),
        "read_fans_ratio": fan_analysis.get("read_fans_ratio"),
        "interaction_fans_ratio": fan_analysis.get("interaction_fans_ratio"),
        "order_fans_ratio": fan_analysis.get("order_fans_ratio"),
        "reply_rate_48h": services.get("reply_rate_48h"),
        "active_days_7d": services.get("active_days_7d"),
    }
    derived_fans_35_plus = None
    if fan_analysis.get("fans_35_44_ratio") is not None or fan_analysis.get("fans_44_plus_ratio") is not None:
        derived_fans_35_plus = (fan_analysis.get("fans_35_44_ratio") or 0) + (fan_analysis.get("fans_44_plus_ratio") or 0)
    if derived_fans_35_plus is not None:
        metric_mapping["fans_35_plus_ratio"] = min(derived_fans_35_plus, 1)
    elif fans_35_plus_ratio is not None:
        metric_mapping["fans_35_plus_ratio"] = fans_35_plus_ratio
    result.update({key: value for key, value in metric_mapping.items() if value is not None})
    return result


def _extract_row_link_fields(row: Any) -> dict[str, Any]:
    try:
        urls = row.evaluate(
            """
            node => Array.from(node.querySelectorAll('*'))
              .flatMap(el => {
                const attrs = Array.from(el.attributes || []).map(attr => attr.value);
                return [el.href, el.getAttribute('href'), el.getAttribute('data-href'), el.getAttribute('data-url'), ...attrs];
              })
              .filter(Boolean)
            """
        )
    except Exception:
        urls = []
    pgy_url = next((url for url in urls if "pgy.xiaohongshu.com" in url and "/blogger-detail/" in url), "")
    if not pgy_url:
        pgy_url = next((url for url in urls if "/blogger-detail/" in url), "")
    if not pgy_url:
        return {}
    return _detail_url_fields(pgy_url, source="row_dom") or {"pgy_url": pgy_url, "profile_url": pgy_url}


def _detail_url_fields(url: str, source: str = "") -> dict[str, Any]:
    if not url or "/blogger-detail/" not in url:
        return {}
    blogger_match = re.search(r"/blogger-detail/([^?/#]+)", url)
    if not blogger_match:
        return {}
    blogger_id = blogger_match.group(1)
    canonical_url = f"https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/{blogger_id}"
    return {
        "pgy_url": canonical_url,
        "profile_url": canonical_url,
        "pgy_blogger_id": blogger_id,
        "pgy_url_source": source,
    }


def _install_kol_response_capture(page: Any) -> None:
    if getattr(page, "_pgy_kol_response_capture_installed", False):
        return
    setattr(page, "_pgy_latest_api_kols", [])

    def handle_response(response: Any) -> None:
        if "/api/solar/cooperator/blogger/v2" not in getattr(response, "url", ""):
            return
        try:
            payload = response.json()
        except Exception:
            return
        data = payload.get("data") if isinstance(payload, dict) else {}
        kols = data.get("kols") if isinstance(data, dict) else []
        if not isinstance(kols, list) or not kols:
            return
        setattr(page, "_pgy_latest_api_kols", kols)

    try:
        page.on("response", handle_response)
        setattr(page, "_pgy_kol_response_capture_installed", True)
    except Exception:
        pass


def _api_kol_link_fields(page: Any, row_index: int, creator: dict[str, Any]) -> dict[str, Any]:
    kols = getattr(page, "_pgy_latest_api_kols", []) or []
    if not isinstance(kols, list):
        return {}
    nickname = _clean_text(str(creator.get("nickname") or ""))
    location = _clean_text(str(creator.get("ip_city") or ""))
    candidates: list[dict[str, Any]] = []
    if 0 <= row_index < len(kols) and isinstance(kols[row_index], dict):
        candidates.append(kols[row_index])
    candidates.extend(kol for kol in kols if isinstance(kol, dict))
    seen_ids: set[int] = set()
    for kol in candidates:
        marker = id(kol)
        if marker in seen_ids:
            continue
        seen_ids.add(marker)
        kol_name = _clean_text(str(kol.get("name") or kol.get("nickName") or kol.get("nickname") or ""))
        kol_location = _clean_text(str(kol.get("location") or kol.get("city") or ""))
        if nickname and kol_name and kol_name != nickname:
            continue
        if location and kol_location and kol_location != location and row_index >= len(kols):
            continue
        user_id = str(kol.get("userId") or kol.get("user_id") or kol.get("bloggerId") or kol.get("kolId") or "").strip()
        if not user_id:
            continue
        fields = _detail_url_fields(
            f"https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/{user_id}",
            source="list_api",
        )
        if not fields:
            continue
        if kol.get("redId"):
            fields["xiaohongshu_id"] = str(kol.get("redId") or "")
        if kol.get("headPhoto"):
            fields["avatar_url"] = str(kol.get("headPhoto") or "")
        return fields
    return {}


def _collect_row_profile_url(context: Any, row: Any) -> dict[str, Any]:
    existing_pages = set(context.pages)
    trigger = row.locator(".kol-name").first
    if not trigger.count():
        trigger = row.locator(".profile").first
    if not trigger.count():
        return {}
    detail_page = None
    try:
        try:
            with context.expect_page(timeout=5000) as page_info:
                trigger.click(timeout=2000)
            detail_page = page_info.value
        except Exception:
            try:
                trigger.click(timeout=2000)
                detail_page = next((page for page in context.pages if page not in existing_pages and "/blogger-detail/" in page.url), None)
            except Exception:
                detail_page = None
        if not detail_page:
            return {}
        try:
            detail_page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        for _ in range(12):
            fields = _detail_url_fields(detail_page.url, source="nickname_click")
            if fields:
                return fields
            detail_page.wait_for_timeout(250)
        return {}
    finally:
        if detail_page:
            try:
                detail_page.close()
            except Exception:
                pass


def _audience_profile_clip(page: Any) -> dict[str, Any] | None:
    try:
        return page.evaluate(
            """
            () => {
              const normalized = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const visible = el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                  && style.display !== 'none'
                  && style.visibility !== 'hidden';
              };
              const textNodes = label => Array.from(document.querySelectorAll('section, div, h1, h2, h3, h4, span, p'))
                .filter(visible)
                .filter(el => normalized(el.innerText || el.textContent) === label)
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.left - br.left;
                });
              const heading = textNodes('粉丝画像')[0];
              if (!heading) return null;
              const titleBlock = heading.closest('.content__title') || heading;
              const titleRect = titleBlock.getBoundingClientRect();
              const fansPic = Array.from(document.querySelectorAll('.contentPic.fansPic'))
                .filter(visible)
                .filter(el => {
                  const text = el.innerText || '';
                  const rect = el.getBoundingClientRect();
                  return text.includes('性别分布') && text.includes('年龄分布') && rect.top >= titleRect.top;
                })
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.left - br.left;
                })[0];
              if (fansPic) {
                const picRect = fansPic.getBoundingClientRect();
                const left = Math.min(titleRect.left, picRect.left);
                const top = Math.max(0, titleRect.top - 12) + window.scrollY;
                const topViewport = Math.max(0, titleRect.top - 12);
                const right = Math.max(titleRect.right, picRect.right);
                const bottom = picRect.bottom + 12;
                const width = right - left;
                const height = bottom - topViewport;
                if (width >= 240 && height >= 160) {
                  return {
                    x: left,
                    y: topViewport,
                    width,
                    height,
                    pageX: left + window.scrollX,
                    pageY: top,
                    source: 'audience_profile_fanspic_clip',
                    rootText: normalized(fansPic.innerText || '').slice(0, 240)
                  };
                }
              }
              const gender = textNodes('性别分布')[0];
              const age = textNodes('年龄分布')[0];
              if (!gender || !age) return null;
              const rootCandidates = Array.from(document.querySelectorAll('section, div'))
                .filter(visible)
                .filter(el => {
                  const text = el.innerText || '';
                  if (!text.includes('粉丝画像') || !text.includes('性别分布') || !text.includes('年龄分布')) return false;
                  const rect = el.getBoundingClientRect();
                  const headingRect = heading.getBoundingClientRect();
                  return rect.top <= headingRect.top && rect.bottom >= age.getBoundingClientRect().bottom;
                })
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  const areaA = ar.width * ar.height;
                  const areaB = br.width * br.height;
                  return areaA - areaB;
                });
              const root = rootCandidates[0];
              if (!root) return null;
              const rootRect = root.getBoundingClientRect();
              const headingRect = heading.getBoundingClientRect();
              const genderRect = gender.getBoundingClientRect();
              const ageRect = age.getBoundingClientRect();
              const allRects = [headingRect, genderRect, ageRect];
              const genderCard = Array.from(document.querySelectorAll('section, div'))
                .filter(visible)
                .filter(el => (el.innerText || '').includes('性别分布'))
                .filter(el => {
                  const rect = el.getBoundingClientRect();
                  return rect.top >= headingRect.top - 20 && rect.left >= rootRect.left - 20 && rect.right <= rootRect.right + 20;
                })
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return (ar.width * ar.height) - (br.width * br.height);
                })[0];
              const ageCard = Array.from(document.querySelectorAll('section, div'))
                .filter(visible)
                .filter(el => (el.innerText || '').includes('年龄分布'))
                .filter(el => {
                  const rect = el.getBoundingClientRect();
                  return rect.top >= headingRect.top - 20 && rect.left >= rootRect.left - 20 && rect.right <= rootRect.right + 20;
                })
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return (ar.width * ar.height) - (br.width * br.height);
                })[0];
              const nextSection = textNodes('地域分布').find(el => {
                const rect = el.getBoundingClientRect();
                return rect.top > headingRect.top && rect.left >= rootRect.left - 20 && rect.left <= rootRect.right + 20;
              }) || textNodes('用户设备分布').find(el => {
                const rect = el.getBoundingClientRect();
                return rect.top > headingRect.top && rect.left >= rootRect.left - 20 && rect.left <= rootRect.right + 20;
              });
              const nextTop = nextSection ? nextSection.getBoundingClientRect().top : rootRect.bottom;
              const cardRects = Array.from(root.querySelectorAll('section, div'))
                .filter(visible)
                .map(el => el.getBoundingClientRect())
                .filter(rect => rect.top >= headingRect.top - 8 && rect.top < nextTop && rect.bottom > Math.max(genderRect.bottom, ageRect.bottom))
                .filter(rect => rect.width > 120 && rect.height > 80);
              if (genderCard) allRects.push(genderCard.getBoundingClientRect());
              if (ageCard) allRects.push(ageCard.getBoundingClientRect());
              allRects.push(...cardRects);
              const leftViewport = Math.max(0, Math.min(...allRects.map(rect => rect.left), rootRect.left));
              const topViewport = Math.max(0, headingRect.top - 12);
              const rightViewport = Math.max(...allRects.map(rect => rect.right), rootRect.right);
              const cardsBottom = Math.max(...allRects.map(rect => rect.bottom));
              const bottomViewport = Math.max(cardsBottom + 12, nextTop ? Math.min(cardsBottom + 12, nextTop - 12) : cardsBottom + 12);
              const left = leftViewport;
              const top = topViewport;
              const right = rightViewport;
              const bottom = bottomViewport;
              const width = right - left;
              const height = bottom - top;
              if (width < 240 || height < 160) return null;
              return {
                x: left,
                y: top,
                width,
                height,
                pageX: leftViewport + window.scrollX,
                pageY: topViewport + window.scrollY,
                source: 'audience_profile_gender_age_clip',
                rootText: normalized(root.innerText || '').slice(0, 240)
              };
            }
            """
        )
    except Exception:
        return None


def _prepare_audience_profile_capture_target(page: Any) -> dict[str, Any]:
    try:
        return page.evaluate(
            """
            () => {
              const normalized = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const visible = el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                  && style.display !== 'none'
                  && style.visibility !== 'hidden';
              };
              const exact = label => Array.from(document.querySelectorAll('section, div, h1, h2, h3, h4, span, p'))
                .filter(visible)
                .filter(el => normalized(el.innerText || el.textContent) === label)
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return ar.top - br.top || ar.left - br.left;
                });
              const heading = exact('粉丝画像')[0];
              if (!heading) return { ok: false, message: 'missing heading' };
              const roots = Array.from(document.querySelectorAll('section, div'))
                .filter(visible)
                .filter(el => {
                  const text = el.innerText || '';
                  return text.includes('粉丝画像') && text.includes('性别分布') && text.includes('年龄分布');
                })
                .filter(el => {
                  const rect = el.getBoundingClientRect();
                  const headingRect = heading.getBoundingClientRect();
                  return rect.top <= headingRect.top && rect.bottom > headingRect.bottom;
                })
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return (ar.width * ar.height) - (br.width * br.height);
                });
              const root = roots[0];
              if (!root) return { ok: false, message: 'missing root' };
              const before = exact('地域分布').find(el => {
                const r = el.getBoundingClientRect();
                const h = heading.getBoundingClientRect();
                return r.top > h.top;
              }) || exact('用户设备分布').find(el => {
                const r = el.getBoundingClientRect();
                const h = heading.getBoundingClientRect();
                return r.top > h.top;
              });
              const previous = document.getElementById('__pgy_fans_profile_capture__');
              if (previous) previous.remove();
              const wrapper = document.createElement('div');
              wrapper.id = '__pgy_fans_profile_capture__';
              wrapper.style.background = '#fff';
              wrapper.style.boxSizing = 'border-box';
              wrapper.style.width = `${root.getBoundingClientRect().width}px`;
              wrapper.style.padding = '0';
              wrapper.style.margin = '0';
              wrapper.style.overflow = 'visible';
              const clone = root.cloneNode(true);
              if (before) {
                const beforeText = normalized(before.innerText || before.textContent);
                const walker = document.createTreeWalker(clone, NodeFilter.SHOW_ELEMENT);
                const toRemove = [];
                while (walker.nextNode()) {
                  const node = walker.currentNode;
                  if (normalized(node.innerText || node.textContent) === beforeText) {
                    let section = node;
                    while (section.parentElement && section.parentElement !== clone) {
                      const text = section.parentElement.innerText || '';
                      if (text.includes(beforeText) && !text.includes('粉丝画像')) {
                        section = section.parentElement;
                        break;
                      }
                      section = section.parentElement;
                    }
                    toRemove.push(section);
                    break;
                  }
                }
                for (const node of toRemove) {
                  let current = node;
                  while (current) {
                    const next = current.nextElementSibling;
                    current.remove();
                    current = next;
                  }
                }
              }
              wrapper.appendChild(clone);
              document.body.appendChild(wrapper);
              wrapper.scrollIntoView({ block: 'center', inline: 'nearest' });
              const rect = wrapper.getBoundingClientRect();
              return { ok: true, selector: '#__pgy_fans_profile_capture__', box: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } };
            }
            """
        )
    except Exception as error:
        return {"ok": False, "message": str(error)}


def _remove_audience_profile_capture_target(page: Any) -> None:
    try:
        page.evaluate("() => document.getElementById('__pgy_fans_profile_capture__')?.remove()")
    except Exception:
        pass


def _scroll_audience_profile_to_viewport_top(page: Any) -> None:
    try:
        page.evaluate(
            """
            () => {
              const normalized = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const visible = el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                  && style.display !== 'none'
                  && style.visibility !== 'hidden';
              };
              const heading = Array.from(document.querySelectorAll('section, div, h1, h2, h3, h4, span, p'))
                .filter(visible)
                .find(el => normalized(el.innerText || el.textContent) === '粉丝画像');
              const target = heading?.closest('.content') || heading?.closest('.content__title') || heading;
              if (!target) return false;
              target.scrollIntoView({ block: 'start', inline: 'nearest' });
              const scrollParents = [];
              let parent = target.parentElement;
              while (parent) {
                const style = window.getComputedStyle(parent);
                if (/(auto|scroll)/.test(`${style.overflowY} ${style.overflow}`)) scrollParents.push(parent);
                parent = parent.parentElement;
              }
              for (const parent of scrollParents) {
                const targetRect = target.getBoundingClientRect();
                const parentRect = parent.getBoundingClientRect();
                parent.scrollTop += targetRect.top - parentRect.top - 24;
              }
              window.scrollBy(0, -24);
              return true;
            }
            """
        )
        page.wait_for_timeout(700)
    except Exception:
        pass


def _scroll_to_fans_analysis(page: Any) -> None:
    for label in ["粉丝分析", "粉丝画像"]:
        try:
            target = page.locator(f"text={label}").last
            if target.count():
                target.scroll_into_view_if_needed(timeout=3000)
                page.wait_for_timeout(1200)
                return
        except Exception:
            continue
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1200)
    except Exception:
        pass


def _capture_audience_profile_screenshot(page: Any, detail: dict[str, Any]) -> dict[str, Any]:
    _scroll_to_fans_analysis(page)
    _scroll_audience_profile_to_viewport_top(page)
    PGY_DETAIL_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    blogger_id = str(detail.get("pgy_blogger_id") or "unknown")
    nickname = str(detail.get("nickname") or blogger_id)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = PGY_DETAIL_SCREENSHOT_DIR / f"{_safe_filename(nickname)}-{_safe_filename(blogger_id)}-fans-profile-{timestamp}.png"
    clip = _audience_profile_clip(page)
    if not clip:
        return {}
    try:
        _scroll_audience_profile_to_viewport_top(page)
        page.wait_for_timeout(500)
        refreshed = _audience_profile_clip(page)
        if refreshed:
            clip = refreshed
    except Exception:
        pass
    box = {key: float(clip[key]) for key in ["x", "y", "width", "height"]}
    if box["y"] < 120:
        shift = 120 - box["y"]
        box["y"] = 120
        box["height"] = max(80, box["height"] - shift)
    if not box or box.get("width", 0) < 120 or box.get("height", 0) < 80:
        return {}
    original_viewport = None
    try:
        original_viewport = page.viewport_size
        if original_viewport:
            target_width = max(int(original_viewport.get("width") or 0), int(box["x"] + box["width"] + 40))
            target_height = max(int(original_viewport.get("height") or 0), int(box["y"] + box["height"] + 80))
            if target_width != original_viewport.get("width") or target_height != original_viewport.get("height"):
                page.set_viewport_size({"width": target_width, "height": target_height})
                page.wait_for_timeout(500)
                refreshed = _audience_profile_clip(page)
                if refreshed:
                    clip = refreshed
                    box = {key: float(clip[key]) for key in ["x", "y", "width", "height"]}
        page.screenshot(path=str(path), clip=box)
    except Exception:
        return {}
    finally:
        if original_viewport:
            try:
                page.set_viewport_size(original_viewport)
            except Exception:
                pass
    source = clip.get("source")
    return {
        "audience_profile_screenshot": str(path),
        "raw_payload": {
            "audience_profile_screenshot": {
                "path": str(path),
                "dom_only": True,
                "scope": "粉丝画像-性别分布-年龄分布",
                "source": source,
                "box": box,
            }
        },
    }


def _merge_detail_payload(detail: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    if not extra:
        return detail
    merged = {**detail, **{key: value for key, value in extra.items() if key != "raw_payload"}}
    raw = {}
    if isinstance(detail.get("raw_payload"), dict):
        raw.update(detail["raw_payload"])
    if isinstance(extra.get("raw_payload"), dict):
        raw.update(extra["raw_payload"])
    if raw:
        merged["raw_payload"] = raw
    return merged


def _collect_first_detail_for_creator(context: Any, row: Any) -> dict[str, Any]:
    existing_pages = set(context.pages)
    trigger = row.locator(".profile").first
    if not trigger.count():
        trigger = row.locator(".kol-name").first
    if not trigger.count():
        return {}
    try:
        with context.expect_page(timeout=4000) as page_info:
            trigger.click(timeout=2000)
        detail_page = page_info.value
    except Exception:
        try:
            trigger.click(timeout=2000)
            detail_page = next((page for page in context.pages if page not in existing_pages and "/blogger-detail/" in page.url), None)
        except Exception:
            detail_page = None
    if not detail_page:
        return {}
    try:
        detail_page.wait_for_load_state("domcontentloaded", timeout=10000)
        detail_page.wait_for_timeout(3500)
        text = detail_page.locator("body").inner_text(timeout=5000)
        detail = _extract_detail_fields(text, detail_page.url)
        detail = {**_detail_url_fields(detail_page.url, source="detail_page"), **detail}
        detail = _merge_detail_payload(detail, _collect_audience_profile_chart_metrics(detail_page))
        detail = _merge_detail_payload(detail, _collect_detail_interaction_states(detail_page))
        detail = _merge_detail_payload(detail, _capture_audience_profile_screenshot(detail_page, detail))
        return _annotate_note_cases_with_traffic_reference(detail)
    finally:
        try:
            detail_page.close()
        except Exception:
            pass


def _collect_detail_by_url(context: Any, url: str) -> dict[str, Any]:
    if not url or "pgy.xiaohongshu.com" not in url:
        return {}
    detail_page = context.new_page()
    try:
        detail_page.goto(url, wait_until="domcontentloaded", timeout=30000)
        detail_page.wait_for_timeout(3500)
        text = detail_page.locator("body").inner_text(timeout=5000)
        detail = _extract_detail_fields(text, detail_page.url)
        detail = _merge_detail_payload(detail, _collect_audience_profile_chart_metrics(detail_page))
        detail = _merge_detail_payload(detail, _collect_detail_interaction_states(detail_page))
        detail = _merge_detail_payload(detail, _capture_audience_profile_screenshot(detail_page, detail))
        return _annotate_note_cases_with_traffic_reference(detail)
    finally:
        try:
            detail_page.close()
        except Exception:
            pass


def _creator_list_rows(page: Any) -> Any:
    return page.locator(".blogger-list_list .d-new-table tbody tr").filter(has_not=page.locator(".skeleton-block"))


def _creator_collection_key(creator: dict[str, Any]) -> str:
    for field in ["pgy_blogger_id", "pgy_url", "profile_url", "xiaohongshu_id", "creator_id"]:
        value = str(creator.get(field) or "").strip()
        if value:
            return f"{field}:{value}"
    return "|".join(
        str(creator.get(field) or "").strip()
        for field in ["nickname", "followers_count", "quote_price", "ip_city"]
    )


def _creator_table_signature(page: Any) -> str:
    try:
        rows = _creator_list_rows(page)
        count = min(rows.count(), 8)
        parts = []
        for index in range(count):
            parts.append(_clean_text(rows.nth(index).inner_text(timeout=800))[:240])
        return "||".join(parts)
    except Exception:
        return ""


def _has_valid_creator_rows(page: Any) -> bool:
    try:
        rows = _creator_list_rows(page)
        count = min(rows.count(), 6)
    except Exception:
        return False
    for index in range(count):
        try:
            text = rows.nth(index).inner_text(timeout=800)
        except Exception:
            continue
        if _parse_row_text(text, page.url):
            return True
    return False


def _reset_creator_list_scroll(page: Any) -> None:
    try:
        page.evaluate(
            """
            () => {
              const body = document.querySelector('.solar_body');
              if (body) body.scrollTop = 0;
              const list = document.querySelector('.blogger-list_list');
              if (list) list.scrollTop = 0;
              window.scrollTo(0, 0);
            }
            """
        )
    except Exception:
        pass


def _wait_for_creator_table_change(page: Any, before_signature: str, timeout_ms: int = 8000) -> bool:
    rounds = max(1, int(timeout_ms / 500))
    for _ in range(rounds):
        page.wait_for_timeout(500)
        try:
            rows = _creator_list_rows(page)
            if rows.count() and _has_valid_creator_rows(page) and _creator_table_signature(page) != before_signature:
                _reset_creator_list_scroll(page)
                return True
        except Exception:
            continue
    return False


def _pagination_page_number(text: str) -> int | None:
    digits = re.findall(r"\d+", text or "")
    if not digits:
        return None
    if len(digits) >= 2 and len(set(digits)) == 1:
        digits = [digits[0]]
    try:
        return int(digits[0])
    except ValueError:
        return None


def _click_pagination_element(page: Any, candidate: Any) -> bool:
    try:
        candidate.scroll_into_view_if_needed(timeout=1200)
    except Exception:
        pass
    try:
        candidate.click(timeout=1800)
    except Exception:
        try:
            candidate.evaluate("node => node.click()")
        except Exception:
            try:
                box = candidate.bounding_box(timeout=1000)
                if not box:
                    return False
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            except Exception:
                return False
    page.wait_for_timeout(900)
    _reset_creator_list_scroll(page)
    return True


def _click_next_creator_page(page: Any, target_page: int | None = None) -> bool:
    page_buttons = page.locator(".d-pagination .d-pagination-page")
    try:
        button_count = min(page_buttons.count(), 80)
    except Exception:
        button_count = 0
    if target_page is not None:
        for index in range(button_count):
            candidate = page_buttons.nth(index)
            try:
                if not _is_visible(candidate):
                    continue
                class_name = (candidate.get_attribute("class") or "").lower()
                if "disabled" in class_name:
                    continue
                number = _pagination_page_number(candidate.inner_text(timeout=500))
                if number == target_page and _click_pagination_element(page, candidate):
                    return True
            except Exception:
                continue
    active_index = -1
    for index in range(button_count):
        candidate = page_buttons.nth(index)
        try:
            class_name = (candidate.get_attribute("class") or "").lower()
            text = _clean_text(candidate.inner_text(timeout=500))
            if ("primary-light" in class_name or "actived" in class_name or "active" in class_name) and text:
                active_index = index
                break
        except Exception:
            continue
    if active_index >= 0:
        for index in range(active_index + 1, button_count):
            candidate = page_buttons.nth(index)
            try:
                if not _is_visible(candidate):
                    continue
                class_name = (candidate.get_attribute("class") or "").lower()
                if "disabled" in class_name:
                    continue
                text = _clean_text(candidate.inner_text(timeout=500))
                if not text or text == "...":
                    continue
                if _click_pagination_element(page, candidate):
                    return True
            except Exception:
                continue

    candidates = page.locator("button, a, li, div[role=button], span[role=button]")
    try:
        count = min(candidates.count(), 300)
    except Exception:
        return False
    for index in range(count):
        candidate = candidates.nth(index)
        try:
            if not _is_visible(candidate):
                continue
            text = _clean_text(candidate.inner_text(timeout=500))
            title = _clean_text(candidate.get_attribute("title") or "")
            aria = _clean_text(candidate.get_attribute("aria-label") or "")
            class_name = (candidate.get_attribute("class") or "").lower()
            descriptor = f"{text}|{title}|{aria}|{class_name}"
            is_next = (
                "下一页" in descriptor
                or "next" in descriptor
                or "pagination-next" in descriptor
                or text in {">", "›", "»"}
            )
            if not is_next or "上一页" in descriptor or "prev" in descriptor:
                continue
            disabled = (
                candidate.get_attribute("disabled") is not None
                or str(candidate.get_attribute("aria-disabled") or "").lower() == "true"
                or "disabled" in class_name
            )
            if disabled:
                continue
            if _click_pagination_element(page, candidate):
                return True
        except Exception:
            continue
    return False


def _scroll_creator_list(page: Any) -> bool:
    try:
        result = page.evaluate(
            """
            () => {
              const root = document.querySelector('.blogger-list_list') || document.body;
              const scrollables = Array.from(root.querySelectorAll('*'))
                .filter(el => el.scrollHeight > el.clientHeight + 8);
              const target = scrollables
                .sort((a, b) => (b.clientHeight * b.clientWidth) - (a.clientHeight * a.clientWidth))[0];
              if (!target) {
                const before = Math.round(window.scrollY || document.documentElement.scrollTop || 0);
                window.scrollBy(0, Math.max(480, Math.floor(window.innerHeight * 0.75)));
                const after = Math.round(window.scrollY || document.documentElement.scrollTop || 0);
                return { changed: after > before, before, after };
              }
              const before = Math.round(target.scrollTop);
              target.scrollTop = Math.min(
                target.scrollTop + Math.max(480, Math.floor(target.clientHeight * 0.85)),
                target.scrollHeight
              );
              const after = Math.round(target.scrollTop);
              return { changed: after > before, before, after };
            }
            """
        )
        return bool(result and result.get("changed"))
    except Exception:
        return False


def _extract_current_creator_page(
    page: Any,
    creators: list[dict[str, Any]],
    seen: set[str],
    limit: int,
    include_details: bool = False,
    collect_profile_urls: bool = False,
    detail_limit: int | None = None,
    page_number: int = 1,
) -> int:
    rows = _creator_list_rows(page)
    try:
        count = rows.count()
    except Exception:
        count = 0
    context = page.context
    headers = _extract_table_headers(page)
    added = 0
    for index in range(min(count, max(limit * 2, 120))):
        row = rows.nth(index)
        try:
            text = row.inner_text(timeout=3000)
        except Exception:
            continue
        table_payload = _extract_row_table_payload(row, headers)
        creator = _parse_row_text(text, page.url, table_payload=table_payload)
        if not creator:
            continue
        creator.update(_extract_row_link_fields(row))
        if not creator.get("pgy_url"):
            creator.update(_api_kol_link_fields(page, index, creator))
        key = _creator_collection_key(creator)
        if key in seen:
            continue
        seen.add(key)
        raw_payload = creator.get("raw_payload") if isinstance(creator.get("raw_payload"), dict) else {}
        creator["raw_payload"] = {**raw_payload, "collection_page": page_number, "collection_row_index": index + 1}
        avatar = row.locator("img.head-photo").first
        if avatar.count():
            creator["avatar_url"] = avatar.get_attribute("src") or ""
        max_detail_count = detail_limit if detail_limit is not None else limit
        if include_details and len(creators) < max_detail_count:
            detail = _collect_first_detail_for_creator(context, row)
            if detail:
                raw_payload = creator.get("raw_payload") if isinstance(creator.get("raw_payload"), dict) else {}
                detail_raw = detail.pop("raw_payload", {})
                creator.update({key: value for key, value in detail.items() if value not in ("", None)})
                creator["raw_payload"] = {**raw_payload, "detail": detail_raw}
        elif collect_profile_urls and not creator.get("pgy_url"):
            link_fields = _collect_row_profile_url(context, row)
            if link_fields:
                raw_payload = creator.get("raw_payload") if isinstance(creator.get("raw_payload"), dict) else {}
                creator.update(link_fields)
                creator["raw_payload"] = {**raw_payload, "pgy_url_source": link_fields.get("pgy_url_source")}
        creators.append(creator)
        added += 1
        if len(creators) >= limit:
            break
    return added


def _extract_visible_creators(
    page: Any,
    limit: int,
    include_details: bool = False,
    collect_profile_urls: bool = True,
    detail_limit: int | None = None,
) -> list[dict[str, Any]]:
    creators: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_number = 1
    idle_rounds = 0
    max_rounds = max(4, min(120, (limit // 20) + 8))
    for _ in range(max_rounds):
        before_count = len(creators)
        _extract_current_creator_page(
            page,
            creators,
            seen,
            limit,
            include_details=include_details,
            collect_profile_urls=collect_profile_urls,
            detail_limit=detail_limit,
            page_number=page_number,
        )
        if len(creators) >= limit:
            break
        added = len(creators) - before_count
        before_signature = _creator_table_signature(page)
        clicked_next = _click_next_creator_page(page, target_page=page_number + 1)
        if clicked_next:
            if _wait_for_creator_table_change(page, before_signature, timeout_ms=12000):
                page_number += 1
                idle_rounds = 0
                continue
            page.wait_for_timeout(2500)
            if _has_valid_creator_rows(page) and _creator_table_signature(page) != before_signature:
                page_number += 1
                idle_rounds = 0
                continue
            if added > 0:
                page_number += 1
                idle_rounds = 0
                continue
        if _scroll_creator_list(page):
            page.wait_for_timeout(1000)
            if _creator_table_signature(page) != before_signature:
                idle_rounds = 0
                continue
        idle_rounds = idle_rounds + 1 if added == 0 else 0
        if idle_rounds >= 2 or added == 0:
            break
    return creators


def _click_text_if_visible(page: Any, text: str) -> bool:
    locator = page.locator(".blogger-list_filter").get_by_text(text, exact=True)
    if not locator.count():
        locator = page.get_by_text(text, exact=True)
    clicked = _click_first_visible(locator)
    if clicked:
        page.wait_for_timeout(500)
    return clicked


def _click_filter_checkbox(page: Any, text: str) -> bool:
    checkbox = page.locator(".blogger-list_filter .d-checkbox").filter(has_text=text)
    try:
        count = min(checkbox.count(), 20)
    except Exception:
        return False
    for index in range(count):
        candidate = checkbox.nth(index)
        if "disabled" in ((candidate.get_attribute("class") or "").lower()):
            continue
        simulator = candidate.locator(".d-checkbox-simulator").first
        simulator_class = simulator.get_attribute("class") if simulator.count() else ""
        if "checked" in (simulator_class or ""):
            return True
        try:
            candidate.scroll_into_view_if_needed(timeout=1200)
            candidate.click(timeout=1500)
            page.wait_for_timeout(500)
            return True
        except Exception:
            continue
    return False


def _click_filter_tag(page: Any, text: str) -> bool:
    tag = page.locator(".blogger-list_filter .tag, .blogger-list_filter .selector-body-options *").filter(has_text=re.compile(f"^{re.escape(text)}$"))
    try:
        count = min(tag.count(), 30)
    except Exception:
        return False
    for index in range(count):
        candidate = tag.nth(index)
        class_name = candidate.get_attribute("class") or ""
        if "disabled" in class_name:
            continue
        if "active" in class_name:
            return True
        try:
            candidate.scroll_into_view_if_needed(timeout=1200)
            candidate.click(timeout=1500)
            page.wait_for_timeout(700)
            return True
        except Exception:
            continue
    return False


def _find_filter_trigger(page: Any, field: str) -> Any:
    selectors = [
        ".blogger-list_filter .custom-selector__button",
        ".blogger-list_filter button.dropdown-button",
        ".blogger-list_filter .tag",
    ]
    field_pattern = re.compile(f"^\\s*(?:新\\s*)?{re.escape(field)}\\s*$")
    for selector in selectors:
        locator = page.locator(selector).filter(has_text=field_pattern)
        try:
            count = min(locator.count(), 10)
        except Exception:
            continue
        for index in range(count):
            candidate = locator.nth(index)
            if _is_visible(candidate):
                return candidate
    return None


def _popover_for_trigger(page: Any, trigger: Any) -> Any:
    try:
        box = trigger.bounding_box(timeout=1000) or {}
        trigger_x = float(box.get("x") or 0)
        trigger_y = float(box.get("y") or 0)
    except Exception:
        trigger_x = 0
        trigger_y = 0
    popovers = page.locator(".d-popover, .filter-select-popover")
    try:
        count = min(popovers.count(), 120)
    except Exception:
        return None
    best = None
    best_score = 10**9
    for index in reversed(range(count)):
        popover = popovers.nth(index)
        try:
            box = popover.bounding_box(timeout=800) or {}
            x = float(box.get("x") or 0)
            y = float(box.get("y") or 0)
            width = float(box.get("width") or 0)
            height = float(box.get("height") or 0)
            if width <= 0 or height <= 0:
                continue
        except Exception:
            continue
        score = abs(x - trigger_x) + abs(y - trigger_y)
        if score < best_score:
            best = popover
            best_score = score
    return best


def _open_filter_popover(page: Any, field: str) -> tuple[Any, str]:
    trigger = _find_filter_trigger(page, field)
    if trigger is None:
        return None, "页面未找到筛选控件"
    try:
        _reset_creator_list_scroll(page)
        page.wait_for_timeout(150)
        if not _click_locator(page, trigger, timeout=1800):
            return None, "打开筛选控件失败：点击未生效"
        page.wait_for_timeout(600)
    except Exception as error:
        return None, f"打开筛选控件失败：{error}"
    popover = _popover_for_trigger(page, trigger)
    if popover is None:
        return None, "筛选弹层未出现"
    return popover, "已打开筛选弹层"


def _click_popover_confirm(page: Any, popover: Any) -> bool:
    confirm = popover.locator("button, .d-button").filter(has_text=re.compile("^\\s*确定\\s*$")).last
    try:
        if confirm.count():
            confirm.click(timeout=1500)
            page.wait_for_timeout(800)
            return True
    except Exception:
        pass
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    return False


def _marketing_goal_parent(item: dict[str, Any]) -> str:
    value = _item_selection_value(item)
    parent = str(item.get("goal") or item.get("parent_value") or item.get("parentValue") or "").strip()
    if not parent and value in PGY_MARKETING_GOAL_DEFAULT_METRIC:
        parent = value
    if not parent:
        parent = PGY_MARKETING_GOAL_METRIC_PARENT.get(value) or ""
    return parent


def _marketing_goal_metric(item: dict[str, Any]) -> str:
    value = _item_selection_value(item)
    return PGY_MARKETING_GOAL_DEFAULT_METRIC.get(value) or value


def _click_marketing_goal_parent(page: Any, parent: str) -> tuple[Any, str]:
    if not parent:
        return None, "营销目标缺少父级目标"
    for selector in [
        ".blogger-list_filter .tag",
        ".blogger-list_filter .selector-body-options *",
        ".blogger-list_filter button",
        ".blogger-list_filter *",
    ]:
        candidates = page.locator(selector).filter(has_text=re.compile(f"^\\s*{re.escape(parent)}\\s*$"))
        try:
            count = min(candidates.count(), 30)
        except Exception:
            continue
        for index in range(count):
            candidate = candidates.nth(index)
            try:
                if not _is_visible(candidate):
                    continue
                if not _click_locator(page, candidate, timeout=1800):
                    continue
                page.wait_for_timeout(650)
                popover = _popover_for_trigger(page, candidate) or _last_visible_popover(page)
                if popover is not None:
                    return popover, "已打开营销目标弹层"
            except Exception:
                continue
    return None, f"页面未找到营销目标父级：{parent}"


def _apply_marketing_goal_group(page: Any, parent: str, items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    pending = [item for item in items if not _filter_already_selected(page, item)]
    for item in items:
        if item not in pending:
            applied.append({**item, "message": "页面已存在该筛选条件"})
    if not pending:
        return applied, skipped

    popover, message = _click_marketing_goal_parent(page, parent)
    if popover is None:
        for item in pending:
            skipped.append({**item, "message": message})
        return applied, skipped

    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for item in pending:
        metric = _marketing_goal_metric(item)
        selected = False
        for candidate in _filter_value_candidates({**item, "value": metric}):
            if _select_popover_checkbox(page, popover, candidate):
                selected = True
                break
        if selected:
            successes.append({**item, "value": metric, "message": f"已选择{parent}下的{metric}"})
        else:
            failures.append({**item, "value": metric, "message": f"营销目标弹层内未找到指标：{metric}"})

    _click_popover_confirm(page, popover)
    return [*applied, *successes], [*skipped, *failures]


def _select_popover_checkbox(page: Any, popover: Any, text: str) -> bool:
    for selector in [".d-checkbox", ".d-dropdown-option", ".d-options *", ".tag", "label", "button", "*"]:
        option = popover.locator(selector).filter(has_text=re.compile(f"^\\s*{re.escape(text)}\\s*$")).first
        try:
            if not option.count() or not _is_visible(option):
                continue
            if selector == ".d-checkbox" and _checkbox_checked(option):
                return True
            if not _click_locator(page, option, timeout=1500):
                continue
            page.wait_for_timeout(300)
            return True
        except Exception:
            continue
    return False


def _click_popover_group(page: Any, popover: Any, group_label: str) -> bool:
    if not group_label:
        return False
    selectors = [
        ".range-select-content__left .range-select-item",
        ".d-new-cascader__option-list__item:first-child .d-new-cascader__option-wrapper",
        ".d-cascader-menu:first-child .d-cascader-menu-item",
        ".d-new-cascader__option-wrapper",
        ".range-select-item",
    ]
    pattern = re.compile(f"^\\s*{re.escape(group_label)}\\s*$")
    for selector in selectors:
        candidates = popover.locator(selector).filter(has_text=pattern)
        try:
            count = min(candidates.count(), 20)
        except Exception:
            continue
        for index in range(count):
            candidate = candidates.nth(index)
            try:
                if not _is_visible(candidate):
                    continue
                class_name = candidate.get_attribute("class") or ""
                if "--active" in class_name or "active" in class_name:
                    return True
                if _click_locator(page, candidate, timeout=1500):
                    page.wait_for_timeout(450)
                    return True
            except Exception:
                continue
    return False


def _select_grouped_popover_value(page: Any, popover: Any, item: dict[str, Any]) -> bool:
    field = str(item.get("field") or "")
    value = _item_selection_value(item)
    group = str(item.get("sub_field") or item.get("subField") or "")
    if not group:
        group = _infer_option_group(field, value)
    if group:
        _click_popover_group(page, popover, group)
    for candidate in _filter_value_candidates({**item, "value": value}):
        if _select_popover_checkbox(page, popover, candidate):
            return True
    if group:
        return False
    for inferred_group in [
        str(group_item.get("label") or "")
        for group_item in _catalog_option_groups(field)
        if value in (group_item.get("options") or [])
    ]:
        if _click_popover_group(page, popover, inferred_group) and _select_popover_checkbox(page, popover, value):
            return True
    return False


PGY_FOREIGN_REGION_OPTIONS = {"美国", "日本", "澳大利亚", "英国", "加拿大", "韩国", "法国", "德国", "新加坡", "其他"}
PGY_CHINA_REGION_OPTIONS = {
    "北京", "上海", "天津", "重庆", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东",
    "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏",
    "新疆", "香港", "澳门", "台湾",
}
PGY_REGION_ALIASES = {
    "北京/上海优先": ["北京", "上海"],
    "北京上海优先": ["北京", "上海"],
    "北上广深": ["北京", "上海", "广州", "深圳"],
    "一线": ["北京", "上海", "广州", "深圳"],
    "一线城市": ["北京", "上海", "广州", "深圳"],
}


def _region_targets_from_item(item: dict[str, Any]) -> list[str]:
    raw_values: list[str] = []
    for key in ("regions", "region_values", "input_values"):
        values = item.get(key)
        if isinstance(values, list):
            raw_values.extend(str(value) for value in values)
    for key in ("city", "province", "country"):
        value = str(item.get(key) or "").strip()
        if value:
            raw_values.append(value)
    raw_value = str(item.get("value") or "")
    raw_values.extend(PGY_REGION_ALIASES.get(raw_value) or [])
    raw_values.extend(re.split(r"[、,，/|｜\s]+", raw_value))
    targets: list[str] = []
    for value in raw_values:
        clean = value.strip(" ：:;；。优先重点必须地域要求地区城市IPip")
        if not clean or clean in {"中国", "国内", "全国", "不限"}:
            continue
        if clean in PGY_REGION_ALIASES:
            targets.extend(PGY_REGION_ALIASES[clean])
            continue
        if clean.endswith("市") and len(clean) <= 4:
            clean = clean[:-1]
        if clean.endswith("省") and len(clean) <= 4:
            clean = clean[:-1]
        if clean:
            targets.append(clean)
    return list(dict.fromkeys(targets))


def _click_cascade_option(page: Any, popover: Any, text: str, column_index: int | None = None, checkbox: bool | None = None) -> bool:
    if not text:
        return False
    column_selectors = [
        ".d-new-cascader__option-list__item",
        ".d-cascader-menu",
        ".range-select-content__column",
        ".range-select-content__left, .range-select-content__middle, .range-select-content__right",
    ]
    scopes: list[Any] = []
    if column_index is not None:
        for selector in column_selectors:
            columns = popover.locator(selector)
            try:
                if columns.count() > column_index:
                    scopes.append(columns.nth(column_index))
            except Exception:
                continue
    scopes.append(popover)
    selectors = [".d-checkbox", "label", ".d-new-cascader__option-wrapper", ".d-cascader-menu-item", ".range-select-item", "button", "*"]
    pattern = re.compile(f"^\\s*{re.escape(text)}\\s*$")
    for scope in scopes:
        for selector in selectors:
            candidates = scope.locator(selector).filter(has_text=pattern)
            try:
                count = min(candidates.count(), 30)
            except Exception:
                continue
            for index in range(count):
                candidate = candidates.nth(index)
                try:
                    if not _is_visible(candidate):
                        continue
                    if checkbox is True and _checkbox_checked(candidate):
                        return True
                    if _click_locator(page, candidate, timeout=1500):
                        page.wait_for_timeout(450)
                        return True
                except Exception:
                    continue
    return False


def _apply_region_cascade(page: Any, item: dict[str, Any]) -> tuple[bool, str]:
    field = str(item.get("field") or "地域")
    popover, message = _open_filter_popover(page, field)
    if popover is None:
        return False, message
    targets = _region_targets_from_item(item)
    if not targets:
        _click_popover_confirm(page, popover)
        return False, "地域条件未解析到可勾选国家/省市，已保留在采集计划中"

    selected: list[str] = []
    failed: list[str] = []
    china_targets = [target for target in targets if target not in PGY_FOREIGN_REGION_OPTIONS]
    foreign_targets = [target for target in targets if target in PGY_FOREIGN_REGION_OPTIONS]

    if china_targets:
        _click_cascade_option(page, popover, "全部", column_index=0, checkbox=True)
        _click_cascade_option(page, popover, "全部", column_index=0)
        if _click_cascade_option(page, popover, "中国", column_index=0, checkbox=True):
            for target in china_targets:
                clicked = False
                candidates = [target]
                if target in {"广州", "深圳"}:
                    candidates = ["广东", target]
                for candidate in candidates:
                    if _click_cascade_option(page, popover, candidate, column_index=1, checkbox=True):
                        clicked = True
                        break
                    if _click_cascade_option(page, popover, candidate, column_index=2, checkbox=True):
                        clicked = True
                        break
                if clicked:
                    selected.append(target)
                else:
                    failed.append(target)
        else:
            failed.extend(china_targets)

    for target in foreign_targets:
        if _click_cascade_option(page, popover, target, column_index=0, checkbox=True):
            selected.append(target)
        else:
            failed.append(target)

    _click_popover_confirm(page, popover)
    if selected:
        suffix = f"；未找到：{'、'.join(failed)}" if failed else ""
        return True, f"已选择地域：{'、'.join(selected)}{suffix}"
    return False, f"地域弹层内未找到匹配选项：{'、'.join(failed or targets)}"


def _visible_popovers(page: Any, selector: str = ".d-popover, .filter-select-popover") -> list[Any]:
    popovers = page.locator(selector)
    try:
        count = min(popovers.count(), 160)
    except Exception:
        return []
    visible: list[Any] = []
    for index in range(count):
        candidate = popovers.nth(index)
        if _is_visible(candidate):
            visible.append(candidate)
    return visible


def _last_visible_popover(page: Any, selector: str = ".d-popover, .filter-select-popover") -> Any:
    visible = _visible_popovers(page, selector)
    return visible[-1] if visible else None


def _subfield_aliases(field: str, sub_field: str) -> list[str]:
    aliases = [sub_field]
    if field == "预估互动单价" and sub_field == "图文笔记互动单价":
        aliases.append("预估图文互动单价")
    if field == "预估互动单价" and sub_field == "视频笔记互动单价":
        aliases.append("预估视频互动单价")
    if field == "预估阅读单价" and sub_field == "图文预估阅读单价":
        aliases.append("图文笔记阅读单价")
    if field == "预估阅读单价" and sub_field == "视频预估阅读单价":
        aliases.append("视频笔记阅读单价")
    return list(dict.fromkeys([item for item in aliases if item]))


def _find_subfield_selector(popover: Any, field: str, sub_field: str) -> Any:
    items = popover.locator(".filters-item")
    aliases = [_clean_text(item) for item in _subfield_aliases(field, sub_field)]
    try:
        count = min(items.count(), 20)
    except Exception:
        count = 0
    for index in range(count):
        item = items.nth(index)
        try:
            text = _clean_text(item.inner_text(timeout=800))
        except Exception:
            text = ""
        if aliases and not any(alias and alias in text for alias in aliases):
            continue
        selector = item.locator(".custom-selector__button, .d-input-wrapper, input[readonly]").first
        try:
            if selector.count() and _is_visible(selector):
                return selector
        except Exception:
            continue
    selectors = popover.locator(".custom-selector__button, input[readonly]")
    try:
        if selectors.count():
            return selectors.first
    except Exception:
        pass
    return None


def _fill_nested_number_range(nested: Any, min_value: Any, max_value: Any) -> int:
    inputs = nested.locator("input[type=text], input[type=number], input:not([type])")
    try:
        count = min(inputs.count(), 8)
    except Exception:
        return 0
    editable: list[Any] = []
    for index in range(count):
        input_box = inputs.nth(index)
        try:
            readonly = input_box.get_attribute("readonly")
            disabled = input_box.get_attribute("disabled")
            if readonly is not None or disabled is not None or not _is_visible(input_box):
                continue
            editable.append(input_box)
        except Exception:
            continue
    target_inputs = editable[-2:]
    values = [min_value, max_value] if len(target_inputs) >= 2 else [max_value]
    filled = 0
    for input_box, value in zip(target_inputs, values):
        if value is None or value == "":
            continue
        text_value = _format_filter_number(value)
        try:
            input_box.fill(text_value, timeout=1500)
            filled += 1
        except Exception:
            try:
                input_box.click(timeout=1000)
                input_box.press("Control+A")
                input_box.type(text_value, timeout=1500)
                filled += 1
            except Exception:
                try:
                    input_box.evaluate(
                        """
                        (node, value) => {
                          node.removeAttribute('readonly');
                          node.removeAttribute('disabled');
                          node.value = value;
                          node.dispatchEvent(new Event('input', { bubbles: true }));
                          node.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        """,
                        text_value,
                    )
                    filled += 1
                except Exception:
                    continue
    return filled


def _click_nested_confirm(page: Any, nested: Any) -> bool:
    confirm = nested.locator("button, .d-button").filter(has_text=re.compile("^\\s*确定\\s*$")).last
    try:
        if confirm.count() and _click_locator(page, confirm, timeout=1500):
            page.wait_for_timeout(700)
            return True
    except Exception:
        pass
    return False


def _apply_single_subfield_number_range(page: Any, popover: Any, item: dict[str, Any], sub_field: str) -> tuple[bool, str]:
    field = item.get("field") or ""
    value = str(item.get("value") or "")
    selector = _find_subfield_selector(popover, field, sub_field)
    if selector is None:
        return False, "弹层内未找到子字段选择框，已保留在采集计划中"
    if not _click_locator(page, selector, timeout=1500):
        return False, "子字段下拉未打开，已保留在采集计划中"
    page.wait_for_timeout(600)
    nested = _last_visible_popover(page, ".d-popover.filters-item-custom, .d-popover .filters-item-custom, .filter-select-popover")
    if nested is None:
        return False, "子字段区间弹层未出现，已保留在采集计划中"
    min_value, max_value = _range_for_subfield(item, sub_field)
    if max_value in (None, ""):
        match = re.search(r"[≤<]\s*([0-9]+(?:\.[0-9]+)?)", value)
        max_value = match.group(1) if match else ""
    filled = _fill_nested_number_range(nested, min_value, max_value)
    required_fills = 2 if min_value not in (None, "") and max_value not in (None, "") else 1
    if filled < required_fills:
        _click_nested_confirm(page, nested)
        return False, "子字段区间输入未完整填写，已保留在采集计划中"
    if not _click_nested_confirm(page, nested):
        return False, "子字段区间确认失败，已保留在采集计划中"
    if min_value not in (None, "") and max_value not in (None, ""):
        range_text = f"{_format_filter_number(min_value)}～{_format_filter_number(max_value)}"
    elif min_value not in (None, ""):
        range_text = f"{_format_filter_number(min_value)}以上"
    else:
        range_text = f"{_format_filter_number(max_value)}以下"
    return True, f"{sub_field or field} {range_text}"


def _apply_subfield_number_range(page: Any, item: dict[str, Any]) -> tuple[bool, str]:
    field = item.get("field") or ""
    popover, message = _open_filter_popover(page, field)
    if popover is None:
        return False, message
    default_subfields: str | list[str] = ["图文笔记", "视频笔记"] if field == "合作报价" else str(item.get("sub_field") or "")
    sub_fields = _subfield_names_from_item(item, default=default_subfields)
    if not sub_fields:
        sub_fields = [str(item.get("sub_field") or "")]
    successes: list[str] = []
    failures: list[str] = []
    for sub_field in sub_fields:
        success, detail = _apply_single_subfield_number_range(page, popover, item, sub_field)
        if success:
            successes.append(detail)
        else:
            failures.append(f"{sub_field or field}：{detail}")
    if not successes:
        _click_popover_confirm(page, popover)
        return False, "；".join(failures) or "子字段区间输入失败，已保留在采集计划中"
    _click_popover_confirm(page, popover)
    suffix = f"；部分失败：{'；'.join(failures)}" if failures else ""
    return True, f"已填写{field}自定义区间：{'；'.join(successes)}{suffix}"


def _apply_preset_or_number_range(page: Any, item: dict[str, Any]) -> tuple[bool, str]:
    field = item.get("field") or ""
    value = str(item.get("value") or "")
    popover, message = _open_filter_popover(page, field)
    if popover is None:
        return False, message
    candidates = _filter_value_candidates(item)
    for candidate in [candidate for candidate in dict.fromkeys(candidates) if candidate]:
        if _select_popover_checkbox(page, popover, candidate):
            _click_popover_confirm(page, popover)
            return True, "已在弹层中选择区间筛选项"
    parsed_min, parsed_max = _range_numbers_from_text(value)
    min_value = item.get("min", parsed_min if parsed_min is not None else "")
    max_value = item.get("max", parsed_max if parsed_max is not None else "")
    if min_value in (None, "") and max_value in (None, ""):
        _click_popover_confirm(page, popover)
        return False, "弹层内未找到匹配区间，已保留在采集计划中"
    filled = _fill_nested_number_range(popover, min_value, max_value)
    if filled < (2 if min_value not in (None, "") and max_value not in (None, "") else 1):
        _click_popover_confirm(page, popover)
        return False, "区间输入未完整填写，已保留在采集计划中"
    if not _click_popover_confirm(page, popover):
        return False, "区间筛选确认失败，已保留在采集计划中"
    return True, f"已填写{field}自定义区间 {_format_filter_number(min_value)}～{_format_filter_number(max_value)}"


def _fill_popover_text_inputs(popover: Any, values: list[str]) -> int:
    filled = 0
    if not values:
        return filled
    inputs = popover.locator("input[type=text], textarea")
    try:
        count = min(inputs.count(), len(values))
    except Exception:
        return filled
    for index in range(count):
        value = values[index]
        if not value:
            continue
        try:
            input_box = inputs.nth(index)
            input_box.fill(str(value), timeout=1500)
            filled += 1
        except Exception:
            continue
    return filled


def _apply_popover_filter_item(page: Any, item: dict[str, Any]) -> tuple[bool, str]:
    field = item.get("field") or ""
    value = str(item.get("value") or "")
    control_type = item.get("control_type") or ""
    if control_type in {"marketing_goal_metric"}:
        parent = _marketing_goal_parent(item)
        applied, skipped = _apply_marketing_goal_group(page, parent, [item])
        if applied:
            return True, applied[-1].get("message") or "已选择营销目标指标"
        return False, (skipped[-1].get("message") if skipped else "营销目标筛选失败，已保留在采集计划中")
    if control_type in {"text_multi_with_exclude", "searchable_multi_select_with_exclude"}:
        popover, message = _open_filter_popover(page, field)
        if popover is None:
            return False, message
        values = item.get("input_values")
        if not isinstance(values, list):
            values = [part.strip() for part in re.split(r"[、,，/]+", value) if part.strip()]
        filled = _fill_popover_text_inputs(popover, [str(part) for part in values])
        if item.get("exclude") or "剔除" in value:
            _select_popover_checkbox(page, popover, "剔除上述品牌已合作博主")
        _click_popover_confirm(page, popover)
        if filled:
            suffix = "；品牌不足3个，已保留待补充" if filled < int(item.get("min_items") or 0) else ""
            return True, f"已填写文本筛选项{suffix}"
        return False, "该筛选项需要填写品牌名称，已保留待补充"
    if control_type in {"checkbox_popover", "dropdown", "select_popover", "single_select_popover", "dropdown_single", "nested_select_popover"}:
        popover, message = _open_filter_popover(page, field)
        if popover is None:
            return False, message
        if control_type == "nested_select_popover":
            _click_popover_confirm(page, popover)
            return False, "该条件打开后仍有下拉选项，需要继续选择，已保留在采集计划中"
        if _select_grouped_popover_value(page, popover, item):
            _click_popover_confirm(page, popover)
            return True, "已在弹层中选择筛选项"
        _click_popover_confirm(page, popover)
        return False, "弹层内未找到匹配选项，已保留在采集计划中"
    if control_type in {"brand_search_recommendation"}:
        return False, "该条件需要在右上角合作品牌/竞品搜索入口选择品牌，已保留在采集计划中"
    if control_type in {"subfield_preset_or_number_range", "subfield_preset_or_percent_range", "multi_subfield_preset_or_number_range"}:
        return _apply_subfield_number_range(page, item)
    if control_type in {"range_select_pair", "number_range", "preset_or_number_range", "preset_or_percent_range"}:
        return _apply_preset_or_number_range(page, item)
    if control_type in {"cascade_checkbox_popover", "three_level_cascade_checkbox_popover"}:
        if field in {"地域", "粉丝地域"}:
            return _apply_region_cascade(page, item)
        return False, "该条件需要区间/子筛选/级联细分，已保留在采集计划中"
    return False, ""


def _apply_filter_item(page: Any, item: dict[str, Any]) -> tuple[bool, str]:
    value = item.get("value") or ""
    field = item.get("field") or ""
    if _filter_already_selected(page, item):
        return True, "页面已存在该筛选条件"
    popover_success, popover_message = _apply_popover_filter_item(page, item)
    if popover_success or popover_message:
        return popover_success, popover_message
    candidates = _filter_value_candidates(item)
    if field in {"平台推荐", "常规剔除"}:
        for candidate in candidates:
            if _click_filter_checkbox(page, candidate):
                return True, "已勾选复选筛选项"
        return False, "未找到可勾选的复选筛选项"
    for candidate in candidates:
        if _click_filter_tag(page, candidate) or _click_text_if_visible(page, candidate):
            return True, "已点击页面筛选项"
    if value.endswith("优先") or "/" in value or value in {"预估阅读/互动单价"}:
        return False, "该条件需要下拉/区间细分，已保留在采集计划中"
    return False, "页面未找到可直接点击的筛选项"


def _checkbox_checked(checkbox: Any) -> bool:
    input_box = checkbox.locator("input[type=checkbox]").first
    try:
        if input_box.count():
            return bool(input_box.is_checked(timeout=500))
    except Exception:
        pass
    for attr in ["aria-checked", "data-checked", "checked"]:
        try:
            value = input_box.get_attribute(attr) if input_box.count() else checkbox.get_attribute(attr)
        except Exception:
            value = None
        if str(value).lower() in {"true", "checked", "1"}:
            return True
    simulator = checkbox.locator(".d-checkbox-simulator").first
    try:
        if simulator.count() and "checked" in (simulator.get_attribute("class") or "").lower():
            return True
    except Exception:
        pass
    try:
        return "checked" in (checkbox.get_attribute("class") or "").lower()
    except Exception:
        return False


def _radio_checked(radio: Any) -> bool:
    simulator = radio.locator(".d-radio-simulator").first
    if not simulator.count():
        return False
    return "checked" in (simulator.get_attribute("class") or "")


def _metric_candidates(metric: str) -> list[str]:
    aliases = PGY_METRIC_ALIASES.get(metric) or []
    if metric.endswith("（日常）"):
        aliases.append(metric.replace("（日常）", ""))
    return list(dict.fromkeys([metric, *aliases]))


def _visible_table_text(page: Any) -> str:
    try:
        table = page.locator(".blogger-list_list .d-new-table, .blogger-list_list").first
        if table.count():
            return table.inner_text(timeout=2500)
    except Exception:
        pass
    try:
        return page.locator("body").inner_text(timeout=2500)
    except Exception:
        return ""


def _metric_already_displayed(page: Any, metric: str) -> bool:
    text = _clean_text(_visible_table_text(page))
    if not text:
        return False
    if metric in {PGY_ALL_NON_LIVE_METRICS, "__ALL_NON_LIVE__"}:
        return all(_clean_text(item) in text for item in PGY_REQUIRED_NON_LIVE_METRICS)
    return any(_clean_text(candidate) in text for candidate in _metric_candidates(metric))


def _display_metrics_already_ready(page: Any, metrics: list[str]) -> bool:
    return bool(metrics) and all(_metric_already_displayed(page, metric) for metric in metrics)


def _selected_modal_metrics(modal: Any) -> set[str]:
    try:
        text = modal.evaluate(
            """
            node => {
              const blocks = Array.from(node.querySelectorAll('*'))
                .filter(el => /已添加/.test(el.textContent || ''));
              const right = blocks
                .sort((a, b) => (b.getBoundingClientRect().left - a.getBoundingClientRect().left))[0] || node;
              return right.innerText || right.textContent || '';
            }
            """
        )
    except Exception:
        try:
            text = modal.inner_text(timeout=1200)
        except Exception:
            text = ""
    lines = _visible_text_lines(str(text or ""))
    ignore = {"已添加", "清空", "以上为横向固定列", "博主信息", "操作", "近期笔记"}
    return {_clean_text(line) for line in lines if line and line not in ignore and not line.startswith("已添加")}


def _required_modal_metrics(metrics: list[str]) -> list[str]:
    required: list[str] = []
    for metric in metrics:
        if metric in {PGY_ALL_NON_LIVE_METRICS, "__ALL_NON_LIVE__"}:
            required.extend(PGY_REQUIRED_NON_LIVE_METRICS)
        else:
            required.append(metric)
    return list(dict.fromkeys(required))


def _modal_metrics_ready(modal: Any, metrics: list[str]) -> bool:
    selected_text = "".join(_selected_modal_metrics(modal))
    if not selected_text:
        return False
    for metric in _required_modal_metrics(metrics):
        candidates = _metric_candidates(metric)
        if not any(_clean_text(candidate) in selected_text for candidate in candidates):
            return False
    return True


def _ensure_modal_option(page: Any, modal: Any, metric: str) -> tuple[bool, str]:
    for candidate in _metric_candidates(metric):
        checkbox = modal.locator(".d-checkbox").filter(has_text=re.compile(f"^{re.escape(candidate)}$")).first
        if checkbox.count():
            if _checkbox_checked(checkbox):
                return True, "已选中"
            try:
                checkbox.scroll_into_view_if_needed(timeout=2000)
                checkbox.click(timeout=2000)
                page.wait_for_timeout(250)
                if _checkbox_checked(checkbox):
                    return True, "已勾选"
                return False, "点击后未变为选中"
            except Exception as error:
                return False, f"勾选失败：{error}"
        radio = modal.locator(".d-radio-group .d-radio, .d-radio-group > *").filter(has_text=re.compile(f"^{re.escape(candidate)}$")).first
        if radio.count():
            if _radio_checked(radio):
                return True, "已选中"
            try:
                radio.scroll_into_view_if_needed(timeout=2000)
                radio.click(timeout=2000)
                page.wait_for_timeout(250)
                return (True, "已选择") if _radio_checked(radio) else (False, "点击后未变为选中")
            except Exception as error:
                return False, f"选择失败：{error}"
    return False, "弹窗内未找到该指标"


def _modal_scroll_state(modal: Any) -> tuple[int, int]:
    try:
        payload = modal.evaluate(
            """
            node => {
              const scrollables = Array.from(node.querySelectorAll('*'))
                .filter(el => el.scrollHeight > el.clientHeight + 8);
              const target = scrollables
                .sort((a, b) => (b.clientHeight * b.clientWidth) - (a.clientHeight * a.clientWidth))[0];
              if (!target) return { top: 0, max: 0 };
              return { top: Math.round(target.scrollTop), max: Math.round(target.scrollHeight - target.clientHeight) };
            }
            """
        )
        return int(payload.get("top") or 0), int(payload.get("max") or 0)
    except Exception:
        return 0, 0


def _scroll_modal_options(modal: Any) -> bool:
    try:
        before, max_top = _modal_scroll_state(modal)
        after = modal.evaluate(
            """
            node => {
              const scrollables = Array.from(node.querySelectorAll('*'))
                .filter(el => el.scrollHeight > el.clientHeight + 8);
              const target = scrollables
                .sort((a, b) => (b.clientHeight * b.clientWidth) - (a.clientHeight * a.clientWidth))[0];
              if (!target) return 0;
              target.scrollTop = Math.min(target.scrollTop + Math.max(320, Math.floor(target.clientHeight * 0.75)), target.scrollHeight);
              return Math.round(target.scrollTop);
            }
            """
        )
        return int(after or 0) > before and before < max_top
    except Exception:
        return False


def _ensure_all_non_live_modal_options(page: Any, modal: Any) -> dict[str, list[dict[str, str]]]:
    selected: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    seen: set[str] = set()
    idle_rounds = 0
    for _ in range(25):
        before_seen_count = len(seen)
        checkboxes = modal.locator(".d-checkbox")
        try:
            count = min(checkboxes.count(), 500)
        except Exception:
            count = 0
        for index in range(count):
            checkbox = checkboxes.nth(index)
            try:
                label = " ".join(_visible_text_lines(checkbox.inner_text(timeout=800)))
            except Exception:
                label = f"指标{index + 1}"
            if not label or label in seen:
                continue
            seen.add(label)
            class_name = (checkbox.get_attribute("class") or "").lower()
            try:
                checked = _checkbox_checked(checkbox)
            except Exception:
                checked = False
            if "直播" in label:
                skipped.append({"metric": label, "message": "直播数据已排除；保持当前选择状态" if checked else "直播数据已排除"})
                continue
            if "disabled" in class_name and not checked:
                skipped.append({"metric": label, "message": "指标不可选"})
                continue
            try:
                checkbox.scroll_into_view_if_needed(timeout=1500)
                if checked:
                    selected.append({"metric": label, "message": "已选中，未重复点击"})
                    continue
                checkbox.click(timeout=1500)
                page.wait_for_timeout(150)
                if _checkbox_checked(checkbox):
                    selected.append({"metric": label, "message": "已勾选"})
                else:
                    skipped.append({"metric": label, "message": "点击后未变为选中，已跳过以避免误取消"})
            except Exception as error:
                skipped.append({"metric": label, "message": f"勾选失败：{error}"})
        if not _scroll_modal_options(modal):
            break
        page.wait_for_timeout(300)
        idle_rounds = idle_rounds + 1 if len(seen) == before_seen_count else 0
        if idle_rounds >= 3:
            break
    if not selected and not skipped:
        skipped.append({"metric": PGY_ALL_NON_LIVE_METRICS, "message": "弹窗内没有识别到指标项"})
    return {"selected_metrics": selected, "skipped_metrics": skipped}


def _ensure_display_metrics(page: Any, metrics: list[str]) -> dict[str, list[dict[str, str]]]:
    selected: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    if not metrics:
        return {"selected_metrics": selected, "skipped_metrics": skipped}
    if _display_metrics_already_ready(page, metrics):
        return {
            "selected_metrics": [{"metric": metric, "message": "页面已展示，跳过重复勾选"} for metric in metrics],
            "skipped_metrics": skipped,
        }
    button = page.locator("button").filter(has_text="选择展示指标").last
    if not button.count():
        return {
            "selected_metrics": selected,
            "skipped_metrics": [{"metric": metric, "message": "页面未找到选择展示指标按钮"} for metric in metrics],
        }
    try:
        button.scroll_into_view_if_needed(timeout=2000)
        button.click(timeout=3000)
        page.wait_for_timeout(800)
    except Exception as error:
        return {
            "selected_metrics": selected,
            "skipped_metrics": [{"metric": metric, "message": f"打开展示指标弹窗失败：{error}"} for metric in metrics],
        }
    modal = page.locator(".d-modal.custom-data-model, .d-modal").last
    try:
        modal.wait_for(state="visible", timeout=5000)
    except Exception:
        return {
            "selected_metrics": selected,
            "skipped_metrics": [{"metric": metric, "message": "展示指标弹窗未出现"} for metric in metrics],
        }
    if _modal_metrics_ready(modal, metrics):
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return {
            "selected_metrics": [{"metric": metric, "message": "自定义列已保留完整配置，跳过重复勾选"} for metric in metrics],
            "skipped_metrics": skipped,
        }
    if any(metric in {PGY_ALL_NON_LIVE_METRICS, "__ALL_NON_LIVE__"} for metric in metrics):
        result = _ensure_all_non_live_modal_options(page, modal)
        selected.extend(result["selected_metrics"])
        skipped.extend(result["skipped_metrics"])
    else:
        for metric in metrics:
            success, message = _ensure_modal_option(page, modal, metric)
            target = selected if success else skipped
            target.append({"metric": metric, "message": message})
    confirm = modal.locator("button").filter(has_text="确定").last
    try:
        if confirm.count():
            confirm.click(timeout=3000)
            page.wait_for_timeout(1500)
        else:
            page.keyboard.press("Escape")
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    return {"selected_metrics": selected, "skipped_metrics": skipped}


def apply_collection_plan(page: Any, plan: dict[str, Any]) -> dict[str, Any]:
    applied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    grouped_marketing_goals: dict[str, list[dict[str, Any]]] = {}
    regular_filters: list[dict[str, Any]] = []
    for item in plan.get("filters") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("field") or "") == "营销目标" or str(item.get("control_type") or "") == "marketing_goal_metric":
            parent = _marketing_goal_parent(item)
            grouped_marketing_goals.setdefault(parent, []).append(item)
        else:
            regular_filters.append(item)
    for parent, items in grouped_marketing_goals.items():
        group_applied, group_skipped = _apply_marketing_goal_group(page, parent, items)
        applied.extend(group_applied)
        skipped.extend(group_skipped)
    for item in regular_filters:
        success, message = _apply_filter_item(page, item)
        if success:
            applied.append({**item, "message": message})
        else:
            skipped.append({**item, "message": message})
    if applied:
        page.wait_for_timeout(1800)
    metric_result = _ensure_display_metrics(page, [str(item) for item in plan.get("display_metrics") or []])
    return {"applied_filters": applied, "skipped_filters": skipped, **metric_result}


def _read_visible_collection_state(page: Any) -> dict[str, Any]:
    rows = _creator_list_rows(page)
    try:
        rows.first.wait_for(state="visible", timeout=8000)
    except Exception:
        pass
    try:
        raw_count = rows.count()
    except Exception:
        raw_count = 0
    count = 0
    for index in range(min(raw_count, 30)):
        try:
            row_text = rows.nth(index).inner_text(timeout=800)
        except Exception:
            continue
        if _parse_row_text(row_text, page.url):
            count += 1
    return {
        "rows": rows,
        "count": count,
        "empty_hint": _page_empty_result_hint(page),
    }


def _apply_relaxed_plan_after_empty_result(page: Any, plan: dict[str, Any], plan_result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    current_plan = plan
    current_result = plan_result
    current_state = _read_visible_collection_state(page)
    if current_state["count"] > 0 or not current_state["empty_hint"]:
        return current_plan, current_result, current_state

    attempts = [("broad", False), ("unfiltered", True)]
    for stage, reset_filters in attempts:
        relaxed_plan = _relaxed_collection_plan(plan, stage)
        if relaxed_plan is None:
            continue
        try:
            if reset_filters or "/solar/pre-trade/note/kol" in page.url:
                page.goto(PGY_KOL_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
        except Exception:
            pass
        retry_result = apply_collection_plan(page, relaxed_plan) if relaxed_plan.get("filters") else {
            "applied_filters": [],
            "skipped_filters": [],
            "selected_metrics": [],
            "skipped_metrics": [],
        }
        if not relaxed_plan.get("filters"):
            metrics_result = _ensure_display_metrics(page, [str(item) for item in relaxed_plan.get("display_metrics") or []])
            retry_result = {**retry_result, **metrics_result}
        retry_state = _read_visible_collection_state(page)
        merged_result = _merge_plan_results(current_result, retry_result, relaxed_plan.get("relaxation") or {})
        if retry_state["count"] > 0 or not retry_state["empty_hint"]:
            return relaxed_plan, merged_result, retry_state
        current_plan = relaxed_plan
        current_result = merged_result
        current_state = retry_state
    return current_plan, current_result, current_state


def _extract_recommendation_count(page: Any) -> dict[str, Any]:
    try:
        text = page.locator("body").inner_text(timeout=3000)
    except Exception as error:
        return {"actual_recommend_count": None, "actual_count_text": "", "actual_count_error": f"读取推荐博主数失败：{error}"}
    patterns = [
        r"推荐\s*([0-9][0-9,，.]*)\s*(万|\+)?\s*位?博主",
        r"推荐博主\s*([0-9][0-9,，.]*)\s*(万|\+)?",
        r"共\s*([0-9][0-9,，.]*)\s*(万|\+)?\s*位?博主",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        number_text = match.group(1).replace(",", "").replace("，", "")
        suffix = match.group(2) or ""
        try:
            value = float(number_text)
        except ValueError:
            continue
        if suffix == "万":
            value *= 10000
        return {
            "actual_recommend_count": int(value),
            "actual_count_text": match.group(0),
            "actual_count_is_lower_bound": suffix == "+",
        }
    return {"actual_recommend_count": None, "actual_count_text": "", "actual_count_error": "页面未识别到“推荐 N 位博主”文案"}


def _export_current_table(page: Any) -> dict[str, Any]:
    export_button = page.locator("button").filter(has_text=re.compile("导出|下载")).last
    if not export_button.count():
        return {"status": "skipped", "message": "页面未找到导出按钮"}
    export_dir = ROOT / "runtime" / "exports" / "pgy"
    export_dir.mkdir(parents=True, exist_ok=True)
    try:
        export_button.scroll_into_view_if_needed(timeout=2000)
        with page.expect_download(timeout=10000) as download_info:
            export_button.click(timeout=3000)
        download = download_info.value
        filename = download.suggested_filename or "pgy-export.csv"
        path = export_dir / filename
        download.save_as(str(path))
        parsed = parse_export_file(path)
        return {"status": "success", "message": "蒲公英列表已导出", "path": str(path), "parsed": parsed}
    except Exception as error:
        return {"status": "failed", "message": f"导出未完成：{error}"}


def browser_status() -> dict[str, Any]:
    try:
        response = requests.get(CDP_URL, timeout=2)
        if response.ok:
            payload = response.json()
            return {
                "connected": True,
                "message": "已连接 Chrome 调试端口",
                "webSocketDebuggerUrl": payload.get("webSocketDebuggerUrl"),
                "browser": payload.get("Browser"),
            }
    except requests.RequestException:
        pass
    return {
        "connected": False,
        "message": "未检测到 Chrome 调试端口，请先启动调试浏览器并登录蒲公英",
        "start_command": 'Start-Process "<chrome.exe>" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=<project>\\runtime\\chrome-pgy-profile"',
    }


def _find_chrome_exe() -> Path | None:
    candidates = [
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    ]
    local_app_data = Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"
    candidates.append(local_app_data)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def start_browser() -> dict[str, Any]:
    status = browser_status()
    if status["connected"]:
        return status
    chrome = _find_chrome_exe()
    if not chrome:
        return {"connected": False, "message": "未找到 Chrome，请手动用调试端口启动浏览器"}
    profile = ROOT / "runtime" / "chrome-pgy-profile"
    profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            str(chrome),
            "--remote-debugging-port=9222",
            f"--user-data-dir={profile}",
            PGY_KOL_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return {**browser_status(), "message": "已尝试启动独立 Chrome，请在打开的页面登录蒲公英"}


def collect_visible_list(
    brief: str = "",
    screening_plan: dict[str, Any] | None = None,
    apply_filters: bool = True,
    limit: int = 1000,
    include_details: bool = True,
    collect_profile_urls: bool = True,
    export_metrics: bool = True,
    reset_filters: bool = False,
    preflight_only: bool = False,
) -> dict[str, Any]:
    if not browser_status()["connected"]:
        return {"ok": False, "message": "未连接 Chrome 调试端口"}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "message": "当前环境未安装 Playwright，无法执行真实页面采集"}

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            pages = context.pages
            page = next((item for item in pages if "pgy.xiaohongshu.com" in item.url), pages[0] if pages else context.new_page())
            _install_kol_response_capture(page)
            setattr(page, "_pgy_latest_api_kols", [])
            if (
                "pgy.xiaohongshu.com" not in page.url
                or "/solar/pre-trade/note/kol" not in page.url
                or reset_filters
            ):
                page.goto(PGY_KOL_URL, wait_until="domcontentloaded", timeout=30000)
            if "/solar/pre-trade/note/kol" not in page.url:
                return {"ok": False, "message": "请先打开蒲公英博主广场 / 找博主页面", "current_url": page.url}
            page.wait_for_timeout(1500)
            login_hint = page.locator("text=登录").first
            if login_hint.count() and "login" in page.url.lower():
                return {"ok": False, "message": "蒲公英尚未登录，请在打开的 Chrome 页面完成登录", "current_url": page.url}
            plan = build_collection_plan(brief, screening_plan)
            plan_result = (
                apply_collection_plan(page, plan)
                if apply_filters
                else {"applied_filters": [], "skipped_filters": [], "selected_metrics": [], "skipped_metrics": []}
            )
            active_plan = plan
            collection_state = _read_visible_collection_state(page)
            if apply_filters and collection_state["count"] == 0 and collection_state["empty_hint"]:
                active_plan, plan_result, collection_state = _apply_relaxed_plan_after_empty_result(page, plan, plan_result)
            recommendation_count = _extract_recommendation_count(page)
            if preflight_only:
                return {
                    "ok": True,
                    "current_url": page.url,
                    "collection_plan": active_plan,
                    **plan_result,
                    **recommendation_count,
                    "detail_collection": "preflight_only",
                    "export_result": {"status": "skipped", "message": "预检阶段不导出列表"},
                    "creators": [],
                }
            export_result = _export_current_table(page) if export_metrics else {"status": "skipped", "message": "本次未请求导出"}
            rows = collection_state["rows"]
            count = collection_state["count"]
            if count == 0:
                hint = collection_state.get("empty_hint")
                message = (
                    f"蒲公英页面提示「{hint}」，系统已尝试自动放宽筛选但仍无可采集列表"
                    if hint
                    else "未识别到博主列表，请确认已登录并停留在博主广场列表页"
                )
                return {
                    "ok": False,
                    "message": message,
                    "current_url": page.url,
                    "collection_plan": active_plan,
                    "export_result": export_result,
                    **plan_result,
                    **recommendation_count,
                }
            collect_limit = max(1, min(limit, 1000))
            creators = _extract_visible_creators(
                page,
                collect_limit,
                include_details=include_details,
                collect_profile_urls=collect_profile_urls,
                detail_limit=collect_limit if include_details else 0,
            )
            if not creators:
                return {
                    "ok": False,
                    "message": "已连接蒲公英页面，但未读取到有效达人内容。请确认列表加载完成后再采集，必要时滚动列表或刷新页面。",
                    "current_url": page.url,
                    "collection_plan": active_plan,
                    "export_result": export_result,
                    **plan_result,
                    **recommendation_count,
                }
            return {
                "ok": True,
                "creators": creators,
                "current_url": page.url,
                "collection_plan": active_plan,
                "detail_collection": "planned" if include_details else "skipped",
                "export_result": export_result,
                **recommendation_count,
                **plan_result,
            }
    except Exception as error:
        return {"ok": False, "message": f"蒲公英采集失败：{error}"}


def collect_details_for_targets(targets: list[dict[str, Any]], limit: int = 20) -> dict[str, Any]:
    if not targets:
        return {"ok": False, "message": "没有可补全详情页的初筛通过达人", "creators": []}
    if not browser_status()["connected"]:
        return {"ok": False, "message": "未连接 Chrome 调试端口"}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "message": "当前环境未安装 Playwright，无法执行真实页面采集"}

    target_limit = max(1, min(limit, 100))
    pending = targets[:target_limit]
    by_nickname = {str(item.get("nickname") or "").strip(): item for item in pending if item.get("nickname")}
    completed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            pages = context.pages
            page = next((item for item in pages if "pgy.xiaohongshu.com" in item.url), pages[0] if pages else context.new_page())
            if "pgy.xiaohongshu.com" not in page.url:
                page.goto(PGY_KOL_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1000)
            rows = page.locator(".blogger-list_list .d-new-table tbody tr").filter(has_not=page.locator(".skeleton-block"))
            try:
                row_count = min(rows.count(), 300)
            except Exception:
                row_count = 0
            matched_ids: set[str] = set()
            for index in range(row_count):
                row = rows.nth(index)
                creator = _parse_row_text(row.inner_text(timeout=2500), page.url)
                if not creator:
                    continue
                target = by_nickname.get(str(creator.get("nickname") or "").strip())
                if not target:
                    continue
                detail = _collect_first_detail_for_creator(context, row)
                if detail:
                    completed.append({**target, **detail, "creator_id": target.get("creator_id")})
                    matched_ids.add(str(target.get("creator_id")))
                else:
                    failed.append({"creator_id": target.get("creator_id"), "nickname": target.get("nickname"), "message": "详情页打开失败"})
            for target in pending:
                creator_id = str(target.get("creator_id") or "")
                if creator_id in matched_ids:
                    continue
                url = str(target.get("pgy_url") or target.get("profile_url") or "")
                if "/blogger-detail/" not in url:
                    if not any(item.get("creator_id") == creator_id for item in failed):
                        failed.append({"creator_id": creator_id, "nickname": target.get("nickname"), "message": "当前列表未找到该达人，且本地没有可打开的详情页链接"})
                    continue
                detail = _collect_detail_by_url(context, url)
                if detail:
                    completed.append({**target, **detail, "creator_id": creator_id})
                else:
                    failed.append({"creator_id": creator_id, "nickname": target.get("nickname"), "message": "详情页解析失败"})
        return {"ok": True, "creators": completed, "failed": failed, "message": f"详情页补全完成 {len(completed)} 个，失败 {len(failed)} 个"}
    except Exception as error:
        return {"ok": False, "message": f"详情页补全失败：{error}", "creators": completed, "failed": failed}
