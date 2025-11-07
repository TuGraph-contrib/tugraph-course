import json
import numpy as np
from collections import defaultdict
from walker import BiasedRandomWalker
from typing import List, Dict, Set, Tuple


class DummyTuGraphDBInstance:
    """A dummy class with a normal adjacency list representation of a graph,
    but with methods that mimic TuGraph Python APIs. This is used for testing
    the implementation of BiasedRandomWalker.
    """

    def __init__(self, edge_list: List[Tuple[int, int, int]]):
        self.nodes = set()
        self.neighbors: Dict[int, Set[int]] = defaultdict(set)
        self.edges: Dict[Tuple[int, int], float] = defaultdict(int)
        self.degrees: Dict[int, int] = defaultdict(int)

        for src, dst in edge_list:
            self.add_edge(src, dst)

    def add_node(self, node: int):
        self.nodes.add(node)

    def add_edge(self, src: int, dst: int):
        self.add_node(src)
        self.add_node(dst)

        self.neighbors[src].add(dst)
        self.neighbors[dst].add(src)

    def get_neighbors(self, vid: int) -> List[int]:
        return list(sorted(self.neighbors[vid]))

    def CreateReadTxn(self):
        return self

    def Commit(self):
        return True

    def GetVertexIterator(self, vid: int = 0):
        return DummyVertexIterator(self, vid)

    def GetInEdgeIterator(self, src: int, dst: int, idx: int):
        eit = DummyEdgeIterator(self, src)
        eit._goto_dst(dst)
        return eit

    def GetOutEdgeIterator(self, src: int, dst: int, idx: int):
        eit = DummyEdgeIterator(self, src)
        eit._goto_dst(dst)
        return eit

    @classmethod
    def from_csv_edges(
        cls, csv_path: str, has_header: bool = True
    ) -> "DummyTuGraphDBInstance":
        """
        Builds a weighted undirected graph from a CSV file containing edges.
        The CSV file should contain two columns: src, dst.
        """
        edge_list = []
        with open(csv_path, "r", encoding="utf-8") as fi:
            if has_header:
                _ = fi.readline()  # skip csv header
            for line in fi.readlines():
                entries = line.strip().split(",")
                if len(entries) == 2:
                    src, dst = map(int, entries)
                else:
                    raise ValueError(f"Invalid edge entry: {entries}")
                edge_list.append((src, dst))

        return cls(edge_list)


class DummyEdgeIterator:
    def __init__(self, graph: DummyTuGraphDBInstance, node_id: int):
        self.graph = graph
        self.node_id = node_id
        self.out_edges = list(graph.neighbors[node_id])
        self.idx = 0

    def _goto_dst(self, dst: int):
        if dst not in self.out_edges:
            self.idx = len(self.out_edges)
        else:
            self.idx = self.out_edges.index(dst)

    def IsValid(self):
        return self.idx < len(self.out_edges)

    def GetDst(self):
        return self.out_edges[self.idx]

    def Next(self):
        self.idx += 1


class DummyVertexIterator:
    def __init__(self, graph: DummyTuGraphDBInstance, node_id: int):
        self.graph = graph
        self.node_id = node_id

    def IsValid(self):
        return self.node_id in self.graph.nodes

    def GetId(self):
        return self.node_id

    def GetNumOutEdges(self):
        return len(self.graph.neighbors[self.node_id]), True

    def ListDstVids(self, limit: int = -1):
        if limit > 0:
            return list(self.graph.neighbors[self.node_id])[:limit], True
        return list(self.graph.neighbors[self.node_id]), True

    def ListSrcVids(self, limit: int = -1):
        if limit > 0:
            return list(self.graph.neighbors[self.node_id])[:limit], True
        return list(self.graph.neighbors[self.node_id]), True

    def HasEdge(self, vid: int):
        return vid in self.graph.neighbors[self.node_id]

    def Next(self):
        self.node_id += 1

    def Goto(self, vid: int, nearest: bool = False):
        self.node_id = vid

    def GetOutEdgeIterator(self):
        return DummyEdgeIterator(self.graph, self.node_id)

    def GetInEdgeIterator(self):
        return DummyEdgeIterator(self.graph, self.node_id)


def main():
    db = DummyTuGraphDBInstance.from_csv_edges("p3_data/test_graph.csv")
    txn = db.CreateReadTxn()

    with open("test_random_walk_references.json", "r") as fi:
        references = json.load(fi)

    walker = BiasedRandomWalker(db, p=1.0, q=1.0)

    test_nodes = [1, 4]

    results_uniform = []
    for prev in test_nodes:
        for curr_id in sorted(db.get_neighbors(prev)):
            vit = txn.GetVertexIterator(curr_id)
            nexts, probs = walker.get_probs_biased(txn, vit, prev)
            results_uniform.append((prev, curr_id, probs))

    walker = BiasedRandomWalker(db, p=1.2, q=2.0)
    results_biased = []
    for prev in test_nodes:
        for curr_id in sorted(db.get_neighbors(prev)):
            vit = txn.GetVertexIterator(curr_id)
            nexts, probs = walker.get_probs_biased(txn, vit, prev)
            results_biased.append((prev, curr_id, probs))

    scores_uniform = []
    for result, reference in zip(results_uniform, references[:10]):
        assert result[0] == reference[0]
        assert result[1] == reference[1]

        if len(result[2]) != len(reference[2]):
            scores_uniform.append(0)
            continue

        scores_uniform.append(np.allclose(result[2], reference[2]))

    scores_biased = []
    for result, reference in zip(results_biased, references[10:]):
        assert result[0] == reference[0]
        assert result[1] == reference[1]

        if len(result[2]) != len(reference[2]):
            scores_biased.append(0)
            continue

        scores_biased.append(np.allclose(result[2], reference[2]))

    print(f"{sum(scores_uniform)}, {sum(scores_biased)}")


if __name__ == "__main__":
    main()
