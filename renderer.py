from datetime import datetime
from typing import Any


def indent_text(
    text: str,
    spaces: int = 4,
) -> str:
    prefix = " " * spaces

    return "\n".join(
        f"{prefix}{line}" if line else ""
        for line in text.splitlines()
    )


def render_declare(
    config: dict[str, Any],
) -> str:
    value = str(
        config.get("variable_value", "")
    )

    if config.get("quote_value", True):
        value = f'"{value}"'

    return (
        f"#DECLARE "
        f"{config['variable_name']} "
        f"{config['variable_type']} = "
        f"{value};"
    )


def render_read(
    config: dict[str, Any],
) -> str:
    schema = config.get("schema", [])

    schema_lines: list[str] = []

    for index, column in enumerate(schema):
        comma = (
            ","
            if index < len(schema) - 1
            else ""
        )

        schema_lines.append(
            f"        {column['name']} "
            f"{column['type']}{comma}"
        )

    extractor_arguments = [
        f'delimiter: "{config["delimiter"]}"'
    ]

    if config.get("skip_header", True):
        extractor_arguments.append(
            "skipFirstRows: 1"
        )

    arguments = ",\n        ".join(
        extractor_arguments
    )

    return "\n".join(
        [
            f"{config['dataset_name']} =",
            "    EXTRACT",
            "\n".join(schema_lines),
            f'    FROM "{config["input_path"]}"',
            f"    USING {config['extractor']}(",
            f"        {arguments}",
            "    );",
        ]
    )


def render_select(
    config: dict[str, Any],
) -> str:
    columns = config.get("columns", [])

    column_lines: list[str] = []

    for index, column in enumerate(columns):
        comma = (
            ","
            if index < len(columns) - 1
            else ""
        )

        column_lines.append(
            f"        {column}{comma}"
        )

    return "\n".join(
        [
            f"{config['output_dataset']} =",
            "    SELECT",
            "\n".join(column_lines),
            f"    FROM {config['source_dataset']};",
        ]
    )


def render_filter(
    config: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"{config['output_dataset']} =",
            "    SELECT *",
            f"    FROM {config['source_dataset']}",
            f"    WHERE {config['condition']};",
        ]
    )


def render_join_source(
    source_type: str,
    dataset_name: str,
    subquery: str,
    alias: str,
) -> str:
    if source_type == "Subquery":
        clean_subquery = subquery.strip().rstrip(";")

        return "\n".join(
            [
                "(",
                indent_text(
                    clean_subquery,
                    spaces=8,
                ),
                f"    ) AS {alias}",
            ]
        )

    return f"{dataset_name} AS {alias}"


def render_join(
    config: dict[str, Any],
) -> str:
    left_source = render_join_source(
        source_type=config.get(
            "left_source_type",
            "Dataset",
        ),
        dataset_name=config.get(
            "left_dataset",
            "",
        ),
        subquery=config.get(
            "left_subquery",
            "",
        ),
        alias=config.get(
            "left_alias",
            "left_data",
        ),
    )

    right_source = render_join_source(
        source_type=config.get(
            "right_source_type",
            "Dataset",
        ),
        dataset_name=config.get(
            "right_dataset",
            "",
        ),
        subquery=config.get(
            "right_subquery",
            "",
        ),
        alias=config.get(
            "right_alias",
            "right_data",
        ),
    )

    selected_columns = config.get(
        "selected_columns",
        [],
    )

    if isinstance(selected_columns, str):
        selected_columns = [
            value.strip()
            for value in selected_columns.replace(
                "\n",
                ",",
            ).split(",")
            if value.strip()
        ]

    if not selected_columns:
        select_section = "    SELECT *"

    else:
        selected_lines: list[str] = []

        for index, column in enumerate(
            selected_columns
        ):
            comma = (
                ","
                if index
                < len(selected_columns) - 1
                else ""
            )

            selected_lines.append(
                f"        {column}{comma}"
            )

        select_section = "\n".join(
            [
                "    SELECT",
                *selected_lines,
            ]
        )

    return "\n".join(
        [
            f"{config['output_dataset']} =",
            select_section,
            f"    FROM {left_source}",
            (
                f"         "
                f"{config['join_type']} JOIN"
            ),
            f"         {right_source}",
            (
                f"    ON "
                f"{config['join_condition']};"
            ),
        ]
    )


def render_aggregate(
    config: dict[str, Any],
) -> str:
    group_by = config.get(
        "group_by_columns",
        [],
    )

    aggregates = config.get(
        "aggregate_expressions",
        [],
    )

    selections = group_by + aggregates

    select_lines: list[str] = []

    for index, expression in enumerate(
        selections
    ):
        comma = (
            ","
            if index < len(selections) - 1
            else ""
        )

        select_lines.append(
            f"        {expression}{comma}"
        )

    lines = [
        f"{config['output_dataset']} =",
        "    SELECT",
        "\n".join(select_lines),
        f"    FROM {config['source_dataset']}",
    ]

    if group_by:
        lines.append(
            "    GROUP BY "
            + ", ".join(group_by)
            + ";"
        )
    else:
        lines[-1] += ";"

    return "\n".join(lines)


def render_union(
    config: dict[str, Any],
) -> str:
    union_keyword = (
        "UNION ALL"
        if config.get("union_all", True)
        else "UNION"
    )

    return "\n".join(
        [
            f"{config['output_dataset']} =",
            "    SELECT *",
            f"    FROM {config['left_dataset']}",
            f"    {union_keyword}",
            "    SELECT *",
            f"    FROM {config['right_dataset']};",
        ]
    )


def render_custom_code(
    config: dict[str, Any],
) -> str:
    return config.get(
        "custom_code",
        "",
    )


def render_write(
    config: dict[str, Any],
) -> str:
    include_header = (
        "true"
        if config.get("include_header", True)
        else "false"
    )

    return "\n".join(
        [
            f"OUTPUT {config['source_dataset']}",
            f'TO "{config["output_path"]}"',
            f"USING {config['outputter']}(",
            (
                f'    delimiter: '
                f'"{config["delimiter"]}",'
            ),
            (
                f"    outputHeader: "
                f"{include_header}"
            ),
            ");",
        ]
    )


RENDERERS = {
    "Declare Variable": render_declare,
    "Read File": render_read,
    "Select Columns": render_select,
    "Filter": render_filter,
    "Join": render_join,
    "Aggregate": render_aggregate,
    "Union": render_union,
    "Custom Code": render_custom_code,
    "Write File": render_write,
}


def generate_scope_script(
    job_name: str,
    environment: str,
    components: list[dict[str, Any]],
) -> str:
    generated_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    sections = [
        "// ====================================================",
        "// Generated by SCOPE Engineering Studio",
        f"// Job Name: {job_name}",
        f"// Environment: {environment}",
        f"// Generated: {generated_at}",
        "// ====================================================",
        "",
    ]

    for index, component in enumerate(
        components,
        start=1,
    ):
        component_type = component["type"]

        renderer = RENDERERS.get(
            component_type
        )

        sections.append(
            f"// Step {index}: {component_type}"
        )

        if renderer is None:
            sections.append(
                f"// Unsupported component: "
                f"{component_type}"
            )
        else:
            sections.append(
                renderer(component["config"])
            )

        sections.append("")

    return "\n".join(sections)
