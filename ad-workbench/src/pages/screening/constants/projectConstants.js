export const STEPS = ['立项', '绑定飞书', '生成计划', '蒲公英采集', '初筛评分', '人工筛选', '项目达人池'];
export const PROJECT_ID = 'youdao_001';

export const initialProjects = [
  {
    id: 'youdao_001', name: '有道答疑笔5-6月合作', product: '有道答疑笔Pro',
    poolType: 'shared', sharedPoolId: 'education_mom',
    budget: 600000, singleBudget: 20000, creatorCount: 30,
    period: '2026.05 - 2026.06', periodStart: '2026-05-01', periodEnd: '2026-06-30',
    status: '进行中', currentStep: 3,
    cooperationType: '合作笔记',
    description: '教育/母婴类达人推广有道答疑笔，面向小学1-6年级学生家长',
    brief: {
      projectId: 'youdao_001', projectName: '有道答疑笔5-6月合作', template: '有道',
      description: '我们需要找一批教育/母婴类的达人来推广有道答疑笔，主要面向小学1-6年级学生的家长。达人需要有真实的教育或育儿背景，粉丝画像中30-40岁宝妈占比要高。'
    },
    screeningPlan: {
      briefType: 'complex', hardFilters: [
        { field: '35岁以上粉丝占比', condition: '>=', value: '40%', required: true },
        { field: '平台报价', condition: '<=', value: '¥20,000', required: true },
        { field: '蒲公英链接', condition: '必须存在', value: '', required: true },
      ],
      scoringWeights: { budget: 15, fans: 5, cpe: 20, engagement: 30, persona: 20, content: 10 },
    },
    feishuBinding: {
      linked: true, tableUrl: 'https://example.feishu.cn/base/abc123', tableName: '有道答疑笔达人池',
      baseToken: 'abc123', tableId: 'tbl001', viewId: 'vew001',
      fieldMapping: [
        { standard: '达人昵称', feishu: '博主名称', writable: true, type: 'text' },
        { standard: '粉丝数', feishu: '粉丝数量', writable: true, type: 'number' },
        { standard: '平台报价', feishu: '报价', writable: true, type: 'number' },
        { standard: '审核状态', feishu: '状态', writable: true, type: 'select' },
        { standard: '评分总分', feishu: '评分', writable: false, type: 'formula' },
      ],
    },
  },
  {
    id: 'ai_course_q2', name: 'AI课程推广Q2', product: 'AI精品课程包',
    poolType: 'shared', sharedPoolId: 'education_mom',
    budget: 450000, singleBudget: 18000, creatorCount: 25,
    period: '2026.04 - 2026.06', periodStart: '2026-04-01', periodEnd: '2026-06-30',
    status: '已完成', currentStep: 7,
    cooperationType: '视频+图文',
    description: '科技教育类达人推广AI编程课程，面向6-12岁学生家长',
    brief: {
      projectId: 'ai_course_q2', projectName: 'AI课程推广Q2', template: 'AI课程',
      description: '推广AI编程课程，面向6-12岁学生家长。需要科技教育类达人，有编程或STEM教育背景优先。'
    },
    screeningPlan: { briefType: 'simple', hardFilters: [], scoringWeights: { budget: 15, fans: 5, cpe: 20, engagement: 30, persona: 20, content: 10 } },
    feishuBinding: { linked: true, tableUrl: 'https://example.feishu.cn/base/def456', tableName: 'AI课程Q2达人', baseToken: 'def456', tableId: 'tbl002', viewId: 'vew002', fieldMapping: [] },
  },
  {
    id: 'baby_food_001', name: '母婴产品种草', product: '婴儿辅食机',
    poolType: 'shared', sharedPoolId: 'baby_care',
    budget: 300000, singleBudget: 15000, creatorCount: 20,
    period: '2026.06 - 2026.08', periodStart: '2026-06-01', periodEnd: '2026-08-31',
    status: '待启动', currentStep: 1,
    cooperationType: '合作笔记',
    description: '真实宝妈人设推广婴儿辅食机，有辅食制作内容经验',
    brief: {
      projectId: 'baby_food_001', projectName: '母婴产品种草', template: '通用母婴',
      description: '婴儿辅食机产品种草，面向0-3岁宝宝家长。需要真实宝妈人设，有辅食制作内容经验。'
    },
    screeningPlan: { briefType: 'complex', hardFilters: [], scoringWeights: {} },
    feishuBinding: { linked: false, tableUrl: '', tableName: '', baseToken: '', tableId: '', viewId: '', fieldMapping: [] },
  },
  {
    id: 'luxury_skincare', name: '高端护肤品牌合作', product: '抗老精华套装',
    poolType: 'isolated', sharedPoolId: null,
    budget: 800000, singleBudget: 50000, creatorCount: 15,
    period: '2026.07 - 2026.09', periodStart: '2026-07-01', periodEnd: '2026-09-30',
    status: '待启动', currentStep: 1,
    cooperationType: '报备',
    description: '美妆护肤垂直达人推广高端护肤品，面向25-40岁都市女性',
    brief: {
      projectId: 'luxury_skincare', projectName: '高端护肤品牌合作', template: '自定义',
      description: '高端护肤品牌推广，面向25-40岁都市女性。需要美妆护肤垂直达人，有高端产品测评经验。'
    },
    screeningPlan: { briefType: 'complex', hardFilters: [], scoringWeights: {} },
    feishuBinding: { linked: false, tableUrl: '', tableName: '', baseToken: '', tableId: '', viewId: '', fieldMapping: [] },
  },
];

