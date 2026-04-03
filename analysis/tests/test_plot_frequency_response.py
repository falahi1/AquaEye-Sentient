import os
import tempfile


def test_normalise_sets_1khz_to_zero():
    from acoustic.plot_frequency_response import normalise_frequency_response
    freqs  = [1000, 2000, 5000, 10000, 20000]
    levels = [-30.0, -32.0, -35.0, -38.0, -42.0]
    result = normalise_frequency_response(freqs, levels)
    assert result[0] == 0.0


def test_normalise_preserves_relative_differences():
    from acoustic.plot_frequency_response import normalise_frequency_response
    freqs  = [1000, 2000, 5000]
    levels = [-30.0, -34.0, -36.0]
    result = normalise_frequency_response(freqs, levels)
    assert abs(result[1] - (-4.0)) < 1e-9
    assert abs(result[2] - (-6.0)) < 1e-9


def test_normalise_flat_response_returns_all_zeros():
    from acoustic.plot_frequency_response import normalise_frequency_response
    freqs  = [1000, 2000, 5000, 10000, 20000]
    levels = [-25.0, -25.0, -25.0, -25.0, -25.0]
    result = normalise_frequency_response(freqs, levels)
    assert all(abs(v) < 1e-9 for v in result)


def test_normalise_raises_without_1khz():
    from acoustic.plot_frequency_response import normalise_frequency_response
    try:
        raised = False
        try:
            normalise_frequency_response([2000, 5000, 10000], [-30.0, -32.0, -35.0])
        except ValueError:
            raised = True
        assert raised, "Expected ValueError when 1000 Hz not in freqs_hz"
    except Exception as e:
        assert False, f"Unexpected exception type: {e}"


def test_plot_creates_nonempty_png():
    from acoustic.plot_frequency_response import plot_frequency_response
    freqs  = [1000, 2000, 5000, 10000, 20000]
    levels = [-30.0, -32.0, -35.0, -38.0, -42.0]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'freq.png')
        plot_frequency_response(freqs, levels, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1024
