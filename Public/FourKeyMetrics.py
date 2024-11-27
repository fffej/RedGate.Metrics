import os
import datetime
import subprocess
import json

def invoke_four_key_metrics_report_generation(octopus_feed_api_key, checkout_location, product_name, release_tag_pattern, fix_tag_pattern, report_package_name=None, report_version_number=None, repo_sub_dirs=None, start_date="01/01/2018", lookback_months=12, window_size_days=30, window_interval_days=7, out_file_path=".", ignore_releases=None, out_file_name="index.html"):
    if repo_sub_dirs is None:
        repo_sub_dirs = [""]
    if ignore_releases is None:
        ignore_releases = [""]

    release_metrics = get_release_metrics_for_checkout(checkout_location, release_tag_pattern, fix_tag_pattern, start_date, repo_sub_dirs, ignore_releases)
    bucketed_release_metrics = get_bucketed_release_metrics_for_report(lookback_months, release_metrics, window_size_days, window_interval_days)
    report_file = new_four_key_metrics_report(bucketed_release_metrics, product_name, out_file_path, f"{window_size_days} days", out_file_name)

    if publish_credentials_provided(octopus_feed_api_key, report_package_name, report_version_number):
        publish_four_key_metrics_report(report_file, report_package_name, octopus_feed_api_key, report_version_number)

    return report_file

def get_release_metrics_for_checkout(checkout_location, release_tag_pattern, fix_tag_pattern, start_date, repo_sub_dirs=None, ignore_releases=None):
    if repo_sub_dirs is None:
        repo_sub_dirs = [""]
    if ignore_releases is None:
        ignore_releases = [""]

    os.chdir(checkout_location)
    releases = get_releases(release_tag_pattern, fix_tag_pattern)
    release_metrics = get_release_metrics(releases, repo_sub_dirs, start_date, ignore_releases)
    os.chdir("..")
    return release_metrics

def get_releases(release_tag_pattern, fix_tag_pattern):
    git_command = f"git for-each-ref --sort='-taggerdate' --format='%(taggerdate:iso8601),%(refname),' 'refs/tags/{release_tag_pattern}'"
    raw_release_tags = subprocess.check_output(git_command, shell=True).decode().strip().split("\n")

    releases = []
    for tag in raw_release_tags:
        split = tag.split(",")
        if split[0] == "":
            print(f"Warning: Tag {split[1]} is a light-weight tag and will be ignored")
            continue

        releases.append({
            "TagRef": split[1],
            "Date": datetime.datetime.strptime(split[0], "%Y-%m-%d %H:%M:%S %z"),
            "IsFix": fnmatch.fnmatch(split[1], f"refs/tags/{fix_tag_pattern}")
        })
    return releases

def get_release_metrics(releases, sub_dirs, start_date, ignore_releases, authors=None, component_name=None):
    releases = sorted(releases, key=lambda x: x["Date"])
    previous_success = releases[0]
    release_metrics = []

    for i in range(len(releases) - 1):
        previous_release = releases[i]
        this_release = releases[i + 1]

        if previous_release["Date"] <= start_date:
            continue

        if not previous_release["IsFix"]:
            previous_success = previous_release

        if this_release["IsFix"]:
            next_release = releases[i + 2] if i + 2 < len(releases) else None
            failure_duration = None if next_release and next_release["IsFix"] else this_release["Date"] - previous_success["Date"]
        else:
            failure_duration = None

        if assert_release_not_ignored(this_release["TagRef"], ignore_releases):
            commit_ages = [this_release["Date"] - commit["Date"] for commit in get_commits_between_tags(previous_release["TagRef"], this_release["TagRef"], sub_dirs, authors)]
        else:
            commit_ages = None

        if commit_ages is None:
            print(f"Warning: Release {this_release['TagRef']} has no relevant commits and will be ignored")
        else:
            release_metrics.append({
                "Component": component_name,
                "From": previous_release["TagRef"],
                "To": this_release["TagRef"],
                "FromDate": previous_release["Date"],
                "ToDate": this_release["Date"],
                "Interval": this_release["Date"] - previous_release["Date"],
                "IsFix": this_release["IsFix"],
                "FailureDuration": failure_duration,
                "CommitAges": commit_ages
            })

    return release_metrics

def assert_release_not_ignored(this_release_tag_ref, ignore_releases):
    return not any(fnmatch.fnmatch(this_release_tag_ref, f"refs/tags/{ignore_release}") for ignore_release in ignore_releases)

def get_commits_between_tags(start, end, sub_dirs, authors):
    author_filter = " ".join([f"--author='{author}'" for author in authors]) if authors else ""
    git_command = f"git log --pretty=format:'%h,%ai' '{start}..{end}' --no-merges {author_filter} -- {' '.join(sub_dirs)}"
    raw_commits = subprocess.check_output(git_command, shell=True).decode().strip().split("\n")

    commits = []
    for commit in raw_commits:
        split = commit.split(",")
        commits.append({
            "SHA": split[0],
            "Date": datetime.datetime.strptime(split[1], "%Y-%m-%d %H:%M:%S %z")
        })
    return commits

def get_bucketed_release_metrics_for_report(lookback_months, release_metrics, window_size_days, window_interval_days):
    now = datetime.datetime.now()
    earliest_date = now - datetime.timedelta(days=lookback_months * 30)

    bucketed_metrics = []
    end_date = now
    while end_date > earliest_date:
        start_date = end_date - datetime.timedelta(days=window_size_days)
        lookback_releases = [release for release in release_metrics if start_date <= release["ToDate"] <= end_date]
        bucketed_metrics.append(get_bucketed_metrics_for_period(lookback_releases, end_date))
        end_date -= datetime.timedelta(days=window_interval_days)

    return bucketed_metrics

