"""Lombok configuration generator — repository-root `lombok.config`."""

from __future__ import annotations


def generate_lombok_config(
    add_constructor_properties: bool = True,
    accessors_chain: bool = False,
    add_suppress_warnings: bool = False,
    log_field_name: str | None = None,
) -> str:
    """Generate `lombok.config` content.

    Args:
        add_constructor_properties: whether @AllArgsConstructor adds
            @ConstructorProperties (helps Jackson)
        accessors_chain: if True, setter returns `this` (builder-like)
        add_suppress_warnings: if False, Lombok won't inject
            @SuppressWarnings("all") into generated code (cleaner code review)
        log_field_name: if set, customize @Slf4j field name (default "log")

    Returns:
        lombok.config content suitable for the repository root.
    """
    lines = [
        "# lombok.config — repository-wide Lombok behavior",
        "# Place at repository root; applies to all submodules unless overridden.",
        "",
        "config.stopBubbling = true",
        "",
        "# === Generated code style ===",
        f"lombok.addSuppressWarnings = {str(add_suppress_warnings).lower()}",
        f"lombok.anyConstructor.addConstructorProperties = {str(add_constructor_properties).lower()}",
    ]

    if accessors_chain:
        lines.append("lombok.accessors.chain = true")
    if log_field_name:
        lines.append(f"lombok.log.fieldName = {log_field_name}")

    lines.extend(
        [
            "",
            "# === Equality & hashing ===",
            "# Force @EqualsAndHashCode to call super if class has a non-Object parent",
            "lombok.equalsAndHashCode.callSuper = call",
            "",
            "# === @Data behavior ===",
            "# Skip generating equals/hashCode for transient fields by default",
            "lombok.data.flagUsage = warning",
            "",
        ]
    )
    return "\n".join(lines)
