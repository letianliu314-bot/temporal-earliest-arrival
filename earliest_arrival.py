import argparse
import heapq
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    # 解析命令行参数，返回包含所有参数的命名空间对象
    # 主要参数包括：起点子版块、终点子版块、起始时间（可包含空格拆分）、字典文件路径、图文件路径、时区偏移量、最低情感值
    # 使用 argparse 自动处理帮助信息、参数类型转换和默认值
    parser = argparse.ArgumentParser(
        description="Earliest-arrival search on the soc-RedditHyperlinks graph."
    )
    parser.add_argument("source", help="Source subreddit name")  # 起点子版块名称
    parser.add_argument("target", help="Target subreddit name")  # 终点子版块名称
    parser.add_argument(
        "tstart",
        nargs="+",
        metavar="TSTART",
        help="Start timestamp (split exactly like: 2015-10-29 12:20:04)",  # 起始时间，允许拆分为多个参数（如日期和时间分开）
    )
    parser.add_argument(
        "--dict",
        dest="dict_path",
        type=Path,
        default=Path("dict.tsv"),
        help="Path to dict.tsv (default: ./dict.tsv)",  # 字典文件路径，默认为当前目录下的 dict.tsv
    )
    parser.add_argument(
        "--graph",
        dest="graph_path",
        type=Path,
        default=Path("graph.tsv"),
        help="Path to graph.tsv (default: ./graph.tsv)",  # 图文件路径，默认为当前目录下的 graph.tsv
    )
    parser.add_argument(
        "--tz-offset",
        type=float,
        default=8.0,
        help=(
            "Timezone offset (hours) applied to the input timestamp. "
            "Default 8 matches the assignment's Hong Kong time requirement."
        ),  # 输入时间的时区偏移，默认8小时对应香港时间
    )
    parser.add_argument(
        "--min-sentiment",
        type=int,
        default=0,
        help=(
            "Minimum LINK_SENTIMENT value an interaction must have to be considered. "
            "Default=0 drops only edges with -1 sentiment."
        ),  # 过滤图中边的最小情感值，默认0，排除情感为-1的边
    )
    return parser.parse_args(argv)


def load_dict(path: Path) -> Tuple[Dict[int, str], Dict[str, int]]:
    # 从 dict.tsv 文件读取子版块ID和名称映射
    # 构造两个字典：id2name（int->str）和 name2id（str->int），方便双向查找
    id2name: Dict[int, str] = {}
    name2id: Dict[str, int] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue  # 跳过空行
            idx_str, name = line.split("\t", maxsplit=1)  # 按tab分割，第一列为ID，第二列为子版块名称
            idx = int(idx_str)
            id2name[idx] = name
            name2id[name] = idx
    return id2name, name2id


