# temporal-earliest-arrival
Time-dependent earliest-arrival path queries on large temporal graphs (Reddit hyperlinks).

## Description
Command-line tools for preprocessing large temporal graphs and answering
earliest-arrival (time-respecting) path queries.

This project studies earliest-arrival path queries on temporal graphs,
where edges are associated with timestamps and paths must respect
temporal ordering constraints.

The implementation is evaluated on a real-world Reddit interaction network.

## Repository Structure
.
├── src/
│   ├── preprocess_graph.py   # graph preprocessing
│   └── earliest_arrival.py   # earliest-arrival query
├── data/                     # local data (not tracked)
├── scripts/                  # helper scripts (optional)
├── requirements.txt
├── README.md

## Dataset

This project uses the SNAP Reddit Hyperlink Network dataset
(`soc-redditHyperlinks-title.tsv`), which records temporal interactions
between subreddit communities.

The raw dataset is large (hundreds of MB) and is therefore **not included**
in this repository. Users should download it directly from the official
SNAP website to ensure correctness and proper citation.

Only the following columns are used:
- SOURCE_SUBREDDIT
- TARGET_SUBREDDIT
- TIMESTAMP
- LINK_SENTIMENT

## Preprocessing

The preprocessing step converts the raw dataset into a temporal graph
representation suitable for path queries.

Generated files:
- `dict.tsv`: mapping from subreddit names to integer IDs
- `graph.tsv`: temporal adjacency lists

These files can be large and are generated locally.

### Run preprocessing

```bash
python preprocess_graph.py \
  --input data/soc-redditHyperlinks-title.tsv \
  --dict_out data/dict.tsv \
  --graph_out data/graph.tsv
```

### Run earliest_arrival

```bash
python earliest_arrival.py \
  --dict data/dict.tsv \
  --graph data/graph.tsv \
  --source 100daysofrejection \
  --target oldschoolcool \
  --tstart "2015-10-29 12:20:04"
```

```md
Output:
- Arrival time (human-readable)
- Path as a sequence of subreddit names
```

## Notes

- Timestamps are processed in ascending order to enforce temporal constraints.
- If no valid time-respecting path exists after the given start time,
  the program reports "No path found".
