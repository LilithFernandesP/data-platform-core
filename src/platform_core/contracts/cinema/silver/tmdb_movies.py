from pyspark.sql.types import (
    ArrayType,
    DateType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from platform_core.contracts.model import TableContract


def _col(name, dtype, nullable, description, pii=False, **extra):
    return StructField(
        name=name,
        dataType=dtype,
        nullable=nullable,
        metadata={"description": description, "pii": pii, **extra},
    )


TMDB_MOVIES = TableContract(
    name="tmdb_movies",
    domain="cinema",
    layer="silver",
    version=1,
    owner="eng_team",
    description="TMDB movies data, including details such as title, release date, genres, production companies, and more.",
    schema=StructType(
        [
            _col("tmdb_id", LongType(), False, "TMDB identifier (e.g. 120)."),
            _col(
                "imdb_id",
                StringType(),
                True,
                "IMDb identifier (e.g. tt0499549). Null when TMDB has no IMDb link.",
            ),
            _col(
                "title",
                StringType(),
                False,
                "movie title in pt-br, Falls back to the original title when no translation exists",
            ),
            _col("original_title", StringType(), False, "original movie title"),
            _col("overview", StringType(), True, "movie overview"),
            _col(
                "original_language",
                StringType(),
                False,
                "original language of the movie",
            ),
            _col("status", StringType(), False, "movie status (e.g. released)"),
            _col("release_date", DateType(), True, "movie release date"),
            _col(
                "runtime_minutes",
                IntegerType(),
                True,
                "movie runtime in minutes",
                unit="minutes",
            ),
            _col(
                "budget",
                LongType(),
                True,
                "movie budget in USD, if not available, it will be null, 0->null",
                unit="USD",
            ),
            _col(
                "revenue",
                LongType(),
                True,
                "movie revenue in USD, if not available, it will be null, 0->null",
                unit="USD",
            ),
            _col("vote_average", DoubleType(), True, "Average user rating, 0 to 10."),
            _col("vote_count", IntegerType(), True, "number of votes for the movie"),
            _col(
                "popularity",
                DoubleType(),
                True,
                "TMDB trend index, unitless; only comparable within the same day. Overwritten on each load",
            ),
            _col(
                "collection_id",
                LongType(),
                True,
                "TMDB collection identifier (e.g. 10). Null when the movie is not part of a collection.",
            ),
            _col(
                "collection_name",
                StringType(),
                True,
                "TMDB collection name (e.g. Star Wars Collection). Null when the movie is not part of a collection.",
            ),
            _col(
                "genres",
                ArrayType(
                    StructType(
                        [
                            _col("id", LongType(), False, "genre identifier"),
                            _col("name", StringType(), False, "genre name"),
                        ]
                    )
                ),
                True,
                "list of genres associated with the movie",
            ),
            _col(
                "production_companies",
                ArrayType(
                    StructType(
                        [
                            _col(
                                "id", LongType(), False, "production company identifier"
                            ),
                            _col(
                                "name", StringType(), False, "production company name"
                            ),
                            _col(
                                "origin_country",
                                StringType(),
                                True,
                                "production company origin country",
                            ),
                        ]
                    )
                ),
                True,
                "list of production companies associated with the movie",
            ),
            _col(
                "ingested_at",
                TimestampType(),
                False,
                "timestamp when the data was ingested into the system",
            ),
        ]
    ),
)
