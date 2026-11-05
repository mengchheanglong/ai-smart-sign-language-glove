from backend.utils import packet_ready_for_inference, validate_sensor_packet


def packet():
    return {"timestamp_ms": 1, "flex": [1800] * 5, "accel": [0., 0., 9.8],
            "gyro": [0., 0., 0.], "imu_valid": True,
            "calibrated": [True] * 5, "straight": [1900.] * 5,
            "bent": [1200.] * 5, "bend_pct": [14.3] * 5,
            "bend_state": ["STRAIGHT"] * 5}


def test_device_telemetry_and_missing_imu():
    sample = packet()
    assert validate_sensor_packet(sample)[0]
    assert packet_ready_for_inference(sample)
    sample.update(imu_valid=False, accel=None, gyro=None)
    assert validate_sensor_packet(sample)[0]
    assert not packet_ready_for_inference(sample)


def test_uncalibrated_finger_and_malformed_bend():
    sample = packet()
    sample["calibrated"][1] = False
    sample["bend_pct"][1] = None
    sample["bend_state"][1] = "UNCALIBRATED"
    assert validate_sensor_packet(sample)[0]
    assert not packet_ready_for_inference(sample)
    sample["bend_pct"][1] = 40
    assert not validate_sensor_packet(sample)[0]


def test_four_finger_packet_does_not_require_missing_channel():
    sample = packet()
    sample['enabled'] = [True, True, True, True, False]
    sample['calibrated'][4] = False
    sample['flex'][4] = 0
    sample['bend_pct'][4] = None
    sample['bend_state'][4] = 'DISCONNECTED'
    assert validate_sensor_packet(sample)[0]
    assert packet_ready_for_inference(sample)
    sample['calibrated'][2] = False
    sample['bend_pct'][2] = None
    sample['bend_state'][2] = 'UNCALIBRATED'
    assert not packet_ready_for_inference(sample)


def test_accelerometer_clipping_blocks_inference():
    sample = packet()
    sample["accel"] = [0.0, -19.613, 9.8]
    assert validate_sensor_packet(sample)[0]
    assert not packet_ready_for_inference(sample)


def test_experimental_imu_blocks_inference():
    sample = packet()
    sample["imu_experimental"] = True
    assert validate_sensor_packet(sample)[0]
    assert not packet_ready_for_inference(sample)


def test_experimental_imu_requires_opt_in_and_rejects_raw_clipping():
    sample = packet()
    sample["imu_experimental"] = True
    assert packet_ready_for_inference(sample, allow_experimental_imu=True)
    sample["accel"] = [0.0, (-8.0 + 5.58236706) * 9.80665, 0.0]
    assert not packet_ready_for_inference(sample, allow_experimental_imu=True)
