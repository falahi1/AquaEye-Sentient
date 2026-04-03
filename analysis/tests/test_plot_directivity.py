import os
import tempfile


def test_normalise_shifts_max_to_zero():
    from acoustic.plot_directivity import normalise_directivity
    data = {0: -20.0, 45: -23.0, 90: -18.0, 135: -25.0}
    result = normalise_directivity(data)
    assert result[90] == 0.0                    # max becomes 0
    assert abs(result[0]  - (-2.0)) < 1e-9
    assert abs(result[45] - (-5.0)) < 1e-9
    assert abs(result[135]- (-7.0)) < 1e-9


def test_normalise_preserves_relative_differences():
    from acoustic.plot_directivity import normalise_directivity
    data = {0: -10.0, 90: -20.0, 180: -15.0}
    result = normalise_directivity(data)
    assert abs((result[0] - result[90])  - 10.0) < 1e-9
    assert abs((result[0] - result[180]) -  5.0) < 1e-9


def test_combine_takes_max_at_each_angle():
    from acoustic.plot_directivity import combine_array_directivity
    ch1 = {0: -20.0, 90: -10.0, 180: -25.0, 270: -15.0}
    ch2 = {0: -15.0, 90: -20.0, 180: -12.0, 270: -18.0}
    result = combine_array_directivity([ch1, ch2])
    assert result[0]   == -15.0   # ch2 louder
    assert result[90]  == -10.0   # ch1 louder
    assert result[180] == -12.0   # ch2 louder
    assert result[270] == -15.0   # ch1 louder


def test_combine_single_channel_returns_same_data():
    from acoustic.plot_directivity import combine_array_directivity
    ch = {0: -20.0, 45: -22.0, 90: -19.0}
    assert combine_array_directivity([ch]) == ch


def test_combine_mismatched_angles_raises_value_error():
    from acoustic.plot_directivity import combine_array_directivity
    ch1 = {0: -20.0, 90: -10.0}
    ch2 = {0: -15.0, 45: -20.0}
    try:
        combine_array_directivity([ch1, ch2])
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_combine_empty_list_raises_value_error():
    from acoustic.plot_directivity import combine_array_directivity
    try:
        combine_array_directivity([])
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_plot_directivity_creates_nonempty_png():
    from acoustic.plot_directivity import plot_directivity
    configs = {
        'Config A': {0: -20.0, 45: -24.0, 90: -18.0, 135: -26.0,
                     180: -22.0, 225: -25.0, 270: -19.0, 315: -23.0}
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'dir.png')
        plot_directivity(configs, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1024   # at least 1 KB