// ==================== 达人池数据（含评分维度）====================

export const sharedPoolEducationMom = [
  { id: 1, name: '陪读妈妈莫小柒', type: 'KOL', typeVariant: 'purple', followers: '52.3万', followersNum: 523000, quote: '¥18,000', quoteNum: 18000, baseScore: 92, risk: ['高粉量', '母婴垂直'],
    scores: { budget: 95, fans: 88, cpe: 90, engagement: 92, persona: 96, content: 88 }, aiReason: '人设高度匹配教育场景，粉丝画像中30-40岁宝妈占比65%，内容质量稳定，互动率高于同类达人平均水平。' },
  { id: 2, name: '教育达人小王', type: 'KOL', typeVariant: 'purple', followers: '38.7万', followersNum: 387000, quote: '¥15,000', quoteNum: 15000, baseScore: 88, risk: ['教育垂直'],
    scores: { budget: 92, fans: 82, cpe: 85, engagement: 88, persona: 94, content: 86 }, aiReason: '教育领域深耕3年，有教师资格认证，粉丝粘性高，CPE数据优秀。' },
  { id: 3, name: '学霸妈妈日记', type: 'KOC', typeVariant: 'blue', followers: '8.2万', followersNum: 82000, quote: '¥5,000', quoteNum: 5000, baseScore: 85, risk: ['低粉量'],
    scores: { budget: 98, fans: 72, cpe: 88, engagement: 90, persona: 92, content: 80 }, aiReason: '真实宝妈人设，陪读日记内容真实度高，粉丝互动活跃，性价比优秀。' },
  { id: 4, name: '育儿百科全书', type: 'KOL', typeVariant: 'purple', followers: '120.5万', followersNum: 1205000, quote: '¥35,000', quoteNum: 35000, baseScore: 82, risk: ['报价偏高', '泛母婴'],
    scores: { budget: 65, fans: 95, cpe: 78, engagement: 82, persona: 80, content: 85 }, aiReason: '粉丝量大但偏泛母婴，教育垂直度不足，报价超出单达人预算上限。' },
  { id: 5, name: '小学老师张老师', type: 'KOC', typeVariant: 'blue', followers: '5.6万', followersNum: 56000, quote: '¥3,500', quoteNum: 3500, baseScore: 79, risk: ['低粉量', '教育垂直'],
    scores: { budget: 98, fans: 65, cpe: 82, engagement: 78, persona: 88, content: 75 }, aiReason: '有教师背景，教育垂直度高，但粉丝量偏小，影响力有限。' },
  { id: 6, name: '亲子时光Alice', type: 'KOL', typeVariant: 'purple', followers: '67.1万', followersNum: 671000, quote: '¥22,000', quoteNum: 22000, baseScore: 76, risk: ['报价偏高'],
    scores: { budget: 72, fans: 88, cpe: 75, engagement: 78, persona: 76, content: 80 }, aiReason: '亲子内容优质，但报价偏高且内容偏亲子娱乐，教育属性较弱。' },
  { id: 7, name: '英语启蒙小课堂', type: 'KOC', typeVariant: 'blue', followers: '3.1万', followersNum: 31000, quote: '¥2,000', quoteNum: 2000, baseScore: 71, risk: ['低粉量', '内容单一'],
    scores: { budget: 98, fans: 58, cpe: 72, engagement: 70, persona: 75, content: 65 }, aiReason: '英语启蒙垂直度高但内容单一，粉丝量小，内容创新度不足。' },
  { id: 8, name: '家有二宝', type: 'KOC', typeVariant: 'blue', followers: '2.8万', followersNum: 28000, quote: '¥1,800', quoteNum: 1800, baseScore: 65, risk: ['低粉量', '互动率低'],
    scores: { budget: 98, fans: 52, cpe: 65, engagement: 60, persona: 68, content: 58 }, aiReason: '互动率持续下降，近30天笔记表现低于历史水平，疑似限流。' },
  { id: 9, name: '全职妈妈小丽', type: 'KOC', typeVariant: 'blue', followers: '1.5万', followersNum: 15000, quote: '¥1,200', quoteNum: 1200, baseScore: 58, risk: ['低粉量', '无蒲公英'],
    scores: { budget: 98, fans: 45, cpe: 55, engagement: 52, persona: 60, content: 48 }, aiReason: '无蒲公英链接，无法验证数据真实性，粉丝量极小。' },
  { id: 10, name: '宝妈好物推荐', type: 'KOC', typeVariant: 'blue', followers: '4.2万', followersNum: 42000, quote: '¥2,500', quoteNum: 2500, baseScore: 52, risk: ['广告过多', '信任度低'],
    scores: { budget: 95, fans: 55, cpe: 48, engagement: 45, persona: 50, content: 42 }, aiReason: '近30天广告占比超过70%，粉丝信任度下降明显，不适合教育类产品推广。' },
];

