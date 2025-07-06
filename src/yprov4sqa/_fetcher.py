import time, sys, json, requests, argparse, os
from datetime import datetime


TOKEN = os.getenv("GITHUB_TOKEN")   # None if not set

def github_get(url, params=None, *, max_wait=3600):
    """
    Wrapper around requests.get that handles GitHub rate-limiting
    (403/429) automatically.  Returns the response only when 200 OK.
    """
    while True:
        headers = {"Authorization": f"token {TOKEN}"} if TOKEN else {}
        r = requests.get(url, params=params, headers=headers, timeout=30)
        if r.status_code in (403, 429):
            reset_ts = int(r.headers.get("X-RateLimit-Reset", 0))
            remain   = int(r.headers.get("X-RateLimit-Remaining", 0))
            if remain == 0 and reset_ts:
                wait_sec = reset_ts - int(time.time()) + 2
                if wait_sec <= max_wait:
                    print(f"\nGitHub rate-limit hit (403). "
                          f"Waiting {wait_sec} s until {time.strftime('%H:%M:%S', time.gmtime(reset_ts))} …")
                    time.sleep(wait_sec)
                    continue
            print("\nGitHub returned 403 Forbidden – probably rate-limit exceeded. "
                  "Try again later or authenticate (GITHUB_TOKEN).")
            sys.exit(1)
        if r.status_code == 404:
            return r
        r.raise_for_status()
        return r


def fetch_all_branches(repo_name):
    """Fetch all branches from the GitHub API, handling pagination."""
    repo_api_url = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas/branches'
    branches = []
    page = 1

    print("Fetching branches...")

    while True:
        response = github_get(f"{repo_api_url}?page={page}&per_page=100")
        if response.status_code != 200:
            print(f"Failed to fetch branches. Status code: {response.status_code}")
            return branches

        new_branches = response.json()
        if not new_branches:
            break

        branches.extend(new_branches)
        page += 1

    print(f"Fetched {len(branches)} branches.")
    return branches

def fetch_assessment_reports(repo_name):
    """Fetch assessment reports from all branches and sort by date."""
    repo_api_url = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas'
    file_path = '.report/assessment_output.json'
    project_folder = f'./{repo_name}_SQAaaS_reports'

    if not os.path.exists(project_folder):
        os.makedirs(project_folder)

    print(f"Fetching reports from: https://github.com/eosc-synergy/{repo_name}.assess.sqaaas")

    branches = fetch_all_branches(repo_name)
    all_commits = []

    for branch in branches:
        branch_name = branch['name']
        commits_url = f'{repo_api_url}/commits?sha={branch_name}&path={file_path}&per_page=100'
        commits_response = github_get(commits_url)
        if commits_response.status_code != 200:
            continue

        commits = commits_response.json()

        for commit in commits:
            commit_hash = commit['sha']
            commit_date = commit['commit']['committer']['date']
            iso_time = datetime.fromisoformat(commit_date.replace('Z', '+00:00')).strftime('%Y-%m-%dT%H_%M_%SZ')
            all_commits.append((commit_hash, commit_date, branch_name, iso_time))


    all_commits.sort(key=lambda x: x[3])
    total_commits = len(all_commits)
    print(f"Total assessments to process: {total_commits}")

    processed_commits = {}

    for index, (commit_hash, _, branch_name, iso_time) in enumerate(all_commits, start=1):
        file_url = f'https://raw.githubusercontent.com/eosc-synergy/{repo_name}.assess.sqaaas/{commit_hash}/{file_path}'
        file_response = github_get(file_url)
        if file_response.status_code != 200:
            continue

        file_content = file_response.text
        commit_last4 = commit_hash[-4:]

        try:
            report_data = json.loads(file_content)

            #Only allow reports with "repository" as a list
            repository_data = report_data.get("repository", [])
            if not isinstance(repository_data, list):
                #print(f"Skipping commit {commit_hash}: 'repository' is not a list")
                continue

            if not repository_data or not isinstance(repository_data[0], dict):
                #print(f"Skipping commit {commit_hash}: invalid 'repository' list contents")
                continue

            commit_id_in_report = repository_data[0].get("commit_id")
            if not commit_id_in_report:
                #print(f"Skipping commit {commit_hash}: 'commit_id' not found in 'repository'")
                continue

        except json.JSONDecodeError:
            print(f"Failed to parse report file for commit {commit_hash}")
            continue

        # Handle duplicates
        if commit_id_in_report in processed_commits:
            old_report_path = processed_commits[commit_id_in_report]
            if os.path.exists(old_report_path):
                os.remove(old_report_path)
                #print(f"Removed old report for commit {commit_id_in_report}")

        # Save the valid report
        safe_branch = branch_name.replace("/", "_").replace("\\", "_")
        report_filename = f"{iso_time}_{index:04d}_{commit_last4}_{safe_branch}.json"
        report_file_path = os.path.join(project_folder, report_filename)
        
        os.makedirs(os.path.dirname(report_file_path), exist_ok=True)

        with open(report_file_path, 'w') as f:
            f.write(file_content)

        processed_commits[commit_id_in_report] = report_file_path

        percent = (index / total_commits) * 100
        print(f"Processing assessments: {percent:.2f}%", end="\r")

    print(f"\nCompleted. Reports saved in '{project_folder}'.")

def check_repo_exists(repo_name):
    """Check if the repository exists on GitHub."""
    repo_api_url = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas'
    try:
        response = github_get(repo_api_url)
        if response.status_code == 404:
            print(f"Repository '{repo_name}' does not exist.")
            return False
        elif response.status_code == 200:
            return True
        else:
            print(f"Failed to check repository. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Fetch SQAaaS reports for a specific repository.")
    parser.add_argument('repo_name', type=str, help="The repository name (e.g., 'my-repo')")
    args = parser.parse_args()

    if check_repo_exists(args.repo_name):
        fetch_assessment_reports(args.repo_name)

if __name__ == "__main__":
    main()
