export const DEFAULT_PGY_DISPLAY_METRICS = [
  '全部非直播指标',
];

export const WEIGHT_LABELS = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };

export const PGY_FOLLOWER_RANGE_OPTIONS = ['100万以上', '50万～100万', '10万～50万', '1万～10万', '0.5万～1万', '0.1万～0.5万'];
export const PGY_FAN_AGE_OPTIONS = ['<18 占比高', '18～24 占比高', '25～34 占比高', '35～44 占比高', '>44 占比高'];
export const PGY_MATERNAL_STAGE_OPTIONS = ['备孕', '0-6月', '7-12月', '1-3岁', '4-6岁', '7-12岁', '孕早期', '孕晚期'];
export const PGY_BLOGGER_CATEGORY_OPTIONS = [
  '美妆', '护肤', '个人护理', '母婴', '时尚', '美食', '家居家装', '影视综资讯',
  '运动健身', '宠物', '文化艺术', '兴趣爱好', '生活记录', '教育', '职场', '情感',
  '摄影', '游戏', '科技数码', '出行旅游', '音乐', '搞笑', '健康养生', '汽车',
  '婚嫁', '商业财经', '素材', '其他',
];
export const PGY_BLOGGER_CATEGORY_SUBCATEGORY_OPTIONS = {
  美妆: ['整体妆容', '唇妆', '眼妆', '美甲', '底妆', '美妆合集', '香水', '美妆其他'],
  护肤: ['面部保养', '面部清洁', '护肤合集', '护肤其他'],
  个人护理: ['头发产品', '身体护理', '口腔护理', '护理其他'],
  母婴: ['母婴日常', '早教', '婴童用品', '婴童洗护', '婴童食品', '婴童时尚', '孕期穿搭', '孕产经验', '产后恢复', '育儿经验', '宝宝才艺', '宝宝写真', '母婴其他'],
  时尚: ['穿搭', '配饰', '发型', '箱包', '鞋靴', '时尚其他'],
  美食: ['美食教程', '美食探店', '美食展示', '美食测评', '吃播', '美食其他'],
  家居家装: ['装修', '家居用品', '花艺园艺', '家居装饰', '家具', '家电', '室内设计', '居家经验', '家居家装其他'],
  影视综资讯: ['动漫', '娱乐资讯', '影视', '民生资讯', '综艺', '影视综其他'],
  运动健身: ['减脂塑形', '滑雪', '滑板', '水上活动', '运动其他', '足球', '篮球', '跑步', '游泳'],
  宠物: ['猫', '狗', '动物其他'],
  文化艺术: ['社科', '文化', '艺术', '文化艺术其他'],
  兴趣爱好: ['绘画', '手工', '阅读', '文具手账', '舞蹈', '兴趣爱好其他', '玩具周边'],
  生活记录: ['接地气生活', '日常片段', '中外生活', '品质生活', '校园生活'],
  教育: ['大学教育', 'k12教育', '家庭教育', '学习日常', '留学教育', '教育其他', '语言教育'],
  职场: ['职场干货', '职场行业', '职业考试', '职场其他'],
  情感: ['情感知识', '情感日常', '情感其他'],
  摄影: ['人文风光摄影', '摄影技巧', '胶片摄影', '人像摄影', '摄影其他'],
  游戏: ['手机游戏', '主机游戏', '游戏其他', '线下游戏'],
  科技数码: ['移动数码', '玩机攻略', '数码科技其他'],
  出行旅游: ['城市出行', '户外', '旅行'],
  音乐: [],
  搞笑: [],
  健康养生: [],
  汽车: ['用车攻略', '汽车评测', '汽车其他'],
  婚嫁: ['婚礼造型', '婚礼记录', '婚礼经验', '婚礼用品'],
  商业财经: [],
  素材: [],
  其他: [],
};
export const PGY_REGION_OPTIONS = ['北京', '上海', '广东', '浙江', '江苏', '四川', '湖北', '湖南', '山东', '河南'];
export const PGY_MARKETING_GOAL_OPTIONS = ['曝光', '种草', '转化'];
export const PGY_MARKETING_GOAL_GROUPS = [
  { label: '曝光', options: ['曝光表现', '阅读表现'] },
  { label: '种草', options: ['互动表现'] },
  { label: '转化', options: ['外溢进店表现'] },
];
export const PGY_MARKETING_GOAL_DEFAULT_METRIC = {
  曝光: '曝光表现',
  种草: '互动表现',
  转化: '外溢进店表现',
};
export const PGY_REGION_CASCADE_GROUPS = [
  {
    label: '中国',
    options: [
      { label: '北京', options: ['东城区', '西城区', '朝阳区', '海淀区', '丰台区', '石景山区', '通州区', '昌平区', '大兴区', '顺义区'] },
      { label: '上海', options: ['黄浦区', '徐汇区', '长宁区', '静安区', '普陀区', '虹口区', '杨浦区', '浦东新区', '闵行区', '宝山区'] },
      { label: '广东', options: ['广州', '深圳', '佛山', '东莞', '珠海', '中山', '惠州', '汕头'] },
      { label: '浙江', options: ['杭州', '宁波', '温州', '嘉兴', '绍兴', '金华'] },
      { label: '江苏', options: ['南京', '苏州', '无锡', '常州', '南通', '扬州'] },
      { label: '四川', options: ['成都', '绵阳', '德阳', '宜宾'] },
      { label: '湖北', options: ['武汉', '宜昌', '襄阳'] },
      { label: '湖南', options: ['长沙', '株洲', '湘潭'] },
      { label: '山东', options: ['济南', '青岛', '烟台'] },
      { label: '河南', options: ['郑州', '洛阳'] },
    ],
  },
  { label: '美国', options: [] },
  { label: '日本', options: [] },
  { label: '澳大利亚', options: [] },
  { label: '英国', options: [] },
  { label: '加拿大', options: [] },
  { label: '韩国', options: [] },
  { label: '法国', options: [] },
  { label: '德国', options: [] },
  { label: '新加坡', options: [] },
  { label: '其他', options: [] },
];
export const PGY_FAMILY_IDENTITY_GROUPS = [
  { label: '家庭角色', options: ['妈妈', '萌娃', '爸爸', '奶奶'] },
  { label: '出镜人关系', options: ['情侣', '夫妻', '家庭', '闺蜜', '兄弟'] },
  { label: '母婴阶段', options: ['备孕中', '孕期中', '0-6个月', '6-12个月', '1-3岁', '3-6岁', '6-12岁', '12岁以上'] },
];
export const PGY_CAREER_IDENTITY_GROUPS = [
  { label: '传统行业', options: ['工程师', '销售', 'HR'] },
  { label: '互联网', options: ['主播', '运营', '产品经理', '程序员'] },
  { label: '教育科研', options: ['学生'] },
  { label: '金融法律', options: ['金融从业者'] },
  { label: '企业创业', options: ['创业者', '品牌创始人', '公益人'] },
  { label: '时尚美妆', options: ['模特', '化妆师', '造型师', '服装设计师', '珠宝设计师', '发型设计师'] },
  { label: '食品饮料', options: ['甜点师', '厨师', '咖啡师', '调酒师'] },
  { label: '文化传媒', options: ['编辑', '记者', '翻译', '作家', '娱评人', '影评人', '乐评人'] },
  { label: '医疗健康', options: ['营养师', '医生', '康复师'] },
  { label: '艺术设计', options: ['摄影师', '插画师', '室内设计师', '画家', '平面设计师', '建筑设计师', '非遗传承人', '涂鸦艺术家', '数字艺术家'] },
  { label: '影视娱乐', options: ['主持人', '导演', '制片人', '编剧', '经纪人', '真人秀嘉宾', '虚拟偶像', 'rapper'] },
  { label: '运动健身', options: ['教练', '运动员', '舞蹈老师'] },
  { label: '专业服务', options: ['空乘', '花艺师', '整理师', '民宿主', '育婴师'] },
];
export const PGY_SPECIAL_BACKGROUND_GROUPS = [
  { label: '生活背景', options: ['留学背景', '海外华人', '铲屎官', '孕妈', '独居人群', '外国人', '混血儿'] },
  { label: '备考经验', options: ['考公过来人', '考研过来人', '法考过来人', '注会过来人'] },
  { label: '兴趣爱好', options: ['户外爱好者', '数码爱好者', '手账爱好者', '二次元人群', '汉服爱好者', '手办爱好者', '模型爱好者', '街舞爱好者', '骑行爱好者', '飞盘爱好者', '书法爱好者'] },
];
export const PGY_FAMILY_IDENTITY_OPTIONS = PGY_FAMILY_IDENTITY_GROUPS.flatMap(group => group.options);
export const PGY_CAREER_IDENTITY_OPTIONS = PGY_CAREER_IDENTITY_GROUPS.flatMap(group => group.options);
export const PGY_SPECIAL_BACKGROUND_OPTIONS = PGY_SPECIAL_BACKGROUND_GROUPS.flatMap(group => group.options);
export const PGY_AUDIENCE_20_GROUPS = [
  { label: '自在户外', options: ['挑战极限者', '野趣探索家', '短逃离自愈派', '心灵远行客', '户外显眼包', '户外欢聚团'] },
  { label: '自由畅行', options: ['都市漫游家', '静奢新贵', '爆改浓人', '出行精算师'] },
  { label: '运动焕活', options: ['轻松健体派', '线条雕塑家', '寻乐运动派', '好动局内人', '自我超越者', '身心觉察师'] },
  { label: '孕育学习', options: ['科研育儿党', '松驰爸妈', '友伴式父母', '积进式父母', '好孕预备役', '稳孕选手'] },
  { label: '娱乐放松', options: ['放松乐子人', '沉浸式“戏”迷', '娱乐交友派', '真爱忠粉'] },
  { label: '优奢享法', options: ['奢派生活家', '悦己摘星人', '潮奢风格家', '静奢知识分子', '奢品入门人', '奢交体面人'] },
  { label: '养身韧体', options: ['爆肝青年', '高能青年', '娇宠彼得潘', '高消耗中年', '稳定守成中年', '探索人生的中年玩家', '熟龄悦己中年', '活力夕阳红'] },
  { label: '虚拟人生', options: ['审美收藏控', '高能“偷闲”客', '沉浸式畅“游”人', '竞技大神', '通关小机灵', '联结小“玩伴”', '“游”文化信徒'] },
  { label: '美力加成', options: ['美养佳人', '风格日抛党', '精养奢美族', '变美练习生', '气场精英', '美研尖子生'] },
  { label: '心灵奇旅', options: ['亲密学习父母', '恋爱修炼家', '实用信徒', '野生玄学家', '精进修心客'] },
  { label: '文艺沉浸', options: ['情绪捕手', '美学鉴赏家', '规律钻研党', '热门玩家', '世界狂想家'] },
  { label: '数智未来', options: ['效能领航员', '灵感创想客', '未来原住民', '品质感官控', '数码时髦精'] },
  { label: '舌尖盛宴', options: ['好味饕客', '精算稳妥人', '食饮养生族', '吃喝欢聚派', '逐潮尝新客', '拓圈商务客', '专味信徒', '“怪味”猎手', '“乐养”零食客', '囤粮“小馋猫”', '生活“增味”家', '“纵情”高压党'] },
  { label: '看世界', options: ['轻松舒心派', '热门追踪党', '同心群游党', '求索漫旅人', '野地探险家', '圣地巡礼者', '追爱忠粉', '山水避世客'] },
  { label: '家有萌宠', options: ['自然“动物学家”', '同行伙伴', '宠溺“爸妈”', '爱宠观赏派', '流浪动物保护党'] },
  { label: '家生活', options: ['游牧青年', '筑巢青年', '全能生活家', '居家策展人'] },
  { label: '发现附近', options: ['下楼享受派', '社区玩咖', '市井“街溜子”', '圈层专研人', '“速联”社交狂', '举家“撒欢”党', '城郊出走族'] },
  { label: '成长进阶', options: ['争渡“上岸”人', '资格证“卷王”', '进阶专业精英', '职场闯关人', '兴趣研学家', '精英培优家', '“社会人”教练', '因材施教师', '尽责陪练员'] },
  { label: '时尚态度', options: ['追新之乐', '弄潮先锋', 'IP狂人', '街头潮客', '三坑玩家', '质感男士', '社会新鲜人', '气场大女主'] },
];
export const PGY_SKILLED_CONTENT_GROUPS = [
  { label: '形式', options: ['vlog', '探店', '测评', 'ootd', '合集', 'plog', '开箱', '教程', '成分解析', '彩妆试色', '仿妆', '沉浸式'] },
  { label: '风格', options: ['韩系', '日系', '欧美风', '氛围感', '纯欲', '甜酷', '复古', '高级感', '校园风', '中性风'] },
  { label: '生活方式', options: ['职场生活', '自律生活', '露营徒步', '极简主义', '低脂低卡'] },
  { label: '肤质肤色', options: ['油皮', '干皮', '混合肌', '敏感肌', '痘痘肌', '瑕疵皮', '白皮', '黄皮'] },
  { label: '皮肤养护', options: ['保湿补水', '美白', '淡斑', '祛黄', '抗氧化', '抗老', '祛皱', '抗炎', '修复', '祛痘祛闭口', '隔离防晒', '控油', '眼部护理'] },
];
export const PGY_CONTENT_SUBJECT_GROUPS = [
  { label: '汽车特色', options: ['沉浸式开车', '汽车美图'] },
  { label: '通用', options: ['大字报', '干货分享', '街头采访', '口播', '长文', '知识科普', '变装', '访谈', '梗图', '好物分享', '幽默搞笑', '挑战'] },
];
export const PGY_INDUSTRY_PORTRAIT_OPTIONS = [
  '家居家装', '日化家清', '多行业适用', '教育培训', '母婴', '汽车出行', '服饰鞋包', '美妆个护', '出行旅游', '珠宝配饰',
  '文玩娱乐', '奢侈品', '食品饮料', '到店综合', '宠物', '3C数码', '互联网', '家用电器', '运动户外', '本地生活', '行业通用人群',
  '家具', '家居百货', '灯饰光源', '装修设计与工程服务', '家居建材零售', '智能家居', '家装主材', '场景', '风格', '产品',
  '卧室兴趣人群', '餐厅兴趣人群', '客厅场景人群', '阳台兴趣用户', '厨房兴趣人群', '儿童房兴趣人群', '自我充电卧室',
  '多边形卧室', '高敏感卧室', '客厅兴趣人群', '浴室兴趣人群', '玄关兴趣人群', '造型卧室',
];
export const PGY_CONSUMPTION_BEHAVIOR_GROUPS = [
  { label: '预估车主作者', options: ['Porsche', 'ORA', 'MINI', 'MAZDA', 'BYD', '萤火虫', '一汽红旗', '一汽奥迪', '小鹏', '五菱', '蔚来', '特斯拉', '坦克', '斯巴鲁', '上汽大众', '梅赛德斯-奔驰', '路虎', '领克', '铃木', '理想', '雷克萨斯', '兰博基尼', '捷途', '江铃福特', '极越', '极氪', '吉普', '吉利银河', '哈弗', '广汽丰田', '福特', '宾利', '宝马', '奥迪', '阿维塔'] },
];
export const PGY_PRICE_RANGE_OPTIONS = ['5万及以上', '1万～5万', '0.5万～1万', '0.1万～0.5万', '0.1万以下'];
export const PGY_UNIT_PRICE_OPTIONS = ['0.5以下', '0.5～1.0', '1.0～1.5', '1.5～2.0', '2.0以上'];
export const PGY_NOTE_COUNT_RANGE_OPTIONS = ['5万以上', '1万～5万', '0.5万～1万', '0.1万～0.5万'];
export const PGY_INTERACTION_RANGE_OPTIONS = ['2000以上', '1000～2000', '500～1000', '200～500', '100～200'];
export const PGY_RATE_RANGE_OPTIONS = ['40%以上', '30%～40%', '20%～30%', '10%～20%', '10%以下'];
export const PGY_LIVE_COUNT_OPTIONS = ['0次', '1～5次', '6～10次', '10次以上'];
export const PGY_LIVE_VIEWER_OPTIONS = ['0~5k', '5k~1w', '1w~10w', '10w~50w', '50w以上'];
export const PGY_LIVE_SALES_OPTIONS = ['5千以下', '5千～1万', '1万～10万', '10万～50万', '50万～100万', '100万～200万', '200万～500万', '500万以上'];

