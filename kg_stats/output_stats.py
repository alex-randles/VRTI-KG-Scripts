import json
import pandas as pd


INPUT_JSON = "kg_stats_results.json"
OUTPUT_CSV = "kg_stats_totals.csv"


def create_output_csv():
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    stats = data.get("stats", [])
    if not stats:
        raise RuntimeError("No stats found in JSON file")

    rows = [
        {
            "stat_name": stat.get("name", stat.get("id")),
            "total": stat.get("total", 0)
        }
        for stat in stats
    ]

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__create_output_csv__":
    create_output_csv()
