from copy import deepcopy
from typing import Any


COMPONENT_TYPES = [
    "Declare Variable",
    "Read File",
    "Select Columns",
    "Filter",
    "Join",
    "Aggregate",
    "Union",
    "Custom Code",
    "Write File",
]


DATA_TYPES = [
    "string",
    "int",
    "long",
    "double",
    "decimal",
    "bool",
    "DateTime",
]


JOIN_TYPES = [
    "INNER",
    "LEFT OUTER",
    "RIGHT OUTER",
    "FULL OUTER",
]


JOIN_SOURCE_TYPES = [
    "Dataset",
    "Subquery",
]


DEFAULT_SCHEMA = [
    {
        "name": "CustomerId",
        "type": "string",
    },
    {
        "name": "ProductId",
        "type": "string",
    },
    {
        "name": "UsageCount",
        "type": "int",
    },
]


DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
    "Declare Variable": {
        "variable_name": "RunDate",
        "variable_type": "string",
        "variable_value": "2026-07-16",
        "quote_value": True,
    },
    "Read File": {
        "dataset_name": "source_data",
        "input_path": "/data/raw/input.csv",
        "extractor": "DefaultTextExtractor",
        "delimiter": ",",
        "skip_header": True,
        "schema": DEFAULT_SCHEMA,
    },
    "Select Columns": {
        "source_dataset": "source_data",
        "output_dataset": "selected_data",
        "columns": [
            "CustomerId",
            "ProductId",
        ],
    },
    "Filter": {
        "source_dataset": "source_data",
        "output_dataset": "filtered_data",
        "condition": "UsageCount > 0",
    },
    "Join": {
    "left_source_type": "Dataset",
    "left_dataset": "customer_data",
    "left_subquery": "",
    "left_alias": "left_data",

    "right_source_type": "Dataset",
    "right_dataset": "product_data",
    "right_subquery": "",
    "right_alias": "right_data",

    "join_type": "INNER",
    "join_condition": (
        "left_data.ProductId == "
        "right_data.ProductId"
    ),

    "selected_columns": [],
    "selected_column_names": [],

    "output_dataset": "joined_data",
    },
    "Aggregate": {
        "source_dataset": "source_data",
        "output_dataset": "aggregated_data",
        "group_by_columns": [
            "CustomerId",
            "ProductId",
        ],
        "aggregate_expressions": [
            "SUM(UsageCount) AS TotalUsage",
        ],
    },
    "Union": {
        "left_dataset": "first_data",
        "right_dataset": "second_data",
        "union_all": True,
        "output_dataset": "unioned_data",
    },
    "Custom Code": {
        "block_name": "Custom transformation",
        "custom_code": (
            "custom_data =\n"
            "    SELECT *\n"
            "    FROM source_data;"
        ),
    },
    "Write File": {
        "source_dataset": "source_data",
        "output_path": "/data/output/result.csv",
        "outputter": "DefaultTextOutputter",
        "delimiter": ",",
        "include_header": True,
    },
}


def create_default_config(
    component_type: str,
) -> dict[str, Any]:
    if component_type not in DEFAULT_CONFIGS:
        raise ValueError(
            f"Unsupported component type: {component_type}"
        )

    return deepcopy(DEFAULT_CONFIGS[component_type])
