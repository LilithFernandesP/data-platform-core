import re
from dataclasses import dataclass

from pyspark.sql.types import StructType


@dataclass(frozen=True)
class TableContract:
    """
    Represents a contract with a name and a list of fields.
    """

    name: str
    domain: str
    layer: str
    version: int
    owner: str
    description: str
    schema: StructType
    partition_by: tuple[str, ...] = ()

    def qualified_name(self, env):
        return f"{self.domain}_{self.layer}_{env}.{self.name}"

    def __post_init__(self):

        if self.layer not in ["bronze", "silver", "gold"]:
            raise ValueError(
                f"Invalid layer: {self.layer}. Must be one of ['bronze', 'silver', 'gold']."
            )

        def is_snake_case(arg):
            return re.fullmatch(r"^[a-z]+(_[a-z]+)*$", arg)

        if not is_snake_case(self.name):
            raise ValueError(f"Invalid name: {self.name}. Must be in snake_case.")

        if not is_snake_case(self.domain):
            raise ValueError(f"Invalid domain: {self.domain}. Must be in snake_case.")

        not_snake_case_columns = [
            field for field in self.schema.fieldNames() if not is_snake_case(field)
        ]
        if not_snake_case_columns:
            raise ValueError(f"{not_snake_case_columns} needs to be snake_case.")

        missing_comment = [
            f.name for f in self.schema.fields if not f.metadata.get("comment")
        ]
        if missing_comment:
            raise ValueError(f"columns missing comment: {', '.join(missing_comment)}")

        if not set(self.partition_by).issubset(self.schema.fieldNames()):
            raise ValueError(
                f"Partition field {', '.join(set(self.partition_by) - set(self.schema.fieldNames()))} is invalid."
            )

        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise TypeError("Version must be int type.")

        if not self.version >= 1:
            raise ValueError("Version must be >= 1.")
