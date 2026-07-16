import json
import re
from datetime import datetime
from typing import Any

import streamlit as st


st.set_page_config(
    page_title="SCOPE Accelerator",
    page_icon="⚙️",
    layout="wide",
)


DEFAULT_SCHEMA = [
    {"name": "CustomerId", "type": "string"},
    {"name": "ProductId", "type": "string"},
    {"name": "UsageDate", "type": "DateTime"},
    {"name": "UsageCount", "type": "int"},
    {"name": "ModifiedDate", "type": "DateTime"},
]


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        value.strip(),
    )

    return cleaned.strip("_") or "generated_scope_job"


def parse_schema(schema_text: str) -> tuple[list[dict], list[str]]:
    errors: list[str] = []

    try:
        schema = json.loads(schema_text)
    except json.JSONDecodeError as error:
        return [], [f"Invalid schema JSON: {error}"]

    if not isinstance(schema, list):
        return [], ["Schema must be a JSON list."]

    cleaned_schema: list[dict] = []
    seen_columns: set[str] = set()

    for index, column in enumerate(schema, start=1):
        if not isinstance(column, dict):
            errors.append(
                f"Schema item {index} must be an object."
            )
            continue

        name = str(column.get("name", "")).strip()
        data_type = str(column.get("type", "")).strip()

        if not name:
            errors.append(
                f"Schema item {index} has no column name."
            )
            continue

        if not data_type:
            errors.append(
                f"Column '{name}' has no data type."
            )
            continue

        if name in seen_columns:
            errors.append(
                f"Duplicate column: {name}"
            )
            continue

        seen_columns.add(name)

        cleaned_schema.append(
            {
                "name": name,
                "type": data_type,
            }
        )

    return cleaned_schema, errors