export const sharedPoolBabyCare = [
  { id: 11, name: '新手妈妈日记', type: 'KOL', typeVariant: 'purple', followers: '45.2万', followersNum: 452000, quote: '¥16,000', quoteNum: 16000, baseScore: 90, risk: ['母婴垂直'],
    scores: { budget: 90, fans: 88, cpe: 92, engagement: 90, persona: 94, content: 86 }, aiReason: '真实新手妈妈人设，辅食制作内容丰富，粉丝画像精准匹配0-3岁宝宝家长。' },
  { id: 12, name: '育儿专家李医生', type: 'KOL', typeVariant: 'purple', followers: '89.5万', followersNum: 895000, quote: '¥28,000', quoteNum: 28000, baseScore: 87, risk: ['报价偏高'],
    scores: { budget: 75, fans: 92, cpe: 88, engagement: 86, persona: 90, content: 88 }, aiReason: '儿科医生背景，专业背书强，但报价偏高，需要评估ROI。' },
  { id: 13, name: '宝宝辅食日记', type: 'KOC', typeVariant: 'blue', followers: '12.3万', followersNum: 123000, quote: '¥6,500', quoteNum: 6500, baseScore: 84, risk: [],
    scores: { budget: 92, fans: 78, cpe: 85, engagement: 86, persona: 88, content: 82 }, aiReason: '辅食制作内容专业度高，有营养师认证，性价比优秀。' },
  { id: 14, name: '母乳喂养指导', type: 'KOC', typeVariant: 'blue', followers: '8.7万', followersNum: 87000, quote: '¥4,500', quoteNum: 4500, baseScore: 81, risk: ['内容单一'],
    scores: { budget: 95, fans: 72, cpe: 80, engagement: 82, persona: 82, content: 78 }, aiReason: '母乳喂养领域专业，但内容范围较窄，与辅食机产品匹配度一般。' },
  { id: 15, name: '婴儿睡眠训练师', type: 'KOL', typeVariant: 'purple', followers: '35.6万', followersNum: 356000, quote: '¥19,000', quoteNum: 19000, baseScore: 78, risk: ['报价偏高'],
    scores: { budget: 78, fans: 82, cpe: 76, engagement: 78, persona: 80, content: 76 }, aiReason: '婴儿睡眠领域专业，但与辅食机产品关联度不高，报价接近预算上限。' },
];

