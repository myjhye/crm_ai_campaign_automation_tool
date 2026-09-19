import pytest
from app.services import imports
from app.core.errors import AppError

@pytest.mark.parametrize("content", [
    b"external_id,name,name\nx,a,a\n",
    b"external_id,name,category,secret\nx,a,b,s\n",
    b"external_id,name,category\nx,a\n",
    b"external_id,name,category\n",
    b"\xff\xfe",
])
def test_reject_malformed_csv(content):
    rows, errors, count = imports.parse("products", content)
    assert count > 0
    assert errors and "secret" not in str(errors)


def test_row_limit_and_capped_errors(monkeypatch):
    monkeypatch.setattr(imports, "MAX_ROWS", 2)
    with pytest.raises(AppError) as error:
        imports.parse("products", b"external_id,name,category\na,b,c\nd,e,f\ng,h,i\n")
    assert error.value.status_code == 413
    monkeypatch.setattr(imports, "MAX_ROWS", 200000)
    _, errors, count = imports.parse("products", b"external_id,name,category\n" + b",,\n" * 105)
    assert count == 105 and len(errors) == 100