def merge_release_metrics_into_one_pseudo_repository(release_metrics):
    release_metrics = sorted(release_metrics, key=lambda x: x["ToDate"], reverse=True)
    broken_components = []
    last_fix = 0

    for i in range(len(release_metrics) - 1):
        previous_metric = release_metrics[i + 1]
        release_metrics[i]["FromDate"] = previous_metric["ToDate"]
        release_metrics[i]["Interval"] = release_metrics[i]["ToDate"] - previous_metric["ToDate"]

        if release_metrics[i]["IsFix"]:
            if broken_components:
                release_metrics[i]["IsFix"] = False

            if not broken_components:
                last_fix = i

            if release_metrics[i]["Component"] not in broken_components:
                broken_components.append(release_metrics[i]["Component"])
        else:
            if release_metrics[i]["Component"] in broken_components:
                broken_components.remove(release_metrics[i]["Component"])

                if not broken_components:
                    release_metrics[last_fix]["FailureDuration"] = release_metrics[last_fix]["ToDate"] - release_metrics[i]["ToDate"]

    if broken_components:
        final_metric = len(release_metrics) - 1
        if release_metrics[final_metric]["IsFix"]:
            release_metrics[last_fix]["FailureDuration"] = release_metrics[last_fix]["ToDate"] - release_metrics[final_metric]["FromDate"]
        else:
            release_metrics[last_fix]["FailureDuration"] = release_metrics[last_fix]["ToDate"] - release_metrics[final_metric]["ToDate"]

    return release_metrics

def get_bucketed_metrics_for_period(release_metrics, end_date):
    release_count = len(release_metrics)
    failed_release_count = len([release for release in release_metrics if release["IsFix"]])

    if release_count > 0:
        deployment_frequency_days = sum([release["Interval"].days for release in release_metrics]) / release_count
        fail_rate = failed_release_count / release_count
        lead_times = [commit_age for release in release_metrics if release["CommitAges"] for commit_age in release["CommitAges"]]
        lead_time_median = get_median(lead_times)
    else:
        deployment_frequency_days = None
        fail_rate = None
        lead_time_median = None

    if failed_release_count > 0:
        mttr_measures = [release["FailureDuration"].total_seconds() / 3600 for release in release_metrics if release["IsFix"]]
        mttr_average = sum(mttr_measures) / len(mttr_measures)
    else:
        mttr_average = None

    return {
        "EndDate": end_date,
        "Releases": release_count,
        "DeploymentFrequencyDays": deployment_frequency_days,
        "MttrHours": mttr_average,
        "LeadTimeDays": lead_time_median,
        "FailRate": fail_rate
    }

def get_median(lead_times):
    ordered_lead_times = sorted(lead_times)
    number_of_commit_ages = len(ordered_lead_times)

    if number_of_commit_ages > 0:
        is_even_number_of_commit_ages = number_of_commit_ages % 2 == 0

        if is_even_number_of_commit_ages:
            midh = number_of_commit_ages // 2
            return (ordered_lead_times[midh - 1].days + ordered_lead_times[midh].days) / 2
        else:
            mid = number_of_commit_ages // 2
            return ordered_lead_times[mid].days

    return None

def new_four_key_metrics_report(metrics, product_name, out_file_path=".", window_size="30 days", out_file_name="index.html"):
    report_start_date = metrics[0]["EndDate"]
    report_end_date = metrics[-1]["EndDate"]
    report_file = os.path.join(out_file_path, out_file_name)
    data = ",\n".join([convert_to_json_with_javascript(period) for period in metrics])

    with open(os.path.join(os.path.dirname(__file__), "FourKeyMetricsTemplate.html"), "r") as template_file:
        template = template_file.read()

    with open(report_file, "w") as report:
        report.write(template.replace("DATA_PLACEHOLDER", data)
                             .replace("PRODUCTNAME_PLACEHOLDER", product_name)
                             .replace("WINDOWSIZE_PLACEHOLDER", window_size)
                             .replace("REPORTSTARTDATE_PLACEHOLDER", f"new Date({datetime_to_timestamp(report_start_date)})")
                             .replace("REPORTENDDATE_PLACEHOLDER", f"new Date({datetime_to_timestamp(report_end_date)})"))

    return report_file

def convert_to_json_with_javascript(period):
    return f"[new Date({datetime_to_timestamp(period['EndDate'])}), {value_or_null(period['DeploymentFrequencyDays'])}, {value_or_null(period['LeadTimeDays'])}, {value_or_null(period['FailRate'])}, {value_or_null(period['MttrHours'])}]"

def value_or_null(value):
    return "null" if value is None else value

def datetime_to_timestamp(datetime_obj):
    return int(datetime_obj.timestamp() * 1000)

def publish_credentials_provided(octopus_feed_api_key, report_package_name, report_version_number):
    if not report_package_name or not octopus_feed_api_key or not report_version_number:
        print("Warning: Publish credentials not provided - skipping publish step")
        return False
    return True

def publish_four_key_metrics_report(report_file, package_name, octopus_feed_api_key, version_number):
    output_zip = f"{package_name.replace(' ', '')}.{version_number}.zip"
    subprocess.check_call(["zip", "-r", output_zip, report_file])

    if octopus_feed_api_key:
        try:
            package_path = os.path.abspath(output_zip)
            subprocess.check_call(["curl", "-X", "POST", f"https://octopus.red-gate.com/api/packages/raw?apiKey={octopus_feed_api_key}", "--upload-file", package_path])
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")
            raise
