import json
import requests
from SPARQLWrapper import SPARQLWrapper, JSON, POST
import pandas as pd

# -------------------------
# CONFIG
# -------------------------

COLLECTION_NAME = "State Papers Ireland"
API_ENDPOINT = "https://by2022-prod.adaptcentre.ie/IR_REST_V2/webapi/kg_search"
SPARQL_ENDPOINT = "https://virtuoso.virtualtreasury.ie/sparql/"

CREDENTIALS_FILE = "../credentials.json"
OUTPUT_CSV = "state_papers_people.csv"

# -------------------------
# COLLECTION API
# -------------------------

def get_collection_uris(collection_name):
    api_request = {
        "indexDBName": "beyond_2022_v11",
        "searchThematicCollectionList": [collection_name],
        "kgQuery": True,
        "kgUrisPageSize": 5000,
        "kgUrisPageNumber": 0
    }

    with open(CREDENTIALS_FILE) as f:
        creds = json.load(f)

    response = requests.post(
        API_ENDPOINT,
        auth=(creds["username"], creds["password"]),
        json=api_request,
        timeout=30
    )

    response.raise_for_status()
    return response.json()

# -------------------------
# EXTRACT PERSON URIS
# -------------------------

import json
from datetime import datetime

import json
import json

import json

def extract_person_uris(collection_json):
    """
    Extract DISTINCT Person URIs from collection JSON
    where kgEntities are nested under 'documents'.
    """

    # 🔎 DEBUG: save entire JSON response
    # with open("collection_debug.json", "w", encoding="utf-8") as f:
    #     json.dump(collection_json, f, indent=2, ensure_ascii=False)

    # Use a set to guarantee DISTINCT URIs
    uris = set()

    documents = collection_json.get("documents", [])

    for doc in documents:
        for ent in doc.get("kgEntities", []):
            if ent.get("type") == "Person" and ent.get("uri"):
                uris.add(ent["uri"])

    # Return as sorted list (stable + readable)
    return sorted(uris)



# -------------------------
# SPARQL QUERY
# -------------------------

def build_values_block(person_uris):
    return "VALUES ?Person {\n" + "\n".join(f"<{u}>" for u in person_uris) + "\n}"

def build_query(values_block):
    return f"""
PREFIX crm: <http://erlangen-crm.org/current/>
PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX vrtivocab: <https://www.w3id.org/virtual-treasury/vocabulary#>

SELECT DISTINCT
    (CONCAT(STR(?FirstNameLabel), " ", STR(?SurnameLabel)) AS ?Name)
    ?Person
WHERE {{
    GRAPH <https://kg.virtualtreasury.ie/graph/DIB-v1> {{
        {values_block}

        ?Person a crm:E21_Person ;
                vrti:VRTI_ERA vrtivocab:Early-Modern-1500-1749 ;
                crm:P1_is_identified_by ?FirstNameRes ;
                crm:P1_is_identified_by ?SurnameRes .

        ?FirstNameRes crm:P2_has_type  vrti:Forename ;
                      rdfs:label ?FirstNameLabel .

        ?SurnameRes crm:P2_has_type  vrti:Surname ;
                    rdfs:label ?SurnameLabel .
    }}
}}
ORDER BY ?Name
"""

def query_person_names(person_uris):
    values_block = build_values_block(person_uris)
    query = build_query(values_block)

    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.setMethod(POST)
    results = sparql.query().convert()

    rows = []
    for r in results["results"]["bindings"]:
        rows.append({
            "Name": r["Name"]["value"],
            "KG_URI": r["Person"]["value"]
        })

    return pd.DataFrame(rows)

# -------------------------
# MAIN
# -------------------------

def main():
    print("🔎 Fetching collection data...")
    collection_json = get_collection_uris(COLLECTION_NAME)
    # print(collection_json)

    person_uris = extract_person_uris(collection_json)
    print(f"👤 Found {len(person_uris)} unique persons")

    if not person_uris:
        print("⚠️ No persons found — exiting")
        return

    print("🔗 Querying SPARQL endpoint...")
    df = query_person_names(person_uris)

    print("\n📊 Preview:")
    print(df.head())

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✅ Saved {len(df)} rows to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
