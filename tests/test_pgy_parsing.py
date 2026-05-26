from rpa_mcp_sync.creator_store import normalize_creator, parse_number, sanitize_creator_type
from rpa_mcp_sync.pgy_browser import (
    _build_detail_collection_summary,
    _looks_like_quote_text,
    _number_from_text,
    _parse_row_text,
    _parse_device_distribution_line,
    _parse_region_distribution_line,
    _recent_note_briefs_from_kol,
    _recent_note_comments_from_payload,
    _merge_note_details_into_payload,
    _overview_from_api_cache,
    _api_note_case_pages_from_cache,
    _api_kol_link_fields,
    _collect_note_case_pages,
    _collect_overview_note_states,
    _collect_performance_states,
    _install_kol_response_capture,
    _prime_kol_api_capture,
    _should_reload_for_api_prime,
    _filter_already_selected,
    _detail_url_fields,
    _extract_detail_fields,
)


def test_parse_number_handles_pgy_follower_formats():
    assert parse_number("1.2 万") == 12000
    assert parse_number("3,456+") == 3456
    assert parse_number("8.4w") == 84000
    assert parse_number("--") is None
    assert _number_from_text("粉丝数 2.6 万+") == 26000


def test_detail_url_fields_builds_xhs_profile_url_from_pgy_blogger_id():
    fields = _detail_url_fields(
        "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/67e3aefa000000000d008d1b?track_id=1",
        source="pytest",
    )

    assert fields["pgy_url"] == "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/67e3aefa000000000d008d1b"
    assert fields["profile_url"] == "https://www.xiaohongshu.com/user/profile/67e3aefa000000000d008d1b"
    assert fields["pgy_blogger_id"] == "67e3aefa000000000d008d1b"


def test_extract_detail_fields_builds_xhs_profile_url_from_current_pgy_url():
    detail = _extract_detail_fields(
        "笔记主页\n直播主页\n听课宝达人\n小红书号：\n95292130186\n北京\n无机构\n教育\n粉丝数\n1234",
        "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/67e3aefa000000000d008d1b",
    )

    assert detail["xiaohongshu_id"] == "95292130186"
    assert detail["pgy_blogger_id"] == "67e3aefa000000000d008d1b"
    assert detail["profile_url"] == "https://www.xiaohongshu.com/user/profile/67e3aefa000000000d008d1b"


def test_parse_row_text_prefers_table_follower_value_over_position_guess():
    text = "\n".join(
        [
            "表头映射达人",
            "北京",
            "教育",
            "42%",
            "1688",
            "98",
            "¥",
            "3500",
        ]
    )

    creator = _parse_row_text(
        text,
        "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol",
        table_payload={
            "raw_table": {"博主名称": "表头映射达人", "粉丝数": "2.3 万", "阅读中位数（日常）": "1688"},
            "nickname": "表头映射达人",
            "followers_count": "2.3 万",
            "daily_read_median": "1688",
        },
    )

    assert creator is not None
    assert creator["followers_count"] == 23000
    assert creator["daily_read_median"] == "1688"
    assert creator["raw_payload"]["raw_table"]["粉丝数"] == "2.3 万"


def test_normalize_creator_keeps_correct_table_follower_count():
    creator = normalize_creator(
        {
            "nickname": "入库粉丝数达人",
            "followers_count": "2.3 万",
            "quote_price": "¥3,500",
        },
        "pytest_pgy_parse",
    )

    assert creator["followers_count"] == 23000
    assert creator["quote_price"] == 3500


def test_creator_from_api_kol_maps_current_list_metric_fields():
    from rpa_mcp_sync.pgy_browser import _creator_from_api_kol

    creator = _creator_from_api_kol(
        {
            "userId": "api-001",
            "name": "接口指标达人",
            "fansNum": 79917,
            "fansCount": 0,
            "picturePrice": 12500,
            "videoPrice": 14000,
            "clickMidNum": 18987,
            "mCpuvNum30d": 191,
            "mEngagementNum": 3057,
            "videoClickMidNum": 8888,
            "videoInterMidNum": 777,
            "accumCoopImpMedinNum30d": 241459,
            "readMidCoop30": 32654,
            "interMidCoop30": 2420,
            "estimatePictureCpm": 75.45,
            "estimateVideoCpm": 0,
            "pictureReadCost": "0.68",
            "estimatePictureEngageCost": 4.62,
            "inviteReply48hNumRatio": 96.2,
            "fansActiveIn28dLv": 87.7,
            "fansEngageNum30dLv": 3.4,
        }
    )

    assert creator["followers_count"] == 79917
    assert creator["daily_read_median"] == 18987
    assert creator["overflow_store_median"] == 191
    assert creator["video_daily_read_median"] == 8888
    assert creator["video_daily_interaction_median"] == 777
    assert creator["cooperation_read_median"] == 32654
    assert creator["cooperation_interaction_median"] == 2420
    assert creator["image_cpm"] == 75.45
    assert creator["image_read_unit_price"] == 0.68
    assert creator["image_interaction_unit_price"] == 4.62
    assert round(creator["reply_rate_48h"], 3) == 0.962
    assert creator["active_fans_ratio"] == 0.877
    assert creator["interaction_fans_ratio"] == 0.034


