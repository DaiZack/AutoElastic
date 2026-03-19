"""Ingest a Parquet file of business entities into Elasticsearch.

Usage:
    python examples/ingest_parquet.py --path data.parquet --index businesses
"""

from __future__ import annotations

import argparse
import logging
import sys

from autoelastic import AutoElastic, IngestConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Parquet into Elasticsearch")
    parser.add_argument("--path", required=True, help="Path to Parquet file")
    parser.add_argument("--index", default="businesses", help="Target ES index")
    parser.add_argument("--hosts", default="http://localhost:9200", help="ES hosts")
    parser.add_argument("--id-field", default=None, help="Column to use as document _id")
    parser.add_argument("--threads", type=int, default=4, help="Parallel bulk threads")
    parser.add_argument("--chunk-size", type=int, default=2000, help="Docs per bulk request")
    args = parser.parse_args()

    ingest_config = IngestConfig(thread_count=args.threads, chunk_size=args.chunk_size)

    with AutoElastic(args.hosts) as ae:
        if not ae.ping():
            print("Cannot connect to Elasticsearch at", args.hosts, file=sys.stderr)
            sys.exit(1)

        schema = ae.parquet_schema(args.path)
        row_count = ae.parquet_row_count(args.path)
        print(f"Parquet schema: {schema}")
        print(f"Total rows: {row_count:,}")

        result = ae.ingest_parquet(
            args.index,
            args.path,
            id_field=args.id_field,
            ingest_config=ingest_config,
        )

        print(f"\nIngest complete:")
        print(f"  Total:     {result.total:,}")
        print(f"  Succeeded: {result.succeeded:,}")
        print(f"  Failed:    {result.failed:,}")
        print(f"  Elapsed:   {result.elapsed_seconds:.2f}s")
        print(f"  Rate:      {result.total / result.elapsed_seconds:,.0f} docs/sec")

        if result.errors:
            print(f"\nFirst 5 errors:")
            for err in result.errors[:5]:
                print(f"  {err}")


if __name__ == "__main__":
    main()
