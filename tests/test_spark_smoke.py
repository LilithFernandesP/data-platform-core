def test_spark(spark_session):
    """
    Smoke test to verify that the SparkSession fixture is working correctly.
    """
    df = spark_session.createDataFrame(
        [(1, "Emily"), (2, "Sergio"), (3, "Alice")], ["id", "value"]
    )
    assert df.count() == 3