export const isolatedPoolLuxury = [
  { id: 101, name: '美妆博主Vivi', type: 'KOL', typeVariant: 'purple', followers: '156.8万', followersNum: 1568000, quote: '¥45,000', quoteNum: 45000, baseScore: 94, risk: ['高粉量', '美妆垂直'],
    scores: { budget: 85, fans: 96, cpe: 94, engagement: 95, persona: 96, content: 92 }, aiReason: '高端美妆领域头部达人，有多次高端护肤品合作经验，粉丝画像精准匹配25-40岁都市女性。' },
  { id: 102, name: '护肤成分党', type: 'KOL', typeVariant: 'purple', followers: '78.3万', followersNum: 783000, quote: '¥32,000', quoteNum: 32000, baseScore: 91, risk: ['专业度高'],
    scores: { budget: 90, fans: 90, cpe: 92, engagement: 90, persona: 94, content: 90 }, aiReason: '成分分析专业度高，粉丝信任度强，适合抗老精华这类需要专业背书的产品。' },
  { id: 103, name: '都市丽人Lisa', type: 'KOL', typeVariant: 'purple', followers: '92.5万', followersNum: 925000, quote: '¥38,000', quoteNum: 38000, baseScore: 89, risk: ['报价偏高'],
    scores: { budget: 82, fans: 92, cpe: 88, engagement: 88, persona: 90, content: 86 }, aiReason: '都市生活方式博主，粉丝画像匹配度高，但报价偏高需评估性价比。' },
  { id: 104, name: '成分实验室', type: 'KOC', typeVariant: 'blue', followers: '15.6万', followersNum: 156000, quote: '¥12,000', quoteNum: 12000, baseScore: 86, risk: [],
    scores: { budget: 95, fans: 78, cpe: 88, engagement: 86, persona: 88, content: 84 }, aiReason: '成分测评内容专业，性价比高，适合作为KOC矩阵补充。' },
  { id: 105, name: '30+护肤日记', type: 'KOC', typeVariant: 'blue', followers: '22.4万', followersNum: 224000, quote: '¥15,000', quoteNum: 15000, baseScore: 83, risk: [],
    scores: { budget: 92, fans: 80, cpe: 84, engagement: 82, persona: 86, content: 80 }, aiReason: '30+女性护肤经验分享，人设真实，粉丝互动活跃，性价比优秀。' },
];

