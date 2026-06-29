import argparse
import os
import json
import re
from datetime import datetime

from ._github import github_get, GitHubRateLimitError  # noqa: F401


class CommitProvenance:
    def __init__(self, repo_owner, repo_name, commit_id_1, commit_id_2,
                 assessment_1=None, assessment_2=None):
        self.repo_owner   = repo_owner
        self.repo_name    = repo_name
        self.commit_id_1  = commit_id_1
        self.commit_id_2  = commit_id_2
        self.assessment_1 = assessment_1 or {}
        self.assessment_2 = assessment_2 or {}
        self.prov_data = {
            "prefix": {
                "ex": "https://sqaaas.eosc-synergy.eu/",
                "w3": "http://www.w3.org/",
                "tr": "http://www.w3.org/TR/2011/"
            },
            "entity":          {},
            "activity":        {},
            "agent":           {},
            "wasDerivedFrom":  {},
            "wasAttributedTo": {},
        }
        self.output_folder = './Compare_commit_provenance'
        os.makedirs(self.output_folder, exist_ok=True)

    def fetch_commit_data(self, commit_id):
        commit_url = (
            f"https://api.github.com/repos/{self.repo_owner}"
            f"/{self.repo_name}/commits/{commit_id}"
        )
        response = github_get(commit_url)
        if response.status_code == 200:
            return response.json()
        raise Exception(
            f"Error fetching data for commit {commit_id}, "
            f"Status code: {response.status_code}"
        )

    def generate_activity_id(self, filename):
        # Remove file extension
        filename_no_ext = filename.rsplit('.', 1)[0]

        # Sanitize: keep only alphanumerics and underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', filename_no_ext)

        if len(sanitized) <= 10:
            return f"ex:activity_{sanitized}"
        return f"ex:activity_{sanitized[:10]}"

    def reduce_commit_id(self, commit_id):
        """Reduce commit ID to first 4 and last 4 characters."""
        return f"{commit_id[:4]}...{commit_id[-4:]}"

    def generate_provenance(self):
        try:
            commit_id_1 = self.commit_id_1
            commit_id_2 = self.commit_id_2
            reduced_1   = self.reduce_commit_id(commit_id_1)
            reduced_2   = self.reduce_commit_id(commit_id_2)

            # Fetch commit metadata (GitHub accepts short SHAs >= 7 chars)
            commit_1_data = self.fetch_commit_data(commit_id_1) if len(commit_id_1) >= 7 else None
            commit_2_data = self.fetch_commit_data(commit_id_2) if len(commit_id_2) >= 7 else None

            if not commit_1_data or not commit_2_data:
                print("One or both commit IDs are invalid. Using branch comparison instead.")

            github_diff_url = (
                f"https://github.com/{self.repo_owner}/{self.repo_name}"
                f"/compare/{commit_id_1}...{commit_id_2}"
            )

            # ── Agents ───────────────────────────────────────────────────────
            committer_1 = commit_1_data['committer'] if commit_1_data else None
            committer_2 = commit_2_data['committer'] if commit_2_data else None

            agent_1_id = None
            agent_2_id = None

            if committer_1:
                agent_1_id = f"ex:agent_{committer_1['login']}_1"
                self.prov_data["agent"][agent_1_id] = {
                    "prov:type":     "prov:Agent",
                    "ex:username":   committer_1['login'],
                    "ex:name":       committer_1['login'],
                    "ex:email":      committer_1.get('email', 'N/A'),
                    "ex:avatar_url": committer_1.get('avatar_url', 'N/A'),
                }
            if committer_2:
                agent_2_id = f"ex:agent_{committer_2['login']}_2"
                self.prov_data["agent"][agent_2_id] = {
                    "prov:type":     "prov:Agent",
                    "ex:username":   committer_2['login'],
                    "ex:name":       committer_2['login'],
                    "ex:email":      committer_2.get('email', 'N/A'),
                    "ex:avatar_url": committer_2.get('avatar_url', 'N/A'),
                }

            # ── Commit entities ───────────────────────────────────────────────
            self.prov_data["entity"][f"ex:commit_{reduced_1}"] = {
                "prov:type":    "document",
                "ex:commit_id": commit_id_1,
                "ex:state":     "before",
                "ex:badge_won": self.assessment_1.get("badge", ""),
                "ex:date":      self.assessment_1.get("date", ""),
            }
            self.prov_data["entity"][f"ex:commit_{reduced_2}"] = {
                "prov:type":    "document",
                "ex:commit_id": commit_id_2,
                "ex:state":     "after",
                "ex:badge_won": self.assessment_2.get("badge", ""),
                "ex:date":      self.assessment_2.get("date", ""),
            }

            # ── wasAttributedTo ───────────────────────────────────────────────
            if agent_1_id:
                self.prov_data["wasAttributedTo"][
                    f"_:id_committer_1_commit_{reduced_1}"
                ] = {
                    "prov:activity": f"ex:activity_commit_{reduced_1}",
                    "prov:agent":    agent_1_id,
                    "prov:entity":   f"ex:commit_{reduced_1}",
                    "ex:github_diff_url": github_diff_url,
                }
            if agent_2_id:
                self.prov_data["wasAttributedTo"][
                    f"_:id_committer_2_commit_{reduced_2}"
                ] = {
                    "prov:activity": f"ex:activity_commit_{reduced_2}",
                    "prov:agent":    agent_2_id,
                    "prov:entity":   f"ex:commit_{reduced_2}",
                    "ex:github_diff_url": github_diff_url,
                }

            # ── File-change activities ────────────────────────────────────────
            comparison_url = (
                f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
                f"/compare/{commit_id_1}...{commit_id_2}"
            )
            comparison_response = github_get(comparison_url)
            if comparison_response.status_code != 200:
                raise Exception(
                    f"Error comparing commits. Status code: {comparison_response.status_code}"
                )

            comparison_data  = comparison_response.json()
            seen_activity_ids = {}   # deduplication counter per base ID

            for file in comparison_data['files']:
                base_id = self.generate_activity_id(file['filename'])

                # Deduplicate: append counter if the same base ID appears twice
                if base_id in seen_activity_ids:
                    seen_activity_ids[base_id] += 1
                    activity_id = f"{base_id}_{seen_activity_ids[base_id]}"
                else:
                    seen_activity_ids[base_id] = 0
                    activity_id = base_id

                file_url = (
                    f"https://github.com/{self.repo_owner}/{self.repo_name}"
                    f"/blob/{commit_id_2}/{file['filename']}"
                )

                lines_added = lines_removed = 0
                if 'patch' in file:
                    for line in file['patch'].split('\n'):
                        if line.startswith('+') and not line.startswith('+++'):
                            lines_added += 1
                        elif line.startswith('-') and not line.startswith('---'):
                            lines_removed += 1

                activity = {
                    "prov:type":                   "activity",
                    "ex:filename":                 file['filename'],
                    "ex:status":                   file['status'],
                    "ex:lines_added":              lines_added,
                    "ex:lines_removed":            lines_removed,
                    "ex:number_of_lines_affected": lines_added + lines_removed,
                    "ex:file_url":                 file_url,
                }

                # Store the activity (activity_id already carries the ex: prefix)
                self.prov_data["activity"][activity_id] = activity

                # wasDerivedFrom: new commit derived from old via this activity
                self.prov_data["wasDerivedFrom"][
                    f"_:id_{file['filename'].replace('/', '_')}_after"
                ] = {
                    "prov:generatedEntity": f"ex:commit_{reduced_2}",
                    "prov:usedEntity":      f"ex:commit_{reduced_1}",
                    "prov:activity":        activity_id,
                }

            # ── Save ──────────────────────────────────────────────────────────
            provenance_filename = os.path.join(
                self.output_folder,
                f"{self.repo_name}_commit_provenance_{reduced_1}_to_{reduced_2}.json"
            )
            with open(provenance_filename, 'w') as fh:
                json.dump(self.prov_data, fh, indent=2)

            print(f"Provenance data saved to {provenance_filename}")
            return self.prov_data

        except Exception as e:
            print(f"An error occurred: {e}")
            return None


