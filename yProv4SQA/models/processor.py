# yProv4SQA/models/processor.py
import os
import requests
import json
import argparse
from .provenance_model import ProvenanceModel
from .repository import Repository
from .assessment import Assessment
from .agent import Agent
from .quality_check import QualityCheck
from .output import Output
from .provenance_relationship import ProvenanceRelationship

def get_commit_Date(name,commit_id):
    url = f'https://api.github.com/repos/{name}/commits/{commit_id}'
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        # Extract commit date from the response JSON
        commit_date = data['commit']['author']['date']
        print(f"Commit Date: {commit_date}")
        return commit_date
    else:
        print(f"Failed to retrieve commit data. Status code: {response.status_code}")


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
    
def process_file(file_path, prov_model, gindex, repo_dict):
    input_data = load_json(file_path)

    if not input_data:
        return

    print(f"Processing file {file_path}, index {gindex}")

    # Directly access the first repository (assuming only one repository per file)
    repo_list = input_data.get("repository", [])
    if not repo_list:
        print(f"No repository found in file {file_path}")
        return

    repo_data = repo_list[0]

    # Use repository name as the unique key
    repo_name = repo_data.get("name", "Unknown Name")

    # Check if the repository already exists in the dictionary
    if repo_name in repo_dict:
        repository_id = repo_dict[repo_name]["id"]
        print(f"Repository '{repo_name}' already exists with ID: {repository_id}")
    else:
        repository_id = f"repository{gindex}"
        # Add repository to dictionary to avoid duplication in future files
        repo_dict[repo_name] = {"id": repository_id, "name": repo_name}

        # Process repository (create a new repository if it doesn't exist)
        repo = Repository(
            id=repository_id,
            name=repo_data.get("name", "Unknown Name"),
            url=repo_data.get("url", ""),
            avatar_url=repo_data.get("avatar_url", ""),
            description=repo_data.get("description", ""),
            languages=repo_data.get("languages", []),
        )
        prov_model.add_entity(repo)

    # Add output
    output_id=f"output{gindex}"
    badge_data=input_data.get("badge", {}).get("software", {}).get("data", {})

    output = Output(
            id = output_id,
            badge_won = repo_data.get("badge_status", "No Badge"),
            Issued_On=badge_data.get("issuedOn", "No information"),
            entityType=badge_data.get("entityType", "No information"),
            openBadgeId=badge_data.get("openBadgeId", "No information"),
            createdAt=badge_data.get("createdAt", "No information"),
            badgeclassOpenBadgeId=badge_data.get("badgeclassOpenBadgeId", "No information"),
            image_URL=badge_data.get("image", "No information")
            )
    prov_model.add_entity(output)

    # Add assessment
    assessment_id = f"assessment{gindex}"
    assessment = Assessment(
        id=assessment_id,
        report_json_url=input_data.get("meta", {}).get("report_json_url", "Unknown URL"),
        commit_id=repo_data.get("commit_id", " "),
        branch_name=repo_data.get("tag", " "),
        commit_date=get_commit_Date(repo_data.get("name", " "),repo_data.get("commit_id", " ")),
        version=input_data.get("meta", {}).get("version", "Unknown Version")
    )
    prov_model.add_entity(assessment)

    # Process activities and relationships
    report_data = input_data.get("report", {})
    for activity_name, activity_data in report_data.items():
        qc = QualityCheck(
            id=f"qc_{activity_name}{gindex}",
            description=activity_data.get("description", f"Description for {activity_name}"),
            is_output=activity_data.get("valid", False),
            percentage=f"{activity_data.get('coverage', {}).get('percentage', 0)}%",
            total_subcriteria=activity_data.get("coverage", {}).get("total_subcriteria", 0),
            success_subcriteria=activity_data.get("coverage", {}).get("success_subcriteria", 0)
        )
        prov_model.add_QualityCheck(qc)

        # Add wasGeneratedBy relationship
        relationship = ProvenanceRelationship(
            RelFrom=f"qc_{activity_name}{gindex}",
            RelTo=assessment_id,
            relationship_type="wasGeneratedBy"
        )
        prov_model.add_relationship(relationship, "wasGeneratedBy")

    # Add relationships
    relationship = ProvenanceRelationship(
        RelFrom=repository_id,
        RelTo=assessment_id,
        relationship_type="wasDerivedFrom"
    )
    prov_model.add_relationship(relationship, "wasDerivedFrom")

    relationship = ProvenanceRelationship(
        RelFrom=assessment_id,
        RelTo=output_id,
        relationship_type="wasDerivedFrom"
    )
    prov_model.add_relationship(relationship, "wasDerivedFrom")

    relationship = ProvenanceRelationship(
        RelFrom="SQAaaS",
        RelTo=repository_id,
        relationship_type="wasAttributedTo"
    )
    prov_model.add_relationship(relationship, "wasAttributedTo")


def process_all_files(folder_path):
    prov_model = ProvenanceModel()

    # Add agent
    agent1 = Agent(id="SQAaaS", name="SQAaaS", agent_type="prov:SoftwareAgent")
    prov_model.add_agent(agent1)

    # Get all files from the folder
    input_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(".json")]

    gindex = 0
    repo_dict = {}  # Dictionary to store existing repositories and their IDs

    # Loop through all files and process them
    for file_path in input_files:
        gindex += 1
        process_file(file_path, prov_model, gindex, repo_dict)

    # Save output to JSON
    prov_json = prov_model.to_json()
    with open("prov_output.json", "w") as f:
        f.write(prov_json)

    print("Saved output to prov_output.json")


def main():
    # Set up argparse to get the folder path from the console
    parser = argparse.ArgumentParser(description="Process all files in a folder and generate a provenance model.")
    parser.add_argument('folder_path', type=str, help="The folder path containing the JSON files to process")
    args = parser.parse_args()

    # Process all files in the given folder
    process_all_files(args.folder_path)


if __name__ == "__main__":
    main()