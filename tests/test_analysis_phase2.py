from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _bootstrap import ensure_src_path

ensure_src_path()

from douyin_wenan.analysis.phase2 import (
    Phase2AnalysisResult,
    _infer_content_type,
    _infer_format,
    analyze_phase2_rows,
    parse_standard_transcript,
    select_phase2_ready,
    write_phase2_exports,
)
from douyin_wenan.common.csv_io import read_csv_rows
from douyin_wenan.normalize.txt_writer import render_standard_transcript, write_standard_transcript


class Phase2AnalysisTests(unittest.TestCase):
    def test_infer_format_does_not_treat_ordinal_reference_as_list_countdown(self) -> None:
        text = (
            "世界的本源是什么？这是古希腊人在哲学上的第一次追问。"
            "它不是倒数结构，而是在连续解释一个概念。"
        )
        self.assertEqual(_infer_format(text, char_count=120, duration_seconds=190), "long_explainer")

    def test_infer_content_type_does_not_treat_generic_huanshi_as_comparison_review(self) -> None:
        text = (
            "我们生活的世界是真实的吗？世界到底是精神的还是物质的？"
            "直到今天，这些问题都没有定论。"
        )
        self.assertEqual(_infer_content_type(text, domain="philosophy"), "concept_explainer")

    def test_parse_standard_transcript_extracts_metadata_and_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            row = {
                "title": "为什么唐朝太监能废立天子",
                "author": "柏拉图的石头",
                "work_id": "1001",
                "followers": "1000",
                "account_link": "https://example.com/u/1",
                "video_link": "https://example.com/v/1001",
                "publish_time": "2026-05-03 12:00",
                "duration_text": "03:30",
                "likes": "200",
                "comments": "20",
                "favorites": "30",
                "shares": "15",
                "raw_video_path": "D:/raw/1001.mp4",
                "asr_provider": "siliconflow",
                "asr_quality_grade": "B",
                "manual_reviewed": "no",
            }
            body = "为什么同样是太监干政，唐朝太监却能废立天子？今天我们只说一个核心原因。"
            write_standard_transcript(output_path=path, content=render_standard_transcript(row, body))

            parsed = parse_standard_transcript(path)
            self.assertEqual(parsed.metadata["标题"], "为什么唐朝太监能废立天子")
            self.assertEqual(parsed.metadata["作者"], "柏拉图的石头")
            self.assertEqual(parsed.body, body)

    def test_analyze_phase2_rows_builds_labels_baselines_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rows = [
                self._make_row(
                    tmp=tmp,
                    work_id="2001",
                    title="为什么唐朝太监能废立天子",
                    likes=220,
                    comments=20,
                    favorites=35,
                    shares=15,
                    duration_seconds=220,
                    body=(
                        "为什么同样是太监干政，唐朝太监却能废立天子？今天我们只说一个核心原因："
                        "神策军和财政都落在了太监手里。先说禁军，再说盐铁税，最后你会看到制度失控。"
                    ),
                ),
                self._make_row(
                    tmp=tmp,
                    work_id="2002",
                    title="为什么晚唐皇帝总被太监压制",
                    likes=180,
                    comments=16,
                    favorites=28,
                    shares=12,
                    duration_seconds=210,
                    body=(
                        "为什么晚唐皇帝总被太监压制？核心不是谁更狠，而是军队和钱袋子都被内廷抓住了。"
                        "我们先看神策军，再看财政路径，最后回到皇权为什么失控。"
                    ),
                ),
                self._make_row(
                    tmp=tmp,
                    work_id="2003",
                    title="唐朝太监问题到底出在哪",
                    likes=55,
                    comments=5,
                    favorites=8,
                    shares=4,
                    duration_seconds=180,
                    body=(
                        "很多人以为唐朝太监只是个人作恶，但真正的问题是制度把军权交错了。"
                        "今天从神策军和财政两条线，重新看这段历史。"
                    ),
                ),
                self._make_row(
                    tmp=tmp,
                    work_id="2004",
                    title="晚唐权力结构怎么一步步失衡",
                    likes=40,
                    comments=4,
                    favorites=7,
                    shares=3,
                    duration_seconds=175,
                    body=(
                        "不要把晚唐失控只理解成个别太监跋扈。真正的危险，是中央武装和财政同时失守。"
                        "先看禁军，再看税权，最后再看皇帝为什么收不回去。"
                    ),
                ),
                self._make_row(
                    tmp=tmp,
                    work_id="2005",
                    title="唐朝太监问题的背景脉络",
                    likes=12,
                    comments=1,
                    favorites=2,
                    shares=1,
                    duration_seconds=170,
                    body=(
                        "今天聊聊唐朝太监问题。先给你说一段背景，再慢慢进入主题。"
                        "很多事情如果只看表面，就容易忽略制度变化。"
                    ),
                ),
                self._make_row(
                    tmp=tmp,
                    work_id="2006",
                    title="晚唐政治的前因后果",
                    likes=8,
                    comments=1,
                    favorites=1,
                    shares=1,
                    duration_seconds=165,
                    body=(
                        "今天继续补一点唐朝背景。我们先从外围环境谈起，再一点点进入太监问题。"
                        "如果不先铺垫，就很难理解后面的变化。"
                    ),
                ),
            ]

            result = analyze_phase2_rows(rows)
            self.assertEqual(len(result.labeled_rows), 6)
            self.assertEqual(len(result.author_baselines), 1)
            self.assertTrue(result.route_foundation_patterns)
            self.assertTrue(result.author_high_low)
            self.assertTrue(result.evidence_records)

            by_work_id = {row["work_id"]: row for row in result.labeled_rows}
            self.assertEqual(by_work_id["2001"]["domain"], "history")
            self.assertEqual(by_work_id["2001"]["format"], "long_explainer")
            self.assertEqual(by_work_id["2001"]["style_family"], "question_hook")
            self.assertEqual(by_work_id["2001"]["author_relative_band"], "high")
            self.assertEqual(by_work_id["2006"]["author_relative_band"], "low")

            baseline = result.author_baselines[0]
            self.assertEqual(baseline["author"], "柏拉图的石头")
            self.assertEqual(baseline["row_count"], "6")

            gain_evidence = [
                record
                for record in result.evidence_records
                if record["evidence_kind"] == "differential_gain_pattern"
            ]
            self.assertTrue(gain_evidence)

    def test_analyze_phase2_rows_keeps_foundation_for_multi_route_author(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rows = []

            for idx in range(1, 7):
                question_opening = idx <= 4
                body = (
                    "为什么制度总会反噬制定制度的人？真正的关键，是执行权和解释权落在了一起。"
                    "今天先把这个机制讲清楚，关注我，下一条继续拆。"
                    if question_opening
                    else "今天聊聊制度反噬人的底层机制。关键在于执行权和解释权落在了一起。关注我，下一条继续拆。"
                )
                rows.append(
                    self._make_row(
                        tmp=tmp,
                        work_id=f"mr_a_{idx}",
                        title=f"制度为什么会反噬人 {idx}",
                        likes=200 - idx,
                        comments=20,
                        favorites=30,
                        shares=12,
                        duration_seconds=210,
                        body=body,
                    )
                )

            for idx in range(1, 7):
                rows.append(
                    self._make_row(
                        tmp=tmp,
                        work_id=f"mr_b_{idx}",
                        title=f"制度如何慢慢失衡 {idx}",
                        likes=60 - idx,
                        comments=4,
                        favorites=6,
                        shares=2,
                        duration_seconds=190,
                        body="今天聊聊制度如何慢慢失衡。核心在于执行权和解释权没有被拆开。",
                    )
                )

            for idx in range(1, 7):
                rows.append(
                    self._make_row(
                        tmp=tmp,
                        work_id=f"mr_c_{idx}",
                        title=f"另一组制度解释样本 {idx}",
                        likes=150 - idx,
                        comments=12,
                        favorites=18,
                        shares=8,
                        duration_seconds=205,
                        body="今天聊聊制度反噬人的底层机制。关键在于执行权和解释权落在了一起。关注我，下一条继续拆。",
                        author="第二作者",
                        account_link="https://example.com/u/2",
                    )
                )

            result = analyze_phase2_rows(rows)
            target_rows = [
                row
                for row in result.author_foundation_patterns
                if row["author"] == "柏拉图的石头"
                and row["route_content_type"] == "concept_explainer"
                and row["route_format"] == "long_explainer"
                and row["route_goal"] == "follow"
                and row["feature_name"] == "hook_type"
                and row["feature_value"] == "question"
            ]

            self.assertTrue(target_rows)
            self.assertEqual(target_rows[0]["support_rate"], "0.6667")
            self.assertEqual(target_rows[0]["route_row_count"], "6")
            self.assertEqual(target_rows[0]["confidence_grade"], "E2")

            evidence_rows = [
                row
                for row in result.evidence_records
                if row["author"] == "柏拉图的石头"
                and row["evidence_kind"] == "author_foundation_pattern"
                and row["feature_name"] == "hook_type"
                and row["feature_value"] == "question"
                and row["route_goal"] == "follow"
            ]
            self.assertTrue(evidence_rows)
            self.assertEqual(evidence_rows[0]["baseline_sample_size"], "6")

    def test_analyze_phase2_rows_author_scoped_uses_external_route_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            author_a_rows = []
            author_b_rows = []

            for idx in range(1, 7):
                author_a_rows.append(
                    self._make_row(
                        tmp=tmp,
                        work_id=f"ab_a_{idx}",
                        title=f"制度机制拆解 A{idx}",
                        likes=180 - idx,
                        comments=16,
                        favorites=24,
                        shares=10,
                        duration_seconds=210,
                        body=(
                            "为什么制度设计最后总会反噬自己？真正的关键，是执行权和解释权被绑在了一起。"
                            "关注我，下一条继续拆。"
                            if idx <= 4
                            else "制度设计最后会反噬自己，关键在于执行权和解释权被绑在了一起。"
                            "关注我，下一条继续拆。"
                        ),
                    )
                )

            for idx in range(1, 7):
                author_b_rows.append(
                    self._make_row(
                        tmp=tmp,
                        work_id=f"ab_b_{idx}",
                        title=f"制度机制拆解 B{idx}",
                        likes=140 - idx,
                        comments=12,
                        favorites=18,
                        shares=8,
                        duration_seconds=210,
                        body=(
                            "为什么制度设计最后总会反噬自己？真正的关键，是执行权和解释权被绑在了一起。"
                            "关注我，下一条继续拆。"
                        ),
                        author="第二作者",
                        account_link="https://example.com/u/2",
                    )
                )

            result = analyze_phase2_rows(
                author_a_rows,
                route_baseline_rows=[*author_a_rows, *author_b_rows],
            )

            route_rows = [
                row
                for row in result.route_foundation_patterns
                if row["route_content_type"] == "concept_explainer"
                and row["route_format"] == "long_explainer"
                and row["route_goal"] == "follow"
                and row["feature_name"] == "opening_problem_presence"
                and row["feature_value"] == "yes"
            ]
            self.assertEqual(len(route_rows), 1)
            self.assertEqual(route_rows[0]["row_count"], "12")
            self.assertEqual(route_rows[0]["support_count"], "10")

            foundation_rows = [
                row
                for row in result.author_foundation_patterns
                if row["author"] == "柏拉图的石头"
                and row["route_content_type"] == "concept_explainer"
                and row["route_format"] == "long_explainer"
                and row["route_goal"] == "follow"
                and row["feature_name"] == "opening_problem_presence"
                and row["feature_value"] == "yes"
            ]
            self.assertFalse(foundation_rows)

            evidence_rows = [
                row
                for row in result.evidence_records
                if row["author"] == "柏拉图的石头"
                and row["evidence_kind"] == "author_foundation_pattern"
                and row["feature_name"] == "opening_problem_presence"
                and row["feature_value"] == "yes"
                and row["route_goal"] == "follow"
            ]
            self.assertFalse(evidence_rows)

    def test_analyze_phase2_rows_emits_route_and_cross_author_transfer_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rows = []

            for author, prefix, base_likes in (
                ("柏拉图的石头", "xfer_a", 180),
                ("第二作者", "xfer_b", 150),
            ):
                for idx in range(1, 7):
                    rows.append(
                        self._make_row(
                            tmp=tmp,
                            work_id=f"{prefix}_{idx}",
                            title=f"制度机制拆解 {prefix} {idx}",
                            likes=base_likes - idx,
                            comments=12,
                            favorites=18,
                            shares=8,
                            duration_seconds=210,
                            body=(
                                "为什么制度设计最后总会反噬自己？真正的关键，是执行权和解释权被绑在了一起。"
                                "先看执行权，再看解释权，最后回到制度为什么会失控。关注我，下一条继续拆。"
                            ),
                            author=author,
                            account_link=f"https://example.com/u/{prefix}",
                        )
                    )

            result = analyze_phase2_rows(rows)

            route_evidence = [
                row
                for row in result.evidence_records
                if row["evidence_kind"] == "route_foundation_pattern"
                and row["route_content_type"] == "concept_explainer"
                and row["route_format"] == "long_explainer"
                and row["route_goal"] == "follow"
                and row["feature_name"] == "argument_shape"
                and row["feature_value"] == "stepwise_explainer"
            ]
            self.assertEqual(len(route_evidence), 1)
            self.assertEqual(route_evidence[0]["transfer_scope"], "route_local")
            self.assertEqual(route_evidence[0]["support_count"], "12")
            self.assertEqual(route_evidence[0]["support_sample_size"], "12")
            self.assertEqual(route_evidence[0]["confidence_grade"], "E3")
            self.assertEqual(route_evidence[0]["ready_for_distillation"], "yes")

            transfer_evidence = [
                row
                for row in result.evidence_records
                if row["evidence_kind"] == "cross_author_transfer_pattern"
                and row["route_content_type"] == "concept_explainer"
                and row["route_format"] == "long_explainer"
                and row["route_goal"] == "follow"
                and row["feature_name"] == "argument_shape"
                and row["feature_value"] == "stepwise_explainer"
            ]
            self.assertEqual(len(transfer_evidence), 1)
            self.assertEqual(transfer_evidence[0]["author"], "多作者")
            self.assertEqual(transfer_evidence[0]["transfer_scope"], "cross_author")
            self.assertEqual(transfer_evidence[0]["scope"], "cross_author")
            self.assertEqual(transfer_evidence[0]["support_count"], "12")
            self.assertEqual(transfer_evidence[0]["confidence_grade"], "E3")
            self.assertEqual(transfer_evidence[0]["ready_for_distillation"], "yes")

    def test_analyze_phase2_rows_does_not_emit_cross_author_transfer_from_one_author(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rows = [
                self._make_row(
                    tmp=tmp,
                    work_id=f"single_{idx}",
                    title=f"制度机制拆解 {idx}",
                    likes=180 - idx,
                    comments=12,
                    favorites=18,
                    shares=8,
                    duration_seconds=210,
                    body=(
                        "为什么制度设计最后总会反噬自己？真正的关键，是执行权和解释权被绑在了一起。"
                        "先看执行权，再看解释权，最后回到制度为什么会失控。关注我，下一条继续拆。"
                    ),
                )
                for idx in range(1, 9)
            ]

            result = analyze_phase2_rows(rows)

            self.assertFalse(
                [
                    row
                    for row in result.evidence_records
                    if row["evidence_kind"] == "cross_author_transfer_pattern"
                ]
            )

    def test_write_phase2_exports_merges_author_scoped_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            analysis_dir = tmp / "analysis"

            author_a_rows = [
                self._make_row(
                    tmp=tmp,
                    work_id="3001",
                    title="为什么唐朝太监能废立天子",
                    likes=220,
                    comments=20,
                    favorites=35,
                    shares=15,
                    duration_seconds=220,
                    body="为什么同样是太监干政，唐朝太监却能废立天子？今天我们只说一个核心原因。",
                ),
                self._make_row(
                    tmp=tmp,
                    work_id="3002",
                    title="晚唐皇帝总被太监压制",
                    likes=15,
                    comments=1,
                    favorites=2,
                    shares=1,
                    duration_seconds=180,
                    body="今天聊聊晚唐背景，先铺垫，再进入主题。",
                ),
            ]
            author_b_rows = [
                self._make_row(
                    tmp=tmp,
                    work_id="4001",
                    title="AI 为什么总让人焦虑",
                    likes=260,
                    comments=22,
                    favorites=40,
                    shares=18,
                    duration_seconds=210,
                    body="为什么 AI 会让很多人焦虑？因为它同时冲击效率和判断边界。",
                    author="第二作者",
                    account_link="https://example.com/u/2",
                ),
                self._make_row(
                    tmp=tmp,
                    work_id="4002",
                    title="AI 叙事为什么总是跑偏",
                    likes=20,
                    comments=2,
                    favorites=3,
                    shares=1,
                    duration_seconds=170,
                    body="今天继续补一点背景，慢慢进入主题。",
                    author="第二作者",
                    account_link="https://example.com/u/2",
                ),
            ]

            write_phase2_exports(analyze_phase2_rows(author_a_rows), analysis_dir)
            write_phase2_exports(analyze_phase2_rows(author_b_rows), analysis_dir)

            label_rows = read_csv_rows(analysis_dir / "labels" / "row_labels.csv")
            baseline_rows = read_csv_rows(analysis_dir / "baselines" / "author_baselines.csv")
            foundation_rows = read_csv_rows(analysis_dir / "baselines" / "author_foundation_patterns.csv")
            route_rows = read_csv_rows(analysis_dir / "baselines" / "route_foundation_patterns.csv")
            evidence_rows = read_csv_rows(analysis_dir / "evidence" / "evidence_records.csv")

            self.assertEqual({row["author"] for row in label_rows}, {"柏拉图的石头", "第二作者"})
            self.assertEqual({row["author"] for row in baseline_rows}, {"柏拉图的石头", "第二作者"})
            self.assertTrue(isinstance(foundation_rows, list))
            self.assertTrue(route_rows)
            self.assertTrue(any(row["author"] == "柏拉图的石头" for row in evidence_rows))
            self.assertTrue(any(row["author"] == "第二作者" for row in evidence_rows))

    def test_write_phase2_exports_author_rerun_keeps_full_route_foundations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            analysis_dir = tmp / "analysis"
            author_a_rows = []
            author_b_rows = []

            for idx in range(1, 7):
                author_a_rows.append(
                    self._make_row(
                        tmp=tmp,
                        work_id=f"route_a_{idx}",
                        title=f"制度机制拆解 A{idx}",
                        likes=180 - idx,
                        comments=16,
                        favorites=24,
                        shares=10,
                        duration_seconds=210,
                        body=(
                            "为什么制度设计最后总会反噬自己？真正的关键，是执行权和解释权被绑在了一起。"
                            "关注我，下一条继续拆。"
                            if idx <= 4
                            else "制度设计最后会反噬自己，关键在于执行权和解释权被绑在了一起。"
                            "关注我，下一条继续拆。"
                        ),
                    )
                )

            for idx in range(1, 7):
                author_b_rows.append(
                    self._make_row(
                        tmp=tmp,
                        work_id=f"route_b_{idx}",
                        title=f"制度机制拆解 B{idx}",
                        likes=140 - idx,
                        comments=12,
                        favorites=18,
                        shares=8,
                        duration_seconds=210,
                        body=(
                            "为什么制度设计最后总会反噬自己？真正的关键，是执行权和解释权被绑在了一起。"
                            "关注我，下一条继续拆。"
                        ),
                        author="第二作者",
                        account_link="https://example.com/u/2",
                    )
                )

            full_rows = [*author_a_rows, *author_b_rows]
            write_phase2_exports(analyze_phase2_rows(full_rows), analysis_dir)
            write_phase2_exports(
                analyze_phase2_rows(author_a_rows, route_baseline_rows=full_rows),
                analysis_dir,
                target_authors=("柏拉图的石头",),
            )

            route_rows = read_csv_rows(analysis_dir / "baselines" / "route_foundation_patterns.csv")
            target_rows = [
                row
                for row in route_rows
                if row["route_content_type"] == "concept_explainer"
                and row["route_format"] == "long_explainer"
                and row["route_goal"] == "follow"
                and row["feature_name"] == "opening_problem_presence"
                and row["feature_value"] == "yes"
            ]
            self.assertEqual(len(target_rows), 1)
            self.assertEqual(target_rows[0]["row_count"], "12")
            self.assertEqual(target_rows[0]["support_count"], "10")

    def test_write_phase2_exports_clears_author_scoped_outputs_when_author_now_has_zero_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            analysis_dir = tmp / "analysis"

            author_a_rows = [
                self._make_row(
                    tmp=tmp,
                    work_id="5001",
                    title="为什么唐朝太监能废立天子",
                    likes=220,
                    comments=20,
                    favorites=35,
                    shares=15,
                    duration_seconds=220,
                    body="为什么同样是太监干政，唐朝太监却能废立天子？今天我们只说一个核心原因。",
                ),
                self._make_row(
                    tmp=tmp,
                    work_id="5002",
                    title="晚唐皇帝总被太监压制",
                    likes=15,
                    comments=1,
                    favorites=2,
                    shares=1,
                    duration_seconds=180,
                    body="今天聊聊晚唐背景，先铺垫，再进入主题。",
                ),
            ]
            author_b_rows = [
                self._make_row(
                    tmp=tmp,
                    work_id="6001",
                    title="AI 为什么总让人焦虑",
                    likes=260,
                    comments=22,
                    favorites=40,
                    shares=18,
                    duration_seconds=210,
                    body="为什么 AI 会让很多人焦虑？因为它同时冲击效率和判断边界。",
                    author="第二作者",
                    account_link="https://example.com/u/2",
                ),
                self._make_row(
                    tmp=tmp,
                    work_id="6002",
                    title="AI 叙事为什么总是跑偏",
                    likes=20,
                    comments=2,
                    favorites=3,
                    shares=1,
                    duration_seconds=170,
                    body="今天继续补一点背景，慢慢进入主题。",
                    author="第二作者",
                    account_link="https://example.com/u/2",
                ),
            ]

            write_phase2_exports(analyze_phase2_rows(author_a_rows), analysis_dir)
            write_phase2_exports(analyze_phase2_rows(author_b_rows), analysis_dir)
            write_phase2_exports(
                Phase2AnalysisResult([], [], [], [], [], []),
                analysis_dir,
                target_authors=("柏拉图的石头",),
            )

            label_rows = read_csv_rows(analysis_dir / "labels" / "row_labels.csv")
            baseline_rows = read_csv_rows(analysis_dir / "baselines" / "author_baselines.csv")
            foundation_rows = read_csv_rows(analysis_dir / "baselines" / "author_foundation_patterns.csv")
            contrast_rows = read_csv_rows(analysis_dir / "contrasts" / "author_high_low.csv")
            evidence_rows = read_csv_rows(analysis_dir / "evidence" / "evidence_records.csv")

            self.assertEqual({row["author"] for row in label_rows}, {"第二作者"})
            self.assertEqual({row["author"] for row in baseline_rows}, {"第二作者"})
            self.assertTrue(isinstance(foundation_rows, list))
            self.assertEqual({row["author"] for row in contrast_rows}, {"第二作者"})
            self.assertEqual({row["author"] for row in evidence_rows}, {"第二作者"})

    def test_select_phase2_ready_uses_txt_and_dedup_not_download_or_asr(self) -> None:
        rows = [
            {
                "work_id": "7001",
                "author": "柏拉图的石头",
                "download_status": "pending",
                "asr_status": "pending",
                "txt_sync_status": "ok",
                "dedup_status": "unique",
                "txt_path": "D:/runtime/corpus/柏拉图的石头/transcripts/7001.txt",
                "legacy_txt_path": "D:/legacy/柏拉图的石头/整理版/01.txt",
            },
            {
                "work_id": "7002",
                "author": "柏拉图的石头",
                "download_status": "ok",
                "asr_status": "ok",
                "txt_sync_status": "pending",
                "dedup_status": "unknown",
                "txt_path": "D:/runtime/corpus/柏拉图的石头/transcripts/7002.txt",
                "legacy_txt_path": "",
            },
        ]
        selected = select_phase2_ready(rows)
        self.assertEqual([row["work_id"] for row in selected], ["7001"])

    def _make_row(
        self,
        *,
        tmp: Path,
        work_id: str,
        title: str,
        likes: int,
        comments: int,
        favorites: int,
        shares: int,
        duration_seconds: int,
        body: str,
        author: str = "柏拉图的石头",
        account_link: str = "https://example.com/u/1",
    ) -> dict[str, str]:
        txt_path = tmp / f"{work_id}.txt"
        row = {
            "title": title,
            "author": author,
            "work_id": work_id,
            "followers": "1000",
            "account_link": account_link,
            "video_link": f"https://example.com/v/{work_id}",
            "publish_time": "2026-05-03 12:00",
            "duration_text": "03:00",
            "duration_seconds": str(duration_seconds),
            "likes": str(likes),
            "comments": str(comments),
            "favorites": str(favorites),
            "shares": str(shares),
            "raw_video_path": f"D:/raw/{work_id}.mp4",
            "asr_provider": "siliconflow",
            "asr_quality_grade": "B",
            "manual_reviewed": "no",
            "dedup_status": "unique",
            "download_status": "ok",
            "asr_status": "ok",
            "txt_sync_status": "ok",
            "txt_path": str(txt_path),
        }
        write_standard_transcript(output_path=txt_path, content=render_standard_transcript(row, body))
        return row


if __name__ == "__main__":
    unittest.main()