export const PGY_FILTER_OPTIONS = [
  { field: '营销目标', value: '曝光表现', goal: '曝光', parent_value: '曝光', reason: 'Brief 提到曝光/声量目标', label: '营销目标：曝光-曝光表现', control_type: 'marketing_goal_metric', priority: 'low' },
  { field: '营销目标', value: '互动表现', goal: '种草', parent_value: '种草', reason: 'Brief 提到种草目标', label: '营销目标：种草-互动表现', control_type: 'marketing_goal_metric', priority: 'low' },
  { field: '营销目标', value: '外溢进店表现', goal: '转化', parent_value: '转化', reason: 'Brief 提到转化目标', label: '营销目标：转化-外溢进店表现', control_type: 'marketing_goal_metric', priority: 'low' },
  { field: '按博主粉丝推荐', value: '待选择合作品牌/竞品', reason: '根据品牌或竞品粉丝画像找博主', label: '人群目标：按博主粉丝推荐', control_type: 'brand_search_recommendation', input_values: [], pending_detail: '右上角搜索合作品牌或竞品品牌' },
  { field: '博主类目', value: '教育', sub_value: '家庭教育', reason: 'Brief 命中教育场景', label: '博主类目：教育-家庭教育', control_type: 'tag_select_with_hover_subcategory' },
  { field: '博主类目', value: '母婴', sub_value: '育儿经验', reason: 'Brief 命中母婴/亲子场景', label: '博主类目：母婴-育儿经验', control_type: 'tag_select_with_hover_subcategory' },
  { field: '家庭身份', value: '妈妈', reason: 'Brief 命中家庭身份画像', label: '家庭身份：妈妈', control_type: 'checkbox_popover' },
  { field: '职业身份', value: '学生', reason: 'Brief 命中学生/留学生画像', label: '职业身份：学生', control_type: 'checkbox_popover' },
  { field: '特色背景', value: '留学背景', reason: 'Brief 命中留学/海外背景', label: '特色背景：留学背景', control_type: 'checkbox_popover' },
  { field: '地域', value: '北京/上海优先', reason: 'Brief 明确强调地域/IP/城市要求', label: '地域：北京/上海优先', control_type: 'three_level_cascade_checkbox_popover' },
  { field: '粉丝年龄', value: '35～44 占比高', reason: 'Brief 要求家长/35岁以上粉丝', label: '粉丝年龄：35～44 占比高', control_type: 'dropdown' },
  { field: '合作报价', value: '图文笔记：0.1万～2万', reason: '单达人预算上限', label: '合作报价：图文 ≤ 2万', control_type: 'subfield_preset_or_number_range', sub_field: '图文笔记' },
  { field: '预估阅读单价', value: '图文笔记阅读单价≤2', reason: 'Brief 要求控制 CPC', label: '预估阅读单价：图文 ≤ 2', control_type: 'subfield_preset_or_number_range', sub_field: '图文笔记阅读单价' },
  { field: '预估互动单价', value: '图文笔记互动单价≤20', reason: 'Brief 要求控制 CPE', label: '预估互动单价：图文 ≤ 20', control_type: 'subfield_preset_or_number_range', sub_field: '图文笔记互动单价' },
  { field: '近期合作品牌', value: '待填品牌', reason: '记录或剔除近期合作品牌', label: '近期合作品牌：待填', control_type: 'searchable_multi_select_with_exclude', input_values: [], min_items: 3, pending_detail: '至少补足3个品牌' },
  { field: '行业推荐博主', value: '我的行业', reason: '使用行业推荐入口', label: '行业推荐博主：我的行业', control_type: 'nested_select_popover', pending_detail: '打开后继续选择我的行业' },
  { field: '常规剔除', value: '剔除低活博主', reason: '规避低活账号', label: '常规剔除：低活博主', control_type: 'checkbox' },
  { field: '常规剔除', value: '剔除掉粉博主', reason: '规避掉粉账号', label: '常规剔除：掉粉博主', control_type: 'checkbox' },
];

