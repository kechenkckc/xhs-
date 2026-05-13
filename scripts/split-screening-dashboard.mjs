import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const sourcePath = path.join(root, 'ad-workbench/src/pages/screening/ScreeningDashboard.jsx');
const source = fs.readFileSync(sourcePath, 'utf8');
const lines = source.split(/\r?\n/);

const out = (relativePath, content) => {
  const filePath = path.join(root, relativePath);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${content.trimEnd()}\n`, 'utf8');
};

const seg = (start, end) => lines.slice(start - 1, end).join('\n');
const exportConsts = (text) => text.replace(/^const ([A-Za-z0-9_]+)\s*=/gm, 'export const $1 =');
const exportFunctions = (text) => text.replace(/^function ([A-Za-z0-9_]+)\s*\(/gm, 'export function $1(');
const stripComments = (text) => text.replace(/^\/\/ ====================.*$/gm, '').trim();

const lucideImports = `import {
  LayoutDashboard, Users, BarChart3, FolderPlus, ScrollText, ExternalLink,
  Filter, CheckCircle2, XCircle, AlertTriangle, Clock, ChevronRight,
  FileText, Upload, Bot, Sparkles, Target, DollarSign, Calendar,
  TrendingUp, Eye, Edit3, Save, Plus, Search, ArrowRight, RefreshCw,
  Link2, Copy, Download, ThumbsUp, ThumbsDown, MessageSquare, Star,
  FolderOpen, ChevronDown, Grid3X3, List, MoreHorizontal, Trash2, Play,
  UserCheck, UserX, Ban, Bookmark, RotateCcw, Send, Settings, Database,
  Shield, Zap, Activity, FileSpreadsheet, ClipboardCheck, ArrowUpRight,
  ArrowDownRight, Minus, Info, X, ChevronUp, ChevronLeft, KeyRound, Globe,
  ToggleLeft, ToggleRight
} from 'lucide-react';`;

const sharedComponentImports = `${lucideImports}
import StatCard from '../../../../components/StatCard';
import DataTable from '../../../../components/DataTable';
import Badge from '../../../../components/Badge';
import ProgressBar from '../../../../components/ProgressBar';`;

out('ad-workbench/src/pages/screening/api/screeningApi.js', exportFunctions(seg(23, 55)));

out('ad-workbench/src/pages/screening/constants/projectConstants.js', exportConsts(`${seg(20, 21)}

${seg(252, 419)}`));

out('ad-workbench/src/pages/screening/constants/pgyConstants.js', exportConsts(`${seg(1355, 1382)}

${seg(1490, 1520)}

${seg(1710, 1799)}`));

out('ad-workbench/src/pages/screening/constants/screeningConstants.js', `import {
  PGY_MARKETING_GOAL_OPTIONS,
  PGY_BLOGGER_CATEGORY_OPTIONS,
  PGY_FAN_AGE_OPTIONS,
  PGY_PRICE_RANGE_OPTIONS,
  PGY_FOLLOWER_RANGE_OPTIONS,
  PGY_FAMILY_IDENTITY_OPTIONS,
  PGY_CAREER_IDENTITY_OPTIONS,
  PGY_SPECIAL_BACKGROUND_OPTIONS,
  PGY_MATERNAL_STAGE_OPTIONS,
  PGY_REGION_OPTIONS,
  PGY_UNIT_PRICE_OPTIONS,
  PGY_NOTE_COUNT_RANGE_OPTIONS,
  PGY_INTERACTION_RANGE_OPTIONS,
} from './pgyConstants';

${exportConsts(`${seg(1359, 1359)}

${seg(1384, 1410)}

${seg(1522, 1559)}`)}
`);

out('ad-workbench/src/pages/screening/utils/formatters.js', exportFunctions(`${seg(58, 90)}

${seg(104, 109)}

${seg(638, 644)}

${seg(849, 868)}`));

out('ad-workbench/src/pages/screening/utils/pgyFilters.js', `import {
  HARD_FILTER_OPTIONS,
  HARD_FILTER_CONDITIONS_BY_KIND,
  DEFAULT_HARD_FILTER_CONDITIONS,
  PGY_REQUIRED_FILTER_FIELDS,
  PGY_ADDITIONAL_FILTER_FIELDS,
  pgyFilterKey,
} from '../constants/screeningConstants';
import {
  PGY_FILTER_CATALOG_BY_FIELD,
} from '../constants/pgyConstants';

${exportFunctions(seg(1412, 1488))}

${exportFunctions(seg(1561, 1640))}

${exportFunctions(seg(1801, 1839))}
`);

out('ad-workbench/src/pages/screening/utils/screeningPlan.js', `import { DEFAULT_PGY_DISPLAY_METRICS } from '../constants/pgyConstants';
import {
  HARD_FILTER_OPTIONS,
  DEFAULT_COLLECTION_HARD_FILTER_FIELDS,
  DEFAULT_SCORING_HARD_FILTER_FIELDS,
} from '../constants/screeningConstants';
import {
  cloneHardFilterOption,
  defaultHardFilterCondition,
  getHardFilterOptionMeta,
  normalizePgyFilters,
} from './pgyFilters';

${exportFunctions(seg(2136, 2405))}
`);

out('ad-workbench/src/pages/screening/utils/projectMappers.js', `import {
  initialProjects,
  initialScreeningStatus,
  sharedPoolEducationMom,
  sharedPoolBabyCare,
  isolatedPoolLuxury,
} from '../constants/projectConstants';

${exportFunctions(seg(188, 239))}

${exportFunctions(seg(422, 550))}
`);

out('ad-workbench/src/pages/screening/utils/creatorMappers.js', `import { formatCompleteness, formatCurrency, compactNumber, formatDateLabel, formatDateTime, formatPercentValue } from './formatters';
import { normalizeWorkbenchPlan } from './screeningPlan';
import { hardFilterLabel } from '../constants/screeningConstants';

${exportFunctions(`${seg(92, 186)}

${seg(552, 1076)}`)}
`);

out('ad-workbench/src/pages/screening/utils/creatorScoring.js', `export {
  reviewVariantFromStatus,
  normalizeDimensionScore,
  deriveDimensionScores,
  getScoreColor,
  getScoreTier,
  getCreatorDetailStatus,
  getProjectScoringCriteria,
  getCreatorMatchProfile,
  getMetricText,
  getCreatorDeepAuditReason,
  parseAuditReasonSections,
  getCreatorRecommendation,
  getCreatorFollowupInfo,
  getCreatorTagGroups,
  getPoolStage,
  getCreatorUpdateLog,
  getReviewVariant,
} from './creatorMappers';
`);

out('ad-workbench/src/pages/screening/components/project/ProjectCard.jsx', `import React from 'react';
${sharedComponentImports}
import { formatDateTime } from '../../utils/formatters';
import { getProjectTaskSummary } from '../../utils/projectMappers';

${exportFunctions(seg(1192, 1275))}
`);

out('ad-workbench/src/pages/screening/components/project/ProjectsPreview.jsx', `import React, { useState } from 'react';
${sharedComponentImports}
import { formatDateTime } from '../../utils/formatters';
import { getProjectStats } from '../../utils/projectMappers';
import { ProjectCard } from './ProjectCard';

${exportFunctions(seg(1079, 1190))}
`);

out('ad-workbench/src/pages/screening/components/project/CreateProjectModal.jsx', `import React, { useState } from 'react';
${lucideImports}

${exportFunctions(seg(1278, 1351))}
`);

out('ad-workbench/src/pages/screening/components/filters/SelectableMenu.jsx', `import React from 'react';
${lucideImports}

${exportFunctions(seg(1642, 1667))}
`);

out('ad-workbench/src/pages/screening/components/filters/SelectedChips.jsx', `import React from 'react';
${lucideImports}

${exportFunctions(seg(1669, 1681))}
`);

out('ad-workbench/src/pages/screening/components/filters/PgyFilterCards.jsx', `import React from 'react';
${lucideImports}
import Badge from '../../../../components/Badge';
import { pgyFilterKey } from '../../constants/screeningConstants';

${exportFunctions(seg(1683, 1709))}
`);

out('ad-workbench/src/pages/screening/components/filters/PgyFilterPopover.jsx', `import React, { useMemo, useState } from 'react';
${lucideImports}
import {
  getPgySelectedItems,
  makePgyFilterItemsFromValues,
  makePgyFilterItem,
} from '../../utils/pgyFilters';

${exportFunctions(seg(1855, 1982))}
`);

out('ad-workbench/src/pages/screening/components/filters/PgyFindBloggerFilterPanel.jsx', `import React, { useMemo, useState } from 'react';
${lucideImports}
import {
  getPgyFilterMeta,
  getPgySelectedItems,
  makePgyFilterItem,
  pgyFilterKey,
  replacePgyFieldFilters,
  togglePgyCollectionFilter,
} from '../../utils/pgyFilters';
import { PGY_FIND_BLOGGER_FILTER_GROUPS } from '../../constants/pgyConstants';
import { PgyFilterPopover } from './PgyFilterPopover';

${exportFunctions(seg(1984, 2134))}
`);

out('ad-workbench/src/pages/screening/components/filters/HardFilterValueControl.jsx', `import React from 'react';
import {
  getHardFilterOptionMeta,
  normalizeHardFilterValue,
  splitHardFilterValue,
} from '../../utils/pgyFilters';

${exportFunctions(seg(2182, 2243))}
`);

out('ad-workbench/src/pages/screening/components/filters/HardFilterEditor.jsx', `import React from 'react';
${lucideImports}
import {
  defaultHardFilterCondition,
  hardFilterConditionsFor,
  normalizeHardFilterItem,
} from '../../utils/screeningPlan';
import { HARD_FILTER_OPTIONS, hardFilterKey, hardFilterLabel } from '../../constants/screeningConstants';
import { HardFilterValueControl } from './HardFilterValueControl';

${exportFunctions(seg(2245, 2333))}
`);

out('ad-workbench/src/pages/screening/components/overview/OverviewTab.jsx', `import React, { useEffect, useMemo, useState } from 'react';
${sharedComponentImports}
import {
  DISPLAY_METRIC_OPTIONS,
  DEFAULT_SCORING_HARD_FILTER_FIELDS,
  hardFilterKey,
  hardFilterLabel,
  metricKey,
  pgyFilterKey,
} from '../../constants/screeningConstants';
import { PGY_FILTER_OPTIONS } from '../../constants/pgyConstants';
import { getProjectCreators, getProjectStats } from '../../utils/projectMappers';
import { getScoreColor, getScoreTier } from '../../utils/creatorScoring';
import { mergeOptionItems, markManualPgyFilters } from '../../utils/pgyFilters';
import { getSchemeAdditionalFilters, getSchemeRequiredFilters, normalizeWorkbenchPlan, syncScreeningCriteria } from '../../utils/screeningPlan';
import { SelectedChips } from '../filters/SelectedChips';
import { PgyFindBloggerFilterPanel } from '../filters/PgyFindBloggerFilterPanel';

${exportFunctions(seg(2408, 2785))}
`);

out('ad-workbench/src/pages/screening/components/screening-review/ScreeningReviewTab.jsx', `import React, { useEffect, useMemo, useState } from 'react';
${sharedComponentImports}
import { DEFAULT_SCORING_HARD_FILTER_FIELDS, hardFilterKey, hardFilterLabel } from '../../constants/screeningConstants';
import { getProjectCreators, getCreatorStatus, getDefaultCreatorStatus } from '../../utils/projectMappers';
import { getScoreColor, getScoreTier } from '../../utils/creatorScoring';
import { mergeOptionItems } from '../../utils/pgyFilters';
import { hardFilterOptionsFor, normalizeWorkbenchPlan, syncScreeningCriteria } from '../../utils/screeningPlan';
import { HardFilterEditor } from '../filters/HardFilterEditor';
import { SelectedChips } from '../filters/SelectedChips';
import { CreatorDetailModal } from './CreatorDetailModal';

${exportFunctions(seg(2788, 3388))}
`);

out('ad-workbench/src/pages/screening/components/screening-review/CreatorDetailModal.jsx', `import React, { useMemo } from 'react';
${sharedComponentImports}
import { formatCompleteness } from '../../utils/formatters';
import {
  getCreatorAvatarUrl,
  getCreatorLocation,
  getCreatorRealNoteCases,
  getPgyUrl,
} from '../../utils/creatorMappers';
import { getCreatorDeepAuditReason, getCreatorMatchProfile, getScoreColor } from '../../utils/creatorScoring';
import { CreatorRecentNotesPanel } from './CreatorRecentNotesPanel';

${exportFunctions(seg(3390, 3494))}
`);

out('ad-workbench/src/pages/screening/components/screening-review/CreatorRecentNotesPanel.jsx', `import React, { useEffect, useMemo, useState } from 'react';
${sharedComponentImports}
import { formatNoteMetric, normalizeNoteType } from '../../utils/formatters';
import { parseCountValue, uniqueCompactItems } from '../../utils/creatorMappers';

${exportFunctions(seg(3496, 3616))}
`);

out('ad-workbench/src/pages/screening/components/creator-audit/CreatorAuditTab.jsx', `import React, { useEffect, useMemo, useState } from 'react';
${sharedComponentImports}
import { compactNumber, formatCompleteness } from '../../utils/formatters';
import { getCreatorStatus, getDefaultCreatorStatus, getProjectCreators } from '../../utils/projectMappers';
import {
  getCreatorAvatarUrl,
  getCreatorIntro,
  getCreatorLocation,
  getCreatorTags,
  getCreatorXhsId,
  getPgyUrl,
} from '../../utils/creatorMappers';
import { getCreatorMatchProfile, getProjectScoringCriteria, getReviewVariant, getScoreColor, getScoreTier } from '../../utils/creatorScoring';

export function CreatorAuditTab({ project, screeningStatus, setScreeningStatus, onCollectDetails, onScore, onReview, onRefresh, onTabChange }) {
${seg(3621, 3980)}
`);

out('ad-workbench/src/pages/screening/components/creator-pool/ScorePreviewTab.jsx', `import React, { useEffect, useMemo, useState } from 'react';
${sharedComponentImports}
import { api, formatApiErrorMessage } from '../../api/screeningApi';
import { compactNumber, formatDateLabel, formatDateTime, formatPercentValue } from '../../utils/formatters';
import { getCreatorStatus, getProjectCreators } from '../../utils/projectMappers';
import {
  creatorHasTag,
  getCreatorAvatarUrl,
  getCreatorCategory,
  getCreatorCollectedAt,
  getCreatorFollowupInfo,
  getCreatorIntro,
  getCreatorLocation,
  getCreatorRecommendation,
  getCreatorTagGroups,
  getCreatorTags,
  getCreatorUpdateLog,
  getCreatorXhsId,
  getPgyUrl,
  mapBackendCreator,
  pickCreatorValue,
  uniqueCompactItems,
} from '../../utils/creatorMappers';
import { getPoolStage, getReviewVariant, getScoreColor, getScoreTier } from '../../utils/creatorScoring';

${exportFunctions(seg(3983, 4425))}
`);

out('ad-workbench/src/pages/screening/components/project/ProjectSetupTab.jsx', `import React, { useEffect, useMemo, useState } from 'react';
${sharedComponentImports}
import { api } from '../../api/screeningApi';
import { DEFAULT_SCORING_HARD_FILTER_FIELDS, hardFilterKey, hardFilterLabel, WEIGHT_LABELS } from '../../constants/screeningConstants';
import { DEFAULT_PGY_DISPLAY_METRICS, PGY_FILTER_OPTIONS } from '../../constants/pgyConstants';
import { briefTextFromProject } from '../../utils/projectMappers';
import { mergeOptionItems, markManualPgyFilters } from '../../utils/pgyFilters';
import { hardFilterOptionsFor, normalizeWorkbenchPlan, syncScreeningCriteria } from '../../utils/screeningPlan';
import { SelectedChips } from '../filters/SelectedChips';
import { PgyFilterCards } from '../filters/PgyFilterCards';
import { PgyFindBloggerFilterPanel } from '../filters/PgyFindBloggerFilterPanel';
import { HardFilterEditor } from '../filters/HardFilterEditor';

${exportFunctions(seg(4429, 4943))}
`);

out('ad-workbench/src/pages/screening/components/logs/AuditLogTab.jsx', `import React, { useMemo, useState } from 'react';
${sharedComponentImports}
import { mockAuditLogs } from '../../constants/projectConstants';

${exportFunctions(seg(4947, 5035))}
`);

out('ad-workbench/src/pages/screening/components/config/AdvancedConfigTab.jsx', `import React, { useEffect, useState } from 'react';
${sharedComponentImports}
import { formatApiErrorMessage } from '../../api/screeningApi';

${exportFunctions(seg(5039, 5272))}
`);

out('ad-workbench/src/pages/screening/ScreeningDashboard.jsx', `import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FolderOpen } from 'lucide-react';
import { api } from './api/screeningApi';
import { PROJECT_ID, initialProjects, initialScreeningStatus } from './constants/projectConstants';
import { mapBackendCreator } from './utils/creatorMappers';
import { getProjectCreators, mapBackendProject } from './utils/projectMappers';
import { ProjectsPreview } from './components/project/ProjectsPreview';
import { CreateProjectModal } from './components/project/CreateProjectModal';
import { OverviewTab } from './components/overview/OverviewTab';
import { ScreeningReviewTab } from './components/screening-review/ScreeningReviewTab';
import { CreatorAuditTab } from './components/creator-audit/CreatorAuditTab';
import { ScorePreviewTab } from './components/creator-pool/ScorePreviewTab';
import { ProjectSetupTab } from './components/project/ProjectSetupTab';
import { AuditLogTab } from './components/logs/AuditLogTab';
import { AdvancedConfigTab } from './components/config/AdvancedConfigTab';

${seg(5274, 5601)}
`);
