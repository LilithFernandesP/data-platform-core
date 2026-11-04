import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark_session():
    """
    Fixture to create a SparkSession for testing.
    """

    spark = (
        SparkSession.builder.appName("pytest-spark")
        .master("local[1]")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield spark
    spark.stop()