def test_parse_row_text_ignores_shifted_percent_quote_from_table():
    text = "\n".join(
        [
            "多妈育儿笔记",
            "浙江 杭州 萧山区",
            "6-12岁",
            "妈妈",
            "教育",
            "母婴",
            "5+",
            "期待与「出行旅游」行业合作",
            "教育",
            "教育",
            "1.6w",
            "8.5%",
            "83.8%",
            "7.1%",
            "109,334",
            "24,242",
            "1,484",
            "91.8%",
            "¥",
            "1,900",
            "添加合作",
        ]
    )

    creator = _parse_row_text(
        text,
        "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol",
        table_payload={
            "raw_table": {"全部报价": "7.1%", "图文预估CPM价格": "¥1,900"},
            "quote_price": "7.1%",
            "followers_count": "--",
        },
    )

    assert creator is not None
    assert _looks_like_quote_text("7.1%") is False
    assert _looks_like_quote_text("¥1,900") is True
    assert creator["quote_price"] == 1900
    assert creator["followers_count"] == 16000


def test_parse_row_text_marks_no_order_permission():
    creator = _parse_row_text(
        "\n".join(
            [
                "无权限达人",
                "北京",
                "教育",
                "粉丝数",
                "1.2w",
                "合作报价",
                "图文笔记一口价",
                "无接单权限",
            ]
        ),
        "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol",
        table_payload={"raw_table": {"全部报价": "无接单权限"}, "pgy_url": "https://pgy.xiaohongshu.com/creator/no-permission"},
    )

    assert creator is not None
    assert creator["order_permission_status"] == "无接单权限"
    assert creator["raw_payload"]["order_permission_status"] == "无接单权限"
    assert creator.get("quote_price") is None


def test_sanitize_creator_type_rejects_detail_metric_text():
    bad_type = "4.8w/获赞与收藏/42.8w/收藏/邀约/合作报价/图文笔记一口价/¥1,151"
    assert sanitize_creator_type(bad_type) == ""
    assert normalize_creator({"nickname": "张老师", "creator_type": bad_type}, "pytest_pgy_parse")["creator_type"] == ""
    assert sanitize_creator_type("教育/母婴/测评") == "教育/母婴/测评"


def test_recent_note_briefs_from_kol_keeps_note_ids_cover_and_tags():
    briefs = _recent_note_briefs_from_kol(
        {
            "noteList": [
                {
                    "noteId": "note-1",
                    "noteType": 2,
                    "imageUrl": "https://img.example/cover-1.jpg",
                    "contentTag": "教育",
                    "featureTags": ["教程", "开箱"],
                    "industryTags": ["教育培训"],
                    "bind": True,
                },
                {
                    "noteId": "note-2",
                    "noteType": 1,
                    "imageUrl": "https://img.example/cover-2.jpg",
                    "contentTag": "母婴",
                    "featureTags": [],
                    "industryTags": [],
                    "bind": False,
                },
            ]
        }
    )

    assert [item["note_id"] for item in briefs] == ["note-1", "note-2"]
    assert briefs[0]["cover_url"].endswith("cover-1.jpg")
    assert briefs[0]["note_type"] == "视频笔记"
    assert briefs[0]["content_category"] == "教育"
    assert briefs[0]["feature_tags"] == ["教程", "开箱"]
    assert briefs[1]["note_type"] == "图文笔记"
    assert briefs[1]["bind"] is False


def test_api_kol_link_fields_reads_nested_user_id_without_clicking():
    class FakePage:
        _pgy_latest_api_kols = [
            {
                "profile": {
                    "userId": "abc123",
                    "redId": "red-9",
                    "headPhoto": "https://img.example/avatar.jpg",
                    "name": "嵌套字段达人",
                }
            }
        ]
        _pgy_api_kol_pool = []

    fields = _api_kol_link_fields(FakePage(), 0, {"nickname": "嵌套字段达人"})

    assert fields["pgy_url"] == "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/abc123"
    assert fields["pgy_blogger_id"] == "abc123"
    assert fields["pgy_url_source"] == "list_api"
    assert fields["xiaohongshu_id"] == "red-9"
    assert fields["avatar_url"].endswith("avatar.jpg")


