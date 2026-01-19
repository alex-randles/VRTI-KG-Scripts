import json
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Any

from SPARQLWrapper import SPARQLWrapper, JSON
import requests
from rdflib import Graph


from output_stats import create_output_csv


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def prefixes_block(prefixes: Dict[str, str]) -> str:
    return "\n".join(f"PREFIX {k}: <{v}>" for k, v in prefixes.items())


def from_clause(graph: str) -> str:
    return f"FROM <{graph}>"


def run_select(endpoint: str, query: str, timeout: int) -> int:
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(timeout)
    result = sparql.query().convert()
    bindings = result["results"]["bindings"]
    if not bindings:
        return 0
    return int(bindings[0]["count"]["value"])


def build_count_query(
    prefixes: Dict[str, str],
    graph: str,
    rdf_type: str | None,
    distinct: bool,
    type_predicate: str,
    variable: str
) -> str:
    select_var = f"DISTINCT ?{variable}" if distinct else f"?{variable}"

    if rdf_type:
        # allow string or list for type_predicate
        if isinstance(type_predicate, list):
            # property path alternation
            tp = "(" + "|".join(type_predicate) + ")"
        else:
            tp = type_predicate

        where = f"""
    ?{variable} {tp} {rdf_type} .
    """
    else:
        where = "?s ?p ?o ."

    return f"""
{prefixes_block(prefixes)}

SELECT (COUNT({select_var}) AS ?count)
{from_clause(graph)}
WHERE {{
{where}
}}
""".strip()


def resolve_graphs(cfg: Dict[str, Any], selection: str) -> List[str]:
    if selection not in cfg["selections"]:
        raise SystemExit(f"Unknown selection '{selection}'")

    graphs = []
    for group_name in cfg["selections"][selection]:
        graphs.extend(cfg["graphs"][group_name])

    # De-duplicate while preserving order
    seen = set()
    ordered = []
    for g in graphs:
        if g not in seen:
            ordered.append(g)
            seen.add(g)
    return ordered


def main():
    ap = argparse.ArgumentParser(description="Execute configurable KG stats")
    ap.add_argument("--config", default="kg_stats.json", help="Path to JSON config")
    ap.add_argument("--out", default="kg_stats_results.json", help="Output JSON file")
    args = ap.parse_args()

    cfg = load_json(args.config)

    endpoint = cfg["endpoint"]
    timeout = int(cfg.get("timeout_seconds", 120))
    prefixes = cfg.get("prefixes", {})

    defaults = cfg.get("defaults", {}).get("entity_count", {})
    default_distinct = bool(defaults.get("distinct", True))
    default_variable = defaults.get("variable", "s")
    default_type_predicate = defaults.get("type_predicate", "rdf:type")

    results = {
        "endpoint": endpoint,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "stats": []
    }

    for stat in cfg["stats"]:

        # --- WIDOCO / static ontology stats ---
        if "ontology_url" in stat:
            count = count_named_individuals_from_widoco(stat["ontology_url"])
            results["stats"].append({
                "id": stat["id"],
                "name": stat["name"],
                "selection": None,
                "type": "owl:NamedIndividual",
                "total": count,
                "per_graph": []
            })
            continue


        stat_result = {
            "id": stat["id"],
            "name": stat["name"],
            "selection": stat["selection"],
            "type": stat.get("type"),
            "total": 0,
            "per_graph": []
        }

        graphs = resolve_graphs(cfg, stat["selection"])

        for graph in graphs:
            if "query_override" in stat:
                override = stat["query_override"]
                query = override.replace("{GRAPH}", graph)
            else:
                query = build_count_query(
                    prefixes=prefixes,
                    graph=graph,
                    rdf_type=stat.get("type"),
                    distinct=default_distinct if stat.get("type") else False,
                    type_predicate=default_type_predicate,
                    variable=default_variable
                )

            count = run_select(endpoint, query, timeout)

            stat_result["per_graph"].append({
                "graph": graph,
                "count": count
            })
            stat_result["total"] += count

        results["stats"].append(stat_result)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Wrote results to {args.out}")


def count_named_individuals_from_widoco(ontology_url: str) -> int:
    headers = {"Accept": "application/rdf+xml"}
    response = requests.get(ontology_url, timeout=30)
    response.raise_for_status()

    g = Graph()
    g.parse(data=response.text, format="xml")

    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT (COUNT(DISTINCT ?c) AS ?count)
    WHERE {
        ?c a owl:NamedIndividual .
    }
    """

    for row in g.query(query):
        return int(row["count"])
    return 0


if __name__ == "__main__":
    main()
    create_output_csv()
