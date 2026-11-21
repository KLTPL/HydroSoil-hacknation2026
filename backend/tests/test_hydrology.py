import numpy as np

from retencja_api.terrain.hydrology import d8_receivers, fill_depressions, terminal_cells


def test_fill_raises_box_depression_to_rim_level():
    z = np.full((20, 20), 10.0)
    z[8:13, 8:13] = 8.0

    filled = fill_depressions(z)

    np.testing.assert_allclose(filled[8:13, 8:13], 10.0, atol=1e-3)
    np.testing.assert_allclose(filled, np.maximum(filled, z))
    np.testing.assert_allclose((filled - z)[8:13, 8:13].sum(), 25 * 2.0, atol=0.05)


def test_fill_leaves_open_slope_unchanged():
    z = np.tile(np.arange(30, dtype=float) * 0.1, (10, 1))

    np.testing.assert_allclose(fill_depressions(z), z)


def test_fill_treats_nan_as_outlet():
    z = np.full((10, 10), 5.0)
    z[4:6, 4:6] = 1.0
    z[5, 6] = np.nan  # hole next to the pit drains it

    filled = fill_depressions(z)

    assert np.isnan(filled[5, 6])
    assert filled[5, 5] < 2.0


def test_d8_flows_down_a_tilted_plane():
    z = np.tile(np.arange(5, dtype=float), (5, 1))  # rises eastward

    receiver = d8_receivers(z).reshape(5, 5)

    w = 5
    assert receiver[2, 3] == 2 * w + 2  # flows west
    assert receiver[2, 0] == 2 * w + 0  # western edge is an outlet


def test_terminal_cells_follow_chain_to_stop():
    receiver = np.array([0, 0, 1, 2, 3])  # 4 → 3 → 2 → 1 → 0
    stop = np.array([False, False, True, False, False])

    np.testing.assert_array_equal(terminal_cells(receiver, stop), [0, 0, 2, 2, 2])