def validate_configuration(
    config: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []

    job_name = config["job_name"].strip()
    input_path = config["input_path"].strip()
    output_path = config["output_path"].strip()
    columns = config["columns"]

    column_names = {
        column["name"]
        for column in columns
    }

    if job_name:
        checks.append("Job name is provided.")
    else:
        errors.append("Job name is required.")

    if input_path:
        checks.append("Input path is provided.")
    else:
        errors.append("Input path is required.")

    if output_path:
        checks.append("Output path is provided.")
    else:
        errors.append("Output path is required.")

    if input_path and output_path:
        if input_path.rstrip("/") == output_path.rstrip("/"):
            errors.append(
                "Input and output paths cannot be identical."
            )
        else:
            checks.append(
                "Input and output paths are different."
            )

    if columns:
        checks.append(
            f"{len(columns)} schema columns are configured."
        )
    else:
        errors.append(
            "At least one schema column is required."
        )

    selected_columns = config.get(
        "selected_columns",
        [],
    )

    if not selected_columns:
        errors.append(
            "Select at least one output column."
        )

    invalid_selected_columns = [
        column
        for column in selected_columns
        if column not in column_names
    ]

    if invalid_selected_columns:
        errors.append(
            "Unknown selected columns: "
            + ", ".join(invalid_selected_columns)
        )

    if config["deduplication_enabled"]:
        deduplication_keys = config[
            "deduplication_keys"
        ]

        if not deduplication_keys:
            errors.append(
                "Select at least one deduplication key."
            )

        if not config["order_by_column"]:
            errors.append(
                "Select an ordering column."
            )

    if config["aggregation_enabled"]:
        if not config["group_by_columns"]:
            errors.append(
                "Select at least one group-by column."
            )

        if not config["aggregation_expression"].strip():
            errors.append(
                "Aggregation expression is required."
            )

        if not config["aggregation_alias"].strip():
            errors.append(
                "Aggregation alias is required."
            )

    if not config["filter_condition"].strip():
        warnings.append(
            "No filter condition is configured."
        )

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def format_columns(
    columns: list[str],
    indentation: int = 8,
) -> str:
    prefix = " " * indentation
    lines: list[str] = []

    for index, column in enumerate(columns):
        comma = "," if index < len(columns) - 1 else ""
        lines.append(
            f"{prefix}{column}{comma}"
        )

    return "\n".join(lines)


def generate_scope_script(
    config: dict[str, Any],
) -> str:
    generated_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    schema_lines: list[str] = []

    for index, column in enumerate(config["columns"]):
        comma = (
            ","
            if index < len(config["columns"]) - 1
            else ""
        )

        schema_lines.append(
            f"        {column['name']} "
            f"{column['type']}{comma}"
        )

    selected_columns = config["selected_columns"]

    script: list[str] = [
        "// =====================================================",
        "// Generated by SCOPE Accelerator",
        f"// Job: {config['job_name']}",
        f"// Environment: {config['environment']}",
        f"// Generated: {generated_at}",
        "// =====================================================",
        "",
        (
            f'#DECLARE InputPath string = '
            f'"{config["input_path"]}";'
        ),
        (
            f'#DECLARE OutputPath string = '
            f'"{config["output_path"]}";'
        ),
        "",
        "source_data =",
        "    EXTRACT",
        "\n".join(schema_lines),
        "    FROM @InputPath",
        "    USING DefaultTextExtractor();",
        "",
        "filtered_data =",
        "    SELECT",
        format_columns(selected_columns),
        "    FROM source_data",
    ]

    filter_condition = config[
        "filter_condition"
    ].strip()

    if filter_condition:
        script.append(
            f"    WHERE {filter_condition};"
        )
    else:
        script[-1] = script[-1] + ";"

    current_source = "filtered_data"

    if config["deduplication_enabled"]:
        deduplication_keys = ", ".join(
            config["deduplication_keys"]
        )

        script.extend(
            [
                "",
                "ranked_data =",
                "    SELECT",
                "        *,",
                "        ROW_NUMBER() OVER",
                "        (",
                (
                    "            PARTITION BY "
                    f"{deduplication_keys}"
                ),
                (
                    "            ORDER BY "
                    f"{config['order_by_column']} "
                    f"{config['order_direction']}"
                ),
                "        ) AS RowNumber",
                "    FROM filtered_data;",
                "",
                "deduplicated_data =",
                "    SELECT",
                format_columns(selected_columns),
                "    FROM ranked_data",
                "    WHERE RowNumber == 1;",
            ]
        )

        current_source = "deduplicated_data"

    if config["aggregation_enabled"]:
        group_by_columns = config[
            "group_by_columns"
        ]

        aggregation_lines = [
            f"        {column},"
            for column in group_by_columns
        ]

        aggregation_lines.append(
            "        "
            f"{config['aggregation_expression']} "
            f"AS {config['aggregation_alias']}"
        )

        script.extend(
            [
                "",
                "final_data =",
                "    SELECT",
                "\n".join(aggregation_lines),
                f"    FROM {current_source}",
                (
                    "    GROUP BY "
                    + ", ".join(group_by_columns)
                    + ";"
                ),
            ]
        )

        output_source = "final_data"
    else:
        output_source = current_source

    script.extend(
        [
            "",
            f"OUTPUT {output_source}",
            "TO @OutputPath",
            "USING DefaultTextOutputter();",
        ]
    )

    return "\n".join(script)


st.title("⚙️ Custom SCOPE Script Accelerator")

st.caption(
    "Configure your processing rules and generate "
    "a custom SCOPE script."
)


with st.sidebar:
    st.header("Script Options")

    operation = st.selectbox(
        "Operation",
        [
            "Filter only",
            "Filter and deduplicate",
            "Filter, deduplicate and aggregate",
        ],
        index=2,
    )

    deduplication_enabled = operation in {
        "Filter and deduplicate",
        "Filter, deduplicate and aggregate",
    }

    aggregation_enabled = (
        operation
        == "Filter, deduplicate and aggregate"
    )


left_column, right_column = st.columns(
    [1.1, 0.9],
    gap="large",
)


with left_column:
    with st.form("custom_scope_form"):
        st.subheader("Job Details")

        job_name = st.text_input(
            "Job name",
            value="CustomerUsageDaily",
        )

        environment = st.selectbox(
            "Environment",
            ["DEV", "TEST", "PROD"],
        )

        input_path = st.text_input(
            "Input path",
            value="/data/raw/customer_usage/",
        )

        output_path = st.text_input(
            "Output path",
            value="/data/processed/customer_usage/",
        )

        st.subheader("Input Schema")

        schema_text = st.text_area(
            "Schema JSON",
            value=json.dumps(
                DEFAULT_SCHEMA,
                indent=2,
            ),
            height=260,
        )

        columns, schema_errors = parse_schema(
            schema_text
        )

        available_columns = [
            column["name"]
            for column in columns
        ]

        selected_columns = st.multiselect(
            "Columns to include in output",
            options=available_columns,
            default=available_columns,
        )

        st.subheader("Filter")

        filter_condition = st.text_input(
            "Filter condition",
            value="UsageCount > 0",
        )

        deduplication_keys: list[str] = []
        order_by_column = ""
        order_direction = "DESC"

        if deduplication_enabled:
            st.subheader("Deduplication")

            deduplication_keys = st.multiselect(
                "Deduplication keys",
                options=available_columns,
                default=[
                    column
                    for column in [
                        "CustomerId",
                        "ProductId",
                        "UsageDate",
                    ]
                    if column in available_columns
                ],
            )

            dedup_column_1, dedup_column_2 = (
                st.columns(2)
            )

            with dedup_column_1:
                order_by_column = st.selectbox(
                    "Ordering column",
                    options=(
                        available_columns
                        if available_columns
                        else [""]
                    ),
                )

            with dedup_column_2:
                order_direction = st.selectbox(
                    "Order direction",
                    ["DESC", "ASC"],
                )

        group_by_columns: list[str] = []
        aggregation_expression = ""
        aggregation_alias = ""

        if aggregation_enabled:
            st.subheader("Aggregation")

            group_by_columns = st.multiselect(
                "Group-by columns",
                options=available_columns,
                default=[
                    column
                    for column in [
                        "CustomerId",
                        "ProductId",
                    ]
                    if column in available_columns
                ],
            )

            aggregation_expression = st.text_input(
                "Aggregation expression",
                value="SUM(UsageCount)",
            )

            aggregation_alias = st.text_input(
                "Aggregation alias",
                value="TotalUsage",
            )

        submitted = st.form_submit_button(
            "Generate Custom SCOPE Script",
            type="primary",
            use_container_width=True,
        )


with right_column:
    st.subheader("Validation and Generated Script")

    if submitted:
        configuration = {
            "job_name": job_name.strip(),
            "environment": environment,
            "input_path": input_path.strip(),
            "output_path": output_path.strip(),
            "columns": columns,
            "selected_columns": selected_columns,
            "filter_condition": (
                filter_condition.strip()
            ),
            "deduplication_enabled": (
                deduplication_enabled
            ),
            "deduplication_keys": (
                deduplication_keys
            ),
            "order_by_column": (
                order_by_column
            ),
            "order_direction": (
                order_direction
            ),
            "aggregation_enabled": (
                aggregation_enabled
            ),
            "group_by_columns": (
                group_by_columns
            ),
            "aggregation_expression": (
                aggregation_expression
            ),
            "aggregation_alias": (
                aggregation_alias
            ),
        }

        validation = validate_configuration(
            configuration
        )

        if schema_errors:
            validation["errors"].extend(
                schema_errors
            )
            validation["is_valid"] = False

        if validation["is_valid"]:
            st.success(
                "Configuration is valid."
            )
        else:
            st.error(
                "Configuration contains errors."
            )

        for check in validation["checks"]:
            st.write(f"✅ {check}")

        for warning in validation["warnings"]:
            st.write(f"⚠️ {warning}")

        for error in validation["errors"]:
            st.write(f"❌ {error}")

        if validation["is_valid"]:
            generated_script = generate_scope_script(
                configuration
            )

            st.code(
                generated_script,
                language="sql",
                line_numbers=True,
            )

            safe_job_name = sanitize_filename(
                job_name
            )

            st.download_button(
                "Download .scope script",
                data=generated_script,
                file_name=f"{safe_job_name}.scope",
                mime="text/plain",
                use_container_width=True,
            )

            st.download_button(
                "Download JSON configuration",
                data=json.dumps(
                    configuration,
                    indent=2,
                ),
                file_name=f"{safe_job_name}.json",
                mime="application/json",
                use_container_width=True,
            )

    else:
        st.info(
            "Configure the job and select "
            "'Generate Custom SCOPE Script'."
        )
