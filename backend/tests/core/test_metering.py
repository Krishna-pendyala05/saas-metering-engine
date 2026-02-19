import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.core import metering
from app.models import all_models


def make_mock_subscription(org_id, limit=1000):
    plan = MagicMock(spec=all_models.SubscriptionPlan)
    plan.monthly_quota = limit

    sub = MagicMock(spec=all_models.Subscription)
    sub.organization_id = org_id
    sub.plan = plan
    return sub


@pytest.mark.anyio
async def test_track_usage_no_subscription():
    """If no active subscription exists, the request must be blocked with 403."""
    db = AsyncMock()
    org_id = 99

    with patch("app.core.metering.get_current_subscription", new_callable=AsyncMock) as mock_get_sub:
        mock_get_sub.return_value = None

        with pytest.raises(HTTPException) as exc:
            await metering.track_and_enforce_usage(db, org_id)

        assert exc.value.status_code == 403
        assert "No active subscription" in exc.value.detail


@pytest.mark.anyio
async def test_track_usage_increment_success():
    """
    Happy path: record exists, limit not reached.
    The new architecture executes 3 statements in order:
      1. INSERT ON CONFLICT DO NOTHING  (ensure record exists)
      2. UPDATE ... WHERE count < limit RETURNING count  (atomic increment)
      3. commit
    """
    db = AsyncMock()
    org_id = 1

    sub = make_mock_subscription(org_id, limit=100)

    with patch("app.core.metering.get_current_subscription", new_callable=AsyncMock) as mock_get_sub:
        mock_get_sub.return_value = sub

        # 1st execute = INSERT ON CONFLICT (return value not used)
        mock_insert_result = MagicMock()

        # 2nd execute = UPDATE RETURNING new count
        mock_update_result = MagicMock()
        mock_update_result.scalars().first.return_value = 55

        db.execute.side_effect = [mock_insert_result, mock_update_result]

        used, limit = await metering.track_and_enforce_usage(db, org_id)

        assert used == 55
        assert limit == 100
        db.commit.assert_called_once()
        # Exactly 2 SQL statements fired
        assert db.execute.call_count == 2


@pytest.mark.anyio
async def test_track_usage_limit_reached():
    """
    Limit reached: UPDATE returns None (WHERE count < limit fails).
    A follow-up SELECT confirms the record is at the limit → 429.
    Sequence: INSERT ON CONFLICT, UPDATE (None), SELECT (record at limit)
    """
    db = AsyncMock()
    org_id = 1
    limit = 100
    sub = make_mock_subscription(org_id, limit=limit)

    with patch("app.core.metering.get_current_subscription", new_callable=AsyncMock) as mock_get_sub:
        mock_get_sub.return_value = sub

        mock_insert_result = MagicMock()

        # UPDATE returns None → limit reached
        mock_update_result = MagicMock()
        mock_update_result.scalars().first.return_value = None

        # SELECT returns existing record at max usage
        mock_record = MagicMock(spec=all_models.UsageRecord)
        mock_record.request_count = limit
        mock_select_result = MagicMock()
        mock_select_result.scalars().first.return_value = mock_record

        db.execute.side_effect = [mock_insert_result, mock_update_result, mock_select_result]

        with pytest.raises(HTTPException) as exc:
            await metering.track_and_enforce_usage(db, org_id)

        assert exc.value.status_code == 429
        assert "Rate limit exceeded" in exc.value.detail


@pytest.mark.anyio
async def test_track_usage_metering_error_fallback():
    """
    UPDATE returns None AND the follow-up SELECT also returns None.
    This is an unexpected edge case → should raise 500.
    """
    db = AsyncMock()
    org_id = 1
    sub = make_mock_subscription(org_id, limit=100)

    with patch("app.core.metering.get_current_subscription", new_callable=AsyncMock) as mock_get_sub:
        mock_get_sub.return_value = sub

        mock_insert_result = MagicMock()

        mock_update_result = MagicMock()
        mock_update_result.scalars().first.return_value = None

        mock_select_result = MagicMock()
        mock_select_result.scalars().first.return_value = None

        db.execute.side_effect = [mock_insert_result, mock_update_result, mock_select_result]

        with pytest.raises(HTTPException) as exc:
            await metering.track_and_enforce_usage(db, org_id)

        assert exc.value.status_code == 500
        assert "Metering error" in exc.value.detail