def load_json(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: File '{file_path}' is not a valid JSON.")
        return {}


def _extract_assessment_summary(entities, activities, assessment_key):
    """Pull badge, QC scores and date from prov_output for one assessment."""
    a   = entities.get(assessment_key, {})
    idx = re.search(r'\d+$', assessment_key).group()
    o   = entities.get(f"ex:output{idx}", {})

    qc_scores = {}
    for k, v in activities.items():
        m = re.fullmatch(rf'ex:qc_([A-Za-z.]+)_{idx}', k)
        if m:
            try:
                qc_scores[m.group(1)] = float(
                    v.get("ex:percentage", "0%").replace("%", "")
                )
            except ValueError:
                qc_scores[m.group(1)] = 0.0

    return {
        "badge":     o.get("ex:badge_won", ""),
        "date":      a.get("ex:commit_date", ""),
        "qc_scores": qc_scores,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compare two commits and generate provenance data.")
    parser.add_argument('File_path',         type=str, help="Path to the prov_output.json")
    parser.add_argument('Assessment_number1', type=int, help="The first assessment number")
    parser.add_argument('Assessment_number2', type=int, help="The second assessment number")
    args = parser.parse_args()

    # Always compare lower -> higher
    n1, n2 = sorted([args.Assessment_number1, args.Assessment_number2])

    if not os.path.exists(args.File_path):
        print(f"Error: File '{args.File_path}' does not exist.")
        return

    input_file = load_json(args.File_path)
    entities   = input_file.get("entity", {})
    activities = input_file.get("activity", {})

    key1 = f"ex:assessment{n1}"
    key2 = f"ex:assessment{n2}"

    if key1 not in entities:
        print(f"Error: Assessment {n1} does not exist in '{args.File_path}'.")
        return
    if key2 not in entities:
        print(f"Error: Assessment {n2} does not exist in '{args.File_path}'.")
        return

    commit_id_1 = entities[key1].get("ex:commit_id", "")
    commit_id_2 = entities[key2].get("ex:commit_id", "")

    if not commit_id_1 or not commit_id_2:
        print(f"Error: commit_id missing for assessment {n1} or {n2}.")
        return

    repo_full = entities.get("ex:repository1", {}).get("ex:name", "")
    if '/' not in repo_full:
        print(f"Error: could not parse owner/name from repository '{repo_full}'.")
        return
    repo_owner, repo_name = repo_full.split('/', 1)

    assessment_1 = _extract_assessment_summary(entities, activities, key1)
    assessment_2 = _extract_assessment_summary(entities, activities, key2)

    cp = CommitProvenance(repo_owner, repo_name, commit_id_1, commit_id_2,
                          assessment_1=assessment_1, assessment_2=assessment_2)
    cp.generate_provenance()


if __name__ == "__main__":
    main()
