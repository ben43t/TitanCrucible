from agent.state import AgentState


class TestMaxIterationEnforcement:
    def test_should_continue_within_limit(self) -> None:
        state = AgentState(max_steps=3)
        assert state.should_continue() is True
        state.increment()
        assert state.should_continue() is True
        state.increment()
        assert state.should_continue() is True
        state.increment()
        assert state.should_continue() is False

    def test_should_continue_returns_false_at_limit(self) -> None:
        state = AgentState(max_steps=1)
        assert state.should_continue() is True
        state.increment()
        assert state.should_continue() is False

    def test_step_count_tracks_increments(self) -> None:
        state = AgentState()
        assert state.step_count == 0
        assert state.increment() == 1
        assert state.increment() == 2
        assert state.step_count == 2

    def test_default_max_steps_is_six(self) -> None:
        state = AgentState()
        for _ in range(6):
            assert state.should_continue() is True
            state.increment()
        assert state.should_continue() is False


class TestDuplicateDetection:
    def test_first_call_is_not_duplicate(self) -> None:
        state = AgentState()
        assert state.is_duplicate("wikipedia", "Federal Reserve") is False

    def test_second_identical_call_is_duplicate(self) -> None:
        state = AgentState()
        state.is_duplicate("wikipedia", "Federal Reserve")
        assert state.is_duplicate("wikipedia", "Federal Reserve") is True

    def test_different_tool_same_query_is_not_duplicate(self) -> None:
        state = AgentState()
        state.is_duplicate("wikipedia", "Federal Reserve")
        assert state.is_duplicate("arxiv", "Federal Reserve") is False

    def test_same_tool_different_query_is_not_duplicate(self) -> None:
        state = AgentState()
        state.is_duplicate("wikipedia", "Federal Reserve")
        assert state.is_duplicate("wikipedia", "discount window") is False

    def test_multiple_unique_calls_not_duplicated(self) -> None:
        state = AgentState()
        assert state.is_duplicate("wikipedia", "q1") is False
        assert state.is_duplicate("arxiv", "q2") is False
        assert state.is_duplicate("fred", "q3") is False
        assert state.is_duplicate("wikipedia", "q1") is True
        assert state.is_duplicate("arxiv", "q2") is True
        assert state.is_duplicate("fred", "q3") is True