export const DISPLAY_METRIC_OPTIONS = [
  { value: '全部非直播指标', label: '全部非直播指标' },
  { value: '粉丝数', label: '粉丝数' },
  { value: '阅读中位数（日常）', label: '阅读中位数（日常）' },
  { value: '互动中位数（日常）', label: '互动中位数（日常）' },
  { value: '全部报价', label: '全部报价' },
  { value: '曝光中位数', label: '曝光中位数' },
  { value: '合作信用度', label: '合作信用度' },
  { value: '近期合作行业', label: '近期合作行业' },
  { value: '近期合作品牌', label: '近期合作品牌' },
];

export const PGY_FIND_BLOGGER_FILTER_GROUPS = [
  {
    section: '合作目标',
    rows: [
      { label: '营销目标', kind: 'marketingGoal', field: '营销目标' },
      { label: '人群目标', kind: 'fields', fields: ['按博主粉丝推荐'] },
    ],
  },
  {
    section: '匹配度',
    rows: [
      { label: '博主类目', kind: 'tags', field: '博主类目', showAll: true },
      { label: '博主人设', kind: 'fields', fields: ['家庭身份', '职业身份', '特色背景'] },
      { label: '博主信息', kind: 'fields', fields: ['二十大人群', '性别', '地域', '行业特色画像', '预估消费行为', '签约情况', '擅长内容', '内容题材'] },
      { label: '粉丝画像', kind: 'fields', fields: ['粉丝量', '粉丝年龄', '粉丝性别', '粉丝地域', '婚恋状态', '消费水平', '母婴阶段', '手机价格', '手机品牌'] },
    ],
  },
  {
    section: '数据表现',
    rows: [
      { label: '日常笔记', kind: 'fields', fields: ['曝光中位数', '阅读中位数', '互动中位数', '千赞笔记比例', '笔记类型'] },
      { label: '合作笔记', kind: 'fields', fields: ['合作报价', '合作信用度', '合作订单数', '近期合作行业', '近期合作品牌'] },
      { label: '数据表现', kind: 'fields', fields: ['传播规模', '预估CPM', '预估阅读单价', '预估互动单价', '外溢进店单价'] },
      { label: '直播数据', kind: 'fields', fields: ['近30天直播场次', '场均观播人数', '场均销售额'] },
    ],
  },
  {
    section: '平台推荐',
    rows: [
      { label: '精选博主', kind: 'checks', field: '平台推荐', appendFields: ['行业推荐博主'] },
    ],
  },
  {
    section: '常规剔除',
    rows: [
      { label: '一键剔除', kind: 'checks', field: '常规剔除' },
    ],
  },
];

