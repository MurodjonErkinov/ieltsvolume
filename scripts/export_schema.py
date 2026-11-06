"""Run: python manage.py shell < scripts/export_schema.py (no database queries)."""
from pathlib import Path

from django.apps import apps
from django.db import connection, models


def quote(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ") + "'"


selected = [apps.get_model("auth", "User")]
for label in ("accounts", "exams", "billing", "attempts", "notifications"):
    selected.extend(apps.get_app_config(label).get_models())

lines = [
    "// Generated from models: python manage.py shell < scripts/export_schema.py",
    "// Conditional uniqueness and CHECK constraints are summarized in table notes.",
    "Project ielts_volume {", "  database_type: 'PostgreSQL'",
    "  Note: 'IELTS Academic. One purchase = one attempt. Separate AI/mentor evaluations.'", "}", "",
]
for model in selected:
    lines.append(f"Table {model._meta.db_table} {{")
    for field in model._meta.local_fields:
        attributes = []
        if field.primary_key:
            attributes.append("pk")
        if isinstance(field, (models.AutoField, models.BigAutoField)):
            attributes.append("increment")
        if not field.null:
            attributes.append("not null")
        if field.unique and not field.primary_key:
            attributes.append("unique")
        if field.is_relation:
            target = field.target_field
            relation = "-" if field.one_to_one else ">"
            attributes.append(f"ref: {relation} {target.model._meta.db_table}.{target.column}")
        notes = []
        if field.choices:
            notes.append("Choices: " + ", ".join(str(value) for value, label in field.choices))
        if field.is_relation:
            notes.append("On delete: " + field.remote_field.on_delete.__name__)
        if field.help_text:
            notes.append(str(field.help_text))
        if notes:
            attributes.append("note: " + quote("; ".join(notes)))
        db_type = field.db_type(connection)
        if " " in db_type:
            db_type = '"' + db_type + '"'
        settings = f" [{', '.join(attributes)}]" if attributes else ""
        lines.append(f"  {field.column} {db_type}{settings}")
    indexes = []
    for constraint in model._meta.constraints:
        if isinstance(constraint, models.UniqueConstraint) and constraint.fields and constraint.condition is None:
            indexes.append("    (" + ", ".join(model._meta.get_field(name).column for name in constraint.fields) + ") [unique]")
    for index in model._meta.indexes:
        columns = ", ".join(model._meta.get_field(name.lstrip("-")).column for name in index.fields)
        indexes.append(f"    ({columns})")
    if indexes:
        lines.extend(["", "  indexes {", *indexes, "  }"])
    constraints = [f"{constraint.name}: {constraint.condition}" for constraint in model._meta.constraints if getattr(constraint, "condition", None) is not None]
    if constraints:
        lines.append("  Note: " + quote("; ".join(constraints)))
    lines.extend(["}", ""])

path = Path("docs/database.dbml")
path.write_text("\n".join(lines))
print(f"Exported {len(selected)} tables to {path}")