export const initialScreeningStatus = {
  youdao_001: {
    1: { review: '已通过', reviewVariant: 'green', finalScore: 92, reason: '人设高度匹配', reviewer: '张策划', reviewedAt: '2026-05-06 14:30' },
    2: { review: '已通过', reviewVariant: 'green', finalScore: 88, reason: '教育领域深耕', reviewer: '张策划', reviewedAt: '2026-05-06 14:35' },
    3: { review: '已通过', reviewVariant: 'green', finalScore: 85, reason: '真实宝妈人设', reviewer: '李媒介', reviewedAt: '2026-05-06 15:00' },
    4: { review: '已驳回', reviewVariant: 'red', finalScore: 82, reason: '报价超出预算', reviewer: '张策划', reviewedAt: '2026-05-06 15:10' },
    5: { review: '备选', reviewVariant: 'amber', finalScore: 79, reason: '影响力有限', reviewer: '李媒介', reviewedAt: '2026-05-06 15:20' },
  },
  ai_course_q2: {
    1: { review: '已通过', reviewVariant: 'green', finalScore: 90, reason: 'AI课程经验丰富', reviewer: '张策划', reviewedAt: '2026-04-20 10:00' },
    2: { review: '已通过', reviewVariant: 'green', finalScore: 89, reason: '科技教育优质', reviewer: '张策划', reviewedAt: '2026-04-20 10:05' },
  },
  baby_food_001: {
    11: { review: '已通过', reviewVariant: 'green', finalScore: 91, reason: '辅食经验丰富', reviewer: '王运营', reviewedAt: '2026-05-07 09:00' },
    12: { review: '人工复核', reviewVariant: 'amber', finalScore: 88, reason: '专家背书强', reviewer: null, reviewedAt: null },
  },
  luxury_skincare: {
    101: { review: '已通过', reviewVariant: 'green', finalScore: 95, reason: '高端测评经验', reviewer: '赵媒介', reviewedAt: '2026-05-07 11:00' },
    102: { review: '已通过', reviewVariant: 'green', finalScore: 93, reason: '成分分析专业', reviewer: '赵媒介', reviewedAt: '2026-05-07 11:05' },
  },
};

export const mockAuditLogs = [
  { id: 1, type: 'review', action: '审核通过', target: '陪读妈妈莫小柒', user: '张策划', time: '2026-05-06 14:30', detail: '人设高度匹配，评分92分，建议通过', status: 'success' },
  { id: 2, type: 'review', action: '审核通过', target: '教育达人小王', user: '张策划', time: '2026-05-06 14:35', detail: '教育领域深耕3年，评分88分', status: 'success' },
  { id: 3, type: 'review', action: '审核通过', target: '学霸妈妈日记', user: '李媒介', time: '2026-05-06 15:00', detail: '真实宝妈人设，性价比优秀', status: 'success' },
  { id: 4, type: 'review', action: '审核驳回', target: '育儿百科全书', user: '张策划', time: '2026-05-06 15:10', detail: '报价¥35,000超出单达人预算¥20,000上限', status: 'warning' },
  { id: 5, type: 'review', action: '加入备选', target: '小学老师张老师', user: '李媒介', time: '2026-05-06 15:20', detail: '有教师背景但影响力有限，列入备选观察', status: 'info' },
  { id: 6, type: 'screening', action: 'AI初筛完成', target: '教育母婴池', user: '系统', time: '2026-05-06 12:00', detail: '共10位达人完成AI评分，建议通过3位，人工复核2位，默认淘汰5位', status: 'success' },
  { id: 7, type: 'feishu', action: '飞书写回', target: '有道答疑笔达人池', user: '系统', time: '2026-05-06 16:00', detail: '成功写回3条达人记录，0条重复跳过', status: 'success' },
  { id: 8, type: 'project', action: '创建项目', target: '有道答疑笔5-6月合作', user: '张策划', time: '2026-05-01 09:00', detail: '项目创建成功，达人池类型：共享池（教育母婴）', status: 'success' },
  { id: 9, type: 'feishu', action: '绑定飞书表格', target: '有道答疑笔达人池', user: '张策划', time: '2026-05-02 10:00', detail: '成功绑定飞书多维表格，读取到5个字段', status: 'success' },
  { id: 10, type: 'screening', action: '量化标准生成', target: '有道答疑笔5-6月合作', user: 'AI', time: '2026-05-03 11:00', detail: 'Brief类型：复杂，生成3条硬性条件，6维评分权重', status: 'success' },
  { id: 11, type: 'review', action: '批量审核', target: '6位待审核达人', user: '李媒介', time: '2026-05-06 15:30', detail: '批量通过3位（评分>=85），驳回1位（报价超标），备选2位', status: 'info' },
  { id: 12, type: 'feishu', action: '飞书写回失败', target: '有道答疑笔达人池', user: '系统', time: '2026-05-05 14:00', detail: '达人"育儿百科全书"写回失败：字段"评分总分"为公式字段不可写', status: 'error' },
];
