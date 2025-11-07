# DO NOT MODIFY THIS FILE
# UNAUTHORIZED CHANGES TO THIS FILE WILL RESULT IN DEDUCTIONS

import unittest
from community import Community
from graph import WeightedDiGraph
from louvain import Louvain


def _get_graph():
    TEST_GRAPH_FILE = "./p2_data/test_graph.csv"
    return WeightedDiGraph.from_csv_edges(TEST_GRAPH_FILE)


class TestCommunity(unittest.TestCase):

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.graph = _get_graph()

    def test_add_node(self):
        c = Community(id=0, graph=self.graph, nodes={0})
        c.add_node(9)
        self.assertEqual(c.get_in_degree(), 10 + 0)
        self.assertEqual(c.get_out_degree(), 20 + 45)

        c.add_node(8)
        self.assertEqual(c.get_in_degree(), 10 + 0 + 20)
        self.assertEqual(c.get_out_degree(), 20 + 45 + 30)

    def test_remove_node(self):
        c = Community(id=0, graph=self.graph, nodes={1, 2, 9})
        c.remove_node(9)
        self.assertEqual(c.get_in_degree(), 5 + 65)
        self.assertEqual(c.get_out_degree(), 70 + 15)

        c.remove_node(1)
        self.assertEqual(c.get_in_degree(), 65)
        self.assertEqual(c.get_out_degree(), 15)

        c.remove_node(2)
        self.assertEqual(c.get_in_degree(), 0)
        self.assertEqual(c.get_out_degree(), 0)


class TestNode2CommDegree(unittest.TestCase):

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.graph = _get_graph()

    def test_node2comm_in_empty(self):
        # empty community
        c = Community(id=0, graph=self.graph, nodes=set())
        self.assertEqual(c.node2comm_in_degree(0), 0)
        self.assertEqual(c.node2comm_in_degree(1), 0)

    def test_node2comm_in(self):
        # single node
        c = Community(id=0, graph=self.graph, nodes={2})
        self.assertEqual(c.node2comm_in_degree(0), 0)
        self.assertEqual(c.node2comm_in_degree(3), 5)
        self.assertEqual(c.node2comm_in_degree(4), 10)

        # multiple nodes
        c = Community(id=0, graph=self.graph, nodes={0, 2, 3})
        self.assertEqual(c.node2comm_in_degree(1), 0)
        self.assertEqual(c.node2comm_in_degree(4), 15)
        self.assertEqual(c.node2comm_in_degree(2), 20)

    def test_node2comm_out_empty(self):
        # empty community
        c = Community(id=0, graph=self.graph, nodes=set())
        self.assertEqual(c.node2comm_out_degree(0), 0)
        self.assertEqual(c.node2comm_out_degree(1), 0)

    def test_node2comm_out(self):
        # single node
        c = Community(id=0, graph=self.graph, nodes={2})
        self.assertEqual(c.node2comm_out_degree(0), 5)
        self.assertEqual(c.node2comm_out_degree(3), 15)
        self.assertEqual(c.node2comm_out_degree(4), 0)

        # multiple nodes
        c = Community(id=0, graph=self.graph, nodes={0, 2, 3})
        self.assertEqual(c.node2comm_out_degree(1), 10)
        self.assertEqual(c.node2comm_out_degree(4), 0)
        self.assertEqual(c.node2comm_out_degree(2), 5)

    def test_node2comm_empty(self):
        # empty community
        c = Community(id=0, graph=self.graph, nodes=set())
        self.assertEqual(c.node2comm_degree(0), 0)
        self.assertEqual(c.node2comm_degree(1), 0)

    def test_node2comm(self):
        # single node
        c = Community(id=0, graph=self.graph, nodes={2})
        self.assertEqual(c.node2comm_degree(0), 5)
        self.assertEqual(c.node2comm_degree(3), 20)
        self.assertEqual(c.node2comm_degree(4), 10)

        # multiple nodes
        c = Community(id=0, graph=self.graph, nodes={0, 2, 3})
        self.assertEqual(c.node2comm_degree(1), 10)
        self.assertEqual(c.node2comm_degree(4), 15)
        self.assertEqual(c.node2comm_degree(2), 25)
        self.assertEqual(c.node2comm_degree(9), 25)

    def test_self_loop(self):
        c = Community(id=0, graph=self.graph, nodes={3})
        self.assertEqual(c.node2comm_in_degree(3), 10)
        self.assertEqual(c.node2comm_out_degree(3), 10)


class TestDeltaModularity(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.graph = _get_graph()
        self.louvain = Louvain(self.graph)

    def test_delta_modularity(self):
        comm = self.louvain.communities[1]  # Community({1})
        comm.remove_node(1)
        # D(1 -> {})
        dq = self.louvain.delta_modularity(1, comm)
        self.assertAlmostEqual(dq, 0.0)

        comm.add_node(1)
        # D(2 -> {1})
        dq = self.louvain.delta_modularity(2, comm)
        self.assertAlmostEqual(dq, -0.04119511090991399)

        comm.add_node(2)
        # D(3 -> {1, 2})
        dq = self.louvain.delta_modularity(3, comm)
        self.assertAlmostEqual(dq, 0.0009053870529651398)


if __name__ == "__main__":
    unittest.main()
