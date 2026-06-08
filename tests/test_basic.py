from p2p_goods import greet


def test_greet():
    assert greet("tester") == "Hello, tester!"