def load_graph(path: Path) -> Dict[int, List[Tuple[int, int, int]]]:
    # 从 graph.tsv 文件读取图的邻接表结构
    # 每行格式为：源节点ID \t 时间戳,目标节点ID,情感值 [空格分隔的多个三元组]
    # 构造字典，key为源节点ID，value为三元组列表 (时间戳, 目标节点ID, 情感值)
    graph: Dict[int, List[Tuple[int, int, int]]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue  # 跳过空行
            if "\t" not in line:
                continue  # 格式异常则跳过
            src_str, rest = line.split("\t", maxsplit=1)
            edges: List[Tuple[int, int, int]] = []
            if rest.strip():
                for triple in rest.split():
                    ts, dst, sent = triple.split(",")  # 每个三元组用逗号分割时间戳、目标节点、情感值
                    edges.append((int(ts), int(dst), int(sent)))
            graph[int(src_str)] = edges
    return graph


def to_epoch(ts_str: str, tz_offset_hours: float) -> int:
    # 将格式化时间字符串转换为Unix时间戳（秒）
    # 先用datetime.strptime解析字符串，再用指定时区偏移构造时区信息，最后转换为时间戳
    # 时区偏移确保输入时间被正确解释为指定时区的本地时间
    dt = datetime.strptime(ts_str, TS_FORMAT)
    tzinfo = timezone(timedelta(hours=tz_offset_hours))
    return int(dt.replace(tzinfo=tzinfo).timestamp())


def format_epoch(epoch: int, tz_offset_hours: float) -> str:
    # 将Unix时间戳转换回格式化时间字符串，使用指定的时区偏移
    # 通过datetime.fromtimestamp指定时区，确保显示的时间对应正确的本地时间
    tzinfo = timezone(timedelta(hours=tz_offset_hours))
    return datetime.fromtimestamp(epoch, tz=tzinfo).strftime(TS_FORMAT)


def earliest_arrival(
    graph: Dict[int, List[Tuple[int, int, int]]],
    start: int,
    target: int,
    tstart: int,
    min_sentiment: int,
) -> Tuple[Optional[int], Optional[List[int]]]:
    # 使用基于优先队列的最短路径搜索算法，求从start到target的最早到达时间和路径
    # pq是堆，存储待扩展节点及其当前最早到达时间，保证每次扩展时间最早的节点
    # best记录每个节点当前已知的最早到达时间，避免重复扩展较晚时间的路径
    # parent记录搜索树中每个节点的父节点，用于路径回溯
    pq: List[Tuple[int, int]] = [(tstart, start)]  # 初始化堆，起点时间和节点
    best: Dict[int, int] = {start: tstart}  # 起点到自己的时间即起始时间
    parent: Dict[int, Optional[int]] = {start: None}  # 起点无父节点

    while pq:
        cur_time, node = heapq.heappop(pq)  # 取出当前最早时间的节点
        if cur_time != best.get(node):
            continue  # 如果该节点已有更早的时间被处理，跳过
        if node == target:
            return cur_time, _reconstruct_path(parent, target)  # 找到目标，回溯路径返回
        for ts, neighbor, sentiment in graph.get(node, []):
            if sentiment < min_sentiment:
                continue  # 过滤情感值低于阈值的边
            if ts < cur_time:
                continue  # 只能沿时间递增的边前进
            if ts < best.get(neighbor, sys.maxsize):
                best[neighbor] = ts  # 记录更早的到达时间
                parent[neighbor] = node  # 记录父节点
                heapq.heappush(pq, (ts, neighbor))  # 将邻居加入堆中等待扩展
    return None, None  # 无路径可达


def _reconstruct_path(
    parent: Dict[int, Optional[int]], target: int
) -> List[int]:
    # 根据parent字典从目标节点回溯到起点，构造完整路径
    # 通过不断取父节点直到None，路径被存储为倒序，最后反转返回
    path: List[int] = []
    node: Optional[int] = target
    while node is not None:
        path.append(node)
        node = parent.get(node)
    return list(reversed(path))


def main(argv: Sequence[str]) -> None:
    # 主函数，按照顺序执行：
    # 1. 解析命令行参数
    # 2. 检查字典文件和图文件是否存在，若不存在则报错退出
    # 3. 读取字典文件，构造id-name映射
    # 4. 读取图文件，构造邻接表
    # 5. 验证起点和终点是否在字典中
    # 6. 将起始时间字符串转换为Unix时间戳（考虑时区）
    # 7. 调用earliest_arrival计算最早到达时间和路径
    # 8. 若无路径，提示无路径；否则格式化时间并打印路径信息
    args = parse_args(argv)
    if not args.dict_path.exists():
        print(f"Dictionary file not found: {args.dict_path}", file=sys.stderr)
        sys.exit(1)
    if not args.graph_path.exists():
        print(f"Graph file not found: {args.graph_path}", file=sys.stderr)
        sys.exit(1)

    start_ts_str = " ".join(args.tstart)  # 将分割的时间参数合并为完整字符串
    id2name, name2id = load_dict(args.dict_path)  # 读入字典映射
    graph = load_graph(args.graph_path)  # 读入图邻接表

    if args.source not in name2id:
        print(f"Unknown source subreddit: {args.source}", file=sys.stderr)
        sys.exit(1)
    if args.target not in name2id:
        print(f"Unknown target subreddit: {args.target}", file=sys.stderr)
        sys.exit(1)

    start_id = name2id[args.source]
    target_id = name2id[args.target]
    tstart = to_epoch(start_ts_str, args.tz_offset)  # 时间字符串转Unix时间戳

    arrival, path = earliest_arrival(
        graph, start_id, target_id, tstart, args.min_sentiment
    )
    if arrival is None or path is None:
        print("No path found")
        return

    formatted = format_epoch(arrival, args.tz_offset)  # Unix时间戳转格式化字符串
    readable_path = " -> ".join(id2name[node] for node in path)  # 路径节点名拼接
    print(f"Arrival time: {formatted}")
    print(f"Path: {readable_path}")


if __name__ == "__main__":
    main(sys.argv[1:])
