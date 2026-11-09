from pyspark.sql import SparkSession

from platform_core.contracts.model import TableContract


def _sql_string(text: str) -> str:
    """
    Wrap text in single quotes for Spark SQL, escaping what would break it.
    """
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def create_table(
    spark: SparkSession, contract: TableContract, env: str, location: str
) -> None:
    """
    Create the catalog table for a silver (Parquet) contract.

    Columns, types, column comments and partitions come straight from the
    contract schema through the DataFrame writer. The table comment and the
    contract version have no place in the writer, so they are set right after.
    """
    if contract.layer != "silver":
        raise NotImplementedError(
            f"Table creation for layer '{contract.layer}' is not implemented "
            f"(contract '{contract.name}'). Only silver is supported."
        )

    table = contract.qualified_name(env)

    (
        spark.createDataFrame([], contract.schema)
        .write.format("parquet")
        .partitionBy(*contract.partition_by)
        .option("path", location)
        .saveAsTable(table)
    )

    spark.sql(
        f"ALTER TABLE {table} SET TBLPROPERTIES ("
        f"'comment' = {_sql_string(contract.description)}, "
        f"'contract_version' = '{contract.version}')"
    )
