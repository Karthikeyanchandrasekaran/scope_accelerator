import json
import re
from datetime import datetime
from typing import Any

import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="SCOPE Engineering Studio",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

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

DEFAULT_SCHEMA = """CustomerId:string
ProductId:string
UsageDate:DateTime
UsageCount:int
ModifiedDate:DateTime"""


# ============================================================
# SESSION STATE
# ============================================================

def initialize_state() -> None:
    if "components" not in st.session_state:
        st.session_state.components = []

    if "component_counter" not in st.session_state:
        st.session_state.component_counter = 1

    if "generated_script" not in st.session_state:
        st.session_state.generated_script = ""


initialize_state()


# ============================================================
# GENERAL HELPERS
# ============================================================

def sanitize_name(value: str, fallback: str = "scope_job") -> str:
    cleaned = re.sub(
        pattern=r"[^A-Za-z0-9_-]+",
        repl="_",
        string=value.strip(),
    )

    return cleaned.strip("_") or fallback


def parse_csv_values(value: str) -> list[str]:
    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def parse_schema_text(
    schema_text: str,
) -> tuple[list[dict[str, str]], list[str]]:
    columns: list[dict[str, str]] = []
    errors: list[str] = []
    existing_names: set[str] = set()

    for line_number, raw_line in enumerate(
        schema_text.splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line:
            continue

        if ":" not in line:
            errors.append(
                f"Schema line {line_number} must use "
                "'ColumnName:DataType'."
            )
            continue

        name, data_type = line.split(":", maxsplit=1)

        name = name.strip()
        data_type = data_type.strip()

        if not name:
            errors.append(
                f"Schema line {line_number} has no column name."
            )
            continue

        if not data_type:
            errors.append(
                f"Column '{name}' has no data type."
            )
            continue

        if name in existing_names:
            errors.append(
                f"Duplicate schema column: {name}"
            )
            continue

        existing_names.add(name)

        columns.append(
            {
                "name": name,
                "type": data_type,
            }
        )

    return columns, errors


def component_title(component: dict[str, Any]) -> str:
    component_type = component["type"]
    config = component["config"]

    if component_type == "Declare Variable":
        return f"Declare: {config.get('variable_name', 'Variable')}"

    if component_type == "Read File":
        return f"Read: {config.get('dataset_name', 'Dataset')}"

    if component_type == "Select Columns":
        return (
            f"Select: {config.get('source_dataset', '?')} "
            f"→ {config.get('output_dataset', '?')}"
        )

    if component_type == "Filter":
        return (
            f"Filter: {config.get('source_dataset', '?')} "
            f"→ {config.get('output_dataset', '?')}"
        )

    if component_type == "Join":
        return (
            f"Join: {config.get('left_dataset', '?')} + "
            f"{config.get('right_dataset', '?')}"
        )

    if component_type == "Aggregate":
        return (
            f"Aggregate: {config.get('source_dataset', '?')} "
            f"→ {config.get('output_dataset', '?')}"
        )

    if component_type == "Union":
        return (
            f"Union: {config.get('left_dataset', '?')} + "
            f"{config.get('right_dataset', '?')}"
        )

    if component_type == "Custom Code":
        return config.get("block_name", "Custom Code")

    if component_type == "Write File":
        return f"Write: {config.get('source_dataset', '?')}"

    return component_type


def add_component(
    component_type: str,
    config: dict[str, Any],
) -> None:
    component = {
        "id": st.session_state.component_counter,
        "type": component_type,
        "config": config,
    }

    st.session_state.components.append(component)
    st.session_state.component_counter += 1


def delete_component(index: int) -> None:
    if 0 <= index < len(st.session_state.components):
        st.session_state.components.pop(index)


def move_component_up(index: int) -> None:
    if index > 0:
        components = st.session_state.components
        components[index - 1], components[index] = (
            components[index],
            components[index - 1],
        )


def move_component_down(index: int) -> None:
    components = st.session_state.components

    if index < len(components) - 1:
        components[index + 1], components[index] = (
            components[index],
            components[index + 1],
        )


def get_available_datasets() -> list[str]:
    datasets: list[str] = []

    for component in st.session_state.components:
        component_type = component["type"]
        config = component["config"]

        if component_type == "Read File":
            dataset_name = config.get("dataset_name")

        elif component_type in {
            "Select Columns",
            "Filter",
            "Join",
            "Aggregate",
            "Union",
        }:
            dataset_name = config.get("output_dataset")

        else:
            dataset_name = None

        if dataset_name and dataset_name not in datasets:
            datasets.append(dataset_name)

    return datasets


# ============================================================
# VALIDATION
# ============================================================

def validate_workflow(
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []
    available_datasets: set[str] = set()
    declared_variables: set[str] = set()

    if not components:
        errors.append("Add at least one workflow component.")

    for position, component in enumerate(
        components,
        start=1,
    ):
        component_type = component["type"]
        config = component["config"]
        label = f"Step {position} ({component_type})"

        if component_type == "Declare Variable":
            variable_name = config.get(
                "variable_name",
                "",
            ).strip()

            if not variable_name:
                errors.append(
                    f"{label}: variable name is required."
                )
            elif variable_name in declared_variables:
                errors.append(
                    f"{label}: duplicate variable "
                    f"'{variable_name}'."
                )
            else:
                declared_variables.add(variable_name)

        elif component_type == "Read File":
            dataset_name = config.get(
                "dataset_name",
                "",
            ).strip()

            input_path = config.get(
                "input_path",
                "",
            ).strip()

            schema = config.get("schema", [])

            if not dataset_name:
                errors.append(
                    f"{label}: dataset name is required."
                )

            if dataset_name in available_datasets:
                errors.append(
                    f"{label}: dataset '{dataset_name}' "
                    "already exists."
                )

            if not input_path:
                errors.append(
                    f"{label}: input path is required."
                )

            if not schema:
                errors.append(
                    f"{label}: schema is required."
                )

            if dataset_name:
                available_datasets.add(dataset_name)

        elif component_type == "Select Columns":
            source = config.get(
                "source_dataset",
                "",
            )

            output = config.get(
                "output_dataset",
                "",
            )

            columns = config.get("columns", [])

            if source not in available_datasets:
                errors.append(
                    f"{label}: source dataset '{source}' "
                    "is not available at this step."
                )

            if not output:
                errors.append(
                    f"{label}: output dataset is required."
                )

            if not columns:
                errors.append(
                    f"{label}: select at least one column."
                )

            if output:
                available_datasets.add(output)

        elif component_type == "Filter":
            source = config.get(
                "source_dataset",
                "",
            )

            output = config.get(
                "output_dataset",
                "",
            )

            condition = config.get(
                "condition",
                "",
            ).strip()

            if source not in available_datasets:
                errors.append(
                    f"{label}: source dataset '{source}' "
                    "is not available."
                )

            if not output:
                errors.append(
                    f"{label}: output dataset is required."
                )

            if not condition:
                errors.append(
                    f"{label}: filter condition is required."
                )

            if output:
                available_datasets.add(output)

        elif component_type == "Join":
            left = config.get("left_dataset", "")
            right = config.get("right_dataset", "")
            output = config.get("output_dataset", "")
            condition = config.get(
                "join_condition",
                "",
            ).strip()

            if left not in available_datasets:
                errors.append(
                    f"{label}: left dataset '{left}' "
                    "is not available."
                )

            if right not in available_datasets:
                errors.append(
                    f"{label}: right dataset '{right}' "
                    "is not available."
                )

            if left == right and left:
                warnings.append(
                    f"{label}: both join inputs are the same."
                )

            if not condition:
                errors.append(
                    f"{label}: join condition is required."
                )

            if not output:
                errors.append(
                    f"{label}: output dataset is required."
                )

            if output:
                available_datasets.add(output)

        elif component_type == "Aggregate":
            source = config.get(
                "source_dataset",
                "",
            )

            output = config.get(
                "output_dataset",
                "",
            )

            group_by_columns = config.get(
                "group_by_columns",
                [],
            )

            aggregate_expressions = config.get(
                "aggregate_expressions",
                [],
            )

            if source not in available_datasets:
                errors.append(
                    f"{label}: source dataset '{source}' "
                    "is not available."
                )

            if not group_by_columns:
                warnings.append(
                    f"{label}: no group-by columns configured."
                )

            if not aggregate_expressions:
                errors.append(
                    f"{label}: at least one aggregate "
                    "expression is required."
                )

            if not output:
                errors.append(
                    f"{label}: output dataset is required."
                )

            if output:
                available_datasets.add(output)

        elif component_type == "Union":
            left = config.get("left_dataset", "")
            right = config.get("right_dataset", "")
            output = config.get("output_dataset", "")

            if left not in available_datasets:
                errors.append(
                    f"{label}: left dataset '{left}' "
                    "is not available."
                )

            if right not in available_datasets:
                errors.append(
                    f"{label}: right dataset '{right}' "
                    "is not available."
                )

            if not output:
                errors.append(
                    f"{label}: output dataset is required."
                )

            if output:
                available_datasets.add(output)

        elif component_type == "Custom Code":
            custom_code = config.get(
                "custom_code",
                "",
            ).strip()

            if not custom_code:
                errors.append(
                    f"{label}: custom code is empty."
                )

        elif component_type == "Write File":
            source = config.get(
                "source_dataset",
                "",
            )

            output_path = config.get(
                "output_path",
                "",
            ).strip()

            if source not in available_datasets:
                errors.append(
                    f"{label}: source dataset '{source}' "
                    "is not available."
                )

            if not output_path:
                errors.append(
                    f"{label}: output path is required."
                )

    if components:
        write_components = [
            component
            for component in components
            if component["type"] == "Write File"
        ]

        if not write_components:
            warnings.append(
                "The workflow does not contain a Write File step."
            )
        else:
            checks.append(
                f"{len(write_components)} output step(s) configured."
            )

        checks.append(
            f"{len(components)} workflow component(s) configured."
        )

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


# ============================================================
# SCOPE CODE GENERATORS
# ============================================================

def generate_declare_component(
    config: dict[str, Any],
) -> str:
    variable_name = config["variable_name"]
    variable_type = config["variable_type"]
    variable_value = config["variable_value"]
    quote_value = config.get("quote_value", True)

    formatted_value = (
        f'"{variable_value}"'
        if quote_value
        else variable_value
    )

    return (
        f"#DECLARE {variable_name} "
        f"{variable_type} = {formatted_value};"
    )


def generate_read_component(
    config: dict[str, Any],
) -> str:
    dataset_name = config["dataset_name"]
    input_path = config["input_path"]
    extractor = config["extractor"]
    delimiter = config["delimiter"]
    skip_header = config["skip_header"]
    schema = config["schema"]

    schema_lines: list[str] = []

    for index, column in enumerate(schema):
        comma = "," if index < len(schema) - 1 else ""

        schema_lines.append(
            f"        {column['name']} "
            f"{column['type']}{comma}"
        )

    extractor_arguments: list[str] = [
        f'delimiter: "{delimiter}"',
    ]

    if skip_header:
        extractor_arguments.append(
            "skipFirstRows: 1"
        )

    extractor_text = ",\n        ".join(
        extractor_arguments
    )

    return "\n".join(
        [
            f"// Read dataset: {dataset_name}",
            f"{dataset_name} =",
            "    EXTRACT",
            "\n".join(schema_lines),
            f'    FROM "{input_path}"',
            f"    USING {extractor}(",
            f"        {extractor_text}",
            "    );",
        ]
    )


def generate_select_component(
    config: dict[str, Any],
) -> str:
    output_dataset = config["output_dataset"]
    source_dataset = config["source_dataset"]
    columns = config["columns"]

    select_lines: list[str] = []

    for index, column in enumerate(columns):
        comma = "," if index < len(columns) - 1 else ""
        select_lines.append(
            f"        {column}{comma}"
        )

    return "\n".join(
        [
            f"// Select columns from {source_dataset}",
            f"{output_dataset} =",
            "    SELECT",
            "\n".join(select_lines),
            f"    FROM {source_dataset};",
        ]
    )


def generate_filter_component(
    config: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"// Filter dataset: {config['source_dataset']}",
            f"{config['output_dataset']} =",
            "    SELECT *",
            f"    FROM {config['source_dataset']}",
            f"    WHERE {config['condition']};",
        ]
    )


def generate_join_component(
    config: dict[str, Any],
) -> str:
    left_dataset = config["left_dataset"]
    right_dataset = config["right_dataset"]
    output_dataset = config["output_dataset"]
    join_type = config["join_type"]
    join_condition = config["join_condition"]
    selected_columns = config.get(
        "selected_columns",
        "",
    ).strip()

    select_text = (
        selected_columns
        if selected_columns
        else "*"
    )

    return "\n".join(
        [
            f"// {join_type} join",
            f"{output_dataset} =",
            f"    SELECT {select_text}",
            f"    FROM {left_dataset} AS left_data",
            f"         {join_type} JOIN "
            f"{right_dataset} AS right_data",
            f"    ON {join_condition};",
        ]
    )


def generate_aggregate_component(
    config: dict[str, Any],
) -> str:
    output_dataset = config["output_dataset"]
    source_dataset = config["source_dataset"]
    group_by_columns = config["group_by_columns"]
    aggregate_expressions = config[
        "aggregate_expressions"
    ]

    select_entries = (
        group_by_columns + aggregate_expressions
    )

    select_lines: list[str] = []

    for index, entry in enumerate(select_entries):
        comma = "," if index < len(select_entries) - 1 else ""
        select_lines.append(
            f"        {entry}{comma}"
        )

    script_lines = [
        f"// Aggregate dataset: {source_dataset}",
        f"{output_dataset} =",
        "    SELECT",
        "\n".join(select_lines),
        f"    FROM {source_dataset}",
    ]

    if group_by_columns:
        script_lines.append(
            "    GROUP BY "
            + ", ".join(group_by_columns)
            + ";"
        )
    else:
        script_lines[-1] += ";"

    return "\n".join(script_lines)


def generate_union_component(
    config: dict[str, Any],
) -> str:
    union_keyword = (
        "UNION ALL"
        if config.get("union_all", True)
        else "UNION"
    )

    return "\n".join(
        [
            "// Combine datasets",
            f"{config['output_dataset']} =",
            "    SELECT *",
            f"    FROM {config['left_dataset']}",
            f"    {union_keyword}",
            "    SELECT *",
            f"    FROM {config['right_dataset']};",
        ]
    )


def generate_custom_component(
    config: dict[str, Any],
) -> str:
    block_name = config.get(
        "block_name",
        "Custom SCOPE Code",
    )

    custom_code = config.get(
        "custom_code",
        "",
    )

    return "\n".join(
        [
            f"// {block_name}",
            custom_code,
        ]
    )


def generate_write_component(
    config: dict[str, Any],
) -> str:
    source_dataset = config["source_dataset"]
    output_path = config["output_path"]
    outputter = config["outputter"]
    delimiter = config["delimiter"]
    include_header = config["include_header"]

    outputter_arguments = [
        f'delimiter: "{delimiter}"',
        (
            "outputHeader: true"
            if include_header
            else "outputHeader: false"
        ),
    ]

    return "\n".join(
        [
            f"// Write dataset: {source_dataset}",
            f"OUTPUT {source_dataset}",
            f'TO "{output_path}"',
            f"USING {outputter}(",
            "    " + ",\n    ".join(outputter_arguments),
            ");",
        ]
    )


def generate_scope_script(
    job_name: str,
    environment: str,
    components: list[dict[str, Any]],
) -> str:
    generated_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    script_parts: list[str] = [
        "// ============================================================",
        "// Generated by SCOPE Engineering Studio",
        f"// Job Name    : {job_name}",
        f"// Environment : {environment}",
        f"// Generated   : {generated_at}",
        "//",
        "// POC output: validate syntax and internal libraries",
        "// before running in the Microsoft SCOPE environment.",
        "// ============================================================",
        "",
    ]

    for index, component in enumerate(
        components,
        start=1,
    ):
        component_type = component["type"]
        config = component["config"]

        script_parts.extend(
            [
                f"// ---------------- STEP {index} ----------------",
            ]
        )

        if component_type == "Declare Variable":
            generated_component = (
                generate_declare_component(config)
            )

        elif component_type == "Read File":
            generated_component = (
                generate_read_component(config)
            )

        elif component_type == "Select Columns":
            generated_component = (
                generate_select_component(config)
            )

        elif component_type == "Filter":
            generated_component = (
                generate_filter_component(config)
            )

        elif component_type == "Join":
            generated_component = (
                generate_join_component(config)
            )

        elif component_type == "Aggregate":
            generated_component = (
                generate_aggregate_component(config)
            )

        elif component_type == "Union":
            generated_component = (
                generate_union_component(config)
            )

        elif component_type == "Custom Code":
            generated_component = (
                generate_custom_component(config)
            )

        elif component_type == "Write File":
            generated_component = (
                generate_write_component(config)
            )

        else:
            generated_component = (
                f"// Unsupported component: {component_type}"
            )

        script_parts.extend(
            [
                generated_component,
                "",
            ]
        )

    return "\n".join(script_parts)


# ============================================================
# COMPONENT FORMS
# ============================================================

def render_declare_form() -> None:
    with st.form("declare_component_form"):
        variable_name = st.text_input(
            "Variable name",
            value="RunDate",
        )

        variable_type = st.selectbox(
            "Variable type",
            options=DATA_TYPES,
            index=0,
        )

        variable_value = st.text_input(
            "Variable value",
            value="2026-07-16",
        )

        quote_value = st.checkbox(
            "Wrap value in quotes",
            value=True,
        )

        submitted = st.form_submit_button(
            "Add Declare Variable",
            use_container_width=True,
        )

        if submitted:
            add_component(
                "Declare Variable",
                {
                    "variable_name": variable_name.strip(),
                    "variable_type": variable_type,
                    "variable_value": variable_value,
                    "quote_value": quote_value,
                },
            )

            st.rerun()


def render_read_form() -> None:
    with st.form("read_component_form"):
        dataset_name = st.text_input(
            "Dataset name",
            value="customer_data",
        )

        input_path = st.text_input(
            "Input path",
            value="/data/raw/customer/customer.csv",
        )

        extractor = st.text_input(
            "Extractor",
            value="DefaultTextExtractor",
        )

        delimiter = st.selectbox(
            "Delimiter",
            options=[",", "|", "\\t", ";"],
        )

        skip_header = st.checkbox(
            "Skip first/header row",
            value=True,
        )

        schema_text = st.text_area(
            "Schema",
            value=DEFAULT_SCHEMA,
            height=180,
            help=(
                "Enter one column per line using "
                "ColumnName:DataType."
            ),
        )

        submitted = st.form_submit_button(
            "Add Read File",
            use_container_width=True,
        )

        if submitted:
            schema, schema_errors = parse_schema_text(
                schema_text
            )

            if schema_errors:
                for error in schema_errors:
                    st.error(error)

            else:
                add_component(
                    "Read File",
                    {
                        "dataset_name": dataset_name.strip(),
                        "input_path": input_path.strip(),
                        "extractor": extractor.strip(),
                        "delimiter": delimiter,
                        "skip_header": skip_header,
                        "schema": schema,
                    },
                )

                st.rerun()


def render_select_form() -> None:
    datasets = get_available_datasets()

    if not datasets:
        st.warning(
            "Add a Read File or another dataset-producing "
            "component first."
        )
        return

    with st.form("select_component_form"):
        source_dataset = st.selectbox(
            "Source dataset",
            options=datasets,
        )

        output_dataset = st.text_input(
            "Output dataset",
            value="selected_data",
        )

        columns_text = st.text_area(
            "Columns",
            value="CustomerId, ProductId, UsageCount",
            help="Enter columns separated by commas.",
        )

        submitted = st.form_submit_button(
            "Add Select Columns",
            use_container_width=True,
        )

        if submitted:
            add_component(
                "Select Columns",
                {
                    "source_dataset": source_dataset,
                    "output_dataset": output_dataset.strip(),
                    "columns": parse_csv_values(
                        columns_text
                    ),
                },
            )

            st.rerun()


def render_filter_form() -> None:
    datasets = get_available_datasets()

    if not datasets:
        st.warning(
            "Add a dataset-producing component first."
        )
        return

    with st.form("filter_component_form"):
        source_dataset = st.selectbox(
            "Source dataset",
            options=datasets,
        )

        output_dataset = st.text_input(
            "Output dataset",
            value="filtered_data",
        )

        condition = st.text_area(
            "Filter condition",
            value="UsageCount > 0",
        )

        submitted = st.form_submit_button(
            "Add Filter",
            use_container_width=True,
        )

        if submitted:
            add_component(
                "Filter",
                {
                    "source_dataset": source_dataset,
                    "output_dataset": output_dataset.strip(),
                    "condition": condition.strip(),
                },
            )

            st.rerun()


def render_join_form() -> None:
    datasets = get_available_datasets()

    if len(datasets) < 2:
        st.warning(
            "A join requires at least two available datasets."
        )
        return

    with st.form("join_component_form"):
        left_dataset = st.selectbox(
            "Left dataset",
            options=datasets,
            key="join_left",
        )

        right_dataset = st.selectbox(
            "Right dataset",
            options=datasets,
            index=1,
            key="join_right",
        )

        join_type = st.selectbox(
            "Join type",
            options=JOIN_TYPES,
        )

        join_condition = st.text_input(
            "Join condition",
            value=(
                "left_data.ProductId == "
                "right_data.ProductId"
            ),
        )

        selected_columns = st.text_area(
            "Selected columns",
            value=(
                "left_data.CustomerId, "
                "left_data.ProductId, "
                "right_data.ProductName"
            ),
            help=(
                "Leave empty to generate SELECT *."
            ),
        )

        output_dataset = st.text_input(
            "Output dataset",
            value="joined_data",
        )

        submitted = st.form_submit_button(
            "Add Join",
            use_container_width=True,
        )

        if submitted:
            add_component(
                "Join",
                {
                    "left_dataset": left_dataset,
                    "right_dataset": right_dataset,
                    "join_type": join_type,
                    "join_condition": join_condition.strip(),
                    "selected_columns": (
                        selected_columns.strip()
                    ),
                    "output_dataset": output_dataset.strip(),
                },
            )

            st.rerun()


def render_aggregate_form() -> None:
    datasets = get_available_datasets()

    if not datasets:
        st.warning(
            "Add a dataset-producing component first."
        )
        return

    with st.form("aggregate_component_form"):
        source_dataset = st.selectbox(
            "Source dataset",
            options=datasets,
        )

        output_dataset = st.text_input(
            "Output dataset",
            value="aggregated_data",
        )

        group_by_text = st.text_input(
            "Group-by columns",
            value="CustomerId, ProductId",
        )

        aggregate_text = st.text_area(
            "Aggregate expressions",
            value=(
                "SUM(UsageCount) AS TotalUsage\n"
                "COUNT(*) AS RecordCount"
            ),
            help=(
                "Enter one aggregate expression per line."
            ),
        )

        submitted = st.form_submit_button(
            "Add Aggregate",
            use_container_width=True,
        )

        if submitted:
            aggregate_expressions = [
                line.strip()
                for line in aggregate_text.splitlines()
                if line.strip()
            ]

            add_component(
                "Aggregate",
                {
                    "source_dataset": source_dataset,
                    "output_dataset": output_dataset.strip(),
                    "group_by_columns": parse_csv_values(
                        group_by_text
                    ),
                    "aggregate_expressions": (
                        aggregate_expressions
                    ),
                },
            )

            st.rerun()


def render_union_form() -> None:
    datasets = get_available_datasets()

    if len(datasets) < 2:
        st.warning(
            "A union requires at least two available datasets."
        )
        return

    with st.form("union_component_form"):
        left_dataset = st.selectbox(
            "First dataset",
            options=datasets,
            key="union_left",
        )

        right_dataset = st.selectbox(
            "Second dataset",
            options=datasets,
            index=1,
            key="union_right",
        )

        union_all = st.checkbox(
            "Use UNION ALL",
            value=True,
        )

        output_dataset = st.text_input(
            "Output dataset",
            value="unioned_data",
        )

        submitted = st.form_submit_button(
            "Add Union",
            use_container_width=True,
        )

        if submitted:
            add_component(
                "Union",
                {
                    "left_dataset": left_dataset,
                    "right_dataset": right_dataset,
                    "union_all": union_all,
                    "output_dataset": output_dataset.strip(),
                },
            )

            st.rerun()


def render_custom_code_form() -> None:
    with st.form("custom_component_form"):
        block_name = st.text_input(
            "Block name",
            value="Custom transformation",
        )

        custom_code = st.text_area(
            "Custom SCOPE code",
            value=(
                "custom_data =\n"
                "    SELECT *\n"
                "    FROM source_data;"
            ),
            height=220,
        )

        submitted = st.form_submit_button(
            "Add Custom Code",
            use_container_width=True,
        )

        if submitted:
            add_component(
                "Custom Code",
                {
                    "block_name": block_name.strip(),
                    "custom_code": custom_code,
                },
            )

            st.rerun()


def render_write_form() -> None:
    datasets = get_available_datasets()

    if not datasets:
        st.warning(
            "Add a dataset-producing component first."
        )
        return

    with st.form("write_component_form"):
        source_dataset = st.selectbox(
            "Dataset to write",
            options=datasets,
        )

        output_path = st.text_input(
            "Output path",
            value="/data/processed/output/result.csv",
        )

        outputter = st.text_input(
            "Outputter",
            value="DefaultTextOutputter",
        )

        delimiter = st.selectbox(
            "Output delimiter",
            options=[",", "|", "\\t", ";"],
        )

        include_header = st.checkbox(
            "Include output header",
            value=True,
        )

        submitted = st.form_submit_button(
            "Add Write File",
            use_container_width=True,
        )

        if submitted:
            add_component(
                "Write File",
                {
                    "source_dataset": source_dataset,
                    "output_path": output_path.strip(),
                    "outputter": outputter.strip(),
                    "delimiter": delimiter,
                    "include_header": include_header,
                },
            )

            st.rerun()


def render_component_form(
    selected_component_type: str,
) -> None:
    if selected_component_type == "Declare Variable":
        render_declare_form()

    elif selected_component_type == "Read File":
        render_read_form()

    elif selected_component_type == "Select Columns":
        render_select_form()

    elif selected_component_type == "Filter":
        render_filter_form()

    elif selected_component_type == "Join":
        render_join_form()

    elif selected_component_type == "Aggregate":
        render_aggregate_form()

    elif selected_component_type == "Union":
        render_union_form()

    elif selected_component_type == "Custom Code":
        render_custom_code_form()

    elif selected_component_type == "Write File":
        render_write_form()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("SCOPE Studio")

    st.caption(
        "Build a script by adding reusable components."
    )

    st.markdown("### Component library")

    selected_component_type = st.selectbox(
        "Choose component",
        options=COMPONENT_TYPES,
    )

    render_component_form(selected_component_type)

    st.divider()

    if st.button(
        "Clear entire workflow",
        use_container_width=True,
    ):
        st.session_state.components = []
        st.session_state.generated_script = ""
        st.rerun()


# ============================================================
# MAIN HEADER
# ============================================================

st.title("⚙️ SCOPE Engineering Studio")

st.caption(
    "Create a workflow using read, transformation, join, "
    "variable, custom-code, and write components."
)

job_column, environment_column = st.columns(
    [2, 1]
)

with job_column:
    job_name = st.text_input(
        "Job name",
        value="CustomerUsagePipeline",
    )

with environment_column:
    environment = st.selectbox(
        "Environment",
        options=["DEV", "TEST", "PROD"],
    )


workflow_tab, script_tab, config_tab = st.tabs(
    [
        "Workflow Builder",
        "Generated Script",
        "Workflow JSON",
    ]
)


# ============================================================
# WORKFLOW TAB
# ============================================================

with workflow_tab:
    st.subheader("Workflow components")

    if not st.session_state.components:
        st.info(
            "Choose a component from the sidebar and add it "
            "to begin building the workflow."
        )

        st.code(
            """
Example workflow

1. Declare Variable
2. Read File — customer_data
3. Read File — product_data
4. Join — customer_data + product_data
5. Filter — active records
6. Aggregate — total usage
7. Write File — processed output
            """,
            language="text",
        )

    for index, component in enumerate(
        st.session_state.components
    ):
        with st.container(border=True):
            header_column, button_column = st.columns(
                [4, 1]
            )

            with header_column:
                st.markdown(
                    f"### {index + 1}. "
                    f"{component_title(component)}"
                )

                st.caption(
                    f"Component type: {component['type']}"
                )

            with button_column:
                move_up_column, move_down_column, delete_column = (
                    st.columns(3)
                )

                with move_up_column:
                    if st.button(
                        "↑",
                        key=f"up_{component['id']}",
                        disabled=index == 0,
                        help="Move component up",
                    ):
                        move_component_up(index)
                        st.rerun()

                with move_down_column:
                    if st.button(
                        "↓",
                        key=f"down_{component['id']}",
                        disabled=(
                            index
                            == len(
                                st.session_state.components
                            )
                            - 1
                        ),
                        help="Move component down",
                    ):
                        move_component_down(index)
                        st.rerun()

                with delete_column:
                    if st.button(
                        "✕",
                        key=f"delete_{component['id']}",
                        help="Delete component",
                    ):
                        delete_component(index)
                        st.rerun()

            st.json(component["config"])

    st.divider()

    validation = validate_workflow(
        st.session_state.components
    )

    validation_column, generation_column = st.columns(
        [1, 1]
    )

    with validation_column:
        st.subheader("Workflow validation")

        if validation["is_valid"]:
            st.success("Workflow configuration is valid.")
        else:
            st.error("Workflow contains validation errors.")

        for check in validation["checks"]:
            st.write(f"✅ {check}")

        for warning in validation["warnings"]:
            st.write(f"⚠️ {warning}")

        for error in validation["errors"]:
            st.write(f"❌ {error}")

    with generation_column:
        st.subheader("Generate output")

        if st.button(
            "Generate SCOPE Script",
            type="primary",
            use_container_width=True,
            disabled=not validation["is_valid"],
        ):
            st.session_state.generated_script = (
                generate_scope_script(
                    job_name=job_name.strip(),
                    environment=environment,
                    components=st.session_state.components,
                )
            )

            st.success(
                "SCOPE script generated successfully."
            )


# ============================================================
# SCRIPT TAB
# ============================================================

with script_tab:
    if st.session_state.generated_script:
        st.success(
            "Review the generated script before execution."
        )

        st.code(
            st.session_state.generated_script,
            language="sql",
            line_numbers=True,
        )

        safe_job_name = sanitize_name(job_name)

        st.download_button(
            label="Download .scope script",
            data=st.session_state.generated_script,
            file_name=f"{safe_job_name}.scope",
            mime="text/plain",
            use_container_width=True,
        )

        st.warning(
            "This application generates conceptual SCOPE "
            "syntax. Confirm the exact extractor, outputter, "
            "join, union, and declaration syntax supported by "
            "your internal environment."
        )

    else:
        st.info(
            "Build a valid workflow and select "
            "'Generate SCOPE Script'."
        )


# ============================================================
# CONFIGURATION TAB
# ============================================================

with config_tab:
    workflow_configuration = {
        "job_name": job_name,
        "environment": environment,
        "components": st.session_state.components,
    }

    st.json(workflow_configuration)

    safe_job_name = sanitize_name(job_name)

    st.download_button(
        label="Download workflow JSON",
        data=json.dumps(
            workflow_configuration,
            indent=2,
        ),
        file_name=f"{safe_job_name}_workflow.json",
        mime="application/json",
        use_container_width=True,
    )
