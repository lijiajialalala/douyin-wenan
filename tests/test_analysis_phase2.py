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

            question_hook_evidence = [
                record
                for record in result.evidence_records
                if record["feature_name"] == "style_family" and record["feature_value"] == "question_hook"
            ]
            self.assertTrue(question_hook_evidence)
            self.assertEqual(question_hook_evidence[0]["scope"], "same_author")
            self.assertEqual(question_hook_evidence[0]["confidence_grade"], "E2")
            self.assertEqual(question_hook_evidence[0]["ready_for_distillation"], "yes")

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
            evidence_rows = read_csv_rows(analysis_dir / "evidence" / "evidence_records.csv")

            self.assertEqual({row["author"] for row in label_rows}, {"柏拉图的石头", "第二作者"})
            self.assertEqual({row["author"] for row in baseline_rows}, {"柏拉图的石头", "第二作者"})
            self.assertTrue(any(row["author"] == "柏拉图的石头" for row in evidence_rows))
            self.assertTrue(any(row["author"] == "第二作者" for row in evidence_rows))

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
                Phase2AnalysisResult([], [], [], []),
                analysis_dir,
                target_authors=("柏拉图的石头",),
            )

            label_rows = read_csv_rows(analysis_dir / "labels" / "row_labels.csv")
            baseline_rows = read_csv_rows(analysis_dir / "baselines" / "author_baselines.csv")
            contrast_rows = read_csv_rows(analysis_dir / "contrasts" / "author_high_low.csv")
            evidence_rows = read_csv_rows(analysis_dir / "evidence" / "evidence_records.csv")

            self.assertEqual({row["author"] for row in label_rows}, {"第二作者"})
            self.assertEqual({row["author"] for row in baseline_rows}, {"第二作者"})
            self.assertEqual({row["author"] for row in contrast_rows}, {"第二作者"})
            self.assertEqual({row["author"] for row in evidence_rows}, {"第二作者"})

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
