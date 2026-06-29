import json, requests, argparse, os
from datetime import datetime

from ._github import github_get, GitHubRateLimitError  # noqa: F401


def fetch_all_branches(repo_name, *, token=None):
    """Fetch all branches from the GitHub API, handling pagination."""
    repo_api_url = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas/branches'
    branches = []
    page = 1

    print("Fetching branches...")

    while True:
        response = github_get(f"{repo_api_url}?page={page}&per_page=100", token=token)
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


def _fetch_all_commits_for_file(repo_api_url, branch_name, file_path, *, token=None):
    """Paginate through ALL commits on branch_name that touched file_path."""
    commits = []
    page = 1
    while True:
        url  = (f"{repo_api_url}/commits"
                f"?sha={branch_name}&path={file_path}&per_page=100&page={page}")
        resp = github_get(url, token=token)
        if resp.status_code != 200:
            break
        batch = resp.json()
        if not batch:
            break
        commits.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return commits


def fetch_assessment_reports(repo_name, *, token=None, on_progress=None):
    """Fetch assessment reports from all branches and sort by date."""
    repo_api_url   = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas'
    file_path      = '.report/assessment_output.json'
    project_folder = f'./{repo_name}_SQAaaS_reports'

    if not os.path.exists(project_folder):
        os.makedirs(project_folder)

    print(f"Fetching reports from: https://github.com/eosc-synergy/{repo_name}.assess.sqaaas")

    branches    = fetch_all_branches(repo_name, token=token)
    all_commits = []

    for branch in branches:
        branch_name = branch['name']
        commits     = _fetch_all_commits_for_file(
            repo_api_url, branch_name, file_path, token=token
        )
        for commit in commits:
            commit_hash = commit['sha']
            commit_date = commit['commit']['committer']['date']
            iso_time    = datetime.fromisoformat(
                commit_date.replace('Z', '+00:00')
            ).strftime('%Y-%m-%dT%H_%M_%SZ')
            all_commits.append((commit_hash, commit_date, branch_name, iso_time))

    all_commits.sort(key=lambda x: x[3])
    total_commits = len(all_commits)
    print(f"Total assessments to process: {total_commits}")

    processed_commits = {}

    for index, (commit_hash, _, branch_name, iso_time) in enumerate(all_commits, start=1):
        file_url      = (
            f'https://raw.githubusercontent.com/eosc-synergy/'
            f'{repo_name}.assess.sqaaas/{commit_hash}/{file_path}'
        )
        file_response = github_get(file_url, token=token)
        if file_response.status_code != 200:
            continue

        file_content = file_response.text
        commit_last4 = commit_hash[-4:]

        try:
            report_data     = json.loads(file_content)
            repository_data = report_data.get("repository", [])

            # Support both schema versions:
            #   new (list) : repository[0]["commit_id"]
            #   old (dict) : repository["commit_id"]
            if isinstance(repository_data, list):
                if not repository_data or not isinstance(repository_data[0], dict):
                    continue
                commit_id_in_report = repository_data[0].get("commit_id")
            elif isinstance(repository_data, dict):
                commit_id_in_report = repository_data.get("commit_id")
            else:
                continue

            if not commit_id_in_report:
                continue

        except json.JSONDecodeError:
            print(f"Failed to parse report file for commit {commit_hash}")
            continue

        # Handle duplicates — keep only the latest report for each source commit
        if commit_id_in_report in processed_commits:
            old_report_path = processed_commits[commit_id_in_report]
            if os.path.exists(old_report_path):
                os.remove(old_report_path)

        safe_branch     = branch_name.replace("/", "_").replace("\\", "_")
        report_filename = f"{iso_time}_{index:04d}_{commit_last4}_{safe_branch}.json"
        report_file_path = os.path.join(project_folder, report_filename)

        os.makedirs(os.path.dirname(report_file_path), exist_ok=True)

        with open(report_file_path, 'w') as f:
            f.write(file_content)

        processed_commits[commit_id_in_report] = report_file_path

        percent = (index / total_commits) * 100
        print(f"Processing assessments: {percent:.2f}%", end="\r")
        if on_progress:
            on_progress(percent, index, total_commits)

    print(f"\nCompleted. Reports saved in '{project_folder}'.")
    return project_folder


