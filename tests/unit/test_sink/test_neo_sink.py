from time import sleep

import pytest
from neo4jrestclient.client import GraphDatabase, Node, Relationship
from neo4jrestclient.query import CypherException

from kgx.sink import NeoSink
from tests import print_graph
from tests.unit import (
    clean_slate,
    DEFAULT_NEO4J_URL,
    DEFAULT_NEO4J_USERNAME,
    DEFAULT_NEO4J_PASSWORD,
    check_container,
    CONTAINER_NAME,
)
from tests.unit import get_graph


def test_sanitize_category():
    """
    Test to ensure behavior of sanitze_category.
    """
    categories = ["biolink:Gene", "biolink:GeneOrGeneProduct"]
    s = NeoSink.sanitize_category(categories)
    assert s == ["`biolink:Gene`", "`biolink:GeneOrGeneProduct`"]


@pytest.mark.parametrize(
    "category", ["biolink:Gene", "biolink:GeneOrGeneProduct", "biolink:NamedThing"]
)
def test_create_constraint_query(category):
    """
    Test to ensure that a CONSTRAINT cypher query is generated as expected.
    """
    sanitized_category = NeoSink.sanitize_category([category])
    q = NeoSink.create_constraint_query(sanitized_category)
    assert q == f"CREATE CONSTRAINT ON (n:{sanitized_category}) ASSERT n.id IS UNIQUE"


@pytest.mark.skip()
@pytest.mark.skipif(
    not check_container(), reason=f"Container {CONTAINER_NAME} is not running"
)
def test_write_neo1(clean_slate):
    """
    Write a graph to a Neo4j instance using NeoSink.
    """
    graph = get_graph("test")[0]
    s = NeoSink(
        uri=DEFAULT_NEO4J_URL,
        username=DEFAULT_NEO4J_USERNAME,
        password=DEFAULT_NEO4J_PASSWORD,
    )
    for n, data in graph.nodes(data=True):
        s.write_node(data)
    for u, v, k, data in graph.edges(data=True, keys=True):
        s.write_edge(data)
    s.finalize()

    d = GraphDatabase(
        DEFAULT_NEO4J_URL,
        username=DEFAULT_NEO4J_USERNAME,
        password=DEFAULT_NEO4J_PASSWORD,
    )

    try:
        results = d.query("MATCH (n) RETURN COUNT(*)")
        number_of_nodes = results[0][0]
        assert number_of_nodes == 3
    except CypherException as ce:
        print(ce)

    try:
        results = d.query("MATCH (s)-->(o) RETURN COUNT(*)")
        number_of_edges = results[0][0]
        assert number_of_edges == 1
    except CypherException as ce:
        print(ce)


@pytest.mark.skipif(
    not check_container(), reason=f"Container {CONTAINER_NAME} is not running"
)
@pytest.mark.parametrize(
    "query",
    [(get_graph("kgx-unit-test")[0], 3, 1), (get_graph("kgx-unit-test")[1], 6, 6)],
)
def test_write_neo2(clean_slate, query):
    """
    Test writing a graph to a Neo4j instance.
    """
    graph = query[0]
    sink = NeoSink(
        uri=DEFAULT_NEO4J_URL,
        username=DEFAULT_NEO4J_USERNAME,
        password=DEFAULT_NEO4J_PASSWORD,
    )
    for n, data in graph.nodes(data=True):
        sink.write_node(data)
    for u, v, k, data in graph.edges(data=True, keys=True):
        sink.write_edge(data)
    sink.finalize()

    nr = sink.http_driver.query("MATCH (n) RETURN count(n)")
    [node_counts] = [x for x in nr][0]
    assert node_counts >= query[1]

    er = sink.http_driver.query("MATCH ()-[p]->() RETURN count(p)")
    [edge_counts] = [x for x in er][0]
    assert edge_counts >= query[2]
    sink.http_driver.flush()


@pytest.mark.skipif(
    not check_container(), reason=f"Container {CONTAINER_NAME} is not running"
)
def test_write_neo3(clean_slate):
    """
    Test writing a graph and then writing a slightly
    modified version of the graph to the same Neo4j instance.
    """
    graph = get_graph("kgx-unit-test")[2]
    sink = NeoSink(
        uri=DEFAULT_NEO4J_URL,
        username=DEFAULT_NEO4J_USERNAME,
        password=DEFAULT_NEO4J_PASSWORD,
    )
    for n, data in graph.nodes(data=True):
        sink.write_node(data)
    for u, v, k, data in graph.edges(data=True, keys=True):
        sink.write_edge(data)
    sink.finalize()

    graph.add_node(
        "B", id="B", publications=["PMID:1", "PMID:2"], category=["biolink:NamedThing"]
    )
    graph.add_node("C", id="C", category=["biolink:NamedThing"], source="kgx-unit-test")
    e = graph.get_edge("A", "B")
    edge_key = list(e.keys())[0]
    graph.add_edge_attribute(
        "A", "B", edge_key, attr_key="test_prop", attr_value="VAL123"
    )
    print_graph(graph)
    assert graph.number_of_nodes() == 3
    assert graph.number_of_edges() == 1

    for n, data in graph.nodes(data=True):
        sink.write_node(data)
    for u, v, k, data in graph.edges(data=True, keys=True):
        sink.write_edge(data)
    sink.finalize()

    nr = sink.http_driver.query("MATCH (n) RETURN n")
    nodes = []
    for node in nr:
        nodes.append(node)

    edges = []
    er = sink.http_driver.query(
        "MATCH ()-[p]-() RETURN p",
        data_contents=True,
        returns=(Node, Relationship, Node),
    )
    for edge in er:
        edges.append(edge)
