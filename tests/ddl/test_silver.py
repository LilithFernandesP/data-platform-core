from dataclasses import replace

import pytest
from pyspark.sql.types import DateType, LongType, StringType, StructField, StructType

from platform_core.contracts.cinema.silver import TABLES
from platform_core.contracts.model import TableContract
from platform_core.ddl.silver import create_table


def _field(name, dtype, comment="A column."):
    return StructField(name, dtype, True, metadata={"comment": comment})


@pytest.fixture
def contract():
    """
    Fixture with a small silver contract.
    """
    return TableContract(
        name="movies",
        domain="test_domain",
        layer="silver",
        version=3,
        owner="data_team",
        description="It's a table for testing.",
        schema=StructType(
            [
                _field("movie_id", LongType(), "Movie id."),
                _field("title", StringType(), "The movie's title."),
                _field("snapshot_date", DateType(), "Collection date."),
            ]
        ),
    )


@pytest.fixture
def created(spark_session, tmp_path):
    """
    Fixture that creates the table of a contract in a throwaway database
    and drops it afterwards, even when the test fails.
    """
    databases = []

    def _create(contract):
        database = contract.qualified_name("test").split(".")[0]
        spark_session.sql(f"CREATE DATABASE IF NOT EXISTS {database}")
        databases.append(database)
        create_table(spark_session, contract, "test", str(tmp_path / contract.name))
        return spark_session.catalog.getTable(contract.qualified_name("test"))

    yield _create

    for database in databases:
        spark_session.sql(f"DROP DATABASE IF EXISTS {database} CASCADE")


def _columns(spark_session, contract):
    return {
        f.name: f for f in spark_session.table(contract.qualified_name("test")).schema
    }


def _properties(spark_session, contract):
    rows = spark_session.sql(
        f"SHOW TBLPROPERTIES {contract.qualified_name('test')}"
    ).collect()
    return {row.key: row.value for row in rows}


def test_table_comment_and_version(spark_session, created, contract):
    """
    Test that the table description, apostrophe included, and the
    contract version reach the catalog.
    """
    table = created(contract)

    assert table.description == "It's a table for testing."
    assert _properties(spark_session, contract)["contract_version"] == "3"


def test_column_comments(spark_session, created, contract):
    """
    Test that every column comment reaches the catalog unchanged.
    """
    created(contract)
    columns = _columns(spark_session, contract)

    assert columns["title"].metadata["comment"] == "The movie's title."
    assert columns["movie_id"].metadata["comment"] == "Movie id."


def test_partitions(spark_session, created, contract):
    """
    Test that partition columns from the contract become table partitions.
    """
    created(replace(contract, partition_by=("snapshot_date",)))

    partitions = [
        c.name
        for c in spark_session.catalog.listColumns(contract.qualified_name("test"))
        if c.isPartition
    ]
    assert partitions == ["snapshot_date"]


def test_env_changes_only_the_database(spark_session, created, contract):
    """
    Test that the environment only changes the database in the table name.
    """
    table = created(contract)

    assert table.database == "test_domain_silver_test"
    assert table.name == "movies"


@pytest.mark.parametrize("layer", ["bronze", "gold"])
def test_other_layers_not_implemented(spark_session, contract, layer):
    """
    Test that bronze and gold are refused until they get their own creation.
    """
    with pytest.raises(NotImplementedError, match=layer):
        create_table(spark_session, replace(contract, layer=layer), "dev", "/tmp/x")


@pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
def test_real_contracts(spark_session, created, table):
    """
    Test that every real silver contract creates a table whose types and
    comments match the contract. Parquet tables keep neither NOT NULL nor
    column order (partitions move to the end), so the check ignores both.
    """
    created(table)
    columns = _columns(spark_session, table)

    assert set(columns) == set(table.schema.fieldNames())
    for field in table.schema.fields:
        column = columns[field.name]
        assert column.dataType.simpleString() == field.dataType.simpleString()
        assert column.metadata["comment"] == field.metadata["comment"]
