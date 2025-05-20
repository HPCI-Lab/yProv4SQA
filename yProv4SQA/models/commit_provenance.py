import requests
import argparse
import os
import json
import re
from datetime import datetime

class CommitProvenance:
    def __init__(self, repo_owner, repo_name, commit_id_1, commit_id_2):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.commit_id_1 = commit_id_1
        self.commit_id_2 = commit_id_2
        self.prov_data = {
            "prefix": {
                "ex": "https://sqaaas.eosc-synergy.eu/",
                "w3": "http://www.w3.org/",
                "tr": "http://www.w3.org/TR/2011/"
            },
            "entity": {},
            "activity": {},
            "wasDerivedFrom": {},
            "agent": {},
            "wasAttributedTo": {}
        }
        self.output_folder = './commit_provenance'
        os.makedirs(self.output_folder, exist_ok=True)

    def fetch_commit_data(self, commit_id):
        commit_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/commits/{commit_id}"
        response = requests.get(commit_url)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error fetching data for commit {commit_id}, Status code: {response.status_code}")
        
    def generate_activity_id(self, filename):
        # Remove file extension
        filename_no_ext = filename.rsplit('.', 1)[0]
        
        # Sanitize filename to remove special characters
        sanitized_filename =  re.sub(r'[^a-zA-Z0-9_]', '', filename_no_ext)
        
        # Check the length of the sanitized filename
        if len(sanitized_filename) <= 10:
            # If the filename is 10 or fewer characters, use the entire sanitized filename
            activity_id = f"ex:activity_{sanitized_filename}"
        else:
            # If the filename is longer than 10 characters, take the first 10 characters
            start = sanitized_filename[:10]
            activity_id = f"ex:activity_{start}"
        
        return activity_id

    def reduce_commit_id(self, commit_id):
        """Reduce commit ID to first 4 and last 4 characters."""
        return f"{commit_id[:4]}...{commit_id[-4:]}"

    def generate_provenance(self):
        try:
            # Reduce commit IDs to the first 4 and last 4 characters
            commit_id_1=self.commit_id_1
            commit_id_2=self.commit_id_2
            reduced_commit_id_1 = self.reduce_commit_id(self.commit_id_1)
            reduced_commit_id_2 = self.reduce_commit_id(self.commit_id_2)

            # Fetch commit data (for commits comparison)
            commit_1_data = self.fetch_commit_data(self.commit_id_1) if len(self.commit_id_1) == 40 else None
            commit_2_data = self.fetch_commit_data(self.commit_id_2) if len(self.commit_id_2) == 40 else None

            # Extract committer information if commits are valid
            committer_1 = commit_1_data['committer'] if commit_1_data else None
            committer_2 = commit_2_data['committer'] if commit_2_data else None

            # Check if the provided commit IDs are valid
            if not commit_1_data or not commit_2_data:
                print(f"One or both commit IDs are invalid. Using branch comparison instead.")

            # Handle the case where commit hashes are not found - use branches instead
            if not commit_1_data or not commit_2_data:
                github_diff_url = f"https://github.com/{self.repo_owner}/{self.repo_name}/compare/{self.commit_id_1}...{self.commit_id_2}"
            else:
                github_diff_url = f"https://github.com/{self.repo_owner}/{self.repo_name}/compare/{self.commit_id_1}...{self.commit_id_2}"

            # Add committer as agents with additional information (like email and avatar)
            if committer_1:
                agent_1_id = f"ex:agent_{committer_1['login']}_1"
                self.prov_data["agent"][agent_1_id] = {
                    "prov:type": "prov:Agent",
                    "ex:username": committer_1['login'],
                    "ex:name": committer_1['login'],
                    "ex:email": committer_1.get('email', 'N/A'),
                    "ex:avatar_url": committer_1.get('avatar_url', 'N/A')
                }
            if committer_2:
                agent_2_id = f"ex:agent_{committer_2['login']}_2"
                self.prov_data["agent"][agent_2_id] = {
                    "prov:type": "prov:Agent",
                    "ex:username": committer_2['login'],
                    "ex:name": committer_2['login'],
                    "ex:email": committer_2.get('email', 'N/A'),
                    "ex:avatar_url": committer_2.get('avatar_url', 'N/A')
                }

            # Define commit entities (before and after) with reduced commit IDs
            commit_entity_1 = {
                "prov:type": "document",
                "ex:commit_id": commit_id_1,
                "ex:state": "before"
            }
            commit_entity_2 = {
                "prov:type": "document",
                "ex:commit_id": commit_id_2,
                "ex:state": "after"
            }

            # Add the commit entities to provenance data
            self.prov_data["entity"][f"ex:commit_{reduced_commit_id_1}"] = commit_entity_1
            self.prov_data["entity"][f"ex:commit_{reduced_commit_id_2}"] = commit_entity_2

            # Add GitHub Diff URL (now handles both commits and branches)
            self.prov_data["wasAttributedTo"][f"_:id_committer_1_commit_{reduced_commit_id_1}"] = {
                "prov:activity": f"ex:activity_commit_{reduced_commit_id_1}",
                "prov:agent": agent_1_id,
                "prov:entity": f"ex:commit_{reduced_commit_id_1}",
                "ex:github_diff_url": github_diff_url  # Adding GitHub diff URL
            }

            self.prov_data["wasAttributedTo"][f"_:id_committer_2_commit_{reduced_commit_id_2}"] = {
                "prov:activity": f"ex:activity_commit_{reduced_commit_id_2}",
                "prov:agent": agent_2_id,
                "prov:entity": f"ex:commit_{reduced_commit_id_2}",
                "ex:github_diff_url": github_diff_url  # Adding GitHub diff URL
            }

            # Process file changes (patch details)
            comparison_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/compare/{self.commit_id_1}...{self.commit_id_2}"
            comparison_response = requests.get(comparison_url)

            if comparison_response.status_code == 200:
                comparison_data = comparison_response.json()

                for file in comparison_data['files']:
                    activity_id = self.generate_activity_id(file['filename'])
                    file_url = f"https://github.com/{self.repo_owner}/{self.repo_name}/blob/{self.commit_id_2}/{file['filename']}"

                    activity = {
                        "prov:type": "activity",
                        "ex:filename": file['filename'],
                        "ex:status": file['status'],
                        "ex:number_of_lines_affected": 0,
                        "ex:file_url": file_url,  # Add the file URL here
                    }

                    # Process changes (added, removed lines) in the file
                    file_changes = []
                    line_count = 0
                    if 'patch' in file:
                        patch_lines = file['patch'].split('\n')
                        for line in patch_lines:
                            if line.startswith('+') and not line.startswith('+++'):
                                file_changes.append({
                                    "line_change": "added",
                                    "line_content": line[1:].strip()
                                })
                                line_count += 1
                            elif line.startswith('-') and not line.startswith('---'):
                                file_changes.append({
                                    "line_change": "removed",
                                    "line_content": line[1:].strip()
                                })
                                line_count += 1

                    activity["ex:number_of_lines_affected"] = line_count
                    # Add the activity to provenance data
                    self.prov_data["activity"][activity_id] = activity

                    # Link the activity to the latest commit using `wasDerivedFrom`
                    self.prov_data["wasDerivedFrom"][f"_:id_{file['filename'].replace('/', '_')}_after"] = {
                        "prov:generatedEntity": f"ex:commit_{reduced_commit_id_2}",
                        "prov:usedEntity": f"ex:commit_{reduced_commit_id_1}",
                        "prov:activity": activity_id
                    }

            else:
                raise Exception(f"Error comparing commits. Status code: {comparison_response.status_code}")

            # Save the provenance data to a JSON file
            provenance_filename = os.path.join(self.output_folder, f'commit_provenance_{reduced_commit_id_1}_to_{reduced_commit_id_2}.json')
            with open(provenance_filename, 'w') as provenance_file:
                json.dump(self.prov_data, provenance_file, indent=2)

            print(f"Provenance data saved to {provenance_filename}")

        except Exception as e:
            print(f"An error occurred: {e}")

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



