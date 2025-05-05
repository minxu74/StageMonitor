from metadata_migrate_sync.globus import GlobusClient
from globus_sdk import SearchQueryV1

from typing import Literal
from metadata_migrate_sync.project import ProjectReadOnly, ProjectReadWrite


def facet_query(*,
    ep_name: Literal["public", "stage"],
    project: ProjectReadOnly | ProjectReadWrite,
) -> None:

    gc = GlobusClient()

    cm = gc.get_client(name = ep_name)


    sc = cm.search_client

    try:
        project_enum = ProjectReadOnly(project)
    except ValueError:
        try: 
            project_enum = ProjectReadWrite(project)
        except ValueError:
            print ("please provide a valid project")
            raise ValueError

    if ep_name == "public":
        _globus_index_id = cm.indexes["public"]
    else:
        _globus_index_id = cm.indexes[project_enum.value]


    results = {}

    if ep_name == "public":
        # get all nodes
        node_query = {
            "q": "*",
            "limit": 0,  # Only want facets
            "facets": [
                {
                    "name": "data_node",
                    "type": "terms",
                    "field_name": "data_node",
                    "size": 200,  # Adjust based on expected projects per node
                },
            ]
        }
        response = sc.post_search(_globus_index_id, SearchQueryV1(**node_query))

        target_nodes = []
        if "facet_results" in response:
            for bucket in response["facet_results"][0]["buckets"]:
                target_nodes.append(bucket["value"])


        for node in target_nodes:
            # Create query filtered to this specific node
            query = {
                "q": "*",
                "limit": 0,  # Only want facets
                "filters": [
                    {
                        "type": "match_all",
                        "field_name": "data_node",
                        "values": [node],
                    },
                ],
                "facets": [
                    {
                        "name": "projects_per_node",
                        "type": "terms",
                        "field_name": "project",
                        "size": 200,  # Adjust based on expected projects per node
                    },
                ]
            }
            
            # Execute query
            result = sc.post_search(_globus_index_id, SearchQueryV1(**query))
            
            # Store results
            results[node] = {
                "total_items": result["total"],
                "projects": {}
            }
            
            if "facet_results" in result:
                for bucket in result["facet_results"][0]["buckets"]:
                    results[node]["projects"][bucket["value"]] = bucket["count"]


        return results

    else:

        institution_query = {
            "q": "*",
            "limit": 0,  # Only want facets
            "filters": [
                {
                    "type": "match_all",
                    "field_name": "project",
                    "values": [project_enum.value],
                },
            ],
            "facets": [
                {
                    "name": "institution_per_project",
                    "type": "terms",
                    "field_name": "institution_id",
                    "size": 200,  # Adjust based on expected projects per node
                },
            ],
        }
        result = sc.post_search(_globus_index_id, SearchQueryV1(**institution_query))

        results[project_enum.value] = {
            "total_items": result["total"],
            "institution_id": {},
        }

        if "facet_results" in result:
            for bucket in result["facet_results"][0]["buckets"]:
                results[project_enum.value]["institution_id"][bucket["value"]] = bucket["count"]


        print (results)
        return results

if __name__ == "__main__":

    #facet_query(ep_name="public", project = "CMIP6")
    facet_query(ep_name="stage", project = "obs4MIPs")