def test_install_kol_response_capture_does_not_clear_existing_preflight_cache():
    class FakePage:
        _pgy_kol_response_capture_installed = True
        _pgy_latest_api_kols = [{"name": "预检方案达人"}]
        _pgy_api_kol_pool = [{"name": "预检方案达人"}]
        _pgy_api_kol_keys = {"预检方案达人"}
        _pgy_latest_kol_request = {"url": "https://pgy.xiaohongshu.com/api/solar/cooperator/blogger/v2"}

    page = FakePage()
    _install_kol_response_capture(page)

    assert page._pgy_latest_api_kols == [{"name": "预检方案达人"}]
    assert page._pgy_api_kol_pool == [{"name": "预检方案达人"}]
    assert page._pgy_api_kol_keys == {"预检方案达人"}
    assert page._pgy_latest_kol_request["url"].endswith("/blogger/v2")


def test_prime_kol_api_capture_does_not_reload_when_disabled():
    class FakePage:
        _pgy_latest_api_kols = []
        reload_called = False

        def wait_for_timeout(self, _timeout):
            return None

        def reload(self, **_kwargs):
            self.reload_called = True
            raise AssertionError("should not reload filtered PGY list")

    page = FakePage()

    assert _prime_kol_api_capture(page, reload_if_empty=False) is False
    assert page.reload_called is False


def test_api_prime_reload_policy_preserves_preflight_and_filtered_collect():
    assert _should_reload_for_api_prime(apply_filters=True, preserve_existing_filters=False, preflight_only=True) is False
    assert _should_reload_for_api_prime(apply_filters=False, preserve_existing_filters=True, preflight_only=False) is False
    assert _should_reload_for_api_prime(apply_filters=False, preserve_existing_filters=False, preflight_only=False) is True


def test_selected_filter_text_confirms_all_required_subfields():
    class FakeLocator:
        @property
        def first(self):
            return self

        def count(self):
            return 1

        def inner_text(self, timeout=None):
            return "\n".join(
                [
                    "合作报价：",
                    "图文笔记：不限-1000",
                    "视频笔记：不限-1000",
                    "合作笔记-预估阅读单价：",
                    "图文笔记阅读单价：不限-3",
                    "合作笔记-预估互动单价：",
                    "预估图文互动单价：不限-10",
                    "日常笔记-曝光中位数：",
                    "2000-不限",
                    "重置",
                    "存为常用筛选",
                ]
            )

    class FakePage:
        def locator(self, selector):
            return FakeLocator()

    page = FakePage()

    assert _filter_already_selected(
        page,
        {"field": "合作报价", "sub_fields": ["图文笔记", "视频笔记"], "max": 1000},
    )
    assert not _filter_already_selected(
        page,
        {"field": "预估互动单价", "sub_fields": ["图文笔记互动单价", "视频笔记互动单价"], "max": 10},
    )
    assert not _filter_already_selected(
        page,
        {"field": "预估阅读单价", "sub_fields": ["图文笔记阅读单价", "视频笔记阅读单价"], "max": 3},
    )
    assert _filter_already_selected(
        page,
        {"field": "曝光中位数", "value": "2000以上", "min": 2000},
    )


def test_recent_note_comments_from_payload_flattens_top_level_and_replies():
    comments = _recent_note_comments_from_payload(
        [
            {
                "comment": {"content": "第一条主评论"},
                "l1L2Comments": [{"content": "第一条回复"}],
            },
            {
                "comment": {"content": "第二条主评论"},
                "l1L2Comments": [],
            },
        ]
    )

    assert comments == ["第一条主评论", "第一条回复", "第二条主评论"]


def test_merge_note_details_into_payload_enriches_case_content_and_comments():
    detail = {
        "raw_payload": {
            "cooperation_note_cases": [
                {
                    "brand": "作业帮智能教育",
                    "title": "破防了，原来告别低效抄错题这么简单啊！",
                    "read_count": 9760,
                    "published_at": "2026-05-07",
                }
            ],
            "recent_notes": [
                {
                    "note_id": "note-1",
                    "title": "破防了，原来告别低效抄错题这么简单啊！",
                    "note_url": "https://www.xiaohongshu.com/explore/note-1",
                    "content": "孩子错题整理终于不用反复手抄。",
                    "comments": ["这个方法很实用", "想看完整测评"],
                    "published_at": "2026-05-07",
                    "source": "note_detail_api",
                }
            ],
        }
    }

    merged = _merge_note_details_into_payload(detail)
    note = merged["raw_payload"]["cooperation_note_cases"][0]

    assert note["note_id"] == "note-1"
    assert note["note_url"].endswith("note-1")
    assert note["content"] == "孩子错题整理终于不用反复手抄。"
    assert note["comment_summary"] == "这个方法很实用；想看完整测评"
    assert note["note_detail_source"] == "note_detail_api"