def main():
    # Set up argparse to get the parameters from the command line
    parser = argparse.ArgumentParser(description="Compare two commits and generate provenance data.")
    parser.add_argument('File_path', type=str, help="Path to the JSON file")
    parser.add_argument('Assessment_number1', type=int, help="The first assessment number")
    parser.add_argument('Assessment_number2', type=int, help="The second assessment number")
    args = parser.parse_args()

        # Check if the file exists
    if not os.path.exists(args.File_path):
        print(f"Error: File '{args.File_path}' does not exist. Please check the correct JSON file path generated by yProv4SQA.")
        return
    
    # Check if the assessment numbers are valid in the file
    assessment_key1 = f"ex:assessment{args.Assessment_number1}"
    assessment_key2 = f"ex:assessment{args.Assessment_number2}"
    
    input_file = load_json(args.File_path)
    
    if assessment_key1 not in input_file.get("entity", {}):
        print(f"Error: Assessment {args.Assessment_number1} does not exist in the file '{args.File_path}'.")
        return

    if assessment_key2 not in input_file.get("entity", {}):
        print(f"Error: Assessment {args.Assessment_number2} does not exist in the file '{args.File_path}'.")
        return

    commit_id_1 =  input_file.get("entity", {}).get(assessment_key1, {}).get("ex:commit_id", "")
    commit_id_1=' '.join(commit_id_1) 
    commit_id_2 =  input_file.get("entity", {}).get(assessment_key2, {}).get("ex:commit_id", "")
    commit_id_2=' '.join(commit_id_2) 
    
    repo_owner, repo_name = input_file.get("entity", {}).get("ex:repository1", {}).get("ex:name", "").split('/')
    
    commit_provenance = CommitProvenance(repo_owner, repo_name, commit_id_1, commit_id_2)
    commit_provenance.generate_provenance()


if __name__ == "__main__":
    main()
