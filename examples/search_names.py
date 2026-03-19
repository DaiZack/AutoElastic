"""Search business names in Elasticsearch.

Usage:
    python examples/search_names.py --index businesses --name "apple"
    python examples/search_names.py --index businesses --names "apple" "google" "microsoft"
"""

from __future__ import annotations

import argparse
import json
import logging

from autoelastic import AutoElastic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Search business names in Elasticsearch")
    parser.add_argument("--index", default="businesses", help="ES index to search")
    parser.add_argument("--hosts", default="http://localhost:9200", help="ES hosts")
    parser.add_argument("--name", help="Single name to search")
    parser.add_argument("--names", nargs="+", help="Multiple names to search in bulk")
    parser.add_argument("--size", type=int, default=10, help="Results per query")
    args = parser.parse_args()

    with AutoElastic(args.hosts) as ae:
        if args.name:
            results = ae.search_name(args.index, args.name, size=args.size)
            print(f"\nResults for '{args.name}' ({len(results)} hits):\n")
            for r in results:
                names = r["_source"].get("name", [])
                city = r["_source"].get("city", "")
                country = r["_source"].get("country", "")
                highlight = r.get("highlight", {}).get("name", [])
                print(f"  [{r['_score']:.2f}] {names}")
                if city or country:
                    print(f"         {city}, {country}")
                if highlight:
                    print(f"         highlight: {highlight}")
                print()

        elif args.names:
            results = ae.search_names_bulk(args.index, args.names)
            for name, hits in results.items():
                print(f"\n'{name}' ({len(hits)} hits):")
                for r in hits[:3]:
                    names = r["_source"].get("name", [])
                    print(f"  [{r['_score']:.2f}] {names}")

        else:
            parser.print_help()


if __name__ == "__main__":
    main()
