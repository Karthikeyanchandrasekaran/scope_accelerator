import copy
from typing import Any

import streamlit as st

from components import COMPONENT_TYPES


def initialize_state() -> None:
    defaults = {
        "components": [],
        "component_counter": 1,
        "generated_script": "",
        "job_name": "CustomerUsagePipeline",
        "environment": "DEV",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_component(
    component_type: str,
    config: dict[str, Any],
) -> None:
    st.session_state.components.append(
        {
            "id": (
                st.session_state.component_counter
            ),
            "type": component_type,
            "config": copy.deepcopy(config),
        }
    )

    st.session_state.component_counter += 1
    st.session_state.generated_script = ""


def update_component(
    index: int,
    config: dict[str, Any],
) -> None:
    st.session_state.components[index][
        "config"
    ] = copy.deepcopy(config)

    st.session_state.generated_script = ""


def delete_component(
    index: int,
) -> None:
    st.session_state.components.pop(index)
    st.session_state.generated_script = ""


def move_component(
    index: int,
    direction: int,
) -> None:
    target_index = index + direction

    components = st.session_state.components

    if 0 <= target_index < len(components):
        components[index], components[target_index] = (
            components[target_index],
            components[index],
        )

        st.session_state.generated_script = ""


def get_available_datasets() -> list[str]:
    datasets: list[str] = []

    output_fields = {
        "Read File": "dataset_name",
        "Select Columns": "output_dataset",
        "Filter": "output_dataset",
        "Join": "output_dataset",
        "Aggregate": "output_dataset",
        "Union": "output_dataset",
    }

    for component in st.session_state.components:
        field = output_fields.get(
            component["type"]
        )

        if not field:
            continue

        dataset = component["config"].get(
            field
        )

        if dataset and dataset not in datasets:
            datasets.append(dataset)

    return datasets


def export_workflow() -> dict[str, Any]:
    return {
        "job_name": st.session_state.job_name,
        "environment": (
            st.session_state.environment
        ),
        "components": copy.deepcopy(
            st.session_state.components
        ),
    }


def load_workflow(
    workflow_data: dict[str, Any],
) -> tuple[bool, str]:
    if not isinstance(workflow_data, dict):
        return False, "Workflow must be a JSON object."

    components = workflow_data.get(
        "components"
    )

    if not isinstance(components, list):
        return False, "Workflow must contain components."

    for index, component in enumerate(
        components,
        start=1,
    ):
        if not isinstance(component, dict):
            return (
                False,
                f"Component {index} is invalid.",
            )

        if component.get("type") not in COMPONENT_TYPES:
            return (
                False,
                f"Unsupported component type at "
                f"position {index}.",
            )

        if not isinstance(
            component.get("config"),
            dict,
        ):
            return (
                False,
                f"Component {index} has no config.",
            )

    restored = []
    highest_id = 0

    for index, component in enumerate(
        components,
        start=1,
    ):
        component_id = component.get(
            "id",
            index,
        )

        try:
            component_id = int(component_id)
        except (TypeError, ValueError):
            component_id = index

        highest_id = max(
            highest_id,
            component_id,
        )

        restored.append(
            {
                "id": component_id,
                "type": component["type"],
                "config": copy.deepcopy(
                    component["config"]
                ),
            }
        )

    environment = workflow_data.get(
        "environment",
        "DEV",
    )

    if environment not in {
        "DEV",
        "TEST",
        "PROD",
    }:
        environment = "DEV"

    st.session_state.components = restored
    st.session_state.component_counter = (
        highest_id + 1
    )

    st.session_state.job_name = str(
        workflow_data.get(
            "job_name",
            "RestoredWorkflow",
        )
    )

    st.session_state.environment = environment
    st.session_state.generated_script = ""

from typing import Any


def get_dataset_schemas() -> dict[str, list[str]]:
    """
    Build a dictionary containing the known columns
    for every dataset produced by the workflow.
    """
    dataset_schemas: dict[str, list[str]] = {}

    for component in st.session_state.components:
        component_type = component["type"]
        config = component["config"]

        if component_type == "Read File":
            dataset_name = config.get(
                "dataset_name",
                "",
            )

            schema = config.get(
                "schema",
                [],
            )

            columns = [
                column.get("name", "").strip()
                for column in schema
                if column.get("name", "").strip()
            ]

            if dataset_name:
                dataset_schemas[dataset_name] = columns

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

            if output_dataset:
                dataset_schemas[output_dataset] = (
                    selected_columns
                )

        elif component_type == "Filter":
            source_dataset = config.get(
                "source_dataset",
                "",
            )

            output_dataset = config.get(
                "output_dataset",
                "",
            )

            if output_dataset:
                dataset_schemas[output_dataset] = list(
                    dataset_schemas.get(
                        source_dataset,
                        [],
                    )
                )

        elif component_type == "Join":
            output_dataset = config.get(
                "output_dataset",
                "",
            )

            selected_columns = config.get(
                "selected_column_names",
                [],
            )

            if output_dataset:
                dataset_schemas[output_dataset] = (
                    selected_columns
                )

        elif component_type == "Aggregate":
            output_dataset = config.get(
                "output_dataset",
                "",
            )

            group_by_columns = config.get(
                "group_by_columns",
                [],
            )

            aggregate_aliases = config.get(
                "aggregate_aliases",
                [],
            )

            if output_dataset:
                dataset_schemas[output_dataset] = (
                    group_by_columns
                    + aggregate_aliases
                )

        elif component_type == "Union":
            left_dataset = config.get(
                "left_dataset",
                "",
            )

            output_dataset = config.get(
                "output_dataset",
                "",
            )

            if output_dataset:
                dataset_schemas[output_dataset] = list(
                    dataset_schemas.get(
                        left_dataset,
                        [],
                    )
                )

    return dataset_schemas


def get_dataset_columns(
    dataset_name: str,
) -> list[str]:
    """
    Return known columns for one dataset.
    """
    schemas = get_dataset_schemas()

    return schemas.get(
        dataset_name,
        [],
    )

    return (
        True,
        f"Loaded {len(restored)} components.",
    )
