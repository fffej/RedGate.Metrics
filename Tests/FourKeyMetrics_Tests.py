import unittest
from datetime import datetime, timedelta
from Public.FourKeyMetrics import (
    get_median,
    merge_release_metrics_into_one_pseudo_repository,
    get_bucketed_metrics_for_period,
    get_bucketed_release_metrics_for_report,
    assert_release_not_ignored,
    get_releases,
    get_commits_between_tags,
    get_release_metrics,
    value_or_null,
)

class TestFourKeyMetrics(unittest.TestCase):

    def test_get_median(self):
        self.assertEqual(get_median([timedelta(days=1), timedelta(days=2)]), 1.5)
        self.assertEqual(get_median([timedelta(days=2), timedelta(days=1)]), 1.5)
        self.assertEqual(get_median([timedelta(days=0), timedelta(days=2), timedelta(days=3)]), 2)
        self.assertEqual(get_median([timedelta(days=2), timedelta(days=3), timedelta(days=0)]), 2)
        self.assertEqual(get_median([timedelta(days=1), timedelta(days=2), timedelta(days=3), timedelta(days=4)]), 2.5)
        self.assertEqual(get_median([timedelta(days=2), timedelta(days=4), timedelta(days=3), timedelta(days=1)]), 2.5)

    def test_merge_release_metrics_into_one_pseudo_repository(self):
        releases = [
            {
                "Component": "Component1",
                "From": "releases/0.0",
                "To": "releases/0.1",
                "FromDate": datetime(2019, 4, 1),
                "ToDate": datetime(2019, 5, 13),
                "Interval": timedelta(days=42),
                "IsFix": False,
                "FailureDuration": timedelta(days=42),
                "CommitAges": [timedelta(days=20)],
            },
            {
                "Component": "Component1",
                "From": "releases/0.1",
                "To": "releases/0.2",
                "FromDate": datetime(2019, 5, 13),
                "ToDate": datetime(2019, 5, 21),
                "Interval": timedelta(days=8),
                "IsFix": False,
                "FailureDuration": timedelta(days=8),
                "CommitAges": [timedelta(days=3.5)],
            },
            {
                "Component": "Component1",
                "From": "releases/0.2",
                "To": "releases/0.3/fix",
                "FromDate": datetime(2019, 5, 21),
                "ToDate": datetime(2019, 5, 24),
                "Interval": timedelta(days=3),
                "IsFix": True,
                "FailureDuration": timedelta(days=3),
                "CommitAges": [timedelta(days=0.5)],
            },
            {
                "Component": "Component2",
                "From": "releases/0.1",
                "To": "releases/0.2",
                "FromDate": datetime(2019, 5, 12),
                "ToDate": datetime(2019, 5, 22),
                "Interval": timedelta(days=10),
                "IsFix": False,
                "FailureDuration": timedelta(days=10),
                "CommitAges": [timedelta(days=2)],
            },
        ]

        merged_metrics = merge_release_metrics_into_one_pseudo_repository(releases)

        expected_releases_after_merge = [
            {
                "Component": "Component1",
                "From": "releases/0.2",
                "To": "releases/0.3/fix",
                "FromDate": datetime(2019, 5, 22),
                "ToDate": datetime(2019, 5, 24),
                "Interval": timedelta(days=2),
                "IsFix": True,
                "FailureDuration": timedelta(days=3),
                "CommitAges": [timedelta(days=0.5)],
            },
            {
                "Component": "Component2",
                "From": "releases/0.1",
                "To": "releases/0.2",
                "FromDate": datetime(2019, 5, 21),
                "ToDate": datetime(2019, 5, 22),
                "Interval": timedelta(days=1),
                "IsFix": False,
                "FailureDuration": timedelta(days=10),
                "CommitAges": [timedelta(days=2)],
            },
            {
                "Component": "Component1",
                "From": "releases/0.1",
                "To": "releases/0.2",
                "FromDate": datetime(2019, 5, 13),
                "ToDate": datetime(2019, 5, 21),
                "Interval": timedelta(days=8),
                "IsFix": False,
                "FailureDuration": timedelta(days=8),
                "CommitAges": [timedelta(days=3.5)],
            },
            {
                "Component": "Component1",
                "From": "releases/0.0",
                "To": "releases/0.1",
                "FromDate": datetime(2019, 4, 1),
                "ToDate": datetime(2019, 5, 13),
                "Interval": timedelta(days=42),
                "IsFix": False,
                "FailureDuration": timedelta(days=42),
                "CommitAges": [timedelta(days=20)],
            },
        ]

        self.assertEqual(len(merged_metrics), len(expected_releases_after_merge))
        for i in range(len(expected_releases_after_merge)):
            self.assertEqual(merged_metrics[i]["Component"], expected_releases_after_merge[i]["Component"])
            self.assertEqual(merged_metrics[i]["From"], expected_releases_after_merge[i]["From"])
            self.assertEqual(merged_metrics[i]["To"], expected_releases_after_merge[i]["To"])
            self.assertEqual(merged_metrics[i]["FromDate"], expected_releases_after_merge[i]["FromDate"])
            self.assertEqual(merged_metrics[i]["ToDate"], expected_releases_after_merge[i]["ToDate"])
            self.assertEqual(merged_metrics[i]["Interval"], expected_releases_after_merge[i]["Interval"])
            self.assertEqual(merged_metrics[i]["IsFix"], expected_releases_after_merge[i]["IsFix"])
            self.assertEqual(merged_metrics[i]["FailureDuration"], expected_releases_after_merge[i]["FailureDuration"])
            self.assertEqual(merged_metrics[i]["CommitAges"], expected_releases_after_merge[i]["CommitAges"])

    def test_get_bucketed_metrics_for_period(self):
        releases = [
            {
                "From": "releases/0.1",
                "To": "releases/0.2",
                "FromDate": datetime(2019, 5, 16),
                "ToDate": datetime(2019, 5, 17),
                "Interval": timedelta(days=1),
                "IsFix": False,
                "CommitAges": [timedelta(hours=24)],
            },
            {
                "From": "releases/0.2",
                "To": "releases/0.3/fix",
                "FromDate": datetime(2019, 5, 17),
                "ToDate": datetime(2019, 5, 21),
                "Interval": timedelta(days=4),
                "IsFix": True,
                "FailureDuration": timedelta(days=4),
                "CommitAges": [timedelta(hours=24)],
            },
        ]

        end_date = datetime(2019, 5, 21)
        bucketed_metrics = get_bucketed_metrics_for_period(releases, end_date)

        self.assertEqual(bucketed_metrics["Releases"], 2)
        self.assertEqual(bucketed_metrics["DeploymentFrequencyDays"], 2.5)
        self.assertEqual(bucketed_metrics["MttrHours"], 96)
        self.assertEqual(bucketed_metrics["LeadTimeDays"], 1)
        self.assertEqual(bucketed_metrics["FailRate"], 0.5)
        self.assertEqual(bucketed_metrics["EndDate"], end_date)

    def test_get_bucketed_release_metrics_for_report(self):
        releases = [
            {
                "From": "releases/0.0",
                "To": "releases/0.1",
                "FromDate": datetime(2019, 4, 1),
                "ToDate": datetime(2019, 5, 13),
                "Interval": timedelta(days=42),
                "IsFix": False,
                "FailureDuration": timedelta(days=0),
                "CommitAges": [timedelta(days=20)],
            },
            {
                "From": "releases/0.1",
                "To": "releases/0.2",
                "FromDate": datetime(2019, 5, 13),
                "ToDate": datetime(2019, 5, 21),
                "Interval": timedelta(days=8),
                "IsFix": False,
                "FailureDuration": timedelta(days=0),
                "CommitAges": [timedelta(days=3.5)],
            },
            {
                "From": "releases/0.2",
                "To": "releases/0.3/fix",
                "FromDate": datetime(2019, 5, 21),
                "ToDate": datetime(2019, 5, 22),
                "Interval": timedelta(days=1),
                "IsFix": True,
                "FailureDuration": timedelta(days=1),
                "CommitAges": [timedelta(days=0.5)],
            },
            {
                "From": "releases/0.3/fix",
                "To": "releases/0.4",
                "FromDate": datetime(2019, 5, 22),
                "ToDate": datetime(2019, 5, 28),
                "Interval": timedelta(days=6),
                "IsFix": False,
                "FailureDuration": timedelta(days=0),
                "CommitAges": [timedelta(days=2)],
            },
            {
                "From": "releases/0.4",
                "To": "releases/0.5",
                "FromDate": datetime(2019, 5, 28),
                "ToDate": datetime(2019, 6, 4),
                "Interval": timedelta(days=7),
                "IsFix": False,
                "FailureDuration": timedelta(days=0),
                "CommitAges": [timedelta(days=4)],
            },
        ]

        def mock_get_date():
            return datetime(2019, 6, 7)

        get_date_backup = get_bucketed_release_metrics_for_report.__globals__.get("get_date")
        get_bucketed_release_metrics_for_report.__globals__["get_date"] = mock_get_date

        metrics = get_bucketed_release_metrics_for_report(releases, lookback_months=1, window_size_days=14, window_interval_days=7)
        metrics = sorted(metrics, key=lambda x: x["EndDate"], reverse=True)

        expected_end_dates = [
            datetime(2019, 6, 7),
            datetime(2019, 5, 31),
            datetime(2019, 5, 24),
            datetime(2019, 5, 17),
            datetime(2019, 5, 10),
        ]

        self.assertEqual([metric["EndDate"] for metric in metrics], expected_end_dates)

        expected_releases = [2, 3, 3, 1, 0]
        expected_deployment_frequency_days = [6.5, 5, 17, 42, None]
        expected_lead_time_days = [3, 2, 4, 20, None]
        expected_fail_rate = [0, 1/3, 1/3, 0, None]
        expected_mttr_hours = [None, 24, 24, None, None]

        self.assertEqual([metric["Releases"] for metric in metrics], expected_releases)
        self.assertEqual([metric["DeploymentFrequencyDays"] for metric in metrics], expected_deployment_frequency_days)
        self.assertEqual([metric["LeadTimeDays"] for metric in metrics], expected_lead_time_days)
        self.assertEqual([metric["FailRate"] for metric in metrics], expected_fail_rate)
        self.assertEqual([metric["MttrHours"] for metric in metrics], expected_mttr_hours)

        get_bucketed_release_metrics_for_report.__globals__["get_date"] = get_date_backup

    def test_assert_release_not_ignored(self):
        self.assertTrue(assert_release_not_ignored("refs/tags/someTag", []))
        self.assertFalse(assert_release_not_ignored("refs/tags/releaseToIgnore", ["releaseToIgnore"]))
        self.assertTrue(assert_release_not_ignored("refs/tags/someTag", ["releaseToIgnore"]))
        self.assertFalse(assert_release_not_ignored("refs/tags/anotherReleaseToIgnore", ["releaseToIgnore", "anotherReleaseToIgnore"]))
        self.assertTrue(assert_release_not_ignored("refs/tags/someTag", ["releaseToIgnore", "anotherReleaseToIgnore"]))

    def test_get_releases(self):
        with unittest.mock.patch("subprocess.check_output", return_value=b"2019-06-11 12:11:25 +0100,refs/tags/releases/5.0.3.1680,\n2019-06-03 10:34:37 +0100,refs/tags/releases/5.0.2.1664,"):
            releases = get_releases("releaseTagPattern", "fixtagPattern")
            self.assertEqual(len(releases), 2)
            self.assertEqual(releases[0]["TagRef"], "refs/tags/releases/5.0.3.1680")
            self.assertEqual(releases[0]["Date"], datetime.strptime("2019-06-11 12:11:25 +0100", "%Y-%m-%d %H:%M:%S %z"))
            self.assertFalse(releases[0]["IsFix"])
            self.assertEqual(releases[1]["TagRef"], "refs/tags/releases/5.0.2.1664")
            self.assertEqual(releases[1]["Date"], datetime.strptime("2019-06-03 10:34:37 +0100", "%Y-%m-%d %H:%M:%S %z"))
            self.assertFalse(releases[1]["IsFix"])

    def test_get_commits_between_tags(self):
        with unittest.mock.patch("subprocess.check_output", return_value=b"b78adbc2f,2020-08-25 09:15:30 +0000\n17d887ea7,2020-08-25 10:54:28 +0100"):
            commits = get_commits_between_tags("releases/1", "releases/2", ["."])
            self.assertEqual(len(commits), 2)
            self.assertEqual(commits[0]["SHA"], "b78adbc2f")
            self.assertEqual(commits[0]["Date"], datetime.strptime("2020-08-25 09:15:30 +0000", "%Y-%m-%d %H:%M:%S %z"))
            self.assertEqual(commits[1]["SHA"], "17d887ea7")
            self.assertEqual(commits[1]["Date"], datetime.strptime("2020-08-25 10:54:28 +0100", "%Y-%m-%d %H:%M:%S %z"))

    def test_get_release_metrics(self):
        releases = [
            {
                "TagRef": "releases/0.0",
                "Date": datetime(2019, 4, 1),
                "IsFix": False,
            },
            {
                "TagRef": "releases/0.1/fix",
                "Date": datetime(2019, 4, 2),
                "IsFix": True,
            },
        ]

        with unittest.mock.patch("subprocess.check_output", return_value=b"b78adbc2f,2020-08-25 09:15:30 +0000\n17d887ea7,2020-08-25 10:54:28 +0100"):
            release_metrics = get_release_metrics(releases, [""], "2018-01-01")
            self.assertEqual(release_metrics[0]["Interval"], timedelta(days=1))
            self.assertTrue(release_metrics[0]["IsFix"])
            self.assertEqual(release_metrics[0]["FailureDuration"], timedelta(days=1))

    def test_value_or_null(self):
        self.assertEqual(value_or_null(5), 5)
        self.assertEqual(value_or_null("null"), "null")
        self.assertEqual(value_or_null(""), "")
        self.assertEqual(value_or_null(None), "null")

if __name__ == "__main__":
    unittest.main()
