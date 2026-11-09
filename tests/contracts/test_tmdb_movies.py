from datetime import date, datetime

import pytest
from pyspark.errors import PySparkValueError

from platform_core.contracts.cinema.silver.tmdb_movies import TMDB_MOVIES


@pytest.fixture
def valid_row():
    """
    Fixture with one movie row that satisfies the contract.
    """
    return {
        "tmdb_id": 299534,
        "imdb_id": "tt4154796",
        "title": "Vingadores: Ultimato",
        "original_title": "Avengers: Endgame",
        "overview": "Após os eventos devastadores de Guerra Infinita...",
        "original_language": "en",
        "status": "Released",
        "release_date": date(2019, 4, 24),
        "runtime_minutes": 181,
        "budget": 356_000_000,
        "revenue": 2_799_439_100,
        "vote_average": 8.2,
        "vote_count": 26_000,
        "popularity": 95.4,
        "collection_id": 86311,
        "collection_name": "Os Vingadores - Coleção",
        "genres": [
            {"id": 12, "name": "Aventura"},
            {"id": 878, "name": "Ficção científica"},
        ],
        "production_companies": [
            {"id": 420, "name": "Marvel Studios", "origin_country": "US"}
        ],
        "ingested_at": datetime(2026, 11, 4, 12, 0, 0),
    }


def test_qualified_name():
    """
    Test that the contract points to the cinema silver database.
    """
    assert TMDB_MOVIES.qualified_name("dev") == "cinema_silver_dev.tmdb_movies"


def test_natural_key_is_not_nullable():
    """
    Test that tmdb_id, the natural key, can never be null.
    """
    assert TMDB_MOVIES.schema["tmdb_id"].nullable is False


@pytest.mark.parametrize("column", ["budget", "revenue"])
def test_money_columns_are_usd(column):
    """
    Test that money columns declare USD as their unit.
    """
    assert TMDB_MOVIES.schema[column].metadata["unit"] == "USD"


def test_no_pii_columns():
    """
    Test that the table holds no personal data.
    """
    assert not any(field.metadata["pii"] for field in TMDB_MOVIES.schema.fields)


def test_metadata_survives_spark(spark_session):
    """
    Test that Spark keeps the contract schema, metadata included,
    when it builds a DataFrame from it.
    """
    df = spark_session.createDataFrame([], TMDB_MOVIES.schema)

    assert df.schema == TMDB_MOVIES.schema
    assert df.schema["budget"].metadata["unit"] == "USD"


def test_valid_row(spark_session, valid_row):
    """
    Test that a row with real-looking values fits the contract,
    including dates, timestamps and nested arrays of structs.
    """
    df = spark_session.createDataFrame([valid_row], TMDB_MOVIES.schema)
    row = df.first()

    assert df.count() == 1
    assert row["revenue"] == 2_799_439_100
    assert row["release_date"] == date(2019, 4, 24)
    assert row["genres"][1]["name"] == "Ficção científica"
    assert row["production_companies"][0]["origin_country"] == "US"


def test_nullable_columns_accept_null(spark_session, valid_row):
    """
    Test that every nullable column accepts null at the same time.
    """
    nullable = [f.name for f in TMDB_MOVIES.schema.fields if f.nullable]
    row = {**valid_row, **{column: None for column in nullable}}

    df = spark_session.createDataFrame([row], TMDB_MOVIES.schema)

    assert df.count() == 1


@pytest.mark.parametrize(
    "column",
    [f.name for f in TMDB_MOVIES.schema.fields if not f.nullable],
)
def test_non_nullable_columns_reject_null(spark_session, valid_row, column):
    """
    Test that Spark refuses null in every non-nullable column.
    """
    row = {**valid_row, column: None}

    with pytest.raises(PySparkValueError):
        spark_session.createDataFrame([row], TMDB_MOVIES.schema)
