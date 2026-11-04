from dataclasses import FrozenInstanceError, replace

import pytest
from pyspark.sql.types import StringType, StructField, StructType

from platform_core.contracts.model import TableContract


@pytest.fixture
def valid_contract():
    """
    Fixture to create a valid contract for testing.
    """

    schema = StructType(
        [
            StructField(
                "id",
                StringType(),
                True,
                metadata={"description": "Unique identifier", "pii": False},
            ),
            StructField(
                "name",
                StringType(),
                True,
                metadata={"description": "Name of the entity", "pii": False},
            ),
        ]
    )

    return TableContract(
        name="valid_contract",
        domain="test_domain",
        layer="bronze",
        version=1,
        owner="test_owner",
        description="A valid contract for testing.",
        schema=schema,
        partition_by=("id",),
    )


def test_valid_contract(valid_contract):
    """
    Test that a valid contract can be created.
    """
    assert valid_contract.name == "valid_contract"
    assert valid_contract.domain == "test_domain"
    assert valid_contract.layer == "bronze"
    assert valid_contract.version == 1
    assert valid_contract.owner == "test_owner"
    assert valid_contract.description == "A valid contract for testing."
    assert valid_contract.schema.fieldNames() == ["id", "name"]
    assert valid_contract.partition_by == ("id",)


def test_invalid_layer(valid_contract):
    """
    Test that an invalid layer raises a ValueError.
    """
    with pytest.raises(
        ValueError, match="Invalid layer: invalid_layer. Must be one of"
    ):
        replace(valid_contract, layer="invalid_layer")


@pytest.mark.parametrize("field", ["name", "domain"])
@pytest.mark.parametrize(
    "value", ["InvalidName", "tmdb-filmes", "_filmes", "filmes_", "tmdb filmes", ""]
)
def test_not_snake_case_name_and_domain(valid_contract, field, value):
    """
    Test that name and domain outside snake_case raise a ValueError.
    """
    with pytest.raises(ValueError, match=f"Invalid {field}"):
        replace(valid_contract, **{field: value})


def test_not_snake_case_columns(valid_contract):
    """
    Test that column names outside snake_case raise a ValueError
    listing every invalid column.
    """
    schema = StructType(
        [
            StructField(
                "id", StringType(), True, metadata={"description": "Id", "pii": False}
            ),
            StructField(
                "TituloOriginal",
                StringType(),
                True,
                metadata={"description": "Original title", "pii": False},
            ),
            StructField(
                "data-lancamento",
                StringType(),
                True,
                metadata={"description": "Release date", "pii": False},
            ),
        ]
    )

    with pytest.raises(ValueError, match="needs to be snake_case") as exc_info:
        replace(valid_contract, schema=schema, partition_by=())

    message = str(exc_info.value)
    assert "TituloOriginal" in message
    assert "data-lancamento" in message
    assert "'id'" not in message


def test_missing_metadata_description(valid_contract):
    """
    Test that missing metadata description raises a ValueError.
    """
    schema = StructType(
        [
            StructField("id", StringType(), True, metadata={"pii": False}),
            StructField("name", StringType(), True, metadata={"pii": False}),
        ]
    )

    with pytest.raises(ValueError, match="columns missing description: id, name"):
        replace(valid_contract, schema=schema)


def test_missing_metadata_pii(valid_contract):
    """
    Test that missing metadata pii raises a ValueError.
    """
    schema = StructType(
        [
            StructField(
                "id", StringType(), True, metadata={"description": "Unique identifier"}
            ),
            StructField(
                "name",
                StringType(),
                True,
                metadata={"description": "Unique identifier"},
            ),
        ]
    )

    with pytest.raises(ValueError, match="columns missing pii: id, name"):
        replace(valid_contract, schema=schema)


def test_invalid_partition_by(valid_contract):
    partition_by = ("test",)

    with pytest.raises(ValueError, match="Partition field test is invalid."):
        replace(valid_contract, partition_by=partition_by)


@pytest.mark.parametrize("pii", ["false", "False", 0, None])
def test_pii_not_bool(valid_contract, pii):
    """
    Test that a pii flag that is not a real bool raises a ValueError.
    """
    schema = StructType(
        [
            StructField(
                "id",
                StringType(),
                True,
                metadata={"description": "Unique identifier", "pii": pii},
            ),
        ]
    )

    with pytest.raises(ValueError, match="columns missing pii: id"):
        replace(valid_contract, schema=schema)


@pytest.mark.parametrize(
    "version", ["1", "1.0", 1.0, True], ids=["str_1", "str_1.0", "float_1.0", "bool_true"]
)
def test_not_int_version(valid_contract, version):
    """
    Test that a version that is not an int raises a TypeError.
    """
    with pytest.raises(TypeError, match="Version must be int type"):
        replace(valid_contract, version=version)


@pytest.mark.parametrize("version", [0, -1])
def test_version_smaller_than_one(valid_contract, version):
    """
    Test that a version below 1 raises a ValueError.
    """
    with pytest.raises(ValueError, match="Version must be >="):
        replace(valid_contract, version=version)


def test_contract_is_immutable(valid_contract):
    """
    Test that a contract cannot be changed after it is created.
    """
    with pytest.raises(FrozenInstanceError):
        valid_contract.version = 2


def test_qualified_name(valid_contract):
    """
    Test that qualified_name builds <domain>_<layer>_<env>.<name>.
    """
    assert (
        valid_contract.qualified_name("dev") == "test_domain_bronze_dev.valid_contract"
    )
    assert (
        valid_contract.qualified_name("prd") == "test_domain_bronze_prd.valid_contract"
    )
