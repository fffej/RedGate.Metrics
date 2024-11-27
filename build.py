import os
import subprocess
import datetime

def restore_build_level_packages():
    # Download paket.exe
    paket_version = ""  # Set this to the value of a specific version of paket.exe to download if need be.
    subprocess.run([os.path.join(os.path.dirname(__file__), "paket.bootstrapper.exe"), paket_version, "--prefer-nuget"], check=True)

    os.chdir(os.path.dirname(__file__))
    try:
        subprocess.run([os.path.join(os.path.dirname(__file__), "paket.exe"), "install"], check=True)
    finally:
        os.chdir("..")

def build(task=["."], configuration="Release", branch_name="dev", is_default_branch=False, nuget_feed_to_publish_to=None, nuget_feed_api_key=None, signing_service_url=None, github_api_token=None):
    restore_build_level_packages()

    os.chdir(os.path.dirname(__file__))
    try:
        subprocess.run(["powershell", "Import-Module", ".\\packages\\RedGate.Build\\tools\\RedGate.Build.psm1", "-Force", "-DisableNameChecking"], check=True)
        subprocess.run(["powershell", ".\\packages\\Invoke-Build\\tools\\Invoke-Build.ps1",
                        "-File", os.path.join(os.path.dirname(__file__), "build.ps1"),
                        "-Task", ",".join(task),
                        "-IsDefaultBranch", str(is_default_branch),
                        "-BranchName", branch_name,
                        "-NugetFeedToPublishTo", nuget_feed_to_publish_to,
                        "-NugetFeedApiKey", nuget_feed_api_key], check=True)
    finally:
        os.chdir("..")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build RedGate.Metrics.")
    parser.add_argument("-Task", type=str, nargs="*", default=["."], help="The Tasks to execute. '.' means the default task as defined in build.ps1")
    parser.add_argument("-Configuration", type=str, choices=["Release", "Debug"], default="Release", help="The Configuration to build. Either Release or Debug")
    parser.add_argument("-BranchName", type=str, default="dev", help="The name of the branch we are building (Set by Teamcity). Defaults to 'dev' for local developer builds.")
    parser.add_argument("-IsDefaultBranch", type=bool, default=False, help="Indicates whether or not BranchName represents the default branch for the source control system currently in use. Defaults to False for local developer builds.")
    parser.add_argument("-NugetFeedToPublishTo", type=str, help="(Optional) URL to the nuget feed to publish nuget packages to.")
    parser.add_argument("-NugetFeedApiKey", type=str, help="(Optional) Api Key to the nuget feed to be able to publish nuget packages.")
    parser.add_argument("-SigningServiceUrl", type=str, help="(Optional) Signing service url used to sign dll/exe.")
    parser.add_argument("-GithubAPIToken", type=str, help="(Optional) A GitHub API Access token used for Pushing and PRs")

    args = parser.parse_args()

    build(task=args.Task, configuration=args.Configuration, branch_name=args.BranchName, is_default_branch=args.IsDefaultBranch, nuget_feed_to_publish_to=args.NugetFeedToPublishTo, nuget_feed_api_key=args.NugetFeedApiKey, signing_service_url=args.SigningServiceUrl, github_api_token=args.GithubAPIToken)
