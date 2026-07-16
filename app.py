import copy
import json
import re
from typing import Any

import streamlit as st

from components import (
    COMPONENT_TYPES,
    DATA_TYPES,
    JOIN_SOURCE_TYPES,
    JOIN_TYPES,
    create_default_config,
)
from renderer import generate_scope_script
from templates import WORKFLOW_TEMPLATES
from validators import validate_workflow
from workflow import (
    add_component,
    delete_component,
    export_workflow,
    get_available_datasets,
    get_dataset_columns,
    get_dataset_schemas,
    initialize_state,
    load_workflow,
    move_component,
    update_component,
)

st.set_page_config(
    page_title="SCOPE Engineering Studio",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


initialize_state()


def sanitize_filename(
    value: str,
) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        value.strip(),
    )

    return cleaned.strip("_") or "scope_workflow"


def schema_to_text(
    schema: list[dict[str, str]],
) -> str:
    return "\n".join(
        f"{column.get('name', '')}:"
        f"{column.get('type', '')}"
        for column in schema
    )


def parse_schema(
    value: str,
) -> tuple[list[dict[str, str]], list[str]]:
    columns = []
    errors = []
    names = set()

    for line_number, raw_line in enumerate(
        value.splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line:
            continue

        if ":" not in line:
            errors.append(
                f"Line {line_number} must use "
                "ColumnName:DataType."
            )
            continue

        name, data_type = line.split(
            ":",
            maxsplit=1,
        )

        name = name.strip()
        data_type = data_type.strip()

        if not name or not data_type:
            errors.append(
                f"Invalid schema on line "
                f"{line_number}."
            )
            continue

        if name in names:
            errors.append(
                f"Duplicate column: {name}"
            )
            continue

        names.add(name)

        columns.append(
            {
                "name": name,
                "type": data_type,
            }
        )

    return columns, errors


def parse_csv(
    value: str,
) -> list[str]:
    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def component_title(
    component: dict[str, Any],
) -> str:
    component_type = component["type"]
    config = component["config"]

    output_names = {
        "Read File": "dataset_name",
        "Select Columns": "output_dataset",
        "Filter": "output_dataset",
        "Join": "output_dataset",
        "Aggregate": "output_dataset",
        "Union": "output_dataset",
        "Write File": "source_dataset",
    }

    field = output_names.get(
        component_type
    )

    if field:
        return (
            f"{component_type}: "
            f"{config.get(field, '?')}"
        )

    if component_type == "Declare Variable":
        return (
            f"Declare Variable: "
            f"{config.get('variable_name', '?')}"
        )

    return component_type


def render_component_editor(
    component: dict[str, Any],
    index: int,
) -> None:
    component_type = component["type"]
    config = component["config"]
    component_id = component["id"]

    with st.expander(
        "Edit component parameters"
    ):
        with st.form(
            f"edit_component_{component_id}"
        ):
            updated_config = copy.deepcopy(
                config
            )

            if component_type == "Declare Variable":
                updated_config["variable_name"] = (
                    st.text_input(
                        "Variable name",
                        value=config.get(
                            "variable_name",
                            "",
                        ),
                    ).strip()
                )

                current_type = config.get(
                    "variable_type",
                    "string",
                )

                updated_config["variable_type"] = (
                    st.selectbox(
                        "Variable type",
                        DATA_TYPES,
                        index=(
                            DATA_TYPES.index(
                                current_type
                            )
                            if current_type
                            in DATA_TYPES
                            else 0
                        ),
                    )
                )

                updated_config["variable_value"] = (
                    st.text_input(
                        "Variable value",
                        value=str(
                            config.get(
                                "variable_value",
                                "",
                            )
                        ),
                    )
                )

                updated_config["quote_value"] = (
                    st.checkbox(
                        "Wrap value in quotes",
                        value=config.get(
                            "quote_value",
                            True,
                        ),
                    )
                )

            elif component_type == "Read File":
                updated_config["dataset_name"] = (
                    st.text_input(
                        "Dataset name",
                        value=config.get(
                            "dataset_name",
                            "",
                        ),
                    ).strip()
                )

                updated_config["input_path"] = (
                    st.text_input(
                        "Input path",
                        value=config.get(
                            "input_path",
                            "",
                        ),
                    ).strip()
                )

                updated_config["extractor"] = (
                    st.text_input(
                        "Extractor",
                        value=config.get(
                            "extractor",
                            "DefaultTextExtractor",
                        ),
                    ).strip()
                )

                updated_config["delimiter"] = (
                    st.selectbox(
                        "Delimiter",
                        [",", "|", "\\t", ";"],
                        index=0,
                    )
                )

                updated_config["skip_header"] = (
                    st.checkbox(
                        "Skip header",
                        value=config.get(
                            "skip_header",
                            True,
                        ),
                    )
                )

                schema_text = st.text_area(
                    "Schema",
                    value=schema_to_text(
                        config.get("schema", [])
                    ),
                    height=180,
                )

                schema, schema_errors = (
                    parse_schema(schema_text)
                )

                for error in schema_errors:
                    st.error(error)

                updated_config["schema"] = schema

            elif component_type == "Join":
                st.markdown("#### Left source")
            
                available_datasets = (
                    get_available_datasets()
                )
            
                left_source_type = config.get(
                    "left_source_type",
                    "Dataset",
                )
            
                updated_config[
                    "left_source_type"
                ] = st.selectbox(
                    "Left source type",
                    JOIN_SOURCE_TYPES,
                    index=(
                        JOIN_SOURCE_TYPES.index(
                            left_source_type
                        )
                        if left_source_type
                        in JOIN_SOURCE_TYPES
                        else 0
                    ),
                    key=f"left_source_type_{component_id}",
                )
            
                left_columns: list[str] = []
            
                if (
                    updated_config["left_source_type"]
                    == "Dataset"
                ):
                    current_left_dataset = config.get(
                        "left_dataset",
                        "",
                    )
            
                    if (
                        current_left_dataset
                        not in available_datasets
                        and available_datasets
                    ):
                        current_left_dataset = (
                            available_datasets[0]
                        )
            
                    updated_config[
                        "left_dataset"
                    ] = st.selectbox(
                        "Left dataset",
                        options=(
                            available_datasets
                            if available_datasets
                            else [""]
                        ),
                        index=(
                            available_datasets.index(
                                current_left_dataset
                            )
                            if current_left_dataset
                            in available_datasets
                            else 0
                        ),
                        key=f"left_dataset_{component_id}",
                    )
            
                    left_columns = get_dataset_columns(
                        updated_config["left_dataset"]
                    )
            
                else:
                    updated_config[
                        "left_subquery"
                    ] = st.text_area(
                        "Left subquery",
                        value=config.get(
                            "left_subquery",
                            "",
                        ),
                        height=180,
                        key=f"left_subquery_{component_id}",
                    )
            
                    left_subquery_columns_text = (
                        st.text_input(
                            "Left subquery output columns",
                            value=", ".join(
                                config.get(
                                    "left_subquery_columns",
                                    [],
                                )
                            ),
                            help=(
                                "Enter the columns returned by "
                                "the subquery."
                            ),
                            key=(
                                f"left_subquery_columns_"
                                f"{component_id}"
                            ),
                        )
                    )
            
                    left_columns = parse_csv(
                        left_subquery_columns_text
                    )
            
                    updated_config[
                        "left_subquery_columns"
                    ] = left_columns
            
                updated_config[
                    "left_alias"
                ] = st.text_input(
                    "Left alias",
                    value=config.get(
                        "left_alias",
                        "left_data",
                    ),
                    key=f"left_alias_{component_id}",
                ).strip()
            
                st.markdown("#### Right source")
            
                right_source_type = config.get(
                    "right_source_type",
                    "Dataset",
                )
            
                updated_config[
                    "right_source_type"
                ] = st.selectbox(
                    "Right source type",
                    JOIN_SOURCE_TYPES,
                    index=(
                        JOIN_SOURCE_TYPES.index(
                            right_source_type
                        )
                        if right_source_type
                        in JOIN_SOURCE_TYPES
                        else 0
                    ),
                    key=f"right_source_type_{component_id}",
                )
            
                right_columns: list[str] = []
            
                if (
                    updated_config["right_source_type"]
                    == "Dataset"
                ):
                    current_right_dataset = config.get(
                        "right_dataset",
                        "",
                    )
            
                    if (
                        current_right_dataset
                        not in available_datasets
                        and available_datasets
                    ):
                        current_right_dataset = (
                            available_datasets[-1]
                        )
            
                    updated_config[
                        "right_dataset"
                    ] = st.selectbox(
                        "Right dataset",
                        options=(
                            available_datasets
                            if available_datasets
                            else [""]
                        ),
                        index=(
                            available_datasets.index(
                                current_right_dataset
                            )
                            if current_right_dataset
                            in available_datasets
                            else 0
                        ),
                        key=f"right_dataset_{component_id}",
                    )
            
                    right_columns = get_dataset_columns(
                        updated_config["right_dataset"]
                    )
            
                else:
                    updated_config[
                        "right_subquery"
                    ] = st.text_area(
                        "Right subquery",
                        value=config.get(
                            "right_subquery",
                            "",
                        ),
                        height=180,
                        key=f"right_subquery_{component_id}",
                    )
            
                    right_subquery_columns_text = (
                        st.text_input(
                            "Right subquery output columns",
                            value=", ".join(
                                config.get(
                                    "right_subquery_columns",
                                    [],
                                )
                            ),
                            help=(
                                "Enter the columns returned by "
                                "the subquery."
                            ),
                            key=(
                                f"right_subquery_columns_"
                                f"{component_id}"
                            ),
                        )
                    )
            
                    right_columns = parse_csv(
                        right_subquery_columns_text
                    )
            
                    updated_config[
                        "right_subquery_columns"
                    ] = right_columns
            
                updated_config[
                    "right_alias"
                ] = st.text_input(
                    "Right alias",
                    value=config.get(
                        "right_alias",
                        "right_data",
                    ),
                    key=f"right_alias_{component_id}",
                ).strip()
            
                current_join_type = config.get(
                    "join_type",
                    "INNER",
                )
            
                updated_config[
                    "join_type"
                ] = st.selectbox(
                    "Join type",
                    JOIN_TYPES,
                    index=(
                        JOIN_TYPES.index(
                            current_join_type
                        )
                        if current_join_type
                        in JOIN_TYPES
                        else 0
                    ),
                    key=f"join_type_{component_id}",
                )
            
                updated_config[
                    "join_condition"
                ] = st.text_area(
                    "Join condition",
                    value=config.get(
                        "join_condition",
                        "",
                    ),
                    key=f"join_condition_{component_id}",
                ).strip()
            
                left_alias = updated_config[
                    "left_alias"
                ]
            
                right_alias = updated_config[
                    "right_alias"
                ]
            
                selectable_columns = [
                    f"{left_alias}.{column}"
                    for column in left_columns
                ] + [
                    f"{right_alias}.{column}"
                    for column in right_columns
                ]
            
                previously_selected = config.get(
                    "selected_columns",
                    [],
                )
            
                if isinstance(
                    previously_selected,
                    str,
                ):
                    previously_selected = parse_csv(
                        previously_selected.replace(
                            "\n",
                            ",",
                        )
                    )
            
                valid_defaults = [
                    column
                    for column in previously_selected
                    if column in selectable_columns
                ]
            
                selected_columns = st.multiselect(
                    "Columns to include after join",
                    options=selectable_columns,
                    default=valid_defaults,
                    help=(
                        "Columns are derived from the schemas "
                        "of the selected datasets."
                    ),
                    key=f"join_selected_columns_{component_id}",
                )
            
                updated_config[
                    "selected_columns"
                ] = selected_columns
            
                updated_config[
                    "selected_column_names"
                ] = [
                    column.split(".", maxsplit=1)[-1]
                    for column in selected_columns
                ]
            
                updated_config[
                    "output_dataset"
                ] = st.text_input(
                    "Output dataset",
                    value=config.get(
                        "output_dataset",
                        "joined_data",
                    ),
                    key=f"join_output_{component_id}",
                ).strip()
            elif component_type == "Filter":
                updated_config[
                    "source_dataset"
                ] = st.text_input(
                    "Source dataset",
                    value=config.get(
                        "source_dataset",
                        "",
                    ),
                ).strip()

                updated_config[
                    "output_dataset"
                ] = st.text_input(
                    "Output dataset",
                    value=config.get(
                        "output_dataset",
                        "",
                    ),
                ).strip()

                updated_config[
                    "condition"
                ] = st.text_area(
                    "Filter condition",
                    value=config.get(
                        "condition",
                        "",
                    ),
                ).strip()

            elif component_type == "Select Columns":
                updated_config[
                    "source_dataset"
                ] = st.text_input(
                    "Source dataset",
                    value=config.get(
                        "source_dataset",
                        "",
                    ),
                ).strip()

                updated_config[
                    "output_dataset"
                ] = st.text_input(
                    "Output dataset",
                    value=config.get(
                        "output_dataset",
                        "",
                    ),
                ).strip()

                updated_config[
                    "columns"
                ] = parse_csv(
                    st.text_area(
                        "Columns",
                        value=", ".join(
                            config.get(
                                "columns",
                                [],
                            )
                        ),
                    )
                )

            elif component_type == "Aggregate":
                updated_config[
                    "source_dataset"
                ] = st.text_input(
                    "Source dataset",
                    value=config.get(
                        "source_dataset",
                        "",
                    ),
                ).strip()

                updated_config[
                    "output_dataset"
                ] = st.text_input(
                    "Output dataset",
                    value=config.get(
                        "output_dataset",
                        "",
                    ),
                ).strip()

                updated_config[
                    "group_by_columns"
                ] = parse_csv(
                    st.text_input(
                        "Group-by columns",
                        value=", ".join(
                            config.get(
                                "group_by_columns",
                                [],
                            )
                        ),
                    )
                )

                aggregate_text = st.text_area(
                    "Aggregate expressions",
                    value="\n".join(
                        config.get(
                            "aggregate_expressions",
                            [],
                        )
                    ),
                )

                updated_config[
                    "aggregate_expressions"
                ] = [
                    line.strip()
                    for line
                    in aggregate_text.splitlines()
                    if line.strip()
                ]

            elif component_type == "Union":
                updated_config[
                    "left_dataset"
                ] = st.text_input(
                    "First dataset",
                    value=config.get(
                        "left_dataset",
                        "",
                    ),
                ).strip()

                updated_config[
                    "right_dataset"
                ] = st.text_input(
                    "Second dataset",
                    value=config.get(
                        "right_dataset",
                        "",
                    ),
                ).strip()

                updated_config[
                    "union_all"
                ] = st.checkbox(
                    "Use UNION ALL",
                    value=config.get(
                        "union_all",
                        True,
                    ),
                )

                updated_config[
                    "output_dataset"
                ] = st.text_input(
                    "Output dataset",
                    value=config.get(
                        "output_dataset",
                        "",
                    ),
                ).strip()

            elif component_type == "Write File":
                updated_config[
                    "source_dataset"
                ] = st.text_input(
                    "Source dataset",
                    value=config.get(
                        "source_dataset",
                        "",
                    ),
                ).strip()

                updated_config[
                    "output_path"
                ] = st.text_input(
                    "Output path",
                    value=config.get(
                        "output_path",
                        "",
                    ),
                ).strip()

                updated_config[
                    "outputter"
                ] = st.text_input(
                    "Outputter",
                    value=config.get(
                        "outputter",
                        "DefaultTextOutputter",
                    ),
                ).strip()

                updated_config[
                    "delimiter"
                ] = st.selectbox(
                    "Delimiter",
                    [",", "|", "\\t", ";"],
                )

                updated_config[
                    "include_header"
                ] = st.checkbox(
                    "Include header",
                    value=config.get(
                        "include_header",
                        True,
                    ),
                )

            elif component_type == "Custom Code":
                updated_config[
                    "block_name"
                ] = st.text_input(
                    "Block name",
                    value=config.get(
                        "block_name",
                        "",
                    ),
                ).strip()

                updated_config[
                    "custom_code"
                ] = st.text_area(
                    "Custom code",
                    value=config.get(
                        "custom_code",
                        "",
                    ),
                    height=220,
                )

            save = st.form_submit_button(
                "Save changes",
                type="primary",
                use_container_width=True,
            )

            if save:
                update_component(
                    index,
                    updated_config,
                )

                st.rerun()
def escape_mermaid_text(value: str) -> str:
    """
    Clean text before using it inside Mermaid labels.
    """
    return (
        str(value)
        .replace('"', "'")
        .replace("\n", " ")
        .replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
    )


def generate_data_flow_mermaid(
    components: list[dict[str, Any]],
) -> str:
    """
    Generate a Mermaid data-flow diagram from workflow metadata.
    """
    if not components:
        return """
flowchart LR
    empty["No workflow components configured"]
"""

    lines: list[str] = ["flowchart LR"]

    # Keeps track of which component produced each dataset.
    dataset_producers: dict[str, str] = {}

    # Variable nodes are connected to the first processing step.
    declaration_nodes: list[str] = []

    # Used for styling.
    read_nodes: list[str] = []
    transform_nodes: list[str] = []
    join_nodes: list[str] = []
    write_nodes: list[str] = []
    missing_nodes: list[str] = []

    for index, component in enumerate(
        components,
        start=1,
    ):
        component_id = component.get("id", index)
        component_type = component.get("type", "Unknown")
        config = component.get("config", {})

        node_id = f"step_{component_id}"

        if component_type == "Declare Variable":
            variable_name = escape_mermaid_text(
                config.get("variable_name", "Variable")
            )

            variable_value = escape_mermaid_text(
                config.get("variable_value", "")
            )

            lines.append(
                f'    {node_id}["Declare Variable<br/>'
                f'{variable_name} = {variable_value}"]'
            )

            declaration_nodes.append(node_id)
            transform_nodes.append(node_id)

        elif component_type == "Read File":
            dataset_name = config.get(
                "dataset_name",
                "dataset",
            )

            input_path = escape_mermaid_text(
                config.get("input_path", "")
            )

            lines.append(
                f'    {node_id}[("Read File<br/>'
                f'{escape_mermaid_text(dataset_name)}<br/>'
                f'{input_path}")]'
            )

            if dataset_name:
                dataset_producers[dataset_name] = node_id

            read_nodes.append(node_id)

        elif component_type == "Select Columns":
            source_dataset = config.get(
                "source_dataset",
                "",
            )

            output_dataset = config.get(
                "output_dataset",
                "",
            )

            selected_columns = config.get(
                "columns",
                [],
            )

            lines.append(
                f'    {node_id}["Select Columns<br/>'
                f'{escape_mermaid_text(output_dataset)}<br/>'
                f'{len(selected_columns)} columns"]'
            )

            source_node = dataset_producers.get(
                source_dataset
            )

            if source_node:
                lines.append(
                    f"    {source_node} --> "
                    f"|{escape_mermaid_text(source_dataset)}| "
                    f"{node_id}"
                )
            else:
                missing_id = f"missing_select_{component_id}"

                lines.append(
                    f'    {missing_id}["Missing dataset<br/>'
                    f'{escape_mermaid_text(source_dataset)}"]'
                )

                lines.append(
                    f"    {missing_id} -.-> {node_id}"
                )

                missing_nodes.append(missing_id)

            if output_dataset:
                dataset_producers[output_dataset] = node_id

            transform_nodes.append(node_id)

        elif component_type == "Filter":
            source_dataset = config.get(
                "source_dataset",
                "",
            )

            output_dataset = config.get(
                "output_dataset",
                "",
            )

            condition = escape_mermaid_text(
                config.get("condition", "")
            )

            if len(condition) > 55:
                condition = condition[:52] + "..."

            lines.append(
                f'    {node_id}{{"Filter<br/>'
                f'{escape_mermaid_text(output_dataset)}<br/>'
                f'{condition}"}}'
            )

            source_node = dataset_producers.get(
                source_dataset
            )

            if source_node:
                lines.append(
                    f"    {source_node} --> "
                    f"|{escape_mermaid_text(source_dataset)}| "
                    f"{node_id}"
                )
            else:
                missing_id = f"missing_filter_{component_id}"

                lines.append(
                    f'    {missing_id}["Missing dataset<br/>'
                    f'{escape_mermaid_text(source_dataset)}"]'
                )

                lines.append(
                    f"    {missing_id} -.-> {node_id}"
                )

                missing_nodes.append(missing_id)

            if output_dataset:
                dataset_producers[output_dataset] = node_id

            transform_nodes.append(node_id)

        elif component_type == "Join":
            output_dataset = config.get(
                "output_dataset",
                "",
            )

            join_type = escape_mermaid_text(
                config.get("join_type", "JOIN")
            )

            lines.append(
                f'    {node_id}{{"{join_type} Join<br/>'
                f'{escape_mermaid_text(output_dataset)}"}}'
            )

            left_source_type = config.get(
                "left_source_type",
                "Dataset",
            )

            right_source_type = config.get(
                "right_source_type",
                "Dataset",
            )

            # Left side
            if left_source_type == "Dataset":
                left_dataset = config.get(
                    "left_dataset",
                    "",
                )

                left_node = dataset_producers.get(
                    left_dataset
                )

                if left_node:
                    lines.append(
                        f"    {left_node} --> "
                        f"|Left: "
                        f"{escape_mermaid_text(left_dataset)}| "
                        f"{node_id}"
                    )
                else:
                    missing_left_id = (
                        f"missing_left_{component_id}"
                    )

                    lines.append(
                        f'    {missing_left_id}'
                        f'["Missing left dataset<br/>'
                        f'{escape_mermaid_text(left_dataset)}"]'
                    )

                    lines.append(
                        f"    {missing_left_id} -.-> {node_id}"
                    )

                    missing_nodes.append(
                        missing_left_id
                    )

            else:
                left_subquery_id = (
                    f"left_subquery_{component_id}"
                )

                left_alias = escape_mermaid_text(
                    config.get(
                        "left_alias",
                        "left_subquery",
                    )
                )

                lines.append(
                    f'    {left_subquery_id}'
                    f'["Left Subquery<br/>{left_alias}"]'
                )

                lines.append(
                    f"    {left_subquery_id} --> "
                    f"|Subquery| {node_id}"
                )

                transform_nodes.append(
                    left_subquery_id
                )

            # Right side
            if right_source_type == "Dataset":
                right_dataset = config.get(
                    "right_dataset",
                    "",
                )

                right_node = dataset_producers.get(
                    right_dataset
                )

                if right_node:
                    lines.append(
                        f"    {right_node} --> "
                        f"|Right: "
                        f"{escape_mermaid_text(right_dataset)}| "
                        f"{node_id}"
                    )
                else:
                    missing_right_id = (
                        f"missing_right_{component_id}"
                    )

                    lines.append(
                        f'    {missing_right_id}'
                        f'["Missing right dataset<br/>'
                        f'{escape_mermaid_text(right_dataset)}"]'
                    )

                    lines.append(
                        f"    {missing_right_id} -.-> {node_id}"
                    )

                    missing_nodes.append(
                        missing_right_id
                    )

            else:
                right_subquery_id = (
                    f"right_subquery_{component_id}"
                )

                right_alias = escape_mermaid_text(
                    config.get(
                        "right_alias",
                        "right_subquery",
                    )
                )

                lines.append(
                    f'    {right_subquery_id}'
                    f'["Right Subquery<br/>{right_alias}"]'
                )

                lines.append(
                    f"    {right_subquery_id} --> "
                    f"|Subquery| {node_id}"
                )

                transform_nodes.append(
                    right_subquery_id
                )

            if output_dataset:
                dataset_producers[output_dataset] = node_id

            join_nodes.append(node_id)

        elif component_type == "Aggregate":
            source_dataset = config.get(
                "source_dataset",
                "",
            )

            output_dataset = config.get(
                "output_dataset",
                "",
            )

            group_by_columns = config.get(
                "group_by_columns",
                [],
            )

            lines.append(
                f'    {node_id}["Aggregate<br/>'
                f'{escape_mermaid_text(output_dataset)}<br/>'
                f'{len(group_by_columns)} group keys"]'
            )

            source_node = dataset_producers.get(
                source_dataset
            )

            if source_node:
                lines.append(
                    f"    {source_node} --> "
                    f"|{escape_mermaid_text(source_dataset)}| "
                    f"{node_id}"
                )
            else:
                missing_id = (
                    f"missing_aggregate_{component_id}"
                )

                lines.append(
                    f'    {missing_id}["Missing dataset<br/>'
                    f'{escape_mermaid_text(source_dataset)}"]'
                )

                lines.append(
                    f"    {missing_id} -.-> {node_id}"
                )

                missing_nodes.append(missing_id)

            if output_dataset:
                dataset_producers[output_dataset] = node_id

            transform_nodes.append(node_id)

        elif component_type == "Union":
            left_dataset = config.get(
                "left_dataset",
                "",
            )

            right_dataset = config.get(
                "right_dataset",
                "",
            )

            output_dataset = config.get(
                "output_dataset",
                "",
            )

            union_type = (
                "UNION ALL"
                if config.get("union_all", True)
                else "UNION"
            )

            lines.append(
                f'    {node_id}{{"{union_type}<br/>'
                f'{escape_mermaid_text(output_dataset)}"}}'
            )

            left_node = dataset_producers.get(
                left_dataset
            )

            right_node = dataset_producers.get(
                right_dataset
            )

            if left_node:
                lines.append(
                    f"    {left_node} --> "
                    f"|{escape_mermaid_text(left_dataset)}| "
                    f"{node_id}"
                )

            if right_node:
                lines.append(
                    f"    {right_node} --> "
                    f"|{escape_mermaid_text(right_dataset)}| "
                    f"{node_id}"
                )

            if output_dataset:
                dataset_producers[output_dataset] = node_id

            transform_nodes.append(node_id)

        elif component_type == "Custom Code":
            block_name = escape_mermaid_text(
                config.get(
                    "block_name",
                    "Custom Code",
                )
            )

            lines.append(
                f'    {node_id}["Custom Code<br/>'
                f'{block_name}"]'
            )

            if index > 1:
                previous_component = components[index - 2]
                previous_id = previous_component.get(
                    "id",
                    index - 1,
                )

                lines.append(
                    f"    step_{previous_id} -.-> "
                    f"|Custom dependency| {node_id}"
                )

            transform_nodes.append(node_id)

        elif component_type == "Write File":
            source_dataset = config.get(
                "source_dataset",
                "",
            )

            output_path = escape_mermaid_text(
                config.get("output_path", "")
            )

            lines.append(
                f'    {node_id}[("Write File<br/>'
                f'{escape_mermaid_text(source_dataset)}<br/>'
                f'{output_path}")]'
            )

            source_node = dataset_producers.get(
                source_dataset
            )

            if source_node:
                lines.append(
                    f"    {source_node} --> "
                    f"|{escape_mermaid_text(source_dataset)}| "
                    f"{node_id}"
                )
            else:
                missing_id = (
                    f"missing_write_{component_id}"
                )

                lines.append(
                    f'    {missing_id}["Missing dataset<br/>'
                    f'{escape_mermaid_text(source_dataset)}"]'
                )

                lines.append(
                    f"    {missing_id} -.-> {node_id}"
                )

                missing_nodes.append(missing_id)

            write_nodes.append(node_id)

    # Connect variables to first non-variable component.
    first_processing_node = None

    for index, component in enumerate(
        components,
        start=1,
    ):
        if component.get("type") != "Declare Variable":
            first_processing_node = (
                f"step_{component.get('id', index)}"
            )
            break

    if first_processing_node:
        for declaration_node in declaration_nodes:
            lines.append(
                f"    {declaration_node} -.-> "
                f"|Parameter| {first_processing_node}"
            )

    # Mermaid styles.
    lines.extend(
        [
            "",
            "    classDef readNode "
            "fill:#e8f1ff,stroke:#4f81bd,stroke-width:1px;",
            "    classDef transformNode "
            "fill:#f3f4f6,stroke:#6b7280,stroke-width:1px;",
            "    classDef joinNode "
            "fill:#fff7e6,stroke:#d97706,stroke-width:2px;",
            "    classDef writeNode "
            "fill:#eaf7ee,stroke:#2e8b57,stroke-width:1px;",
            "    classDef missingNode "
            "fill:#fdecec,stroke:#c0392b,stroke-width:2px;",
        ]
    )

    if read_nodes:
        lines.append(
            "    class "
            + ",".join(read_nodes)
            + " readNode;"
        )

    if transform_nodes:
        lines.append(
            "    class "
            + ",".join(transform_nodes)
            + " transformNode;"
        )

    if join_nodes:
        lines.append(
            "    class "
            + ",".join(join_nodes)
            + " joinNode;"
        )

    if write_nodes:
        lines.append(
            "    class "
            + ",".join(write_nodes)
            + " writeNode;"
        )

    if missing_nodes:
        lines.append(
            "    class "
            + ",".join(missing_nodes)
            + " missingNode;"
        )

    return "\n".join(lines)

def build_dataset_lineage(
    components: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Build dataset-level lineage from workflow components.

    Each lineage record contains:
    - producing component
    - source datasets
    - consuming components
    - known schema
    - input/output path
    """
    lineage: dict[str, dict[str, Any]] = {}

    def ensure_dataset(dataset_name: str) -> None:
        if not dataset_name:
            return

        if dataset_name not in lineage:
            lineage[dataset_name] = {
                "dataset_name": dataset_name,
                "producer_type": "",
                "producer_step": None,
                "producer_label": "",
                "source_datasets": [],
                "consumers": [],
                "schema": [],
                "input_path": "",
                "output_paths": [],
            }

    for step_number, component in enumerate(
        components,
        start=1,
    ):
        component_type = component.get(
            "type",
            "Unknown",
        )

        config = component.get(
            "config",
            {},
        )

        component_id = component.get(
            "id",
            step_number,
        )

        component_label = (
            f"Step {step_number}: {component_type}"
        )

        if component_type == "Read File":
            dataset_name = config.get(
                "dataset_name",
                "",
            ).strip()

            ensure_dataset(dataset_name)

            if dataset_name:
                lineage[dataset_name].update(
                    {
                        "producer_type": "Read File",
                        "producer_step": step_number,
                        "producer_id": component_id,
                        "producer_label": component_label,
                        "source_datasets": [],
                        "schema": [
                            {
                                "name": column.get(
                                    "name",
                                    "",
                                ),
                                "type": column.get(
                                    "type",
                                    "",
                                ),
                            }
                            for column in config.get(
                                "schema",
                                [],
                            )
                            if column.get("name")
                        ],
                        "input_path": config.get(
                            "input_path",
                            "",
                        ),
                    }
                )

        elif component_type == "Select Columns":
            source_dataset = config.get(
                "source_dataset",
                "",
            ).strip()

            output_dataset = config.get(
                "output_dataset",
                "",
            ).strip()

            ensure_dataset(source_dataset)
            ensure_dataset(output_dataset)

            if source_dataset:
                lineage[source_dataset]["consumers"].append(
                    {
                        "step": step_number,
                        "component_id": component_id,
                        "component_type": component_type,
                        "output_dataset": output_dataset,
                    }
                )

            source_schema = lineage.get(
                source_dataset,
                {},
            ).get("schema", [])

            selected_columns = config.get(
                "columns",
                [],
            )

            selected_schema = [
                column
                for column in source_schema
                if column.get("name")
                in selected_columns
            ]

            if output_dataset:
                lineage[output_dataset].update(
                    {
                        "producer_type": component_type,
                        "producer_step": step_number,
                        "producer_id": component_id,
                        "producer_label": component_label,
                        "source_datasets": [
                            source_dataset
                        ],
                        "schema": selected_schema,
                    }
                )

        elif component_type == "Filter":
            source_dataset = config.get(
                "source_dataset",
                "",
            ).strip()

            output_dataset = config.get(
                "output_dataset",
                "",
            ).strip()

            ensure_dataset(source_dataset)
            ensure_dataset(output_dataset)

            if source_dataset:
                lineage[source_dataset]["consumers"].append(
                    {
                        "step": step_number,
                        "component_id": component_id,
                        "component_type": component_type,
                        "output_dataset": output_dataset,
                    }
                )

            if output_dataset:
                lineage[output_dataset].update(
                    {
                        "producer_type": component_type,
                        "producer_step": step_number,
                        "producer_id": component_id,
                        "producer_label": component_label,
                        "source_datasets": [
                            source_dataset
                        ],
                        "schema": list(
                            lineage.get(
                                source_dataset,
                                {},
                            ).get("schema", [])
                        ),
                    }
                )

        elif component_type == "Join":
            output_dataset = config.get(
                "output_dataset",
                "",
            ).strip()

            source_datasets: list[str] = []

            left_source_type = config.get(
                "left_source_type",
                "Dataset",
            )

            right_source_type = config.get(
                "right_source_type",
                "Dataset",
            )

            if left_source_type == "Dataset":
                left_dataset = config.get(
                    "left_dataset",
                    "",
                ).strip()

                if left_dataset:
                    source_datasets.append(
                        left_dataset
                    )
                    ensure_dataset(left_dataset)

                    lineage[left_dataset][
                        "consumers"
                    ].append(
                        {
                            "step": step_number,
                            "component_id": component_id,
                            "component_type": component_type,
                            "side": "Left",
                            "output_dataset": output_dataset,
                        }
                    )

            else:
                left_dataset = (
                    f"Subquery: "
                    f"{config.get('left_alias', 'left')}"
                )

                source_datasets.append(
                    left_dataset
                )

                ensure_dataset(left_dataset)

                lineage[left_dataset].update(
                    {
                        "producer_type": "Subquery",
                        "producer_step": step_number,
                        "producer_id": component_id,
                        "producer_label": (
                            f"{component_label} left subquery"
                        ),
                        "schema": [
                            {
                                "name": column,
                                "type": "Unknown",
                            }
                            for column in config.get(
                                "left_subquery_columns",
                                [],
                            )
                        ],
                    }
                )

                lineage[left_dataset][
                    "consumers"
                ].append(
                    {
                        "step": step_number,
                        "component_id": component_id,
                        "component_type": component_type,
                        "side": "Left",
                        "output_dataset": output_dataset,
                    }
                )

            if right_source_type == "Dataset":
                right_dataset = config.get(
                    "right_dataset",
                    "",
                ).strip()

                if right_dataset:
                    source_datasets.append(
                        right_dataset
                    )
                    ensure_dataset(right_dataset)

                    lineage[right_dataset][
                        "consumers"
                    ].append(
                        {
                            "step": step_number,
                            "component_id": component_id,
                            "component_type": component_type,
                            "side": "Right",
                            "output_dataset": output_dataset,
                        }
                    )

            else:
                right_dataset = (
                    f"Subquery: "
                    f"{config.get('right_alias', 'right')}"
                )

                source_datasets.append(
                    right_dataset
                )

                ensure_dataset(right_dataset)

                lineage[right_dataset].update(
                    {
                        "producer_type": "Subquery",
                        "producer_step": step_number,
                        "producer_id": component_id,
                        "producer_label": (
                            f"{component_label} right subquery"
                        ),
                        "schema": [
                            {
                                "name": column,
                                "type": "Unknown",
                            }
                            for column in config.get(
                                "right_subquery_columns",
                                [],
                            )
                        ],
                    }
                )

                lineage[right_dataset][
                    "consumers"
                ].append(
                    {
                        "step": step_number,
                        "component_id": component_id,
                        "component_type": component_type,
                        "side": "Right",
                        "output_dataset": output_dataset,
                    }
                )

            ensure_dataset(output_dataset)

            selected_column_names = config.get(
                "selected_column_names",
                [],
            )

            output_schema = [
                {
                    "name": column,
                    "type": "Unknown",
                }
                for column in selected_column_names
            ]

            if output_dataset:
                lineage[output_dataset].update(
                    {
                        "producer_type": component_type,
                        "producer_step": step_number,
                        "producer_id": component_id,
                        "producer_label": component_label,
                        "source_datasets": source_datasets,
                        "schema": output_schema,
                    }
                )

        elif component_type == "Aggregate":
            source_dataset = config.get(
                "source_dataset",
                "",
            ).strip()

            output_dataset = config.get(
                "output_dataset",
                "",
            ).strip()

            ensure_dataset(source_dataset)
            ensure_dataset(output_dataset)

            if source_dataset:
                lineage[source_dataset]["consumers"].append(
                    {
                        "step": step_number,
                        "component_id": component_id,
                        "component_type": component_type,
                        "output_dataset": output_dataset,
                    }
                )

            group_by_columns = config.get(
                "group_by_columns",
                [],
            )

            aggregate_expressions = config.get(
                "aggregate_expressions",
                [],
            )

            aggregate_columns: list[dict[str, str]] = []

            for expression in aggregate_expressions:
                upper_expression = expression.upper()

                if " AS " in upper_expression:
                    alias_position = (
                        upper_expression.rfind(
                            " AS "
                        )
                    )

                    alias = expression[
                        alias_position + 4:
                    ].strip()
                else:
                    alias = expression.strip()

                aggregate_columns.append(
                    {
                        "name": alias,
                        "type": "Derived",
                    }
                )

            group_schema = [
                column
                for column in lineage.get(
                    source_dataset,
                    {},
                ).get("schema", [])
                if column.get("name")
                in group_by_columns
            ]

            if output_dataset:
                lineage[output_dataset].update(
                    {
                        "producer_type": component_type,
                        "producer_step": step_number,
                        "producer_id": component_id,
                        "producer_label": component_label,
                        "source_datasets": [
                            source_dataset
                        ],
                        "schema": (
                            group_schema
                            + aggregate_columns
                        ),
                    }
                )

        elif component_type == "Union":
            left_dataset = config.get(
                "left_dataset",
                "",
            ).strip()

            right_dataset = config.get(
                "right_dataset",
                "",
            ).strip()

            output_dataset = config.get(
                "output_dataset",
                "",
            ).strip()

            ensure_dataset(left_dataset)
            ensure_dataset(right_dataset)
            ensure_dataset(output_dataset)

            for source_dataset in [
                left_dataset,
                right_dataset,
            ]:
                if source_dataset:
                    lineage[source_dataset][
                        "consumers"
                    ].append(
                        {
                            "step": step_number,
                            "component_id": component_id,
                            "component_type": component_type,
                            "output_dataset": output_dataset,
                        }
                    )

            if output_dataset:
                lineage[output_dataset].update(
                    {
                        "producer_type": component_type,
                        "producer_step": step_number,
                        "producer_id": component_id,
                        "producer_label": component_label,
                        "source_datasets": [
                            left_dataset,
                            right_dataset,
                        ],
                        "schema": list(
                            lineage.get(
                                left_dataset,
                                {},
                            ).get("schema", [])
                        ),
                    }
                )

        elif component_type == "Write File":
            source_dataset = config.get(
                "source_dataset",
                "",
            ).strip()

            ensure_dataset(source_dataset)

            if source_dataset:
                lineage[source_dataset]["consumers"].append(
                    {
                        "step": step_number,
                        "component_id": component_id,
                        "component_type": component_type,
                        "output_path": config.get(
                            "output_path",
                            "",
                        ),
                    }
                )

                output_path = config.get(
                    "output_path",
                    "",
                )

                if output_path:
                    lineage[source_dataset][
                        "output_paths"
                    ].append(output_path)

    return lineage
with st.sidebar:
    
    st.title("SCOPE Studio")

    selected_template = st.selectbox(
        "Template",
        [
            "Blank workflow",
            *WORKFLOW_TEMPLATES.keys(),
        ],
    )

    if st.button(
        "Load template",
        use_container_width=True,
    ):
        if selected_template == "Blank workflow":
            st.session_state.components = []
            st.session_state.component_counter = 1
            st.session_state.generated_script = ""
        else:
            load_workflow(
                copy.deepcopy(
                    WORKFLOW_TEMPLATES[
                        selected_template
                    ]
                )
            )

        st.rerun()

    uploaded_file = st.file_uploader(
        "Upload workflow JSON",
        type=["json"],
    )

    if uploaded_file is not None:
        if st.button(
            "Load uploaded workflow",
            use_container_width=True,
        ):
            try:
                data = json.load(
                    uploaded_file
                )

                success, message = load_workflow(
                    data
                )

                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

            except json.JSONDecodeError as error:
                st.error(
                    f"Invalid JSON: {error}"
                )

    st.divider()

    component_type = st.selectbox(
        "Add component",
        COMPONENT_TYPES,
    )

    if st.button(
        "Add selected component",
        type="primary",
        use_container_width=True,
    ):
        default_config = create_default_config(
            component_type
        )

        datasets = get_available_datasets()

        if component_type in {
            "Filter",
            "Select Columns",
            "Aggregate",
            "Write File",
        } and datasets:
            default_config[
                "source_dataset"
            ] = datasets[-1]

        if (
            component_type == "Join"
            and len(datasets) >= 2
        ):
            default_config[
                "left_dataset"
            ] = datasets[-2]

            default_config[
                "right_dataset"
            ] = datasets[-1]

        add_component(
            component_type,
            default_config,
        )

        st.rerun()

    if st.button(
        "Clear workflow",
        use_container_width=True,
    ):
        st.session_state.components = []
        st.session_state.component_counter = 1
        st.session_state.generated_script = ""
        st.rerun()


st.title("⚙️ SCOPE Engineering Studio")

job_column, environment_column = st.columns(
    [2, 1]
)

with job_column:
    st.text_input(
        "Job name",
        key="job_name",
    )

with environment_column:
    st.selectbox(
        "Environment",
        ["DEV", "TEST", "PROD"],
        key="environment",
    )


(
    workflow_tab,
    data_flow_tab,
    lineage_tab,
    script_tab,
    json_tab,
) = st.tabs(
    [
        "Workflow",
        "Data Flow",
        "Dataset Lineage",
        "Generated SCOPE",
        "Workflow JSON",
    ]
)


with workflow_tab:
    if not st.session_state.components:
        st.info(
            "Load a template or add a component."
        )

    for index, component in enumerate(
        st.session_state.components
    ):
        with st.container(border=True):
            title_column, action_column = (
                st.columns([5, 1])
            )

            with title_column:
                st.subheader(
                    f"{index + 1}. "
                    f"{component_title(component)}"
                )

            with action_column:
                up, down, delete = st.columns(3)

                with up:
                    if st.button(
                        "↑",
                        key=f"up_{component['id']}",
                        disabled=index == 0,
                    ):
                        move_component(index, -1)
                        st.rerun()

                with down:
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
                    ):
                        move_component(index, 1)
                        st.rerun()

                with delete:
                    if st.button(
                        "✕",
                        key=(
                            f"delete_"
                            f"{component['id']}"
                        ),
                    ):
                        delete_component(index)
                        st.rerun()

            st.json(component["config"])

            render_component_editor(
                component,
                index,
            )

    validation = validate_workflow(
        st.session_state.components
    )

    st.divider()
    st.subheader("Validation")

    if validation["is_valid"]:
        st.success("Workflow is valid.")
    else:
        st.error(
            "Workflow contains errors."
        )

    for check in validation["checks"]:
        st.write(f"✅ {check}")

    for warning in validation["warnings"]:
        st.write(f"⚠️ {warning}")

    for error in validation["errors"]:
        st.write(f"❌ {error}")

    if st.button(
        "Generate SCOPE script",
        type="primary",
        disabled=not validation["is_valid"],
    ):
        st.session_state.generated_script = (
            generate_scope_script(
                job_name=(
                    st.session_state.job_name
                ),
                environment=(
                    st.session_state.environment
                ),
                components=(
                    st.session_state.components
                ),
            )
        )

        st.success("Script generated.")

with data_flow_tab:
    st.subheader("Workflow Data Flow")

    st.caption(
        "The diagram is generated automatically from "
        "workflow components and dataset dependencies."
    )

    if not st.session_state.components:
        st.info(
            "Load a template or add workflow components "
            "to generate the data-flow diagram."
        )

    else:
        mermaid_definition = generate_data_flow_mermaid(
            st.session_state.components
        )

        try:
            st.mermaid_chart(
                mermaid_definition,
                width="stretch",
            )

        except Exception as error:
            st.error(
                "The Mermaid diagram could not be displayed."
            )

            st.exception(error)

        with st.expander(
            "View Mermaid diagram definition"
        ):
            st.code(
                mermaid_definition,
                language="text",
            )

        diagram_filename = sanitize_filename(
            st.session_state.job_name
        )

        st.download_button(
            label="Download data-flow definition",
            data=mermaid_definition,
            file_name=(
                f"{diagram_filename}_data_flow.mmd"
            ),
            mime="text/plain",
            use_container_width=True,
        )
with lineage_tab:
    st.subheader("Dataset Lineage")

    st.caption(
        "Explore which components create and consume "
        "each dataset in the workflow."
    )

    if not st.session_state.components:
        st.info(
            "Load a template or add workflow components "
            "to generate dataset lineage."
        )

    else:
        dataset_lineage = build_dataset_lineage(
            st.session_state.components
        )

        dataset_names = sorted(
            dataset_lineage.keys()
        )

        if not dataset_names:
            st.info(
                "No datasets were found in the workflow."
            )

        else:
            total_datasets = len(dataset_names)

            source_datasets = sum(
                1
                for dataset in dataset_lineage.values()
                if dataset.get("producer_type")
                in {"Read File", "Subquery"}
            )

            transformed_datasets = sum(
                1
                for dataset in dataset_lineage.values()
                if dataset.get("producer_type")
                in {
                    "Select Columns",
                    "Filter",
                    "Join",
                    "Aggregate",
                    "Union",
                }
            )

            output_datasets = sum(
                1
                for dataset in dataset_lineage.values()
                if dataset.get("output_paths")
            )

            metric_1, metric_2, metric_3, metric_4 = (
                st.columns(4)
            )

            with metric_1:
                st.metric(
                    "Total datasets",
                    total_datasets,
                )

            with metric_2:
                st.metric(
                    "Source datasets",
                    source_datasets,
                )

            with metric_3:
                st.metric(
                    "Derived datasets",
                    transformed_datasets,
                )

            with metric_4:
                st.metric(
                    "Written datasets",
                    output_datasets,
                )

            st.divider()

            selected_dataset = st.selectbox(
                "Select dataset",
                options=dataset_names,
            )

            lineage_record = dataset_lineage[
                selected_dataset
            ]

            detail_column, relation_column = (
                st.columns([1, 1])
            )

            with detail_column:
                st.markdown(
                    f"### {selected_dataset}"
                )

                producer_type = (
                    lineage_record.get(
                        "producer_type"
                    )
                    or "Unknown"
                )

                producer_step = (
                    lineage_record.get(
                        "producer_step"
                    )
                )

                st.write(
                    f"**Created by:** {producer_type}"
                )

                if producer_step is not None:
                    st.write(
                        f"**Producer step:** "
                        f"{producer_step}"
                    )

                input_path = lineage_record.get(
                    "input_path",
                    "",
                )

                if input_path:
                    st.write(
                        f"**Input path:** `{input_path}`"
                    )

                output_paths = lineage_record.get(
                    "output_paths",
                    [],
                )

                if output_paths:
                    st.write("**Output paths:**")

                    for output_path in output_paths:
                        st.code(
                            output_path,
                            language="text",
                        )

            with relation_column:
                st.markdown(
                    "### Relationships"
                )

                source_datasets = (
                    lineage_record.get(
                        "source_datasets",
                        [],
                    )
                )

                if source_datasets:
                    st.write("**Upstream datasets:**")

                    for source_dataset in source_datasets:
                        st.write(
                            f"⬆️ `{source_dataset}`"
                        )
                else:
                    st.write(
                        "**Upstream datasets:** None"
                    )

                consumers = lineage_record.get(
                    "consumers",
                    [],
                )

                if consumers:
                    st.write(
                        "**Downstream consumers:**"
                    )

                    for consumer in consumers:
                        consumer_type = consumer.get(
                            "component_type",
                            "Unknown",
                        )

                        consumer_step = consumer.get(
                            "step",
                            "?",
                        )

                        output_dataset = consumer.get(
                            "output_dataset",
                            "",
                        )

                        output_path = consumer.get(
                            "output_path",
                            "",
                        )

                        consumer_text = (
                            f"Step {consumer_step}: "
                            f"{consumer_type}"
                        )

                        if output_dataset:
                            consumer_text += (
                                f" → {output_dataset}"
                            )

                        if output_path:
                            consumer_text += (
                                f" → {output_path}"
                            )

                        st.write(
                            f"⬇️ {consumer_text}"
                        )

                else:
                    st.write(
                        "**Downstream consumers:** None"
                    )

            st.divider()

            st.markdown("### Dataset schema")

            schema = lineage_record.get(
                "schema",
                [],
            )

            if schema:
                st.dataframe(
                    schema,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "name": st.column_config.TextColumn(
                            "Column"
                        ),
                        "type": st.column_config.TextColumn(
                            "Data type"
                        ),
                    },
                )
            else:
                st.info(
                    "Schema information is not available "
                    "for this dataset."
                )

            st.divider()

            st.markdown("### Complete lineage inventory")

            lineage_rows: list[dict[str, Any]] = []

            for dataset_name in dataset_names:
                record = dataset_lineage[
                    dataset_name
                ]

                lineage_rows.append(
                    {
                        "Dataset": dataset_name,
                        "Created by": (
                            record.get(
                                "producer_type"
                            )
                            or "Unknown"
                        ),
                        "Producer step": (
                            record.get(
                                "producer_step"
                            )
                        ),
                        "Upstream datasets": ", ".join(
                            record.get(
                                "source_datasets",
                                [],
                            )
                        ),
                        "Consumer count": len(
                            record.get(
                                "consumers",
                                [],
                            )
                        ),
                        "Column count": len(
                            record.get(
                                "schema",
                                [],
                            )
                        ),
                        "Written": (
                            "Yes"
                            if record.get(
                                "output_paths"
                            )
                            else "No"
                        ),
                    }
                )

            st.dataframe(
                lineage_rows,
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                label="Download lineage JSON",
                data=json.dumps(
                    dataset_lineage,
                    indent=2,
                ),
                file_name=(
                    f"{sanitize_filename(st.session_state.job_name)}"
                    "_dataset_lineage.json"
                ),
                mime="application/json",
                use_container_width=True,
            )
            
with script_tab:
    if st.session_state.generated_script:
        st.code(
            st.session_state.generated_script,
            language="sql",
            line_numbers=True,
        )

        filename = sanitize_filename(
            st.session_state.job_name
        )

        st.download_button(
            "Download .scope",
            data=(
                st.session_state.generated_script
            ),
            file_name=f"{filename}.scope",
            mime="text/plain",
        )
    else:
        st.info(
            "Generate the workflow first."
        )


with json_tab:
    workflow_data = export_workflow()

    st.json(workflow_data)

    filename = sanitize_filename(
        st.session_state.job_name
    )

    st.download_button(
        "Download workflow JSON",
        data=json.dumps(
            workflow_data,
            indent=2,
        ),
        file_name=(
            f"{filename}_workflow.json"
        ),
        mime="application/json",
    )