export const PGY_FILTER_CATALOG_UI = [
  { field: '营销目标', control_type: 'marketing_goal_metric', parent_options: PGY_MARKETING_GOAL_OPTIONS, option_groups: PGY_MARKETING_GOAL_GROUPS, options: PGY_MARKETING_GOAL_GROUPS.flatMap(group => group.options) },
  { field: '按博主粉丝推荐', control_type: 'brand_search_recommendation', options: ['待选择合作品牌/竞品'] },
  { field: '博主类目', control_type: 'tag_select_with_hover_subcategory', options: PGY_BLOGGER_CATEGORY_OPTIONS, option_groups: Object.entries(PGY_BLOGGER_CATEGORY_SUBCATEGORY_OPTIONS).map(([label, options]) => ({ label, options })) },
  { field: '家庭身份', control_type: 'checkbox_popover', option_groups: PGY_FAMILY_IDENTITY_GROUPS, options: PGY_FAMILY_IDENTITY_GROUPS.flatMap(group => group.options) },
  { field: '职业身份', control_type: 'checkbox_popover', option_groups: PGY_CAREER_IDENTITY_GROUPS, options: PGY_CAREER_IDENTITY_GROUPS.flatMap(group => group.options) },
  { field: '特色背景', control_type: 'checkbox_popover', option_groups: PGY_SPECIAL_BACKGROUND_GROUPS, options: PGY_SPECIAL_BACKGROUND_GROUPS.flatMap(group => group.options) },
  { field: '性别', control_type: 'dropdown_single', options: ['不限', '男', '女'] },
  { field: '地域', control_type: 'three_level_cascade_checkbox_popover', option_groups: PGY_REGION_CASCADE_GROUPS, options: ['中国', '美国', '日本', '澳大利亚', '英国', '加拿大', '韩国', '法国', '德国', '新加坡', '其他'] },
  { field: '二十大人群', control_type: 'checkbox_popover', option_groups: PGY_AUDIENCE_20_GROUPS, options: PGY_AUDIENCE_20_GROUPS.flatMap(group => group.options) },
  { field: '行业特色画像', control_type: 'checkbox_popover', options: PGY_INDUSTRY_PORTRAIT_OPTIONS },
  { field: '预估消费行为', control_type: 'checkbox_popover', option_groups: PGY_CONSUMPTION_BEHAVIOR_GROUPS, options: PGY_CONSUMPTION_BEHAVIOR_GROUPS.flatMap(group => group.options) },
  { field: '内容题材', control_type: 'checkbox_popover', option_groups: PGY_CONTENT_SUBJECT_GROUPS, options: PGY_CONTENT_SUBJECT_GROUPS.flatMap(group => group.options) },
  { field: '签约情况', control_type: 'dropdown_single', options: ['不限', '个人博主', '机构博主'] },
  { field: '擅长内容', control_type: 'checkbox_popover', option_groups: PGY_SKILLED_CONTENT_GROUPS, options: PGY_SKILLED_CONTENT_GROUPS.flatMap(group => group.options) },
  { field: '粉丝量', control_type: 'preset_or_number_range', options: PGY_FOLLOWER_RANGE_OPTIONS },
  { field: '粉丝年龄', control_type: 'dropdown', options: PGY_FAN_AGE_OPTIONS },
  { field: '粉丝性别', control_type: 'dropdown', options: ['男性占比高', '女性占比高'] },
  { field: '粉丝地域', control_type: 'three_level_cascade_checkbox_popover', option_groups: PGY_REGION_CASCADE_GROUPS, options: ['中国', '美国', '日本', '澳大利亚', '英国', '加拿大', '韩国', '法国', '德国', '新加坡', '其他'] },
  { field: '婚恋状态', control_type: 'dropdown_single', options: ['不限', '未婚', '已婚'] },
  { field: '消费水平', control_type: 'dropdown_single', options: ['不限', '低消费', '中消费', '高消费'] },
  { field: '母婴阶段', control_type: 'checkbox_popover', options: PGY_MATERNAL_STAGE_OPTIONS },
  { field: '手机价格', control_type: 'checkbox_popover', options: ['0-999', '1000-1999', '2000-2999', '3000-3999', '4000-4999', '5000-5999', '6000-6999', '7000-7999', '8000+'] },
  { field: '手机品牌', control_type: 'checkbox_popover', options: ['苹果', '华为', 'OPPO', 'VIVO', '荣耀', '小米', '一加', '魅族', '中兴', '联想'] },
  { field: '曝光中位数', control_type: 'preset_or_number_range', options: PGY_NOTE_COUNT_RANGE_OPTIONS },
  { field: '阅读中位数', control_type: 'preset_or_number_range', options: PGY_NOTE_COUNT_RANGE_OPTIONS },
  { field: '互动中位数', control_type: 'preset_or_number_range', options: PGY_INTERACTION_RANGE_OPTIONS },
  { field: '千赞笔记比例', control_type: 'preset_or_percent_range', options: PGY_RATE_RANGE_OPTIONS },
  { field: '笔记类型', control_type: 'dropdown_single', options: ['不限', '图文笔记为主', '视频笔记为主'] },
  { field: '合作报价', control_type: 'subfield_preset_or_number_range', sub_fields: ['图文笔记', '视频笔记'], options: PGY_PRICE_RANGE_OPTIONS },
  { field: '合作信用度', control_type: 'subfield_preset_or_percent_range', sub_fields: ['邀约48h回复率'], options: PGY_RATE_RANGE_OPTIONS },
  { field: '合作订单数', control_type: 'number_range', options: ['1～5', '6～10', '10～20', '20以上'] },
  { field: '近期合作行业', control_type: 'dropdown', options: ['美妆个护', '食品饮料', '母婴', '3c及电器', '日用百货', '服装配饰', '互联网', '生活服务', '家居建材', '汽车'] },
  { field: '近期合作品牌', control_type: 'searchable_multi_select_with_exclude', options: ['剔除上述品牌已合作博主'] },
  { field: '传播规模', control_type: 'multi_subfield_preset_or_number_range', sub_fields: ['曝光中位数', '阅读中位数', '互动中位数', '外溢进店中位数'], options: PGY_NOTE_COUNT_RANGE_OPTIONS },
  { field: '预估CPM', control_type: 'subfield_preset_or_number_range', sub_fields: ['预估图文CPM', '预估视频CPM'], options: PGY_UNIT_PRICE_OPTIONS },
  { field: '预估阅读单价', control_type: 'subfield_preset_or_number_range', sub_fields: ['图文笔记阅读单价', '视频笔记阅读单价'], options: PGY_UNIT_PRICE_OPTIONS },
  { field: '预估互动单价', control_type: 'subfield_preset_or_number_range', sub_fields: ['图文笔记互动单价', '视频笔记互动单价'], options: PGY_UNIT_PRICE_OPTIONS },
  { field: '外溢进店单价', control_type: 'preset_or_number_range', options: ['0.5以下', '0.5～1.0', '1.0～1.5', '1.5～2.5', '2.5～4.0'] },
  { field: '近30天直播场次', control_type: 'checkbox_popover', options: PGY_LIVE_COUNT_OPTIONS },
  { field: '场均观播人数', control_type: 'checkbox_popover', options: PGY_LIVE_VIEWER_OPTIONS },
  { field: '场均销售额', control_type: 'checkbox_popover', options: PGY_LIVE_SALES_OPTIONS },
  { field: '平台推荐', control_type: 'checkbox', options: ['明星', '优质博主', '新锐博主', '笔记+直播均可合作', '意向行业匹配'] },
  { field: '行业推荐博主', control_type: 'nested_select_popover', options: ['我的行业'] },
  { field: '常规剔除', control_type: 'checkbox', options: ['剔除低活博主', '剔除掉粉博主', '剔除已合作博主', '剔除已邀约博主'] },
];

export const PGY_FILTER_CATALOG_BY_FIELD = PGY_FILTER_CATALOG_UI.reduce((map, item) => ({ ...map, [item.field]: item }), {});
export const PGY_SINGLE_VALUE_CONTROLS = new Set([
  'dropdown',
  'dropdown_single',
  'preset_or_number_range',
  'preset_or_percent_range',
  'number_range',
  'subfield_preset_or_number_range',
  'subfield_preset_or_percent_range',
]);
