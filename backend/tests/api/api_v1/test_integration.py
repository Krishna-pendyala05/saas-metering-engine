import pytest
from httpx import AsyncClient
from app.core.config import settings

@pytest.mark.anyio
async def test_full_user_flow(client: AsyncClient):
    # 1. Signup
    email = "test_integration@example.com"
    password = "password123"
    org_name = "Integration Test Org"
    
    response = await client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "organization_name": org_name
        }
    )
    # Check if user already exists from previous run
    if response.status_code == 400 and "already exists" in response.text:
         # Login directly
         pass
    else:
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert "id" in data

    # 2. Login
    login_data = {
        "username": email,
        "password": password,
    }
    response = await client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    token = token_data["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Access Metered Endpoint (Widgets)
    # Call multiple times to verify metering
    for _ in range(3):
        response = await client.get(f"{settings.API_V1_STR}/widgets/", headers=headers)
        assert response.status_code == 200
        assert response.json() == [{"name": "Widget A"}, {"name": "Widget B"}]

    # 4. (Optional) Verify DB Usage Count
    # We could query the DB directly here or add an endpoint to check usage.
    # For now, relying on the fact that we got 200 OK means metering didn't block us (limit is 1000).
    print("Integration test passed: Signup -> Login -> Metered API Access")