def fetch_all_reports_unfiltered(repo_name, *, token=None, on_progress=None):
    """Download ALL assessment reports with no content-based filtering.

    Unlike fetch_assessment_reports(), this function:
      - Saves every downloadable report regardless of internal JSON structure
      - Uses the GitHub commit SHA for deduplication (same SHA on multiple
        branches is downloaded only once)
      - Paginates through ALL commits per branch (not just the first 100)
      - Prints a summary of how many list-format, dict-format, and
        unparseable reports were found
    """
    repo_api_url   = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas'
    file_path      = '.report/assessment_output.json'
    project_folder = f'./{repo_name}_SQAaaS_reports_all'

    if not os.path.exists(project_folder):
        os.makedirs(project_folder)

    print(f"Fetching ALL reports from: https://github.com/eosc-synergy/{repo_name}.assess.sqaaas")

    branches    = fetch_all_branches(repo_name, token=token)
    all_commits = []

    for branch in branches:
        branch_name = branch['name']
        commits     = _fetch_all_commits_for_file(
            repo_api_url, branch_name, file_path, token=token
        )
        for commit in commits:
            commit_hash = commit['sha']
            commit_date = commit['commit']['committer']['date']
            iso_time    = datetime.fromisoformat(
                commit_date.replace('Z', '+00:00')
            ).strftime('%Y-%m-%dT%H_%M_%SZ')
            all_commits.append((commit_hash, commit_date, branch_name, iso_time))

    # Deduplicate by GitHub commit SHA — same SHA on multiple branches is
    # the identical file; keep the first branch encountered.
    seen: set = set()
    unique_commits = []
    for entry in all_commits:
        if entry[0] not in seen:
            seen.add(entry[0])
            unique_commits.append(entry)

    unique_commits.sort(key=lambda x: x[3])
    total = len(unique_commits)
    print(f"Total unique assessments to download: {total}")

    stats = {
        'saved':        0,
        'list_format':  0,
        'dict_format':  0,
        'invalid_json': 0,
        'http_error':   0,
    }

    for index, (commit_hash, _, branch_name, iso_time) in enumerate(unique_commits, start=1):
        file_url  = (
            f'https://raw.githubusercontent.com/eosc-synergy/'
            f'{repo_name}.assess.sqaaas/{commit_hash}/{file_path}'
        )
        file_resp = github_get(file_url, token=token)
        if file_resp.status_code != 200:
            stats['http_error'] += 1
            print(f"Downloading: {(index/total)*100:.2f}%", end="\r")
            continue

        file_content = file_resp.text
        commit_last4 = commit_hash[-4:]
        safe_branch  = branch_name.replace("/", "_").replace("\\", "_")

        # Classify format for stats — but never skip because of it
        fmt = 'raw'
        try:
            repo_field = json.loads(file_content).get("repository")
            if isinstance(repo_field, list):
                fmt = 'list'
                stats['list_format'] += 1
            elif isinstance(repo_field, dict):
                fmt = 'dict'
                stats['dict_format'] += 1
            else:
                stats['invalid_json'] += 1
        except (json.JSONDecodeError, ValueError):
            fmt = 'invalid'
            stats['invalid_json'] += 1

        report_filename  = f"{iso_time}_{index:04d}_{commit_last4}_{safe_branch}.json"
        report_file_path = os.path.join(project_folder, report_filename)

        with open(report_file_path, 'w') as f:
            f.write(file_content)

        stats['saved'] += 1

        percent = (index / total) * 100
        print(f"Downloading: {percent:.2f}%  [{fmt}]", end="\r")
        if on_progress:
            on_progress(percent, index, total)

    print(f"\nCompleted. Reports saved in '{project_folder}'.")
    print(
        f"  Total saved : {stats['saved']}\n"
        f"  List format : {stats['list_format']}  (new schema — has commit_id)\n"
        f"  Dict format : {stats['dict_format']}  (old schema — has commit_id too)\n"
        f"  Invalid JSON: {stats['invalid_json']}\n"
        f"  HTTP errors : {stats['http_error']}"
    )
    return project_folder, stats


def normalize_reports(source_folder, dest_folder=None):
    """Normalize all reports in source_folder to list-format repository schema.

    Converts old dict-format reports  {"repository": {...}}
    into new list-format              {"repository": [{...}]}
    so the provenance pipeline can process all reports uniformly.

    dest_folder defaults to source_folder (in-place).
    Returns a dict with counts: converted, already_ok, skipped.
    """
    if dest_folder is None:
        dest_folder = source_folder

    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    files   = sorted(f for f in os.listdir(source_folder) if f.endswith('.json'))
    total   = len(files)
    stats   = {'converted': 0, 'already_ok': 0, 'skipped': 0}

    print(f"Normalizing {total} reports: {source_folder} → {dest_folder}")

    for i, fname in enumerate(files, 1):
        src_path  = os.path.join(source_folder, fname)
        dest_path = os.path.join(dest_folder,   fname)

        try:
            with open(src_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            stats['skipped'] += 1
            continue

        repo = data.get('repository')

        if isinstance(repo, list):
            # Already correct format — copy as-is if dest differs from source
            if dest_folder != source_folder:
                with open(dest_path, 'w') as f:
                    json.dump(data, f)
            stats['already_ok'] += 1

        elif isinstance(repo, dict):
            # Wrap dict in a list so provenance pipeline can do repo_list[0]
            data['repository'] = [repo]
            with open(dest_path, 'w') as f:
                json.dump(data, f)
            stats['converted'] += 1

        else:
            stats['skipped'] += 1

        print(f"  {i}/{total}  {fname[:60]}", end="\r")

    print(f"\nDone.")
    print(
        f"  Already list-format : {stats['already_ok']}\n"
        f"  Converted dict→list : {stats['converted']}\n"
        f"  Skipped (bad JSON)  : {stats['skipped']}"
    )
    return stats


def check_repo_exists(repo_name, *, token=None):
    """Check if the repository exists on GitHub."""
    repo_api_url = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas'
    try:
        response = github_get(repo_api_url, token=token)
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
