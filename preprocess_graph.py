import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple

SOURCE_COL = "SOURCE_SUBREDDIT"
TARGET_COL = "TARGET_SUBREDDIT"
TIMESTAMP_COL = "TIMESTAMP"
SENTIMENT_COL = "LINK_SENTIMENT"
TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess soc-RedditHyperlinks temporal graph."
    )
    parser.add_argument(
        "input_path", type=Path, help="Path to soc-redditHyperlinks-title.tsv"
    )
    parser.add_argument(
        "--dict-out", type=Path, default=Path("dict.tsv"), help="Dictionary TSV path"
    )
    parser.add_argument(
        "--graph-out", type=Path, default=Path("graph.tsv"), help="Graph TSV path"
    )
    parser.add_argument(
        "--tz-offset",
        type=float,
        default=8.0,
        help=(
            "Timezone offset in hours to apply to timestamp strings before converting "
            "to Unix epoch (default: 8, i.e., Hong Kong time)."
        ),
    )
    return parser.parse_args(argv)


def iter_rows(tsv_path: Path) -> Iterable[Dict[str, str]]:
    with tsv_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if not row:
                continue
            if not row.get(SOURCE_COL) or not row.get(TARGET_COL):
                continue
            yield row


def build_dict(tsv_path: Path, dict_path: Path) -> Dict[str, int]:
    names = set()
    for row in iter_rows(tsv_path):
        names.add(row[SOURCE_COL].strip())
        names.add(row[TARGET_COL].strip())
    sorted_names = sorted(names)
    idmap = {name: idx for idx, name in enumerate(sorted_names)}
    with dict_path.open("w", encoding="utf-8") as handle:
        for idx, name in enumerate(sorted_names):
            handle.write(f"{idx}\t{name}\n")
    return idmap


def to_epoch(ts_value: str, tz_offset_hours: float) -> int:
    ts_value = ts_value.strip()
    if not ts_value:
        raise ValueError("Empty timestamp encountered.")
    if ts_value.isdigit():
        return int(ts_value)
    try:
        naive = datetime.strptime(ts_value, TS_FORMAT)
    except ValueError as exc:  
        raise ValueError(f"Unsupported timestamp format: {ts_value}") from exc
    offset = timezone(timedelta(hours=tz_offset_hours))
    aware = naive.replace(tzinfo=offset)
    return int(aware.timestamp())


def build_graph(tsv_path: Path, graph_path: Path, idmap: Dict[str, int], tz_offset_hours: float) -> None:
    edges: Dict[int, set[Tuple[int, int, int]]] = defaultdict(set)
    for row in iter_rows(tsv_path):
        try:
            src = idmap[row[SOURCE_COL].strip()]
            dst = idmap[row[TARGET_COL].strip()]
        except KeyError:
            continue  
        ts = to_epoch(row[TIMESTAMP_COL], tz_offset_hours)
        sentiment = int(float(row[SENTIMENT_COL]))
        if sentiment == -1:
            continue
        edges[src].add((ts, dst, sentiment))
    with graph_path.open("w", encoding="utf-8") as handle:
        for src in sorted(edges):
            adjacency = sorted(edges[src], key=lambda triple: (triple[0], triple[1]))
            triples = " ".join(f"{ts},{dst},{sent}" for ts, dst, sent in adjacency)
            handle.write(f"{src}\t{triples}\n")


def main(argv: Sequence[str]) -> None:
    args = parse_args(argv)
    input_path = args.input_path
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[+] Reading input file: {input_path}")
    idmap = build_dict(input_path, args.dict_out)
    print(f"[+] Wrote {args.dict_out} with {len(idmap)} subreddits")
    build_graph(input_path, args.graph_out, idmap, args.tz_offset)
    print(f"[+] Wrote {args.graph_out}")
    print("[+] Done.")


if __name__ == "__main__":
    main(sys.argv[1:])
