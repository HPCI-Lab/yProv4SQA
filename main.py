import json
from models.provenance_model import ProvenanceModel
from models.agent import Agent
from models.repository import Repository
from models.assessment import Assessment
from models.quality_check import QualityCheck
from models.output import Output
from models.provenance_relationship import ProvenanceRelationship


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
    prov_model = ProvenanceModel()

# Add agents
    agent1 = Agent(id="SQAaaS", name="SQAaaS", agent_type="prov:SoftwareAgent")
    prov_model.add_agent(agent1)

# Load input data
    input_data = load_json("pipeline_output.json")

# Process repositories
    repo_list = input_data.get("repository", [])
    repo = Repository(
        id="repository1",
        name=repo_list[0].get("name", "Unknown Name"),
        url=repo_list[0].get("url", ""),
        tag=repo_list[0].get("tag", ""),
        commit_id=repo_list[0].get("commit_id", ""),
        is_main_repo=repo_list[0].get("is_main_repo", "False"),
        avatar_url=repo_list[0].get("avatar_url", ""),
        description=repo_list[0].get("description", ""),
        languages=repo_list[0].get("languages", []),
        badge_status=repo_list[0].get("badge_status", "")
    )
    prov_model.add_entity(repo)

# Add output
    badge_status = repo_list[0].get("badge_status", "No Badge") if repo_list else "No Badge"
    output = Output(id="output1", badge_won=badge_status)
    prov_model.add_entity(output)

# Add assessment
    assessment = Assessment(
        id="assessment1",
        report_json_url=input_data.get("meta", {}).get("report_json_url", "Unknown URL"),
        version=input_data.get("meta", {}).get("version", "Unknown Version")
    )
    prov_model.add_entity(assessment)

# Process activities and relationships
    report_data = input_data.get("report", {})
    for activity_name, activity_data in report_data.items():
        qc = QualityCheck(
            id=f"qc_{activity_name}",
            description=activity_data.get("description", f"Description for {activity_name}"),
            is_output=activity_data.get("valid", False),
            percentage=f"{activity_data.get('coverage', {}).get('percentage', 0)}%",
            total_subcriteria=activity_data.get("coverage", {}).get("total_subcriteria", 0),
            success_subcriteria=activity_data.get("coverage", {}).get("success_subcriteria", 0)
        )
        prov_model.add_activity(qc)

        relationship = ProvenanceRelationship(
            RelFrom=f"qc_{activity_name}",
            RelTo="assessment1",
            relationship_type="wasGeneratedBy"
        )
        prov_model.add_relationship(relationship, "wasGeneratedBy")
        
        relationship = ProvenanceRelationship(
            RelFrom=f"qc_{activity_name}",
            RelTo="assessment1",
            relationship_type="wasAssociatedWith"
        )
        prov_model.add_relationship(relationship, "wasGeneratedBy")

    #OKKK
    relationship = ProvenanceRelationship(
        RelFrom="repository1",
        RelTo="assessment1",
        relationship_type="wasDerivedFrom"
    )
    prov_model.add_relationship(relationship, "wasDerivedFrom")

    #OKKK
    relationship = ProvenanceRelationship(
        RelFrom="assessment1",
        RelTo="output1",
        relationship_type="wasDerivedFrom"
    )
    prov_model.add_relationship(relationship, "wasDerivedFrom")
    
    #okkkk
    relationship = ProvenanceRelationship(
        RelFrom="SQAaaS",
        RelTo="repository1",
        relationship_type="wasAttributedTo"
    )
    prov_model.add_relationship(relationship, "wasAttributedTo")

    # Save output to JSON
    prov_json = prov_model.to_json()
    with open("prov_output.json", "w") as f:
        f.write(prov_json)

    print("Saved output to prov_output.json")


if __name__ == "__main__":
    main()
