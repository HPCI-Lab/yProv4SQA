import argparse
import os
import requests
import json

def fetch_all_branches(repo_name):
    """Fetch all branches from the GitHub API, handling pagination."""
    repo_api_url = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas/branches'
    branches = []
    page = 1

    print("Fetching branches...")

    while True:
        response = requests.get(f"{repo_api_url}?page={page}&per_page=100")  # Fetch 100 branches per page
        if response.status_code != 200:
            print("Failed to fetch branches.")
            return branches  # Return whatever we got if request fails

        new_branches = response.json()
        if not new_branches:
            break  # Stop when no more branches are returned

        branches.extend(new_branches)
        page += 1  # Go to the next page

    print(f"Fetched {len(branches)} branches.")
    return branches


def fetch_assessment_reports(repo_name):
    """Fetch assessment reports from all branches and sort by date."""
    repo_api_url = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas'
    file_path = '.report/assessment_output.json'

    # Create a folder with the repository name
    project_folder = f'./{repo_name}_reports'
    if not os.path.exists(project_folder):
        os.makedirs(project_folder)

    print(f"Please hold on... yProv4SQA is fetching your reports from GitHub: https://github.com/eosc-synergy/{repo_name}.assess.sqaaas")

    # Fetch all branches
    branches = fetch_all_branches(repo_name)
    all_commits = []

    for branch in branches:
        branch_name = branch['name']

        # Fetch commits for each branch
        commits_url = f'{repo_api_url}/commits?sha={branch_name}&path={file_path}&per_page=100'
        commits_response = requests.get(commits_url)
        if commits_response.status_code != 200:
            continue  # Skip if we can't fetch commits for this branch

        commits = commits_response.json()

        for commit in commits:
            commit_hash = commit['sha']
            commit_date = commit['commit']['committer']['date']
            all_commits.append((commit_hash, commit_date, branch_name))  # Store with branch name

    # Sort all commits by date
    all_commits.sort(key=lambda x: x[1])

    total_commits = len(all_commits)
    print(f"Total assessments to process: {total_commits}")

    # Track commits we've already processed
    processed_commits = {}

    # Fetch and save reports with sequential numbering + last 4 of commit hash
    for index, (commit_hash, _, branch_name) in enumerate(all_commits, start=1):
        file_url = f'https://raw.githubusercontent.com/eosc-synergy/{repo_name}.assess.sqaaas/{commit_hash}/{file_path}'
        file_response = requests.get(file_url)
        if file_response.status_code != 200:
            continue  # Skip if the file can't be fetched

        file_content = file_response.text
        commit_last4 = commit_hash[-4:]

        # Extract commit ID from the report file content
        try:
            report_data = json.loads(file_content)
            # Get the commit_id from the report content, assuming it is inside 'repository' key
            commit_id_in_report = report_data.get("repository", [{}])[0].get("commit_id", None)
        except json.JSONDecodeError:
            print(f"Failed to parse report file for commit {commit_hash}")
            continue

        if commit_id_in_report:
            # Check if the commit ID is already processed
            if commit_id_in_report in processed_commits:
                # Remove the old report if it's not the latest one
                old_report_path = processed_commits[commit_id_in_report]
                if os.path.exists(old_report_path):
                    os.remove(old_report_path)
                    print(f"Removed old report for commit {commit_id_in_report}")

            # Save the new report and update the dictionary
            report_filename = f"report_{index}_{commit_last4}_{branch_name}.json"
            report_file_path = os.path.join(project_folder, report_filename)

            with open(report_file_path, 'w') as f:
                f.write(file_content)

            # Update the processed commits dictionary with the latest report path
            processed_commits[commit_id_in_report] = report_file_path

        # Print progress (percentage only)
        percent = (index / total_commits) * 100
        print(f"Processing assessments: {percent:.2f}%", end="\r")

    print(f"\nCompleted processing all assessments and saved reports in '{project_folder}'.")


def check_repo_exists(repo_name):
    """Check if the repository exists on GitHub."""
    repo_api_url = f'https://api.github.com/repos/eosc-synergy/{repo_name}.assess.sqaaas'

    response = requests.get(repo_api_url)
    if response.status_code == 404:
        print(f"Repository '{repo_name}' does not exist.")
        print("Please check the correct repository name at: https://github.com/eosc-synergy")
        return False
    elif response.status_code == 200:
        return True
    else:
        print("Failed to check repository existence.")
        return False


def main():
    # Set up argparse to get the repository name from the console
    parser = argparse.ArgumentParser(description="Fetch SQAaaS reports for a specific repository.")
    parser.add_argument('repo_name', type=str, help="The repository name (e.g., 'my-repo')")
    args = parser.parse_args()

    # Check if the repository exists
    if check_repo_exists(args.repo_name):
        # Fetch and save assessment reports
        fetch_assessment_reports(args.repo_name)
    else:
        # Do nothing, just inform the user that the repo does not exist
        pass


if __name__ == "__main__":
    main()