def test_detail_api_cache_builds_overview_and_note_cases():
    class FakePage:
        _pgy_detail_api_cache = {
            "data_summary": {
                "daily": {
                    "mAccumImpNum": 123456,
                    "readMedian": 45678,
                    "mEngagementNum": 987,
                    "responseRate": "43.1",
                }
            },
            "notes_rate": {
                "daily": {
                    "interactionRate": "3.2",
                    "videoFullViewRate": "11.1",
                    "thousandLikePercent": "80.0",
                    "hundredLikePercent": "100.0",
                }
            },
            "notes_detail": {
                4: {
                    1: {
                        "list": [
                            {
                                "noteId": "note-1",
                                "title": "API 案例标题",
                                "brandName": "测试品牌",
                                "readNum": 1000,
                                "likeNum": 100,
                                "collectNum": 50,
                                "date": "2026-05-18",
                                "isAdvertise": True,
                            }
                        ]
                    }
                }
            },
        }

    overview = _overview_from_api_cache(FakePage())
    cases = _api_note_case_pages_from_cache(FakePage(), note_type=4)

    assert overview["daily"]["scale"]["metrics"]["曝光中位数"] == "123,456"
    assert overview["daily"]["scale"]["metrics"]["互动率"] == "3.2%"
    assert cases["cooperation_note_cases"][0]["note_id"] == "note-1"
    assert cases["cooperation_note_cases"][0]["title"] == "API 案例标题"


def test_detail_collectors_return_api_cache_without_clicking():
    class NoClickPage:
        _pgy_detail_api_cache = {
            "data_summary": {
                "daily": {
                    "mAccumImpNum": 123456,
                    "readMedian": 45678,
                    "mEngagementNum": 987,
                }
            },
            "notes_rate": {
                "cooperation": {
                    "impMedian": 2222,
                    "readMedian": 1111,
                    "interactionRate": "3.2",
                }
            },
            "notes_detail": {
                4: {
                    1: {
                        "list": [
                            {
                                "noteId": "note-api-only",
                                "title": "纯 API 案例",
                                "brandName": "测试品牌",
                                "readNum": 1000,
                                "date": "2026-05-18",
                            }
                        ]
                    }
                }
            },
        }

        def locator(self, *args, **kwargs):
            raise AssertionError("API cache path should not touch DOM locators")

        def evaluate(self, *args, **kwargs):
            raise AssertionError("API cache path should not fetch or evaluate")

    page = NoClickPage()
    cases = _collect_note_case_pages(page)
    overview = _collect_overview_note_states(page)
    performance = _collect_performance_states(page)

    assert cases["cooperation_note_cases"][0]["note_id"] == "note-api-only"
    assert overview["daily"]["scale"]["metrics"]["阅读中位数"] == "45,678"
    assert performance["cooperation"]["scale"]["metrics"]["阅读中位数"] == "1,111"


def test_parse_region_distribution_line_extracts_top_regions():
    parsed = _parse_region_distribution_line("国内最高的三个省份：广东（13.9%）、海外（7.5%）、江苏（6.7%）")

    assert parsed["dominant"] == {"label": "广东", "ratio": 0.139}
    assert [item["label"] for item in parsed["top_regions"]] == ["广东", "海外", "江苏"]


def test_parse_device_distribution_line_extracts_dominant_brand():
    parsed = _parse_device_distribution_line("苹果用户占比48.68%，消费力较强")

    assert parsed["dominant"] == {"label": "苹果", "ratio": 0.4868}
    assert parsed["insight"] == "消费力较强"


def test_build_detail_collection_summary_counts_modules():
    detail = {
        "nickname": "小离Niko",
        "followers_count": 147341,
        "daily_read_median": 12027,
        "audience_age_distribution": {"segments": [{"label": "25-34", "ratio": 0.319}]},
        "audience_gender_distribution": {"segments": [{"label": "女性", "ratio": 0.628}]},
        "audience_region_distribution": {"dominant": {"label": "广东", "ratio": 0.139}},
        "audience_device_distribution": {"dominant": {"label": "苹果", "ratio": 0.4868}},
        "audience_profile_screenshot": "runtime/pgy_detail_screenshots/x.png",
        "raw_payload": {
            "fan_analysis": {"active_fans_ratio": 0.703},
            "service_performance": {"reply_rate_48h": 0.786},
            "recent_notes": [{"note_id": "1"}, {"note_id": "2"}],
        },
    }

    summary = _build_detail_collection_summary(detail)

    assert summary["module_count"] >= 7
    assert summary["note_case_count"] == 2
    assert summary["has_region_distribution"] is True
    assert summary["has_device_distribution"] is True
