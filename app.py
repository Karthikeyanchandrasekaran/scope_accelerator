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


workflow_tab, script_tab, json_tab = st.tabs(
    [
        "Workflow",
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
