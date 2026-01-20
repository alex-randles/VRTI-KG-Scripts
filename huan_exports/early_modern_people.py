from SPARQLWrapper import SPARQLWrapper, JSON
import pandas as pd

ENDPOINT = "https://virtuoso.virtualtreasury.ie/sparql/"

QUERY = """
PREFIX crm: <http://erlangen-crm.org/current/>
PREFIX vrti: <https://www.w3id.org/virtual-treasury/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX vrtivocab: <https://www.w3id.org/virtual-treasury/vocabulary#>

SELECT DISTINCT
    ?Person
    (CONCAT(STR(?FirstNameLabel), " ", STR(?SurnameLabel)) AS ?Name)
WHERE {
    GRAPH <https://kg.virtualtreasury.ie/graph/DIB-v1> {

        ?Person a crm:E21_Person ;
                vrti:VRTI_ERA vrtivocab:Early-Modern-1500-1749 ;
                crm:P1_is_identified_by ?FirstNameRes ;
                crm:P1_is_identified_by ?SurnameRes .

        ?FirstNameRes crm:P2_has_type vrti:Forename ;
                      rdfs:label ?FirstNameLabel .

        ?SurnameRes crm:P2_has_type vrti:Surname ;
                    rdfs:label ?SurnameLabel .
    }
}
ORDER BY ?Name
"""

def main():
    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setQuery(QUERY)
    sparql.setReturnFormat(JSON)

    print("🔎 Querying SPARQL endpoint...")
    results = sparql.query().convert()

    rows = []
    for r in results["results"]["bindings"]:
        rows.append({
            "Name": r["Name"]["value"],
            "KG_URI": r["Person"]["value"],
        })

    df = pd.DataFrame(rows)

    print("\n📊 Preview:")
    print(df.head())

    df.to_csv("early_modern_people.csv", index=False)
    print(f"\n✅ Retrieved {len(df)} Early Modern people")
    print("📄 Saved to EM_people.csv")

if __name__ == "__main__":
    main()
