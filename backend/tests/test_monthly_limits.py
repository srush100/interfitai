"""Monthly limits agreed 16 Nov: 5 workout programs and 5 meal plans per member
per calendar month (admins have no limit)."""
import inspect
import server


def test_limits_are_five_and_five():
    assert server.PROGRAM_MONTHLY_LIMIT == 5 and server.MEAL_PLAN_LIMIT_PER_MONTH == 5


def test_every_program_check_uses_the_setting():
    src = inspect.getsource(server)
    assert "used >= 3" not in src and '"limit": 3,' not in src and "limit = 3\n" not in src
    assert "MEAL_PLAN_MONTHLY_LIMIT = 4" not in src
