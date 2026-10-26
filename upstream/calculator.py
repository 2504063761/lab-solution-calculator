"""Core calculations for the sub-culturing volume calculator."""

import math


def calculate_volumes(od_readings, target_od=0.1, final_volume=10.0):
    """Return culture and fresh-media volumes for each labelled OD reading.

    Args:
        od_readings: Mapping of sample labels to starting OD values.
        target_od: Desired final optical density. Must be non-negative.
        final_volume: Desired final volume in mL. Must be positive.

    Returns:
        A dictionary mapping each sample label to ``(culture_ml, media_ml)``.

    Raises:
        ValueError: If an input is missing, non-finite, or outside its valid range.
    """
    target_od = _finite_number(target_od, "Target OD")
    final_volume = _finite_number(final_volume, "Final volume")
    if target_od < 0:
        raise ValueError("Target OD must be zero or greater.")
    if final_volume <= 0:
        raise ValueError("Final volume must be greater than zero.")
    if not od_readings:
        raise ValueError("Enter at least one OD reading.")

    results = {}
    for label, value in od_readings.items():
        label = str(label).strip()
        if not label:
            raise ValueError("Each OD reading needs a sample label.")
        if label in results:
            raise ValueError("Sample label {!r} appears more than once.".format(label))
        od = _finite_number(value, "Starting OD for {}".format(label))
        if od <= 0:
            raise ValueError("Starting OD for {} must be greater than zero.".format(label))
        if target_od > od:
            raise ValueError(
                "Target OD cannot exceed the starting OD for {}.".format(label)
            )

        culture_volume = (target_od / od) * final_volume
        media_volume = final_volume - culture_volume
        if not math.isfinite(culture_volume) or not math.isfinite(media_volume):
            raise ValueError("Calculated volumes are outside the supported numeric range.")
        results[label] = (culture_volume, media_volume)
    return results


def _finite_number(value, field_name):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("{} must be a number.".format(field_name))
    if not math.isfinite(number):
        raise ValueError("{} must be a finite number.".format(field_name))
    return number
