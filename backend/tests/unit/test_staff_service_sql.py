"""Staff service SQL expression compatibility."""

from sqlalchemy import select
from sqlalchemy.dialects import mssql

from app.db.models import RestaurantResourceModel
from app.services.staff_service import active_resource_clause


def test_active_resource_clause_compiles_for_mssql() -> None:
    statement = select(RestaurantResourceModel).where(active_resource_clause())

    sql = str(
        statement.compile(
            dialect=mssql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "is_active = 1" in sql
    assert "is_active IS 1" not in sql
