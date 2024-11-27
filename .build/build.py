import os
import subprocess
import datetime

def write_info(message):
    print(f"#### {message} ####")

def generate_version_number():
    with open(os.path.join(os.path.dirname(__file__), "version.txt"), "r") as version_file:
        version_txt = version_file.read().strip()
    version = f"{version_txt}.0"

    build_counter = os.getenv("BUILD_COUNTER")
    if build_counter:
        print(f"Overriding version number using values from Version.txt ({version_txt}) and Revision number ({build_counter})")
        version = f"{version_txt}.{build_counter}"
        # Let Teamcity know we changed the build number
        print(f"##teamcity[buildNumber '{version}']")

    nuget_package_version = new_nuget_package_version(version, branch_name, is_default_branch)
    print(f"Version number is {version}")
    print(f"Nuget packages Version number is {nuget_package_version}")
    return version, nuget_package_version

def new_nuget_package_version(version, branch_name, is_default_branch):
    if is_default_branch:
        return version
    else:
        return f"{version}-{branch_name}"

def clean(output_dir, nuget_package_path):
    write_info('Cleaning any prior build output')
    if os.path.exists(nuget_package_path):
        print(f"Deleting {nuget_package_path}")
        os.remove(nuget_package_path)
    if 'RedGate.Metrics' in sys.modules:
        print('Removing RedGate.Metrics module')
        del sys.modules['RedGate.Metrics']

def pack(output_dir, nuget_package_version, nuget_path, root_dir):
    write_info('Creating RedGate.Metrics NuGet package')
    os.makedirs(output_dir, exist_ok=True)
    result = subprocess.run([nuget_path, "pack", os.path.join(root_dir, "RedGate.Metrics.nuspec"), "-NoPackageAnalysis", "-Version", nuget_package_version, "-OutputDirectory", output_dir, "-NoDefaultExcludes"])
    if result.returncode != 0:
        raise Exception(f"Could not nuget pack RedGate.Metrics. nuget returned exit code {result.returncode}")
    nuget_output_path = os.path.abspath(os.path.join(output_dir, f"RedGate.Metrics.{nuget_package_version}.nupkg"))
    print(f"##teamcity[publishArtifacts '{nuget_output_path}']")
    return nuget_output_path

def tests(output_dir, root_dir):
    result = subprocess.run(["powershell.exe", "-Command", f"""
        Import-Module '{os.path.join(root_dir, ".build", "packages", "Pester", "tools", "Pester.psd1")}'
        Import-Module '{os.path.join(root_dir, "RedGate.Metrics.psm1")}'
        $results = Invoke-Pester -Script {os.path.join(root_dir, "Tests")} -OutputFile {os.path.join(output_dir, "TestResults.xml")} -OutputFormat NUnitXml -PassThru
        exit $results.FailedCount
    """])
    tests_failed = result.returncode
    print(f"##teamcity[importData type='nunit' path='{os.path.join(output_dir, 'TestResults.xml')}']")
    if tests_failed:
        raise Exception(f"{tests_failed} test(s) failed.")

def publish(nuget_output_path, nuget_feed_to_publish_to, nuget_feed_api_key, nuget_path):
    if nuget_feed_to_publish_to and nuget_feed_api_key:
        write_info('Publishing RedGate.Metrics NuGet package')
        subprocess.run([nuget_path, "push", nuget_output_path, "-Source", nuget_feed_to_publish_to, "-ApiKey", nuget_feed_api_key])
    else:
        write_info('Skipping - Publishing RedGate.Metrics NuGet package')

def main(is_default_branch=False, branch_name="dev", nuget_feed_to_publish_to=None, nuget_feed_api_key=None):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    output_dir = os.path.join(root_dir, ".output")
    nuget_path = os.path.join(os.path.dirname(__file__), "packages", "NuGet.Commandline", "tools", "nuget.exe")
    nuget_package_path = os.path.join(output_dir, f"RedGate.Metrics.{version}.nupkg")

    version, nuget_package_version = generate_version_number()
    clean(output_dir, nuget_package_path)
    nuget_output_path = pack(output_dir, nuget_package_version, nuget_path, root_dir)
    tests(output_dir, root_dir)
    publish(nuget_output_path, nuget_feed_to_publish_to, nuget_feed_api_key, nuget_path)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build RedGate.Metrics.")
    parser.add_argument("-IsDefaultBranch", type=bool, default=False, help="Indicates whether or not BranchName represents the default branch for the source control system currently in use. Defaults to False for local developer builds.")
    parser.add_argument("-BranchName", type=str, default="dev", help="The name of the branch we are building (Set by Teamcity). Defaults to 'dev' for local developer builds.")
    parser.add_argument("-NugetFeedToPublishTo", type=str, help="(Optional) URL to the nuget feed to publish nuget packages to.")
    parser.add_argument("-NugetFeedApiKey", type=str, help="(Optional) Api Key to the nuget feed to be able to publish nuget packages.")

    args = parser.parse_args()

    main(is_default_branch=args.IsDefaultBranch, branch_name=args.BranchName, nuget_feed_to_publish_to=args.NugetFeedToPublishTo, nuget_feed_api_key=args.NugetFeedApiKey)
