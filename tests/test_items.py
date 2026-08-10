from sqlmodel import Session, select

from app.models.item import Domain, Item, Status


def test_dashboard_loads_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Nothing open" in response.text


def test_create_item_across_all_domains(client, session: Session):
    for domain in Domain:
        response = client.post(
            "/items",
            data={
                "title": f"test {domain.value} item",
                "domain": domain.value,
                "item_type": "",
                "priority": "normal",
                "assignee_id": "",
                "due_at": "",
            },
        )
        assert response.status_code == 200
        assert f"test {domain.value} item" in response.text

    items = session.exec(select(Item)).all()
    assert {i.domain for i in items} == set(Domain)
    assert all(i.status == Status.pending for i in items)


def test_create_item_with_assignee_and_due_date(client, session: Session):
    member = session.exec(select(Item)).all()  # noqa: F841 (sanity: table accessible)
    response = client.post(
        "/items",
        data={
            "title": "pay water bill",
            "domain": "bill",
            "item_type": "water_bill",
            "priority": "high",
            "assignee_id": "1",
            "due_at": "2026-08-15T09:00",
        },
    )
    assert response.status_code == 200
    item = session.exec(select(Item).where(Item.title == "pay water bill")).one()
    assert item.assignee_id == 1
    assert item.priority.value == "high"
    assert item.due_at is not None


def test_complete_item_removes_it_from_open_list(client, session: Session):
    item = Item(title="take out trash", domain=Domain.chore, item_type="trash")
    session.add(item)
    session.commit()
    session.refresh(item)

    response = client.post(f"/items/{item.id}/complete", data={"completed_by_id": "1"})
    assert response.status_code == 200
    assert "take out trash" not in response.text

    session.refresh(item)
    assert item.status == Status.done
    assert item.completed_at is not None
    assert item.completed_by_id == 1


def test_skip_item_removes_it_from_open_list(client, session: Session):
    item = Item(title="optional errand", domain=Domain.chore, item_type="errand")
    session.add(item)
    session.commit()
    session.refresh(item)

    response = client.post(f"/items/{item.id}/skip")
    assert response.status_code == 200
    assert "optional errand" not in response.text

    session.refresh(item)
    assert item.status == Status.skipped
